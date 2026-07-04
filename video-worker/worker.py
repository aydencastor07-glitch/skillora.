"""
Skillora — video-worker : « Améliorer ma vidéo »
=================================================
Tourne sur un petit serveur (Hetzner/Railway/n'importe quel Docker).
Boucle : réclame un job dans Supabase -> télécharge la vidéo -> l'analyse ->
décide QUOI améliorer (IA + règles) -> applique -> renvoie la vidéo améliorée.

Le pipeline est CONDITIONNEL : chaque amélioration n'est appliquée que si la
vidéo en a besoin (pas de sous-titres sur une vidéo sans parole, pas de
recadrage si déjà 9:16, etc.), et il s'adapte au contexte du créateur
(niche, retours du scan) transmis par l'app.

Ordre des opérations (important pour la cohérence des timestamps) :
  1. coupe des silences        (change la timeline)
  2. recadrage 9:16            (change l'image)
  3. b-roll                    (incrusté au-dessus de l'image)
  4. sous-titres + hook        (par-dessus tout, jamais recouverts)
  5. musique + normalisation   (audio final)
La transcription pour les sous-titres est faite APRÈS la coupe des silences,
pour que les timings collent à la vidéo coupée.

Env requis   : SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Env conseillé: GROQ_API_KEY  (transcription Whisper + plan d'amélioration LLM)
Env optionnel: PEXELS_API_KEY (b-roll), MUSIC_BUCKET (musique libre de droits)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
MUSIC_BUCKET = os.environ.get("MUSIC_BUCKET", "music-library")
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "3"))
MAX_DURATION_S = float(os.environ.get("MAX_DURATION_S", "300"))  # 5 min max en v1

FONT = os.environ.get("SUB_FONT", "Anton")  # Anton = police "impact" des sous-titres viraux (fallback auto si absente)
# Mots de remplissage coupés automatiquement (avec les silences)
FILLERS = {"euh", "heu", "hum", "hmm", "uh", "um", "euhh", "mmm", "ben"}
# User-Agent navigateur pour les services derrière Cloudflare (Groq, Pexels…),
# qui renvoient 403 au User-Agent Python par défaut. Ne JAMAIS l'envoyer à
# Supabase : leur pare-feu rejette ce UA falsifié avec un 401.
GROQ_UA = "Mozilla/5.0 (X11; Linux x86_64) Skillora-Worker/1.0"


def download(url, out, ua=GROQ_UA):
    """Télécharge un fichier avec un UA navigateur (CDN derrière Cloudflare)."""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=180) as r, open(out, "wb") as f:
        shutil.copyfileobj(r, f)

if not SB_URL or not SB_KEY:
    print("SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY sont obligatoires.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- HTTP utils
def http(method, url, headers=None, data=None, timeout=120):
    req = urllib.request.Request(url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    body = None
    if data is not None:
        body = data if isinstance(data, (bytes, bytearray)) else json.dumps(data).encode()
        if not isinstance(data, (bytes, bytearray)):
            req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=timeout) as r:
        return r.status, r.read()


def sb_headers(extra=None):
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY}
    h.update(extra or {})
    return h


def claim_job():
    try:
        st, raw = http("POST", SB_URL + "/rest/v1/rpc/claim_video_job", sb_headers(), {})
        rows = json.loads(raw or b"[]")
        return rows[0] if rows else None
    except Exception as e:
        print("claim_job:", e, file=sys.stderr)
        return None


def update_job(job_id, patch):
    try:
        http("PATCH", SB_URL + "/rest/v1/video_jobs?id=eq." + job_id,
             sb_headers({"Prefer": "return=minimal"}), patch)
    except Exception as e:
        print("update_job:", e, file=sys.stderr)


class Steps:
    """Journal d'étapes poussé en direct dans la ligne du job (l'app l'affiche)."""

    def __init__(self, job_id):
        self.job_id = job_id
        self.items = []

    def start(self, key, label):
        self.items.append({"key": key, "label": label, "state": "running"})
        self.push()

    def done(self, key, detail=None):
        for it in self.items:
            if it["key"] == key:
                it["state"] = "done"
                if detail:
                    it["detail"] = detail
        self.push()

    def skip(self, key, label, detail=None):
        self.items.append({"key": key, "label": label, "state": "skipped", "detail": detail})
        self.push()

    def push(self):
        update_job(self.job_id, {"steps": self.items})


