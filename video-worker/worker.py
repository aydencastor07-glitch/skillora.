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

FONT = os.environ.get("SUB_FONT", "DejaVu Sans")

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


def cut_silences(src, dst, silences, duration, keep_pad=0.22):
    """Garde les segments parlés (+ un petit coussin naturel autour)."""
    if not silences:
        return False
    keep, cursor = [], 0.0
    for (s, e) in silences:
        s2, e2 = max(0.0, s + keep_pad), max(0.0, e - keep_pad)
        if e2 - s2 <= 0.15:  # pause trop courte une fois le coussin retiré
            continue
        if s2 > cursor + 0.05:
            keep.append((cursor, s2))
        cursor = e2
    if cursor < duration - 0.05:
        keep.append((cursor, duration))
    removed = duration - sum(e - s for s, e in keep)
    if removed < 1.0 or not keep:  # pas la peine de ré-encoder pour < 1 s
        return False
    parts = []
    for (s, e) in keep:
        parts.append(f"between(t,{s:.3f},{e:.3f})")
    expr = "+".join(parts)
    run(["ffmpeg", "-y", "-i", src,
         "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
         "-af", f"aselect='{expr}',asetpts=N/SR/TB",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", dst])
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
                        "Content-Type": f"multipart/form-data; boundary={boundary}"},
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
        " \"broll_keywords\": [\"2-3 mots-clés ANGLAIS de plans d'illustration, ou vide\"]}"
    )
    try:
        st, raw = http("POST", "https://api.groq.com/openai/v1/chat/completions",
                       {"Authorization": "Bearer " + GROQ_KEY},
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
    """Sous-titres karaoké par groupes de 3 mots + accroche des 2,5 premières secondes."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},72,&H00FFFFFF,&H0054DC3D,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,260,1
Style: Hook,{FONT},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,8,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook_text:
        safe = hook_text.replace("{", "").replace("}", "").replace("\n", " ")
        lines.append(f"Dialogue: 1,0:00:00.10,0:00:02.60,Hook,,0,0,0,,{{\\fad(120,160)}}{safe}")
    group = []
    for w in words:
        group.append(w)
        if len(group) == 3 or (w is words[-1] and group):
            start, end = group[0]["start"], group[-1]["end"]
            if end - start < 0.12:
                end = start + 0.12
            text = ""
            for g in group:
                k = max(1, int(round((g["end"] - g["start"]) * 100)))
                word = str(g["word"]).strip().replace("{", "").replace("}", "")
                text += f"{{\\k{k}}}{word} "
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{{\\fad(60,60)}}{text.strip()}")
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
        try:
            q = urllib.parse.quote(str(kw))
            st, raw = http("GET",
                           f"https://api.pexels.com/videos/search?query={q}&orientation=portrait&per_page=3",
                           {"Authorization": PEXELS_KEY}, timeout=60)
            data = json.loads(raw)
            for vid in data.get("videos", []):
                pick = None
                for f in vid.get("video_files", []):
                    if f.get("height", 0) >= min_h and f.get("width", 0) < f.get("height", 0):
                        if pick is None or f["height"] < pick["height"]:
                            pick = f
                if pick:
                    out = tempfile.mktemp(suffix=".mp4")
                    urllib.request.urlretrieve(pick["link"], out)
                    files.append(out)
                    break
        except Exception as e:
            print("pexels:", kw, e, file=sys.stderr)
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

        # 1. Coupe des silences (uniquement s'il y a de la parole : couper une
        #    vidéo d'ambiance n'a pas de sens)
        if plan.get("cut_silences") and tr_text and silences:
            steps.start("cut", "Coupe des temps morts…")
            out = os.path.join(work, "cut.mp4")
            if cut_silences(cur, out, silences, facts["duration"]):
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

        # 4. Sous-titres + hook — transcription REFAITE sur la vidéo coupée
        if plan.get("subtitles") and facts["has_audio"]:
            steps.start("subs", "Sous-titres animés…")
            mp3b = os.path.join(work, "b.mp3")
            extract_audio_mp3(cur, mp3b)
            tr2 = groq_transcribe(mp3b)
            words = (tr2 or {}).get("words") or []
            if words:
                ass = os.path.join(work, "subs.ass")
                with open(ass, "w", encoding="utf-8") as f:
                    f.write(build_ass(words, str(plan.get("hook_text") or "")))
                out = os.path.join(work, "subs.mp4")
                burn_subs(cur, out, ass)
                cur = out
                steps.done("subs", f"{len(words)} mots synchronisés")
            else:
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