# ---------------------------------------------------------------- ffmpeg utils
def run(cmd, timeout=1800):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError("Commande échouée: " + " ".join(cmd[:6]) + " … — " + (p.stderr or "")[-800:])
    return p


def ffprobe_facts(path):
    p = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path])
    info = json.loads(p.stdout)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    w, h = int(v.get("width", 0) or 0), int(v.get("height", 0) or 0)
    return {"duration": dur, "width": w, "height": h, "has_audio": a is not None,
            "vertical": h > 0 and w > 0 and (h / w) >= 1.6}


def detect_silences(path, noise_db=-30, min_d=0.55):
    """Retourne [(début, fin), …] des silences (pauses > min_d secondes)."""
    p = subprocess.run(["ffmpeg", "-i", path, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    out = p.stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends[:len(starts)]))


def filler_spans(words):
    """Plages des 'euh/hum…' à retirer, d'après les timestamps par mot."""
    spans = []
    for w in words or []:
        t = re.sub(r"[^a-zà-ÿ]", "", str(w.get("word", "")).lower())
        if t in FILLERS:
            s, e = float(w.get("start", 0)), float(w.get("end", 0))
            if e - s > 0.12:
                spans.append((max(0.0, s - 0.03), e + 0.03))
    return spans


def cut_spans(src, dst, silences, fillers, duration, keep_pad=0.22):
    """Coupe silences (avec coussin naturel) + mots de remplissage, en une passe."""
    remove = []
    for (s, e) in silences or []:
        s2, e2 = max(0.0, s + keep_pad), max(0.0, e - keep_pad)
        if e2 - s2 > 0.15:
            remove.append((s2, e2))
    remove += list(fillers or [])
    if not remove:
        return False
    remove.sort()
    merged = []
    for (s, e) in remove:  # fusionne les plages qui se chevauchent
        if merged and s <= merged[-1][1] + 0.04:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    keep, cursor = [], 0.0
    for (s, e) in merged:
        if s > cursor + 0.05:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration - 0.05:
        keep.append((cursor, duration))
    removed = duration - sum(e - s for s, e in keep)
    if removed < 0.9 or not keep:  # pas la peine de ré-encoder pour < 1 s
        return False
    expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for (s, e) in keep)
    run(["ffmpeg", "-y", "-i", src,
         "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
         "-af", f"aselect='{expr}',asetpts=N/SR/TB",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", dst])
    return True


def zoom_boundaries(words, duration, max_len=4.0, gap_split=0.8):
    """Instants de 'punch' : nouvelle phrase (pause > 0,8 s) ou toutes les ~4 s."""
    if not words:
        return []
    bounds, seg_start, prev_end = [0.0], float(words[0].get("start", 0)), 0.0
    for w in words:
        ws, we = float(w.get("start", 0)), float(w.get("end", 0))
        if bounds and (ws - prev_end > gap_split or ws - seg_start > max_len):
            if ws - bounds[-1] > 1.0:
                bounds.append(round(ws, 3))
            seg_start = ws
        prev_end = we
    return [b for b in bounds if b < duration - 1.0]


def make_whoosh(path):
    """Petit 'whoosh' synthétisé par nous (aucun droit d'auteur)."""
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.3:amplitude=0.6",
         "-af", "highpass=f=500,lowpass=f=5200,afade=t=in:st=0:d=0.05,afade=t=out:st=0.10:d=0.20,volume=1.1",
         "-ar", "44100", path])


def zoom_punch(src, dst, words, has_audio, work):
    """Zooms dynamiques : léger punch-in alterné à chaque phrase + whoosh discret.
    La timeline ne change pas -> les timings des sous-titres restent valides."""
    facts = ffprobe_facts(src)
    duration, W, H = facts["duration"], facts["width"], facts["height"]
    bounds = zoom_boundaries(words, duration)
    if len(bounds) < 2 or len(bounds) > 60:
        return False
    edges = bounds + [duration]
    fc, vlabels = [], []
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        f = 1.0 if i % 2 == 0 else 1.07
        chain = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
        if f > 1.0:
            chain += (f",crop=trunc(iw/{f}/2)*2:trunc(ih/{f}/2)*2:(iw-iw/{f})/2:(ih-ih/{f})/2,scale={W}:{H}")
        chain += f",setsar=1[v{i}]"
        fc.append(chain)
        vlabels.append(f"[v{i}]")
    n = len(vlabels)
    fc.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[vz]")
    cmd = ["ffmpeg", "-y", "-i", src]
    maps = ["-map", "[vz]"]
    if has_audio:
        whoosh = os.path.join(work, "whoosh.wav")
        make_whoosh(whoosh)
        cmd += ["-i", whoosh]
        sfx = [b for b in bounds[1:]][:12]  # pas de whoosh à t=0, max 12
        if sfx:
            k = len(sfx)
            fc.append(f"[1:a]asplit={k}" + "".join(f"[s{j}]" for j in range(k)))
            wl = []
            for j, t in enumerate(sfx):
                ms = int(t * 1000)
                fc.append(f"[s{j}]adelay={ms}|{ms},volume=0.22[w{j}]")
                wl.append(f"[w{j}]")
            fc.append("[0:a]" + "".join(wl) + f"amix=inputs={k + 1}:duration=first:dropout_transition=0:normalize=0[am]")
            maps += ["-map", "[am]"]
        else:
            maps += ["-map", "0:a"]
    cmd += ["-filter_complex", ";".join(fc), *maps,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", dst]
    run(cmd)
    return True


def reframe_916(src, dst, w, h):
    """Recadre au format vertical 1080x1920 (crop centré + léger zoom)."""
    run(["ffmpeg", "-y", "-i", src,
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])


def loudnorm(src, dst, music_path=None, music_gain_db=-21):
    """Normalise la voix à -14 LUFS ; mixe la musique en dessous si fournie."""
    if music_path:
        run(["ffmpeg", "-y", "-i", src, "-stream_loop", "-1", "-i", music_path,
             "-filter_complex",
             f"[1:a]volume={music_gain_db}dB[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=3,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", dst])
    else:
        run(["ffmpeg", "-y", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             "-c:v", "copy", "-c:a", "aac", dst])


# ---------------------------------------------------------------- Groq (Whisper + LLM)
def groq_transcribe(path):
    """Transcription avec timestamps par mot (Groq Whisper). None si pas de clé/échec.
    IMPORTANT : les timestamps par mot ne sont dispos QUE sur whisper-large-v3
    (le modèle 'turbo' les refuse -> réponse vide -> 'pas de parole')."""
    if not GROQ_KEY:
        return None
    boundary = "----skillora" + str(int(time.time()))
    with open(path, "rb") as f:
        audio = f.read()
    parts = []
    for name, val in [("model", "whisper-large-v3"), ("response_format", "verbose_json"),
                      ("timestamp_granularities[]", "word")]:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode())
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp3\"\r\n"
                  "Content-Type: audio/mpeg\r\n\r\n").encode() + audio + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    try:
        st, raw = http("POST", "https://api.groq.com/openai/v1/audio/transcriptions",
                       {"Authorization": "Bearer " + GROQ_KEY,
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "User-Agent": GROQ_UA},
                       body, timeout=300)
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            print("groq_transcribe HTTP", e.code, ":", e.read().decode()[:300], file=sys.stderr)
        except Exception:
            print("groq_transcribe HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("groq_transcribe:", e, file=sys.stderr)
        return None


def extract_audio_mp3(src, dst):
    run(["ffmpeg", "-y", "-i", src, "-vn", "-acodec", "libmp3lame", "-b:a", "96k", "-ac", "1", dst])


def groq_plan(facts, transcript_text, context):
    """Demande au LLM le plan d'amélioration adapté à CE créateur. Fallback: règles."""
    fallback = {
        "subtitles": bool(transcript_text and len(transcript_text.split()) >= 8),
        "subtitle_style": "karaoke",
        "cut_silences": True,
        "reframe": not facts["vertical"],
        "hook_text": "",
        "music_mood": "" if transcript_text else "chill",
        "broll_keywords": [],
    }
    if not GROQ_KEY:
        return fallback
    niche = str(context.get("niche", "") or "")
    feedback = str(context.get("feedback", "") or "")
    prompt = (
        "Tu améliores une vidéo courte pour un créateur. Décide ce qui est UTILE — pas tout systématiquement.\n"
        f"Faits: durée {facts['duration']:.0f}s, format {'vertical' if facts['vertical'] else 'horizontal'}, "
        f"parole: {'oui' if transcript_text else 'non'}.\n"
        f"Niche du créateur: {niche or 'inconnue'}. Retours du scan Skillora: {feedback or 'aucun'}.\n"
        f"Transcription (début): {transcript_text[:900] or '(aucune)'}\n\n"
        "Réponds UNIQUEMENT ce JSON:\n"
        "{\"subtitles\": bool,  // sous-titres seulement s'il y a de la parole utile\n"
        " \"cut_silences\": bool,\n"
        " \"hook_text\": \"accroche ultra courte (<=42 caractères, langue de la transcription) ou vide\",\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic ou vide si la vidéo a déjà son ambiance\",\n"
        " \"broll_keywords\": [\"2-3 mots-clés ANGLAIS, OBLIGATOIRES dès que la parole mentionne un objet, un lieu, une activité ou un produit (ex: 'online shopping', 'gym workout') — vide UNIQUEMENT si la personne ne parle que d'elle-même face caméra\"]}"
    )
    try:
        st, raw = http("POST", "https://api.groq.com/openai/v1/chat/completions",
                       {"Authorization": "Bearer " + GROQ_KEY, "User-Agent": GROQ_UA},
                       {"model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2, "response_format": {"type": "json_object"}},
                       timeout=90)
        out = json.loads(raw)
        plan = json.loads(out["choices"][0]["message"]["content"])
        merged = dict(fallback)
        for k in ("subtitles", "cut_silences", "hook_text", "music_mood", "broll_keywords"):
            if k in plan:
                merged[k] = plan[k]
        merged["reframe"] = not facts["vertical"]
        # Les sous-titres sont notre effet phare : dès qu'il y a de la parole, on les
        # met — l'IA ne peut pas les désactiver (elle ne décide que du style/hook).
        merged["subtitles"] = bool(transcript_text and len(transcript_text.split()) >= 3)
        return merged
    except Exception as e:
        print("groq_plan:", e, file=sys.stderr)
        return fallback


# ---------------------------------------------------------------- sous-titres ASS
def ass_time(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(words, hook_text, play_w=1080, play_h=1920):
    """Sous-titres style viral : MAJUSCULES, 2 mots max, gros, le mot parlé passe
    au vert Skillora, pop d'apparition. Accroche encadrée en haut (3 premières s)."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},108,&H0084DC3D,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,8,3,2,50,50,520,1
Style: Hook,{FONT},58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H6E000000,-1,0,0,0,100,100,1,0,3,10,0,8,70,70,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    POP = "{\\fad(30,40)\\t(0,110,\\fscx112\\fscy112)\\t(110,190,\\fscx100\\fscy100)}"
    lines = []
    if hook_text:
        safe = str(hook_text).upper().replace("{", "").replace("}", "").replace("\n", " ")
        lines.append(f"Dialogue: 1,0:00:00.15,0:00:03.00,Hook,,0,0,0,,{{\\fad(140,200)}}{safe}")
    group = []
    for i, w in enumerate(words):
        group.append(w)
        last = (i == len(words) - 1)
        if len(group) == 2 or last:
            start, end = float(group[0]["start"]), float(group[-1]["end"])
            if end - start < 0.30:
                end = start + 0.30
            text = ""
            for g in group:
                k = max(1, int(round((float(g["end"]) - float(g["start"])) * 100)))
                word = str(g["word"]).strip().upper().replace("{", "").replace("}", "")
                text += f"{{\\k{k}}}{word} "
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{POP}{text.strip()}")
            group = []
    return head + "\n".join(lines) + "\n"


def burn_subs(src, dst, ass_path):
    safe = ass_path.replace("\\", "/").replace(":", "\\:")
    run(["ffmpeg", "-y", "-i", src, "-vf", f"ass='{safe}'",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])


# ---------------------------------------------------------------- b-roll (Pexels)
def pexels_broll(keywords, want=2, min_h=1000):
    """Télécharge jusqu'à `want` clips verticaux libres (licence Pexels, usage commercial ok)."""
    if not PEXELS_KEY or not keywords:
        return []
    files = []
    for kw in keywords[:want]:
        got = False
        for orientation in ("portrait", "landscape"):  # paysage = fallback, recadré ensuite
            if got:
                break
            try:
                q = urllib.parse.quote(str(kw))
                st, raw = http("GET",
                               f"https://api.pexels.com/videos/search?query={q}&orientation={orientation}&per_page=4",
                               {"Authorization": PEXELS_KEY, "User-Agent": GROQ_UA}, timeout=60)
                data = json.loads(raw)
                for vid in data.get("videos", []):
                    pick = None
                    for f in vid.get("video_files", []):
                        h = f.get("height", 0)
                        ok = h >= (min_h if orientation == "portrait" else 720)
                        if ok and (pick is None or h < pick["height"]):
                            pick = f
                    if pick:
                        out = tempfile.mktemp(suffix=".mp4")
                        download(pick["link"], out)
                        files.append(out)
                        got = True
                        break
            except Exception as e:
                print("pexels:", kw, orientation, e, file=sys.stderr)
    return files


def overlay_broll(src, dst, brolls, duration):
    """Incruste chaque b-roll en plein cadre ~1,6 s, réparti dans la vidéo
    (jamais dans les 3 premières secondes : le hook doit rester le créateur)."""
    if not brolls:
        return False
    seg = 1.6
    slots = []
    n = len(brolls)
    for i in range(n):
        t = 3.0 + (duration - 5.0) * (i + 1) / (n + 1)
        if t + seg < duration - 1.0:
            slots.append(t)
    if not slots:
        return False
    inputs = ["-i", src]
    for b in brolls[:len(slots)]:
        inputs += ["-i", b]
    fc, last = [], "[0:v]"
    for i, t in enumerate(slots[:len(brolls)]):
        fc.append(f"[{i+1}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                  f"crop=1080:1920,setpts=PTS-STARTPTS+{t}/TB[b{i}]")
        nxt = f"[v{i}]"
        fc.append(f"{last}[b{i}]overlay=enable='between(t,{t},{t + seg})':eof_action=pass{nxt}")
        last = nxt
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", last, "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-c:a", "copy", dst])
    return True


# ---------------------------------------------------------------- musique (bucket)
def pick_music(mood):
    """Choisit une piste libre de droits du bucket musique (manifest.json). None si absent."""
    if not mood:
        return None
    try:
        st, raw = http("GET", f"{SB_URL}/storage/v1/object/public/{MUSIC_BUCKET}/manifest.json", timeout=30)
        tracks = [t for t in json.loads(raw) if t.get("mood") == mood]
        if not tracks:
            return None
        t = tracks[int(time.time()) % len(tracks)]
        out = tempfile.mktemp(suffix=os.path.splitext(t["file"])[1] or ".mp3")
        urllib.request.urlretrieve(f"{SB_URL}/storage/v1/object/public/{MUSIC_BUCKET}/{t['file']}", out)
        return out
    except Exception:
        return None  # pas de bibliothèque musicale -> on saute, silencieusement


# ---------------------------------------------------------------- upload résultat
def upload_result(job, path):
    with open(path, "rb") as f:
        blob = f.read()
    key = f"improved/{job['user_id']}/{job['id']}.mp4"
    http("POST", f"{SB_URL}/storage/v1/object/post-media/{key}",
         sb_headers({"Content-Type": "video/mp4", "x-upsert": "true"}), blob, timeout=600)
    return f"{SB_URL}/storage/v1/object/public/post-media/{key}"


# ---------------------------------------------------------------- pipeline
def process(job):
    steps = Steps(job["id"])
    steps.items = [{"key": "wait", "label": "En file d'attente…", "state": "done"}]
    work = tempfile.mkdtemp(prefix="skillora-")
    try:
        context = job.get("context") or {}

        steps.start("dl", "Téléchargement de ta vidéo…")
        src = os.path.join(work, "src.mp4")
        urllib.request.urlretrieve(job["source_url"], src)
        facts = ffprobe_facts(src)
        if facts["duration"] > MAX_DURATION_S:
            raise RuntimeError(f"Vidéo trop longue ({facts['duration']:.0f}s) — max {MAX_DURATION_S:.0f}s pour l'amélioration.")
        steps.done("dl", f"{facts['duration']:.0f}s · {facts['width']}x{facts['height']}")

        steps.start("analyze", "Analyse : qu'est-ce qui manque à ta vidéo ?")
        silences = detect_silences(src) if facts["has_audio"] else []
        first_tr = None
        if facts["has_audio"]:
            mp3 = os.path.join(work, "a.mp3")
            extract_audio_mp3(src, mp3)
            first_tr = groq_transcribe(mp3)
        tr_text = (first_tr or {}).get("text", "").strip() if first_tr else ""
        plan = groq_plan(facts, tr_text, context)
        update_job(job["id"], {"plan": plan})
        steps.done("analyze", "parole détectée" if tr_text else "pas de parole détectée")

        cur = src
        tr1_words = (first_tr or {}).get("words") or []

        # 1. Coupe des silences ET des "euh/hum" (uniquement s'il y a de la parole)
        if plan.get("cut_silences") and tr_text and (silences or tr1_words):
            steps.start("cut", "Coupe des temps morts et des « euh »…")
            out = os.path.join(work, "cut.mp4")
            if cut_spans(cur, out, silences, filler_spans(tr1_words), facts["duration"]):
                cur = out
                facts = ffprobe_facts(cur)
                steps.done("cut", f"nouvelle durée {facts['duration']:.0f}s")
            else:
                steps.done("cut", "rien à couper")
        else:
            steps.skip("cut", "Coupe des temps morts", "pas nécessaire")

        # 2. Recadrage 9:16
        if plan.get("reframe"):
            steps.start("frame", "Recadrage vertical 9:16…")
            out = os.path.join(work, "frame.mp4")
            reframe_916(cur, out, facts["width"], facts["height"])
            cur = out
            steps.done("frame")
        else:
            steps.skip("frame", "Recadrage 9:16", "déjà au bon format")

        # 3. B-roll
        brolls = []
        if plan.get("broll_keywords"):
            steps.start("broll", "Recherche de plans d'illustration…")
            brolls = pexels_broll(plan["broll_keywords"])
            if brolls:
                out = os.path.join(work, "broll.mp4")
                if overlay_broll(cur, out, brolls, ffprobe_facts(cur)["duration"]):
                    cur = out
                steps.done("broll", f"{len(brolls)} plan(s) inséré(s)")
            else:
                steps.done("broll", "aucun plan adapté trouvé")
        else:
            steps.skip("broll", "Plans d'illustration", "pas utile pour cette vidéo")

        # 4. Transcription finale (timings exacts sur la vidéo coupée)
        words = []
        if plan.get("subtitles") and facts["has_audio"]:
            mp3b = os.path.join(work, "b.mp3")
            extract_audio_mp3(cur, mp3b)
            tr2 = groq_transcribe(mp3b)
            words = (tr2 or {}).get("words") or []

        # 5. Zooms dynamiques + whoosh (punch-in à chaque phrase — timeline inchangée,
        #    donc les timings des sous-titres restent bons ; on zoome AVANT d'incruster
        #    les sous-titres pour qu'ils restent nets)
        if len(words) >= 6 and ffprobe_facts(cur)["duration"] > 6:
            steps.start("fx", "Zooms dynamiques et effets…")
            try:
                out = os.path.join(work, "fx.mp4")
                if zoom_punch(cur, out, words, facts["has_audio"], work):
                    cur = out
                    steps.done("fx", "punch-in à chaque phrase + whoosh")
                else:
                    steps.done("fx", "vidéo trop courte pour des zooms")
            except Exception as e:
                print("zoom_punch:", e, file=sys.stderr)
                steps.done("fx", "effets non appliqués (on continue sans)")
        else:
            steps.skip("fx", "Zooms dynamiques", "pas assez de parole")

        # 6. Sous-titres + hook incrustés par-dessus
        if words:
            steps.start("subs", "Sous-titres animés…")
            ass = os.path.join(work, "subs.ass")
            with open(ass, "w", encoding="utf-8") as f:
                f.write(build_ass(words, str(plan.get("hook_text") or "")))
            out = os.path.join(work, "subs.mp4")
            burn_subs(cur, out, ass)
            cur = out
            steps.done("subs", f"{len(words)} mots synchronisés")
        elif plan.get("subtitles") and facts["has_audio"]:
            steps.done("subs", "transcription indisponible")
        else:
            steps.skip("subs", "Sous-titres", "pas de parole — pas de sous-titres")

        # 5. Musique + normalisation du son
        steps.start("audio", "Mixage du son…")
        music = pick_music(str(plan.get("music_mood") or ""))
        out = os.path.join(work, "final.mp4")
        loudnorm(cur, out, music_path=music)
        cur = out
        steps.done("audio", "musique ajoutée" if music else "voix normalisée")

        steps.start("up", "Envoi de la vidéo améliorée…")
        url = upload_result(job, cur)
        steps.done("up")

        update_job(job["id"], {"status": "done", "result_url": url,
                               "finished_at": "now()", "steps": steps.items})
        print("Job", job["id"], "terminé:", url)
    except Exception as e:
        traceback.print_exc()
        update_job(job["id"], {"status": "error", "error": str(e)[:500],
                               "finished_at": "now()", "steps": steps.items})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    print("Skillora video-worker démarré.",
          "Groq:", "oui" if GROQ_KEY else "NON (sous-titres/plan IA désactivés)",
          "· Pexels:", "oui" if PEXELS_KEY else "non")
    while True:
        job = claim_job()
        if job:
            print("Job réclamé:", job["id"])
            process(job)
        else:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
