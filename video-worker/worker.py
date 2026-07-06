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

import base64
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
# Modèles multimodaux Groq (essayés dans l'ordre jusqu'à ce qu'un réponde) :
# donnent des YEUX au worker. Le premier qui marche est mémorisé.
VISION_MODELS = [m for m in [os.environ.get("GROQ_VISION_MODEL", "")] if m] + [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]
_VISION_MODEL_OK = []  # cache du modèle qui répond (worker longue durée)


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
    tags = {str(k).lower(): str(vv) for k, vv in (info.get("format", {}).get("tags", {}) or {}).items()}
    return {"duration": dur, "width": w, "height": h, "has_audio": a is not None,
            "vertical": h > 0 and w > 0 and (h / w) >= 1.6,
            "improved": "skillora-improved" in tags.get("comment", "")}


def detect_silences(path, noise_db=-30, min_d=0.55):
    """Retourne [(début, fin), …] des silences (pauses > min_d secondes)."""
    p = subprocess.run(["ffmpeg", "-i", path, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    out = p.stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends[:len(starts)]))


def _frange(start, stop, step):
    """range() en flottants (le pas peut être décimal)."""
    out, t = [], start
    while t < stop:
        out.append(round(t, 3))
        t += step
    return out


def scene_cuts(path, threshold=0.30, cap=60):
    """Détecte les CHANGEMENTS DE PLAN sur TOUTE la vidéo (analyse chaque image,
    c'est gratuit). Retourne les instants où l'image change franchement -> ce sont
    les vrais points de coupe/transition d'un vlog ou d'un montage multi-plans."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-i", path, "-filter:v",
             f"select='gt(scene,{threshold})',metadata=print:file=-",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600)
        times = [round(float(m), 3) for m in re.findall(r"pts_time:([\d.]+)", p.stdout + p.stderr)]
        out = []
        for t in sorted(times):  # déduplique les cuts trop rapprochés (< 0.4 s)
            if not out or t - out[-1] >= 0.4:
                out.append(t)
        return out[:cap]
    except Exception as e:
        print("scene_cuts:", e, file=sys.stderr)
        return []


def audio_energy(path, duration, win=0.5):
    """Énergie sonore fenêtre par fenêtre (RMS) sur toute la vidéo -> repère les
    moments FORTS (action, choc, drop) vs les moments calmes. Stdlib pur via WAV
    mono 8 kHz. Retourne [(t, niveau 0..1)] ou [] si pas d'audio."""
    try:
        wav = path + ".energy.wav"
        run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "8000",
             "-vn", "-f", "wav", wav], timeout=300)
        import wave as _wave
        import array as _array
        with _wave.open(wav, "rb") as wf:
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        os.remove(wav)
        samples = _array.array("h")
        samples.frombytes(raw)
        step = max(1, int(sr * win))
        out, peak = [], 1.0
        for i in range(0, len(samples), step):
            chunk = samples[i:i + step]
            if not chunk:
                continue
            rms = (sum(v * v for v in chunk) / len(chunk)) ** 0.5
            out.append([round(i / sr, 3), rms])
            peak = max(peak, rms)
        for e in out:
            e[1] = round(min(1.0, e[1] / peak), 3)
        return [(t, lv) for (t, lv) in out]
    except Exception as e:
        print("audio_energy:", e, file=sys.stderr)
        return []


def detect_beats(path, duration):
    """Estime les TEMPS FORTS de la musique/ambiance (pour caler coupes et zooms
    sur le rythme, façon edit TikTok). Onsets par montée d'énergie ; si le tempo
    est régulier, on renvoie une grille régulière. [] si rien d'exploitable."""
    energy = audio_energy(path, duration, win=0.10)
    if len(energy) < 8:
        return []
    lv = [e[1] for e in energy]
    ts = [e[0] for e in energy]
    onsets = []
    for i in range(2, len(lv)):
        rise = lv[i] - (lv[i - 1] + lv[i - 2]) / 2
        if rise > 0.14 and lv[i] > 0.42:
            if not onsets or ts[i] - onsets[-1] >= 0.28:  # anti-doublons (>210 bpm)
                onsets.append(ts[i])
    if len(onsets) < 6:
        return []
    gaps = sorted(onsets[i + 1] - onsets[i] for i in range(len(onsets) - 1))
    med = gaps[len(gaps) // 2]
    if 0.3 <= med <= 1.2:  # 50–200 bpm plausible -> grille régulière propre
        grid, t = [], onsets[0]
        while t < duration - 0.2:
            grid.append(round(t, 3))
            t += med
        return grid[:80]
    return onsets[:80]


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


# Intentions de bruitage -> mots-clés cherchés dans les noms de fichiers du bucket.
# L'IA choisit une intention ; le worker trouve le fichier correspondant.
SFX_INTENTS = {
    "typing": ["typing", "keyboard", "keypress", "keypad"],
    "click": ["click", "mouse"],
    "pop": ["pop"],
    "whoosh": ["whoosh", "swish", "swoosh", "swipe"],
    "cash": ["cash", "money", "register", "coin", "kaching", "chaching"],
    "ding": ["ding", "chime", "bell", "glocken", "correct", "notification"],
    "impact": ["impact", "hit", "punch", "boom", "slam", "bass drop", "dramatic"],
    "explosion": ["explosion", "explos", "blast"],
    "magic": ["magic", "glitter", "sparkle", "reveal", "shimmer", "fairy"],
    "glitch": ["glitch", "hack", "teleren", "digital", "error"],
    "camera": ["camera", "shutter", "flash", "photo"],
    "beep": ["beep", "censure", "censor", "bleep"],
    "scratch": ["scratch", "record", "vinyl", "rewind"],
    "applause": ["applause", "cheers", "clap", "crowd"],
    "fail": ["fail", "trumpet", "fart", "whistle", "sad"],
    "scream": ["scream", "horror", "surprised", "shock"],
    "heartbeat": ["heartbeat", "heart"],
    "riser": ["riser", "rise", "tension", "brass crisis", "crisis", "metallic"],
    "airhorn": ["airhorn", "air horn", "horn"],
    "boom": ["boom", "cinematic"],
}


def make_whoosh(path):
    """Petit 'whoosh' synthétisé par nous (aucun droit d'auteur)."""
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.3:amplitude=0.6",
         "-af", "highpass=f=500,lowpass=f=5200,afade=t=in:st=0:d=0.05,afade=t=out:st=0.10:d=0.20,volume=1.1",
         "-ar", "44100", path])


def make_pop(path):
    """'Pop/clic' court pour les mots importants (synthétisé, libre)."""
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=920:duration=0.09",
         "-af", "afade=t=in:st=0:d=0.005,afade=t=out:st=0.03:d=0.06,volume=1.4",
         "-ar", "44100", "-ac", "2", path])


def make_sfx_bank(work):
    """Banque de bruitages 100 % synthétisés (aucun droit d'auteur) :
    typing, click, ding, cash, magic, impact, pop, whoosh."""
    bank = {}

    def synth(name, expr, dur):
        p = os.path.join(work, f"sfx_{name}.wav")
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc={expr}:d={dur}:s=44100",
             "-af", "volume=1.0", "-ar", "44100", "-ac", "2", p])
        bank[name] = [p]  # liste : plusieurs variantes possibles par intention

    # clic souris / bouton
    synth("click", "'0.9*sin(2*PI*2100*t)*exp(-55*t)+0.5*sin(2*PI*3400*t)*exp(-70*t)'", "0.12")
    # ding (cloche, note E6 + harmonique)
    synth("ding", "'0.6*sin(2*PI*1318*t)*exp(-6*t)+0.3*sin(2*PI*2637*t)*exp(-8*t)'", "0.8")
    # cha-ching caisse (2 cloches rapprochées)
    synth("cash", "'0.55*sin(2*PI*1318*t)*exp(-9*t)+0.55*sin(2*PI*1760*(t-0.09))*exp(-7*(t-0.09))*gt(t,0.09)+0.3*sin(2*PI*3520*(t-0.09))*exp(-9*(t-0.09))*gt(t,0.09)'", "0.9")
    # magie (arpège montant scintillant)
    synth("magic", "'0.4*sin(2*PI*1046*t)*exp(-9*t)+0.4*sin(2*PI*1318*(t-0.08))*exp(-9*(t-0.08))*gt(t,0.08)+0.4*sin(2*PI*1568*(t-0.16))*exp(-9*(t-0.16))*gt(t,0.16)+0.35*sin(2*PI*2093*(t-0.24))*exp(-8*(t-0.24))*gt(t,0.24)'", "1.0")
    # impact (coup sourd)
    synth("impact", "'1.2*sin(2*PI*82*t)*exp(-11*t)+0.5*sin(2*PI*55*t)*exp(-7*t)'", "0.5")
    # pop
    pop = os.path.join(work, "sfx_pop.wav")
    make_pop(pop)
    bank["pop"] = [pop]
    # whoosh
    wh = os.path.join(work, "sfx_whoosh.wav")
    make_whoosh(wh)
    bank["whoosh"] = [wh]
    # clavier qui tape = rafale de 6 clics irréguliers
    typing = os.path.join(work, "sfx_typing.wav")
    delays = [0, 90, 160, 270, 350, 460]
    fc = [f"[0:a]asplit={len(delays)}" + "".join(f"[c{i}]" for i in range(len(delays)))]
    for i, d in enumerate(delays):
        vol = 0.8 + (i % 3) * 0.12
        fc.append(f"[c{i}]adelay={d}|{d},volume={vol:.2f}[t{i}]")
    fc.append("".join(f"[t{i}]" for i in range(len(delays))) +
              f"amix=inputs={len(delays)}:normalize=0,volume=1.2")
    run(["ffmpeg", "-y", "-i", bank["click"][0], "-filter_complex", ";".join(fc),
         "-ar", "44100", "-ac", "2", typing])
    bank["typing"] = [typing]

    # Bruitages PRO uploadés dans le bucket public 'sfx-library'. Matching SOUPLE
    # par mots-clés : les noms descriptifs (keyboard_typing-01.mp3, cash_register-01.mp3,
    # teleren_hack_glitch-01.mp3…) sont rattachés à une "intention" que l'IA peut demander.
    try:
        st, raw = http("POST", f"{SB_URL}/storage/v1/object/list/sfx-library",
                       sb_headers(), {"prefix": "", "limit": 300}, timeout=25)
        files = [str(it.get("name", "")) for it in json.loads(raw)
                 if str(it.get("name", "")).lower().endswith((".mp3", ".wav", ".m4a", ".ogg"))]
        by_intent = {}
        for name in files:
            n = norm_token(name.rsplit(".", 1)[0].replace("-", "_").replace("_", " "))
            for intent, kws in SFX_INTENTS.items():
                if any(kw in n for kw in kws):
                    by_intent.setdefault(intent, []).append(name)
        for intent, matches in by_intent.items():
            paths = []
            for j, name in enumerate(matches[:3]):  # jusqu'à 3 VARIANTES par intention
                try:
                    rawp = os.path.join(work, "dl_" + re.sub(r"[^a-z0-9.]", "_", name.lower()))
                    download(f"{SB_URL}/storage/v1/object/public/sfx-library/{urllib.parse.quote(name)}", rawp)
                    out = os.path.join(work, f"pro_{intent}_{j}.wav")
                    run(["ffmpeg", "-y", "-i", rawp, "-t", "2.2",
                         "-af", "afade=t=out:st=1.9:d=0.3", "-ar", "44100", "-ac", "2", out])
                    paths.append(out)
                except Exception as e:
                    print("sfx dl", name, e, file=sys.stderr)
            if paths:
                bank[intent] = paths  # remplace les sons synthétisés
        if by_intent:
            print("sfx-library: intentions disponibles ->", sorted(by_intent.keys()), file=sys.stderr)
    except Exception as e:
        print("sfx-library:", e, file=sys.stderr)
    return bank


def norm_token(w):
    return re.sub(r"[^0-9a-zà-ÿ€$%]", "", str(w).lower())


KEYWORD_RX = re.compile(r"^\d|€|\$|%|^(gratuit|gratuits|free|promo|code|secret|jamais|incroyable|zero|zéro|euros?|dollars?)$")


def groq_qc(frames):
    """Contrôle qualité par l'IA : le worker REGARDE sa propre vidéo finale.
    Renvoie {"subs_visible": bool, "face_covered": bool, "issue": str} ou None."""
    if not GROQ_KEY or not frames:
        return None
    content = [{"type": "text", "text": (
        "Tu es contrôleur qualité de vidéos TikTok montées (sous-titres incrustés).\n"
        "Regarde ces images du RENDU FINAL et réponds UNIQUEMENT ce JSON:\n"
        "{\"subs_visible\": bool,   // les sous-titres sont-ils bien lisibles et entièrement dans l'écran ?\n"
        " \"face_covered\": bool,   // le TEXTE recouvre-t-il le visage de la personne ?\n"
        " \"issue\": \"problème visuel principal en 1 phrase, ou vide\"}"
    )}]
    for (t, p) in frames[:3]:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "text", "text": f"Image à t={t:.1f}s :"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    models = _VISION_MODEL_OK + [m for m in VISION_MODELS if m not in _VISION_MODEL_OK]
    for model in models[:2]:
        try:
            st, raw = http("POST", "https://api.groq.com/openai/v1/chat/completions",
                           {"Authorization": "Bearer " + GROQ_KEY, "User-Agent": GROQ_UA},
                           {"model": model, "messages": [{"role": "user", "content": content}],
                            "temperature": 0.1, "response_format": {"type": "json_object"}},
                           timeout=90)
            out = json.loads(raw)
            return json.loads(out["choices"][0]["message"]["content"])
        except Exception as e:
            print("groq_qc:", e, file=sys.stderr)
    return None


def sfx_event_times(words, plan_sfx, kws):
    """Associe chaque bruitage choisi par l'IA au timestamp de son mot exact.
    Fallback : les mots forts sans bruitage reçoivent un 'ding' (argent -> 'cash')."""
    events, used_ts = [], set()
    for item in (plan_sfx or [])[:6]:
        target = norm_token((item or {}).get("word", ""))
        sound = str((item or {}).get("sound", "pop")).strip().lower()
        if not target:
            continue
        for w in words or []:
            t = float(w.get("start", 0))
            if norm_token(w.get("word", "")) == target and t not in used_ts:
                events.append((t, sound))
                used_ts.add(t)
                break
    for k in kws or []:
        t = float(k["start"])
        if any(abs(t - e[0]) < 0.4 for e in events):
            continue
        txt = norm_token(k["text"])
        sound = "cash" if (("€" in txt) or ("$" in txt) or txt.startswith(("0", "gratuit", "free"))) else "ding"
        events.append((t, sound))
    events.sort()
    return events[:8]


def head_tail_spans(words, duration, silences=None, lead=0.7, tail_gap=1.0, keep_opening=None):
    """Démarrage mou (personnage figé/muet) et fin vide -> plages à couper.
    Combine les mots (transcription) ET les silences détectés au début.
    keep_opening (analyse visuelle) : True = l'ouverture est captivante, on la
    GARDE même sans parole ; False = ouverture statique, coupe agressive."""
    spans = []
    head_end = 0.0
    if keep_opening is False:
        lead = 0.35  # ouverture pas captivante -> on saute direct au premier mot
    if words:
        first = float(words[0].get("start", 0))
        if first > lead:
            head_end = max(head_end, first - (0.15 if keep_opening is False else 0.25))
    for (s, e) in silences or []:
        if s < 0.2 and e > 0.8:  # silence qui colle au tout début
            head_end = max(head_end, e - 0.25)
    if keep_opening is True:
        head_end = 0.0  # action captivante au début : on n'y touche pas
    if head_end > 0.3:
        spans.append((0.0, head_end))
    if words:
        last = float(words[-1].get("end", duration))
        if duration - last > tail_gap:
            spans.append((last + 0.45, duration))
    return spans


def sentence_layout(words, sub_position="dynamic", seed=0, bands=None):
    """Position Y du sous-titre pour CHAQUE mot (change à chaque phrase).
    Partagé entre les sous-titres et les émojis. `bands` (analyse visuelle) :
    positions autorisées qui ÉVITENT le visage du créateur."""
    sp = str(sub_position).lower()
    if bands:
        base = list(bands) * 3
    else:
        base = [1430] * 3 if sp == "bottom" else ([960] * 3 if sp == "middle" else [1430, 960, 620])
    ys, sent, prev = [], seed % 3, None
    for w in words or []:
        ws = float(w.get("start", 0))
        if prev is not None and ws - prev > 0.8:
            sent += 1
        ys.append(base[sent % 3])
        prev = float(w.get("end", ws))
    return ys


def keyword_times(words, plan_keywords, max_n=6, min_gap=1.5):
    """Moments des mots forts : ceux choisis par l'IA + prix/chiffres détectés."""
    kwset = {norm_token(k.split()[0]) for k in (plan_keywords or []) if str(k).strip()}
    hits, last = [], -10.0
    for w in words or []:
        t = norm_token(w.get("word", ""))
        if not t:
            continue
        if (t in kwset or KEYWORD_RX.search(t)) and float(w["start"]) - last >= min_gap:
            hits.append({"start": float(w["start"]), "end": float(w["end"]),
                         "text": str(w["word"]).strip().upper().strip(".,!?;:")})
            last = float(w["start"])
        if len(hits) >= max_n:
            break
    return hits


EMOJI_CDN = "https://raw.githubusercontent.com/jdecked/twemoji/main/assets/72x72/{}.png"
EMOJI_SVG = "https://raw.githubusercontent.com/jdecked/twemoji/main/assets/svg/{}.svg"


def emoji_events(words, plan_emojis, work, layout=None):
    """[(t, png, y)] : émoji Twemoji du mot exact, positionné JUSTE AU-DESSUS du
    sous-titre correspondant (même position que le texte à cet instant)."""
    events = []
    for i, item in enumerate((plan_emojis or [])[:6]):
        target = norm_token((item or {}).get("word", ""))
        emo = str((item or {}).get("emoji", "")).strip()
        if not target or not emo:
            continue
        code = "-".join(f"{ord(c):x}" for c in emo if ord(c) != 0xFE0F)
        if not code:
            continue
        try:
            p = os.path.join(work, f"emoji_{i}.png")
            download(EMOJI_CDN.format(code), p)
            for idx, w in enumerate(words or []):
                if norm_token(w.get("word", "")) == target:
                    suby = layout[idx] if layout and idx < len(layout) else 1430
                    y = max(150, suby - 265)  # collé au-dessus de la ligne de texte
                    events.append((float(w["start"]), p, y))
                    break
        except Exception as e:
            print("emoji:", emo, e, file=sys.stderr)
    return events


def brand_events(words, plan_brands, work):
    """Logos OFFICIELS de marques CITÉES -> gros objets animés à l'écran.
    1) Simple Icons (SVG monochrome, converti via rsvg-convert) ;
    2) repli : favicon officiel du site via Google (PNG couleur, marche pour
       TOUTES les marques du monde — Temu, Shein… absentes de Simple Icons)."""
    events = []
    for i, item in enumerate((plan_brands or [])[:2]):
        target = norm_token((item or {}).get("word", ""))
        slug = re.sub(r"[^a-z0-9]", "", str((item or {}).get("slug", "")).lower())
        if not target or not slug:
            continue
        png = os.path.join(work, f"brand_{i}.png")
        got = False
        try:
            svg = os.path.join(work, f"brand_{i}.svg")
            download(f"https://cdn.simpleicons.org/{slug}", svg)
            run(["rsvg-convert", "-w", "300", "-o", png, svg], timeout=60)
            got = os.path.exists(png) and os.path.getsize(png) > 500
        except Exception as e:
            print("brand simpleicons:", slug, e, file=sys.stderr)
        if not got:
            try:
                download(f"https://www.google.com/s2/favicons?domain={slug}.com&sz=256", png)
                got = os.path.exists(png) and os.path.getsize(png) > 500
            except Exception as e:
                print("brand favicon:", slug, e, file=sys.stderr)
        if not got:
            continue
        for w in (words or []):
            if norm_token(w.get("word", "")) == target:
                events.append((float(w["start"]), png))
                break
    return events


def object_events(words, plan_objects, work):
    """Gros objets qui illustrent le sujet (voiture, téléphone, produit…) :
    émoji Twemoji rendu en GRAND depuis le SVG (net à 300 px)."""
    events = []
    for i, item in enumerate((plan_objects or [])[:2]):
        target = norm_token((item or {}).get("word", ""))
        emo = str((item or {}).get("emoji", "")).strip()
        if not target or not emo:
            continue
        code = "-".join(f"{ord(c):x}" for c in emo if ord(c) != 0xFE0F)
        if not code:
            continue
        try:
            png = os.path.join(work, f"obj_{i}.png")
            try:
                svg = os.path.join(work, f"obj_{i}.svg")
                download(EMOJI_SVG.format(code), svg)
                run(["rsvg-convert", "-w", "300", "-o", png, svg], timeout=60)
                assert os.path.exists(png) and os.path.getsize(png) > 500
            except Exception:
                download(EMOJI_CDN.format(code), png)  # repli 72px (flou mais présent)
            for w in (words or []):
                if norm_token(w.get("word", "")) == target:
                    events.append((float(w["start"]), png))
                    break
        except Exception as e:
            print("object:", emo, e, file=sys.stderr)
    return events


OBJ_IN, OBJ_HOLD, OBJ_OUT = 0.45, 1.5, 0.45  # entrée glissée / pause / sortie


def overlay_objects(src, dst, events, seed=0):
    """Objets/logos animés façon monteur : l'objet GLISSE depuis un bord,
    s'ARRÊTE au milieu de l'écran (tiers haut, jamais sur les sous-titres),
    puis REPART de l'autre côté — accélérations douces. Sens alterné par job."""
    if not events:
        return False
    fc, last = [], "[0:v]"
    inputs = []
    for i, (t, png) in enumerate(events[:3]):
        inputs += ["-i", png]
        t_in_end = t + OBJ_IN
        t_out = t + OBJ_IN + OBJ_HOLD
        t_end = t_out + OBJ_OUT
        sgn = 1 if (seed + i) % 2 == 0 else -1  # gauche->droite puis l'inverse
        # x : hors-champ -> centre (ease-out) ; puis centre -> hors-champ opposé (ease-in)
        x_expr = (f"(W-w)/2-({sgn})*(W+w)/2*pow(1-min((t-{t:.3f})/{OBJ_IN}\\,1)\\,2)"
                  f"+({sgn})*(W+w)/2*pow(max(0\\,(t-{t_out:.3f})/{OBJ_OUT})\\,2)")
        fc.append(f"[{i + 1}:v]scale=300:-1[ob{i}]")
        nxt = f"[oo{i}]"
        fc.append(f"{last}[ob{i}]overlay=x='{x_expr}':y=400:"
                  f"enable='between(t,{t:.3f},{t_end:.3f})'{nxt}")
        last = nxt
    run(["ffmpeg", "-y", "-i", src, *inputs,
         "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])
    return True


def overlay_emojis(src, dst, events):
    """Incruste chaque émoji (~1 s) au-dessus du sous-titre du moment."""
    if not events:
        return False
    fc, last = [], "[0:v]"
    inputs = []
    for i, (t, png, y) in enumerate(events[:6]):
        inputs += ["-i", png]
        fc.append(f"[{i + 1}:v]scale=175:-1[e{i}]")
        nxt = f"[o{i}]"
        fc.append(f"{last}[e{i}]overlay=(W-w)/2:{int(y)}:enable='between(t,{t:.3f},{t + 1.0:.3f})'{nxt}")
        last = nxt
    run(["ffmpeg", "-y", "-i", src, *inputs,
         "-filter_complex", ";".join(fc), "-map", last, "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])
    return True


def slide_aside(src, dst, t1, dur=1.5):
    """Effet 'zoom à côté' PRO : la vidéo est ZOOMÉE (1.35x) et GLISSE vers la
    gauche — tout reste dans l'image, aucune bordure ni fond flou. Le sujet part
    à gauche, le gros texte (ASS) occupe l'espace libéré à droite.
    Timeline inchangée."""
    facts = ffprobe_facts(src)
    W, H = facts["width"], facts["height"]
    t2 = t1 + dur
    sw, sh = int(W * 1.35) // 2 * 2, int(H * 1.35) // 2 * 2
    base_x = (sw - W) // 2
    y_c = (sh - H) // 2
    # p monte en 0,3 s, reste à 1, redescend en 0,3 s -> glissement doux
    p = (f"(min(1\\,max(0\\,(t-{t1:.3f})/0.3))*min(1\\,max(0\\,({t2:.3f}-t)/0.3)))")
    x_expr = f"{base_x}+{base_x}*{p}"
    fc = (f"[0:v]split=2[base][z];"
          f"[z]scale={sw}:{sh},crop={W}:{H}:'{x_expr}':{y_c}[zc];"
          f"[base][zc]overlay=0:0:enable='between(t,{t1:.3f},{t2:.3f})'[v]")
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])
    return t2


def zoom_punch(src, dst, words, has_audio, work, sfx_events=None, extra_whooshes=None,
               avoid=None, seed=0, bounds_override=None):
    """Zooms dynamiques : punch-in/out alterné à chaque phrase, la caméra GLISSE
    latéralement pendant les segments zoomés (panoramique), whoosh aux punchs et
    bruitages contextuels (typing/ding/cash/…) bien audibles sur les mots forts.
    La timeline ne change pas -> timings des sous-titres valides.
    `sfx_events` = [(t, nom_du_son)] ; `avoid` = fenêtre sans punch (effet 'côté') ;
    `bounds_override` = points de zoom imposés (rythme sans voix : beats/plans)."""
    facts = ffprobe_facts(src)
    duration, W, H = facts["duration"], facts["width"], facts["height"]
    if bounds_override is not None:
        bounds = [b for b in sorted(set(round(x, 2) for x in bounds_override)) if 0.0 <= b < duration - 0.4]
        if not bounds or bounds[0] > 0.3:
            bounds = [0.0] + bounds
    else:
        bounds = zoom_boundaries(words, duration)
    if avoid:
        bounds = [b for b in bounds if not (avoid[0] - 0.5 <= b <= avoid[1] + 0.5)] or [0.0]
    if len(bounds) > 48:  # trop de points (beats rapides) -> on garde 1 sur N
        keep = max(1, len(bounds) // 40)
        bounds = bounds[::keep]
    if len(bounds) < 2:
        return False
    edges = bounds + [duration]
    base_zooms = [1.0, 1.13, 1.0, 1.2]  # alternance zoom avant / arrière — punchs bien VISIBLES
    r = seed % 4
    ZOOMS = base_zooms[r:] + base_zooms[:r]  # varie d'un job à l'autre (anti-figé)
    fc, vlabels = [], []
    zoomed_i = 0
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        f = ZOOMS[i % len(ZOOMS)]
        chain = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
        if f > 1.0:
            # zoom + glissement latéral : x démarre décalé et revient vers le centre
            seg = max(0.4, b - a)
            margin_expr = f"(iw-iw/{f})"
            drift = 0.42 if zoomed_i % 2 == 0 else -0.42  # gauche puis droite
            x0 = 0.5 + drift / 2
            x_expr = (f"{margin_expr}*({x0:.3f}-{drift:.3f}*min(t/{seg:.3f}\\,1)/2)")
            chain += (f",crop=trunc(iw/{f}/2)*2:trunc(ih/{f}/2)*2:'{x_expr}':(ih-ih/{f})/2"
                      f",scale={W}:{H}")
            zoomed_i += 1
        chain += f",setsar=1[v{i}]"
        fc.append(chain)
        vlabels.append(f"[v{i}]")
    n = len(vlabels)
    fc.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[vz]")
    cmd = ["ffmpeg", "-y", "-i", src]
    maps = ["-map", "[vz]"]
    if has_audio:
        bank = make_sfx_bank(work)
        events = [(t, "whoosh") for t in ([b for b in bounds[1:]] + list(extra_whooshes or []))[:14]]
        for (t, name) in (sfx_events or [])[:14]:
            events.append((t, name if name in bank else "pop"))
        # volume par type : les bruitages "sens" doivent s'entendre par-dessus la voix
        # Repli des intentions non présentes dans la banque -> son le plus proche
        NEAR = {"explosion": "impact", "boom": "impact", "glitch": "beep", "camera": "click",
                "scratch": "whoosh", "applause": "magic", "fail": "pop", "scream": "impact",
                "heartbeat": "impact", "riser": "whoosh", "airhorn": "ding", "beep": "pop"}
        events = [(t, name if name in bank else NEAR.get(name, "pop")) for (t, name) in events]
        VOL = {"whoosh": 0.5, "pop": 0.8, "click": 0.9, "typing": 0.9, "ding": 0.8,
               "cash": 0.85, "magic": 0.8, "impact": 0.9, "explosion": 0.9, "glitch": 0.8,
               "camera": 0.85, "beep": 0.85, "scratch": 0.8, "applause": 0.7, "fail": 0.85,
               "scream": 0.85, "heartbeat": 0.6, "riser": 0.7, "airhorn": 0.9, "boom": 0.9}
        # Résout chaque événement vers un FICHIER concret, en tournant entre les
        # variantes de l'intention (6 whooshs différents -> jamais deux fois le même à la suite)
        rot = {}
        resolved = []  # (t, fichier, volume)
        for (t, name) in events:
            paths = bank.get(name) or []
            if not paths:
                continue
            k = rot.get(name, seed % max(1, len(paths)))
            rot[name] = k + 1
            resolved.append((t, paths[k % len(paths)], VOL.get(name, 0.8)))
        if resolved:
            uniq = sorted({p for (_t, p, _v) in resolved})
            idx = {}
            for k, p in enumerate(uniq):
                cmd += ["-i", p]
                idx[p] = k + 1  # l'entrée 0 est la vidéo
            counts = {p: sum(1 for (_t, p2, _v) in resolved if p2 == p) for p in uniq}
            mix_inputs = []
            for k, p in enumerate(uniq):
                fc.append(f"[{idx[p]}:a]asplit={counts[p]}" + "".join(f"[f{k}_{j}]" for j in range(counts[p])))
            seen = {p: 0 for p in uniq}
            for (t, p, vol) in resolved:
                k = uniq.index(p)
                j = seen[p]; seen[p] += 1
                # pré-déclenchement de 80 ms : le son claque PILE sur le mot (réflexe de monteur)
                ms = int(max(0.0, t - 0.08) * 1000)
                lab = f"mx{k}_{j}"
                fc.append(f"[f{k}_{j}]adelay={ms}|{ms},volume={vol}[{lab}]")
                mix_inputs.append(f"[{lab}]")
            fc.append("[0:a]" + "".join(mix_inputs) +
                      f"amix=inputs={len(mix_inputs) + 1}:duration=first:dropout_transition=0:normalize=0[am]")
            maps += ["-map", "[am]"]
        else:
            maps += ["-map", "0:a"]
    cmd += ["-filter_complex", ";".join(fc), *maps,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", dst]
    run(cmd)
    return True


def reframe_916(src, dst, w, h):
    """Passe au format 9:16 style clip : la vidéo entière au centre, et le fond
    (haut/bas) = la même vidéo zoomée-floutée. AUCUNE bordure noire."""
    run(["ffmpeg", "-y", "-i", src, "-filter_complex",
         "[0:v]split=2[bg][fg];"
         "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2[b];"
         "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[f];"
         "[b][f]overlay=(W-w)/2:(H-h)/2[v]",
         "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])


# ---------------------------------------------------------------- texte derrière la personne
_REMBG_SESSION = None


def _rembg_session():
    """Charge (une fois) le modèle IA de détourage. None si rembg absent."""
    global _REMBG_SESSION
    if _REMBG_SESSION is not None:
        return _REMBG_SESSION
    try:
        from rembg import new_session
        _REMBG_SESSION = new_session("u2netp")
    except Exception as e:
        print("rembg indisponible:", e, file=sys.stderr)
        _REMBG_SESSION = False
    return _REMBG_SESSION


def _bg_text_png(text, out_png, y_center):
    """Rend le texte en PNG transparent 1080x1920, effet 3D extrudé (couches
    décalées sombres + face blanche) — style 'ME AT 7:00' des edits pro."""
    safe = re.sub(r"[^A-Z0-9 ÀÂÉÈÊËÎÏÔÙÛÇ€$%!?:'.,-]", "", str(text).upper())[:18].strip()
    if not safe:
        return False
    lines_txt = [safe]
    if len(safe) > 10 and " " in safe:  # 2 lignes équilibrées si trop long
        mid = min(range(len(safe)), key=lambda i: abs(i - len(safe) // 2) if safe[i] == " " else 999)
        if safe[mid] == " ":
            lines_txt = [safe[:mid].strip(), safe[mid + 1:].strip()]
    maxlen = max(len(l) for l in lines_txt)
    fs = max(96, min(330, int(1020 / (max(1, maxlen) * 0.56))))
    font = "/usr/share/fonts/truetype/custom/Anton-Regular.ttf"
    fspec = f"fontfile={font}" if os.path.exists(font) else "font=Anton"
    dt = []
    for li, ltxt in enumerate(lines_txt):
        esc = ltxt.replace("\\", "").replace("'", "’").replace(":", "\\:").replace(",", "\\,").replace("%", "\\%")
        y0 = y_center - (len(lines_txt) - 1) * (fs // 2 + 20) + li * (fs + 40) - fs // 2
        for k in range(10, 0, -1):  # extrusion 3D (profondeur vers le bas-droite)
            dt.append(f"drawtext={fspec}:text='{esc}':fontsize={fs}"
                      f":fontcolor=0x0E0E12@0.92:x=(w-text_w)/2+{k * 4}:y={y0}+{k * 4}")
        dt.append(f"drawtext={fspec}:text='{esc}':fontsize={fs}"
                  f":fontcolor=white@0.96:x=(w-text_w)/2:y={y0}")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black@0.0:s=1080x1920:r=1:d=1,format=rgba",
         "-vf", ",".join(dt), "-frames:v", "1", out_png])
    return os.path.exists(out_png) and os.path.getsize(out_png) > 1000


def depth_text(src, dst, text, work, face_y="", duration=0.0):
    """Effet 'texte DERRIÈRE le personnage' sans fond vert : l'IA détoure la
    personne image par image (rembg), le texte 3D est posé sur la vidéo, puis
    la personne est ré-incrustée PAR-DESSUS le texte. False si impossible."""
    sess = _rembg_session()
    if not sess:
        return False
    try:
        from rembg import remove
        t0 = 0.4
        t1 = min(3.4, float(duration) - 0.6)
        if t1 - t0 < 1.2:
            return False
        y_center = {"top": 900, "middle": 620, "bottom": 460}.get(str(face_y).lower(), 700)
        txt_png = os.path.join(work, "bgtext.png")
        if not _bg_text_png(text, txt_png, y_center):
            return False
        dtd = os.path.join(work, "dt")
        os.makedirs(dtd, exist_ok=True)
        run(["ffmpeg", "-y", "-i", src, "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}",
             "-vf", "fps=30,scale=540:960", os.path.join(dtd, "f_%03d.png")])
        frames = sorted(f for f in os.listdir(dtd) if f.startswith("f_"))
        if len(frames) < 20:
            return False
        for f in frames:
            with open(os.path.join(dtd, f), "rb") as fh:
                cut = remove(fh.read(), session=sess)
            with open(os.path.join(dtd, "p" + f[1:]), "wb") as fh:
                fh.write(cut)
        # Une personne est-elle vraiment là ? (aire du détourage sur l'image du milieu)
        from PIL import Image
        mid = os.path.join(dtd, "p" + frames[len(frames) // 2][1:])
        alpha = Image.open(mid).convert("RGBA").getchannel("A")
        cover = sum(1 for a in alpha.getdata() if a > 96) / (540 * 960)
        if cover < 0.04 or cover > 0.72:
            print(f"depth_text: personne non exploitable (aire {cover:.0%})", file=sys.stderr)
            return False
        D = t1 - t0
        fc = (f"[1:v]format=rgba,fade=t=in:d=0.25:alpha=1,"
              f"fade=t=out:st={D - 0.30:.2f}:d=0.30:alpha=1,setpts=PTS+{t0:.2f}/TB[txt];"
              f"[2:v]format=rgba,scale=1080:1920,setpts=PTS-STARTPTS+{t0:.2f}/TB[per];"
              f"[0:v][txt]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})':eof_action=pass[a];"
              f"[a][per]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})':eof_action=pass[v]")
        run(["ffmpeg", "-y", "-i", src,
             "-loop", "1", "-t", f"{D + 0.05:.2f}", "-i", txt_png,
             "-framerate", "30", "-start_number", "1", "-i", os.path.join(dtd, "p_%03d.png"),
             "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])
        return os.path.exists(dst) and os.path.getsize(dst) > 50000
    except Exception as e:
        print("depth_text:", e, file=sys.stderr)
        return False


def loudnorm(src, dst, music_path=None, music_gain_db=-21, music_foreground=False):
    """Normalise la voix à -14 LUFS ; mixe la musique en dessous si fournie.
    music_foreground=True (vidéo sans voix) : la musique passe au PREMIER PLAN,
    forte, et devient le moteur sonore de la vidéo."""
    # Le tag 'skillora-improved' permet de refuser une 2e amélioration (doublons de sous-titres).
    if music_path and music_foreground:
        # Pas de voix : la musique porte la vidéo (forte), l'audio original reste
        # en ambiance discrète en dessous.
        run(["ffmpeg", "-y", "-i", src, "-stream_loop", "-1", "-i", music_path,
             "-filter_complex",
             "[0:a]volume=-16dB[amb];[1:a]volume=0dB[m];"
             "[m][amb]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
             "loudnorm=I=-13:TP=-1.5:LRA=11[a]",
             "-map", "0:v", "-map", "[a]", "-metadata", "comment=skillora-improved",
             "-c:v", "copy", "-c:a", "aac", "-shortest", dst])
    elif music_path:
        run(["ffmpeg", "-y", "-i", src, "-stream_loop", "-1", "-i", music_path,
             "-filter_complex",
             f"[1:a]volume={music_gain_db}dB[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=3,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "0:v", "-map", "[a]", "-metadata", "comment=skillora-improved",
             "-c:v", "copy", "-c:a", "aac", "-shortest", dst])
    else:
        run(["ffmpeg", "-y", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             "-metadata", "comment=skillora-improved", "-c:v", "copy", "-c:a", "aac", dst])


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


def extract_frames(src, times, work, width=480):
    """Extrait des images clefs (réduites) pour l'analyse visuelle."""
    frames = []
    for i, t in enumerate(times):
        p = os.path.join(work, f"fr_{i}.jpg")
        try:
            run(["ffmpeg", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", src, "-frames:v", "1",
                 "-vf", f"scale={width}:-2", "-q:v", "7", p], timeout=120)
            if os.path.exists(p):
                frames.append((t, p))
        except Exception:
            pass
    return frames


def _vision_call(prompt, frames):
    """UN appel au modèle de vision (max 5 images, limite dure). Retourne le JSON
    décodé ou None. Gère le repli entre modèles."""
    if not GROQ_KEY or not frames:
        return None
    content = [{"type": "text", "text": prompt}]
    for (t, p) in frames[:5]:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "text", "text": f"Image à t={t:.1f}s :"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    models = _VISION_MODEL_OK + [m for m in VISION_MODELS if m not in _VISION_MODEL_OK]
    for model in models:
        try:
            st, raw = http("POST", "https://api.groq.com/openai/v1/chat/completions",
                           {"Authorization": "Bearer " + GROQ_KEY, "User-Agent": GROQ_UA},
                           {"model": model,
                            "messages": [{"role": "user", "content": content}],
                            "temperature": 0.2, "response_format": {"type": "json_object"}},
                           timeout=120)
            out = json.loads(raw)
            if not _VISION_MODEL_OK:
                _VISION_MODEL_OK.append(model)
                print("_vision_call: modèle OK ->", model, file=sys.stderr)
            return json.loads(out["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()[:200]
            except Exception:
                body = ""
            print("_vision_call HTTP", e.code, "(", model, "):", body, file=sys.stderr)
            if e.code in (400, 404, 422):
                continue
            return None
        except Exception as e:
            print("_vision_call:", e, file=sys.stderr)
            return None
    return None


def groq_vision_full(src, work, duration, transcript_text, scenecuts=None):
    """Les YEUX du worker — regarde TOUTE la vidéo (pas 5 images).
    On échantillonne densément (≈1 image / 2,5 s + chaque changement de plan),
    par lots de 5 images -> plusieurs appels -> une carte complète de la vidéo :
    type de vidéo, scènes horodatées, meilleurs moments, où mettre les effets."""
    if not GROQ_KEY:
        return None
    # Points d'échantillonnage : grille dense + chaque changement de plan détecté
    n = max(6, min(24, int(duration / 2.5) + 2))
    grid = [round(duration * (k + 0.5) / n, 2) for k in range(n)]
    times = sorted(set([0.3, 1.0] + grid + [round(t, 2) for t in (scenecuts or [])]))
    times = [t for t in times if 0 <= t < duration - 0.15][:24]
    frames = extract_frames(src, times, work, width=448)
    if not frames:
        return None
    # 1) Chaque lot de 5 images -> description des scènes de ce segment
    all_scenes = []
    faces, objs = [], []
    for bi in range(0, len(frames), 5):
        batch = frames[bi:bi + 5]
        seg = _vision_call(
            "Tu es un monteur vidéo pro. Voici des images successives d'une vidéo courte "
            f"({duration:.0f}s), avec leur timestamp. "
            f"Transcription (contexte): {transcript_text[:400] or '(aucune parole)'}\n"
            "Décris CE QUI SE PASSE à chaque image. Réponds UNIQUEMENT ce JSON:\n"
            "{\"scenes\": [{\"t\": secondes, \"action\": \"ce qu'on voit (court)\", "
            "\"motion\": bool, \"interest\": 0-10, \"shot\": \"wide|medium|close|product|text|other\"}], "
            "// une entrée par image, interest=à quel point le moment est fort/captivant\n"
            " \"face_y\": \"top|middle|bottom|none\", \"objects\": [\"éléments importants\"]}",
            batch)
        if seg:
            all_scenes += seg.get("scenes") or []
            if seg.get("face_y") and seg["face_y"] != "none":
                faces.append(seg["face_y"])
            objs += seg.get("objects") or []
    if not all_scenes:
        return None
    all_scenes.sort(key=lambda s: float(s.get("t", 0)))
    # 2) Un appel de SYNTHÈSE (2 images clefs) -> type de vidéo + ouverture + ambiance
    key_frames = [frames[0]] + ([frames[len(frames) // 2]] if len(frames) > 1 else [])
    scenes_txt = "; ".join(f"t={float(s.get('t',0)):.0f}s {s.get('action','')}"
                           f"(int {s.get('interest','?')})" for s in all_scenes[:20])
    synth = _vision_call(
        "Tu es directeur de post-production. Voici le résumé des scènes d'une vidéo "
        f"de {duration:.0f}s : {scenes_txt}\n"
        f"Transcription: {transcript_text[:400] or '(aucune parole — vidéo sans voix off)'}\n"
        "En regardant aussi ces 2 images clefs, classe la vidéo. Réponds UNIQUEMENT ce JSON:\n"
        "{\"video_type\": \"talk_facecam|vlog|horror|luxury_aesthetic|energetic|product|story|other\", "
        "// le STYLE de montage adapté\n"
        " \"opening_captivating\": bool,  // les 1res s accrochent-elles ? (visage figé = non)\n"
        " \"opening_note\": \"pourquoi (court)\",\n"
        " \"mood\": \"ambiance en 1-2 mots\",\n"
        " \"has_person\": bool,  // une personne est-elle clairement filmée ?\n"
        " \"best_moments\": [secondes],  // 2-5 instants les PLUS forts (à mettre en valeur)\n"
        " \"summary\": \"de quoi parle la vidéo, 1 phrase\"}",
        key_frames)
    result = {
        "scenes": all_scenes,
        "face_y": max(set(faces), key=faces.count) if faces else "none",
        "objects": list(dict.fromkeys(objs))[:12],
        "frames_analyzed": len(frames),
    }
    if synth:
        result.update({k: synth[k] for k in
                       ("video_type", "opening_captivating", "opening_note", "mood",
                        "has_person", "best_moments", "summary") if k in synth})
    return result


def groq_plan(facts, transcript_text, context, vision=None):
    """Demande au LLM le plan d'amélioration adapté à CE créateur. Fallback: règles."""
    fallback = {
        "subtitles": bool(transcript_text and len(transcript_text.split()) >= 8),
        "subtitle_style": "karaoke",
        "cut_silences": True,
        "reframe": not facts["vertical"],
        "hook_text": "",
        "music_mood": "" if transcript_text else "chill",
        "keywords": [],
        "sfx": [],
        "emojis": [],
        "brands": [],
        "sub_position": "dynamic",
        "sub_style": "group",
        "sub_style_id": 0,
        "highlight": "yellow",
        "broll_keywords": [],
        "transition": "",
        "color_grade": "",
        "bg_text": "",
        "objects": [],
    }
    if not GROQ_KEY:
        return fallback
    niche = str(context.get("niche", "") or "")
    feedback = str(context.get("feedback", "") or "")
    vis_txt = ""
    if vision:
        sc = "; ".join(f"t={s.get('t', 0)}s {s.get('action', '')}" + (" (mouvement)" if s.get("motion") else "")
                       for s in (vision.get("scenes") or [])[:12])
        vis_txt = ("Analyse VISUELLE de TOUTE la vidéo (" + str(vision.get("frames_analyzed", "?")) + " images) :\n"
                   f"- Type détecté: {vision.get('video_type', '?')} · ambiance: {vision.get('mood', '?')} · "
                   f"personne filmée: {'oui' if vision.get('has_person') else 'non'}.\n"
                   f"- Résumé: {vision.get('summary', 'n/a')}\n"
                   f"- Ouverture captivante: {'oui' if vision.get('opening_captivating') else 'non'} "
                   f"({vision.get('opening_note', '')}).\n"
                   f"- Scènes: {sc or 'n/a'}\n"
                   f"- Objets visibles: {', '.join((vision.get('objects') or [])[:10]) or 'n/a'}\n"
                   "Adapte TOUTES tes décisions (style de sous-titres, étalonnage, transitions, hook, "
                   "musique) à CE type de vidéo et à CETTE ambiance.\n")
    prompt = (
        vis_txt +
        "Tu améliores une vidéo courte pour un créateur. Décide ce qui est UTILE — pas tout systématiquement.\n"
        f"Faits: durée {facts['duration']:.0f}s, format {'vertical' if facts['vertical'] else 'horizontal'}, "
        f"parole: {'oui' if transcript_text else 'non'}.\n"
        f"Niche du créateur: {niche or 'inconnue'}. Retours du scan Skillora: {feedback or 'aucun'}.\n"
        f"Transcription (début): {transcript_text[:900] or '(aucune)'}\n\n"
        "Réponds UNIQUEMENT ce JSON:\n"
        "{\"subtitles\": bool,  // sous-titres seulement s'il y a de la parole utile\n"
        " \"cut_silences\": bool,\n"
        " \"hook_text\": \"accroche ultra courte (<=42 caractères). S'il y a de la parole, langue de la transcription. S'il N'Y A PAS de parole (vidéo muette/esthétique), DÉDUIS une accroche de ce que l'IA a VU (résumé/scènes) — ex: 'POV: coucher de soleil à Bali', 'Le café parfait en 30s'. Vide seulement si vraiment rien à dire\",\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic — choisis presque toujours une ambiance adaptée au contenu (fond musical discret sous la voix) ; vide UNIQUEMENT si la vidéo contient déjà de la musique\",\n"
        " \"keywords\": [\"3-6 mots EXACTS de la transcription à mettre en avant (prix, chiffres, mots forts : '0€', 'gratuit', 'secret'…) — copie-les tels quels\"],\n"
        " \"sfx\": [{\"word\": \"mot EXACT de la transcription\", \"sound\": \"typing|click|pop|whoosh|cash|ding|impact|explosion|magic|glitch|camera|beep|scratch|applause|fail|scream|heartbeat|riser|airhorn|boom\"}],  // 3-7 bruitages qui renforcent le SENS de la vidéo (monteur pro) : taper->typing, cliquer->click, argent/prix->cash, bonne réponse/chiffre->ding, punchline/choc->impact, révélation->magic, bug/tech->glitch, photo->camera, gros mot censuré->beep, échec drôle->fail, applaudir/gagner->applause, montée de tension->riser, transition->whoosh\n"
        " \"emojis\": [{\"word\": \"mot EXACT de la transcription\", \"emoji\": \"un seul émoji\"}],  // 3-6 émojis : TOUT ce qui s'illustre (téléphone->📱, courir->🏃, rire->😂, sport->🏋️, champion->🏆, argent->💰, feu->🔥, idée->💡)\n"
        " \"brands\": [{\"word\": \"mot EXACT\", \"slug\": \"slug simpleicons en minuscules\"}],  // 0-2 logos de marques/apps CITÉES dans la parole (netflix, tiktok, instagram, youtube, spotify, amazon, temu, shein, whatsapp…)\n"
        " \"sub_position\": \"dynamic|bottom|middle\",  // dynamic par défaut ; bottom si des éléments importants occupent le centre de l'image ; middle pour les vidéos très rythmées\n"
        " \"sub_style\": \"group|word\",  // group = 3 mots à la fois (défaut) ; word = mot par mot, pour les vidéos punchy et rapides\n"
        " \"sub_style_id\": 0,  // style visuel des sous-titres selon le TYPE de vidéo : 0=signature (défaut sûr) ; 2=bleu Hormozi (business/motivation) ; 3=cartoon (fun/vlog) ; 4=script néon (lifestyle/mode) ; 5=vert fluo (tech/gadgets) ; 6=ombre floue (docu/voyage) ; 7=rétro ombre jaune (créatif) ; 8=machine à écrire (mystère/code) ; 9=badge boîte (fond chargé) ; 10=dégradé or (luxe/flex) ; 11=sticker bulle (memes/humour) ; 12=karaoké rempli (podcast/monologue) ; 15=glitch (gaming/IA) ; 16=contour évidé (sport/musique) ; 17=ghost (dramatique) ; 18=serif cinéma (histoire/documentaire haut de gamme) ; 20=néon pulsé (edits musicaux) ; 21=horreur rouge empilé (horreur/creepy/mystère/caméra de surveillance/faits sombres — mots rouges qui s'accumulent à l'écran)\n"
        " \"highlight\": \"yellow|green|red|cyan\",  // couleur des mots forts, adaptée à l'ambiance\n"
        " \"broll_keywords\": [\"2-3 mots-clés ANGLAIS, OBLIGATOIRES dès que la parole mentionne un objet, un lieu, une activité ou un produit (ex: 'online shopping', 'gym workout') — vide UNIQUEMENT si la personne ne parle que d'elle-même face caméra\"],\n"
        " \"transition\": \"film_fade_dissolve|whip_pan_right|soft_swipe_blur|zoom_in_motion_blur|scale_up_reveal|white_flash_glare|chromatic_flash_burst|burn_out_edge\",  // transition de monteur pour insérer les plans d'illustration, adaptée au TON de la vidéo : fondu=lifestyle/docu/émotion ; whip pan=énergique/vlog/humour ; balayage doux=mode/beauté ; zoom flou=tech/gaming/punchy ; scale up=luxe/cinématique ; flash blanc=révélation/produit/photo ; flash chromatique=gaming/glitch/IA ; noir=dramatique/tension\n"
        " \"color_grade\": \"|dark_moody|warm_luxury|cold_cinematic|vibrant_pop|bw_horror|vintage_warm\",  // étalonnage couleur — VIDE (aucun) par défaut ! Choisis-en un UNIQUEMENT si le ton s'y prête vraiment : dark_moody=motivation sombre/gym ; warm_luxury=luxe/lifestyle doré ; cold_cinematic=tech/business froid ; vibrant_pop=fun/vlog coloré ; bw_horror=horreur/creepy (noir et blanc + grain) ; vintage_warm=nostalgie/rétro\n"
        " \"bg_text\": \"texte TRÈS court (<=16 caractères, ex 'ME AT 7:00', '0€ DE PUB') affiché en GÉANT derrière la personne au début (effet 3D pro) — UNIQUEMENT si une personne est clairement visible en pied ou buste face caméra, sinon vide\",\n"
        " \"objects\": [{\"word\": \"mot EXACT de la transcription\", \"emoji\": \"un émoji OBJET\"}]}  // 0-2 GROS objets animés qui traversent l'écran (voiture 🚗, téléphone 📱, produit 📦…) quand la parole cite un objet IMPORTANT — différent des petits émojis de sous-titres"
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
        for k in ("subtitles", "cut_silences", "hook_text", "music_mood", "keywords", "sfx",
                  "emojis", "brands", "sub_position", "sub_style", "sub_style_id", "highlight",
                  "broll_keywords", "transition", "color_grade", "bg_text", "objects"):
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


YELLOW = "&H0000D4FF&"   # jaune vif (BGR)
GREEN = "&H0084DC3D&"    # vert Skillora (BGR)
WHITE = "&H00FFFFFF&"
BLACK = "&H00000000&"
HI_COLORS = {"yellow": "&H0000D4FF&", "green": "&H0084DC3D&",
             "red": "&H004040FF&", "cyan": "&H00FFD400&"}

# ── Catalogue de styles de sous-titres (l'IA choisit selon le type de vidéo) ──
# kar : 'switch' = le mot change de couleur en étant prononcé ; 'fill' = remplissage
# progressif (\kf) ; None = mot fort coloré. fx : animation d'apparition.
SUB_STYLES = {
    0:  dict(name="Signature Skillora", font="Anton", size=124, kar=None, hi="dyn",
             prim=WHITE, sec=WHITE, out=BLACK, outw=10, shad=3, bs=1, fx="pop", chunk=3, upper=True),
    1:  dict(name="Par défaut", font="DejaVu Sans", size=92, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=4, shad=1, bs=1, fx=None, chunk=3, upper=False),
    2:  dict(name="Hormozi bleu", font="Anton", size=128, kar="switch", hi=None,
             prim="&H00FEF200&", sec=WHITE, out=BLACK, outw=11, shad=3, bs=1, fx=None, chunk=3, upper=True),
    3:  dict(name="Cartoon jaune", font="Luckiest Guy", size=118, kar=None, hi="yellow",
             prim=WHITE, sec=WHITE, out=BLACK, outw=9, shad=2, bs=1, fx="bounce", chunk=3, upper=True),
    4:  dict(name="Script néon", font="Pacifico", size=104, kar=None, hi=None, italic=True,
             prim="&H0060F2FE&", sec=WHITE, out="&H0030D5FF&", outw=3, shad=0, bs=1, blur=6, fx="pop", chunk=3, upper=False),
    5:  dict(name="Tech vert fluo", font="Orbitron", size=92, kar=None, hi="green",
             prim=WHITE, sec=WHITE, out="&H0000FF6A&", outw=2, shad=0, bs=1, fx=None, chunk=3, upper=True),
    6:  dict(name="Docu ombre floue", font="Anton", size=112, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=5, shad=7, bs=1, blur=9, fx=None, chunk=4, upper=True),
    7:  dict(name="Rétro ombre jaune", font="Anton", size=118, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=4, shad=9, shadc="&H0000D4FF&", bs=1, fx="pop", chunk=3, upper=True),
    8:  dict(name="Typewriter", font="Courier Prime", size=84, kar=None, hi=None, bold=True,
             prim=WHITE, sec=WHITE, out=BLACK, outw=4, shad=1, bs=1, fx="typewriter", chunk=3, upper=False),
    9:  dict(name="Badge boîte", font="Anton", size=104, kar=None, hi="yellow",
             prim=WHITE, sec=WHITE, out="&H50000000&", outw=14, shad=0, bs=3, fx=None, chunk=3, upper=True),
    10: dict(name="Dégradé or", font="Anton", size=128, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=8, shad=3, bs=1, fx="gradient", chunk=2, upper=True),
    11: dict(name="Sticker bulle", font="Luckiest Guy", size=120, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=16, shad=0, bs=1, fx="sticker", chunk=2, upper=True),
    12: dict(name="Karaoké fill", font="Anton", size=120, kar="fill", hi=None,
             prim="&H0000D4FF&", sec="&H60FFFFFF&", out=BLACK, outw=9, shad=2, bs=1, fx=None, chunk=4, upper=True),
    15: dict(name="Glitch gaming", font="Orbitron", size=96, kar=None, hi="cyan", bold=True,
             prim=WHITE, sec=WHITE, out=BLACK, outw=3, shad=0, bs=1, fx="glitch", chunk=2, upper=True),
    16: dict(name="Outline évidé", font="Anton", size=132, kar="switch", hi=None,
             prim="&H0000D4FF&", sec="&HFF000000&", out="&H0000FF6A&", outw=3, shad=0, bs=1, fx=None, chunk=2, upper=True),
    17: dict(name="Ghost dramatique", font="Anton", size=126, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=8, shad=2, bs=1, fx="ghost", chunk=2, upper=True),
    18: dict(name="Cinéma serif", font="Playfair Display", size=92, kar=None, hi=None,
             prim=WHITE, sec=WHITE, out=BLACK, outw=3, shad=2, bs=1, fx=None, chunk=1, upper=False),
    20: dict(name="Néon pulsé", font="Orbitron", size=104, kar=None, hi=None, bold=True,
             prim=WHITE, sec=WHITE, out="&H00FEF200&", outw=4, shad=0, bs=1, blur=4, fx="pulse", chunk=2, upper=True),
    # 21 = horreur : mots ROUGES qui s'accumulent en escalier (rendu spécial, voir build_ass)
    21: dict(name="Horreur rouge empilé", font="Anton", size=140, kar=None, hi=None,
             prim="&H001414E8&", sec=WHITE, out="&H000000A0&", outw=2, shad=0, bs=1, fx="stack", chunk=1, upper=True),
}


def _horror_stack(words, layout, seed, fit):
    """Style 21 : chaque mot apparaît et RESTE à l'écran, empilé en escalier
    (décalages gauche/droite, légères rotations), rouge + halo — puis l'écran se
    vide à la fin de la phrase. Look 'CapCut horreur' des vidéos creepy."""
    RED = "&H001414E8&"          # rouge vif (BGR)
    GLOW = "&H000000B4&"         # halo rouge sombre
    XOFF = [-150, 130, -180, 90, -110, 160]   # escalier gauche/droite
    lines = []
    # Découpe en phrases : pause > 0.8 s ou 6 mots max
    phrases, cur = [], []
    for w in words:
        if cur and (float(w["start"]) - float(cur[-1]["end"]) > 0.8 or len(cur) >= 6):
            phrases.append(cur)
            cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    base_y = 640
    if layout:
        base_y = max(340, min(1000, int(sum(layout) / len(layout)) - 320))
    for pi, ph in enumerate(phrases):
        ph_end = float(ph[-1]["end"]) + 0.30
        if pi + 1 < len(phrases):
            ph_end = min(ph_end, float(phrases[pi + 1][0]["start"]) - 0.05)
        n = len(ph)
        step = 158 if n <= 5 else 132
        for wi, w in enumerate(ph):
            raw = str(w["word"]).strip().replace("{", "").replace("}", "").strip(",.;:!?").upper()
            if not raw:
                continue
            ws = float(w["start"])
            if ph_end - ws < 0.12:
                continue
            # GROS comme les edits CapCut : les mots courts dominent l'écran
            size = 215 if len(raw) <= 4 else (175 if len(raw) <= 7 else 135)
            fz = fit(raw, size)
            x = 540 + XOFF[(wi + seed) % len(XOFF)]
            # le mot reste DANS l'écran malgré le décalage
            half = int(len(raw) * size * 0.30)
            x = max(60 + half, min(1020 - half, x))
            y = base_y + wi * step
            rot = ((seed * 7 + wi * 5 + pi * 3) % 13) - 6   # -6°..+6°
            pop = "\\fad(40,0)\\t(0,90,\\fscx112\\fscy112)\\t(90,170,\\fscx100\\fscy100)"
            # couche halo (dessous) + couche texte
            lines.append(f"Dialogue: 0,{ass_time(ws)},{ass_time(ph_end)},Sub,,0,0,0,,"
                         f"{{\\an5\\pos({x},{y})\\frz{rot}\\fs{size}{fz}\\c{RED}\\alpha&H60&\\blur16}}{raw}")
            lines.append(f"Dialogue: 1,{ass_time(ws)},{ass_time(ph_end)},Sub,,0,0,0,,"
                         f"{{\\an5\\pos({x},{y})\\frz{rot}\\fs{size}{fz}\\c{RED}\\3c{GLOW}\\blur2{pop}}}{raw}")
    return lines


def _grad_text(txt):
    """Faux dégradé : chaque lettre colorée du jaune (FFD400) vers l'orange (FF7A00)."""
    chars = [c for c in txt]
    n = max(1, len(chars) - 1)
    out = []
    for i, c in enumerate(chars):
        if c == " ":
            out.append(" ")
            continue
        r = 0xFF
        g = int(0xD4 + (0x7A - 0xD4) * i / n)
        b = 0x00
        out.append(f"{{\\c&H{b:02X}{g:02X}{r:02X}&}}{c}")
    return "".join(out)


def build_ass(words, hook_text, keywords=None, slide=None, sub_position="dynamic",
              highlight="yellow", sub_style="group", style_id=0, layout=None,
              play_w=1080, play_h=1920, seed=0):
    """Sous-titres 'montage dynamique' pilotés par le catalogue SUB_STYLES.
    Mécanique commune : position par phrase, mot fort géant (Mega), verrou
    anti-chevauchement, texte géant pendant l'effet 'côté'."""
    spec = SUB_STYLES.get(int(style_id) if str(style_id).isdigit() else 0, SUB_STYLES[0])
    kwhits = {round(k["start"], 2) for k in (keywords or [])}
    hi_mode = spec.get("hi")
    HI = HI_COLORS.get(str(highlight).lower(), YELLOW) if hi_mode == "dyn" else HI_COLORS.get(hi_mode or "", None)
    fx = spec.get("fx")
    bold = -1 if spec.get("bold", True) else 0
    italic = -1 if spec.get("italic") else 0
    shadc = spec.get("shadc", "&HB4000000&")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{spec['font']},{spec['size']},{spec['prim'].rstrip('&')},{spec['sec'].rstrip('&')},{spec['out'].rstrip('&')},{shadc.rstrip('&')},{bold},{italic},0,0,100,100,1,0,{spec['bs']},{spec['outw']},{spec['shad']},5,40,40,0,1
Style: Mega,Anton,185,{YELLOW.rstrip('&')},&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,12,4,5,40,40,0,1
Style: Hook,Anton,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,1,0,3,14,0,8,60,60,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    FX = {
        "pop": "\\fad(25,35)\\t(0,100,\\fscx115\\fscy115)\\t(100,180,\\fscx100\\fscy100)",
        "bounce": "\\fad(20,30)\\t(0,90,\\fscx118\\fscy86)\\t(90,180,\\fscx98\\fscy108)\\t(180,260,\\fscx100\\fscy100)",
        "sticker": "\\fad(15,25)\\t(0,110,\\fscx135\\fscy135)\\t(110,200,\\fscx100\\fscy100)",
        "ghost": "\\blur12\\fscx130\\fscy130\\t(0,160,\\blur0\\fscx100\\fscy100)\\fad(30,40)",
    }
    MEGAPOP = "\\fad(20,40)\\t(0,120,\\fscx130\\fscy130)\\t(120,220,\\fscx100\\fscy100)"
    base_blur = f"\\blur{spec['blur']}" if spec.get("blur") else ""
    if layout is None:
        layout = sentence_layout(words, sub_position)
    chunk = 1 if str(sub_style).lower() == "word" else int(spec.get("chunk", 3))
    lines = []
    if hook_text:
        safe = str(hook_text).upper().replace("{", "").replace("}", "").replace("\n", " ")
        lines.append(f"Dialogue: 2,0:00:00.15,0:00:03.00,Hook,,0,0,0,,{{\\fad(140,200)}}{safe}")

    def fit_early(raw, size):
        est = max(1, len(raw)) * size * 0.55
        return "" if est <= 980 else f"\\fs{max(44, int(size * 980 / est))}"

    if spec.get("fx") == "stack":
        # Style 21 : rendu spécial 'mots empilés' — remplace toute la mécanique de groupes
        lines += _horror_stack(words, layout, seed, fit_early)
        return head + "\n".join(lines) + "\n"

    # Découpe en groupes ; la position vient de `layout` (partagé avec les émojis).
    prev_end = None
    group, gfirst = [], 0
    cues = []  # [start, end, mega, y, txt_stylé, txt_brut]

    def wtxt(it):
        w = str(it["word"]).strip().replace("{", "").replace("}", "").strip(",.;:!?")
        return w.upper() if spec.get("upper") else w

    def fit(raw, size):
        """Anti-débordement : réduit la taille si le texte est trop large pour l'écran."""
        est = max(1, len(raw)) * size * 0.55
        return "" if est <= 980 else f"\\fs{max(44, int(size * 980 / est))}"

    def flush():
        nonlocal group
        if not group:
            return
        g = group
        group = []
        start, end = float(g[0]["start"]), float(g[-1]["end"])
        if end - start < 0.35:
            end = start + 0.35
        solo_kw = len(g) == 1 and round(float(g[0]["start"]), 2) in kwhits
        if spec.get("kar") in ("switch", "fill") and not solo_kw:
            tag = "\\kf" if spec["kar"] == "fill" else "\\k"
            parts = []
            for it in g:
                k = max(1, int(round((float(it["end"]) - float(it["start"])) * 100)))
                parts.append(f"{{{tag}{k}}}{wtxt(it)}")
            txt = " ".join(parts)
        else:
            parts = []
            for it in g:
                word = wtxt(it)
                if HI and round(float(it["start"]), 2) in kwhits and not solo_kw:
                    parts.append(f"{{\\c{HI}}}{word}{{\\c{spec['prim']}}}")
                else:
                    parts.append(word)
            txt = " ".join(parts)
        raw = " ".join(wtxt(it) for it in g)
        if slide and slide[0] <= start <= slide[1]:
            return  # pendant l'effet 'côté', pas de sous-titre normal
        y = layout[gfirst] if gfirst < len(layout) else 1430
        cues.append([start, end, solo_kw, y, txt, raw])

    for i, w in enumerate(words):
        ws = float(w["start"])
        if prev_end is not None and ws - prev_end > 0.8:
            flush()
        is_kw = round(ws, 2) in kwhits
        if is_kw and group:
            flush()
        if not group:
            gfirst = i
        group.append(w)
        if is_kw or len(group) == chunk:
            flush()
        prev_end = float(w["end"])
    flush()

    for i in range(len(cues) - 1):  # verrou anti-chevauchement (la non-superposition PRIME)
        cap = cues[i + 1][0] - 0.02
        want = max(cues[i][1], cues[i][0] + 0.15)
        cues[i][1] = min(want, cap) if cap > cues[i][0] + 0.05 else max(cues[i][0] + 0.03, cap)

    for (start, end, mega, y, txt, raw) in cues:
        if mega:
            lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Mega,,0,0,0,,"
                         f"{{\\an5\\pos(540,960){fit(raw, 185)}{MEGAPOP}}}{txt if HI else raw}")
            continue
        pos = f"\\an5\\pos(540,{y}){fit(raw, spec['size'])}"
        if fx == "typewriter":
            # lettre par lettre avec curseur (style machine à écrire)
            steps = min(len(raw), 36)
            if steps <= 1:
                lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{{{pos}{base_blur}}}{raw}")
                continue
            per = max(0.03, (end - start) * 0.6 / steps)
            for si in range(1, steps + 1):
                a = start + (si - 1) * per
                b = start + si * per if si < steps else end
                shown = raw[:int(len(raw) * si / steps)]
                cur = "▌" if si < steps else ""
                lines.append(f"Dialogue: 1,{ass_time(a)},{ass_time(b)},Sub,,0,0,0,,{{{pos}{base_blur}}}{shown}{cur}")
            continue
        if fx == "gradient":
            body = _grad_text(raw)
            lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,"
                         f"{{{pos}{FX['pop']}{base_blur}}}{body}")
            continue
        if fx == "glitch":
            # aberration chromatique : couches rouge et cyan décalées sous le texte
            fz = fit(raw, spec['size'])
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,"
                         f"{{\\an5\\pos(536,{y - 3}){fz}\\c&H0000F2&\\alpha&H78&\\blur1}}{raw}")
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,"
                         f"{{\\an5\\pos(544,{y + 3}){fz}\\c&HFEF200&\\alpha&H78&\\blur1}}{raw}")
            lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{{{pos}}}{txt}")
            continue
        if fx == "pulse":
            dur_ms = max(200, int((end - start) * 1000))
            h = dur_ms // 2
            anim = f"\\blur2\\t(0,{h},\\blur7)\\t({h},{dur_ms},\\blur2)"
            lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{{{pos}{anim}}}{txt}")
            continue
        anim = FX.get(fx, "")
        lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{{{pos}{anim}{base_blur}}}{txt}")

    # Texte géant pendant l'effet 'la vidéo se pousse sur le côté'
    if slide:
        t1, t2, text = slide
        safe = str(text).upper().replace("{", "").replace("}", "")
        # le sujet glisse à GAUCHE -> texte dans l'espace libéré à DROITE
        lines.append(f"Dialogue: 3,{ass_time(t1 + 0.10)},{ass_time(t2)},Mega,,0,0,0,,"
                     f"{{\\an5\\pos(800,960)\\fs140{MEGAPOP}}}{safe}")
    return head + "\n".join(lines) + "\n"


# Étalonnages (color grading) — appliqués SEULEMENT quand l'IA juge que le ton
# de la vidéo s'y prête (jamais systématique). Sous la vidéo, avant les sous-titres.
GRADES = {
    "dark_moody":     "eq=contrast=1.10:brightness=-0.03:saturation=0.88,"
                      "colorbalance=bs=.06:bm=.03,vignette=PI/5",
    "warm_luxury":    "eq=contrast=1.06:saturation=1.05,"
                      "colorbalance=rs=.05:rm=.04:bs=-.04,vignette=PI/6",
    "cold_cinematic": "eq=contrast=1.10:saturation=0.92,colorbalance=bs=.08:bm=.05:rs=-.03",
    "vibrant_pop":    "eq=contrast=1.09:saturation=1.30:brightness=0.01",
    "bw_horror":      "hue=s=0,eq=contrast=1.28:brightness=-0.04,"
                      "vignette=PI/4.6,noise=alls=7:allf=t",
    "vintage_warm":   "curves=preset=vintage,eq=saturation=1.02,noise=alls=5:allf=t",
}


def burn_subs(src, dst, ass_path, grade=""):
    """Incruste les sous-titres + passe 'clarté' gratuite : léger débruitage,
    netteté et couleurs plus vives. `grade` = étalonnage optionnel (GRADES),
    appliqué SOUS les sous-titres (le texte garde ses vraies couleurs)."""
    safe = ass_path.replace("\\", "/").replace(":", "\\:")
    g = GRADES.get(str(grade or "").lower())
    pre = (g + ",") if g else ""
    run(["ffmpeg", "-y", "-i", src,
         "-vf", f"{pre}ass='{safe}',hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.5,eq=contrast=1.04:saturation=1.13",
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


# --- Transitions premium (catalogue style CapCut -> 9 familles réalisables en FFmpeg pur).
# Chaque nom du catalogue est rattaché à la famille la plus proche visuellement.
TRANSITION_FAMILIES = ("cut", "fade", "whip", "swipe", "zoom_blur", "scale_reveal",
                       "white_flash", "chroma_flash", "dip_black")
TRANSITION_NEAR = {
    "cut_clean_direct": "cut", "mosaic_grid_snap": "cut",
    "film_fade_dissolve": "fade", "smoke_vapor_dissolve": "fade",
    "cross_fade_blur": "fade", "echo_motion_ghost": "fade",
    "whip_pan_right": "whip", "cube_gallery_rotation": "whip",
    "skewed_panels_slide": "whip", "multi_frame_slide": "whip",
    "card_deck_flip": "whip", "triple_slide_panel": "whip",
    "soft_swipe_blur": "swipe", "split_screen_slide": "swipe",
    "shadow_wipe_ambient": "swipe", "directional_shadow_swipe": "swipe",
    "radial_radar_wipe": "swipe",
    "zoom_in_motion_blur": "zoom_blur", "warp_speed_distortion": "zoom_blur",
    "punch_in_instant": "zoom_blur", "snap_zoom_bounce": "zoom_blur",
    "snap_back_bounce": "zoom_blur",
    "scale_up_reveal": "scale_reveal",
    "white_flash_glare": "white_flash", "light_leak_flare_v3": "white_flash",
    "light_leak_soft": "white_flash",
    "chromatic_flash_burst": "chroma_flash",
    "burn_out_edge": "dip_black",
}
# Le son de CHAQUE transition (réflexe de monteur : une transition s'entend).
TR_SOUND = {"whip": "whoosh", "swipe": "whoosh", "fade": "whoosh", "zoom_blur": "whoosh",
            "scale_reveal": "magic", "white_flash": "camera",
            "chroma_flash": "glitch", "dip_black": "impact"}
BROLL_SEG = 1.3  # durée d'un plan d'illustration incrusté


def resolve_transition(name, seed=0):
    """Nom du catalogue (ou famille) -> famille implémentée. Si l'IA n'a rien
    choisi, on tourne dans les familles premium selon le job (anti-figé)."""
    n = str(name or "").strip().lower()
    if n in TRANSITION_FAMILIES:
        return n
    if n in TRANSITION_NEAR:
        return TRANSITION_NEAR[n]
    premium = ("fade", "whip", "zoom_blur", "white_flash", "swipe", "scale_reveal")
    return premium[seed % len(premium)]


def overlay_broll(src, dst, brolls, duration, transition="fade", seed=0):
    """Incruste chaque b-roll en plein cadre ~1,3 s, réparti dans la vidéo
    (jamais dans les 3 premières secondes : le hook doit rester le créateur),
    avec une VRAIE transition de monteur à l'entrée ET à la sortie du plan
    (fondu, balayage, zoom fluide, flash, noir…) au lieu d'une coupure sèche.
    Retourne les instants d'entrée des plans (pour y caler les sons)."""
    if not brolls:
        return []
    seg = BROLL_SEG
    fam = transition if transition in TRANSITION_FAMILIES else "fade"
    W, H = 1080, 1920
    slots = []
    n = len(brolls)
    for i in range(n):
        t = 3.0 + (duration - 5.0) * (i + 1) / (n + 1)
        if t + seg < duration - 1.0:
            slots.append(round(t, 3))
    if not slots:
        return []
    inputs = ["-i", src]
    for b in brolls[:len(slots)]:
        inputs += ["-i", b]
    fc, last = [], "[0:v]"
    flashes = []        # (couleur, instant, opacité) — flash blanc / passage au noir
    shift_windows = []  # fenêtres du décalage chromatique (chroma_flash)
    for i, t in enumerate(slots[:len(brolls)]):
        t2 = t + seg
        pre = (f"[{i+1}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H}")
        if fam == "zoom_blur":
            # Le plan arrive en zoom arrière ultra rapide (punch) + flou de mouvement
            pre += (f",fps=30,zoompan=z='if(lte(in,8),1.55-0.55*in/8,1)'"
                    f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30"
                    f",setpts=PTS-STARTPTS,gblur=sigma=7:enable='lte(t,0.16)'"
                    f",setpts=PTS+{t:.3f}/TB")
        elif fam == "scale_reveal":
            # Révélation cinématique : le plan pousse lentement + fondu doux
            frames = max(2, int(seg * 30))
            pre += (f",fps=30,zoompan=z='1+0.12*in/{frames}'"
                    f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30"
                    f",format=yuva420p,setpts=PTS-STARTPTS+{t:.3f}/TB"
                    f",fade=t=in:st={t:.3f}:d=0.22:alpha=1"
                    f",fade=t=out:st={t2 - 0.22:.3f}:d=0.22:alpha=1")
        elif fam == "fade":
            pre += (f",format=yuva420p,setpts=PTS-STARTPTS+{t:.3f}/TB"
                    f",fade=t=in:st={t:.3f}:d=0.25:alpha=1"
                    f",fade=t=out:st={t2 - 0.25:.3f}:d=0.25:alpha=1")
        else:
            pre += f",setpts=PTS-STARTPTS+{t:.3f}/TB"
        fc.append(pre + f"[b{i}]")
        x_expr = "0"
        if fam in ("whip", "swipe"):
            # Le plan GLISSE à l'écran (rapide=whip, doux=swipe), entre d'un côté
            # et ressort de l'autre — côté alterné selon le job (anti-figé)
            d_in = 0.22 if fam == "whip" else 0.4
            off = W if (seed + i) % 2 == 0 else -W
            x_expr = (f"({off})*pow(1-min((t-{t:.3f})/{d_in:.2f}\\,1)\\,2)"
                      f"-({off})*pow(max(0\\,(t-{t2 - d_in:.3f})/{d_in:.2f})\\,2)")
        nxt = f"[v{i}]"
        fc.append(f"{last}[b{i}]overlay=x='{x_expr}':y=0:"
                  f"enable='between(t,{t:.3f},{t2:.3f})':eof_action=pass{nxt}")
        last = nxt
        if fam == "white_flash":
            flashes += [("white", t, 0.95), ("white", t2, 0.95)]
        elif fam == "dip_black":
            flashes += [("black", t, 1.0), ("black", t2, 1.0)]
        elif fam == "chroma_flash":
            flashes += [("white", t, 0.55), ("white", t2, 0.55)]
            shift_windows += [t, t2]
    # Flashs aux frontières (le flash CACHE la coupure : c'est ça le côté premium)
    base_idx = len(brolls[:len(slots)]) + 1
    for j, (col, tb, amp) in enumerate(flashes):
        d_in, d_out = (0.07, 0.16) if col == "white" else (0.12, 0.14)
        start = max(0.0, tb - d_in)
        dur_f = d_in + d_out + 0.05
        inputs += ["-f", "lavfi", "-i", f"color={col}:s={W}x{H}:r=30:d={dur_f:.2f}"]
        fc.append(f"[{base_idx + j}:v]format=yuva420p,colorchannelmixer=aa={amp:.2f},"
                  f"fade=t=in:d={d_in:.2f}:alpha=1,"
                  f"fade=t=out:st={d_in:.2f}:d={d_out:.2f}:alpha=1,"
                  f"setpts=PTS+{start:.3f}/TB[fl{j}]")
        nxt = f"[vf{j}]"
        fc.append(f"{last}[fl{j}]overlay=0:0:"
                  f"enable='between(t,{start:.3f},{start + dur_f:.3f})':eof_action=pass{nxt}")
        last = nxt
    if shift_windows:
        en = "+".join(f"between(t,{tb - 0.06:.3f},{tb + 0.12:.3f})" for tb in shift_windows)
        fc.append(f"{last}rgbashift=rh=18:bh=-18:enable='{en}'[vsh]")
        last = "[vsh]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", last, "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-c:a", "copy", dst])
    return slots[:len(brolls)]


# ---------------------------------------------------------------- musique (bucket)
def pick_music(mood):
    """Choisit une piste du bucket musique d'après le NOM du fichier :
    'hype-01.mp3' -> ambiance hype. Aucun manifest nécessaire. None si vide."""
    if not mood:
        return None
    try:
        st, raw = http("POST", f"{SB_URL}/storage/v1/object/list/{MUSIC_BUCKET}",
                       sb_headers(), {"prefix": "", "limit": 300}, timeout=30)
        items = json.loads(raw)
        names = [it.get("name", "") for it in items
                 if it.get("name", "").lower().startswith(str(mood).lower())
                 and it.get("name", "").lower().endswith((".mp3", ".m4a", ".wav", ".ogg"))]
        if not names:
            return None
        name = names[int(time.time()) % len(names)]
        out = tempfile.mktemp(suffix=os.path.splitext(name)[1] or ".mp3")
        urllib.request.urlretrieve(f"{SB_URL}/storage/v1/object/public/{MUSIC_BUCKET}/{urllib.parse.quote(name)}", out)
        return out
    except Exception as e:
        print("pick_music:", e, file=sys.stderr)
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
        if facts.get("improved"):
            raise RuntimeError("Cette vidéo a DÉJÀ été améliorée par Skillora. Renvoie la vidéo originale "
                               "(sans les sous-titres incrustés) — l'améliorer deux fois créerait des doublons.")
        # Graine propre à ce job : deux vidéos identiques ne sortent pas identiques
        # (ordre des zooms, position de départ des sous-titres…)
        seed = int(str(job["id"]).replace("-", "")[:8], 16) & 0xFFFF
        steps.done("dl", f"{facts['duration']:.0f}s · {facts['width']}x{facts['height']}")

        steps.start("analyze", "Analyse : le worker regarde et écoute ta vidéo…")
        d = facts["duration"]
        silences = detect_silences(src) if facts["has_audio"] else []
        # Analyse de TOUTE la vidéo (gratuit, image par image) : changements de plan,
        # énergie sonore, temps forts du rythme -> base d'un vrai montage.
        cuts = scene_cuts(src)
        beats = detect_beats(src, d) if facts["has_audio"] else []
        first_tr = None
        if facts["has_audio"]:
            mp3 = os.path.join(work, "a.mp3")
            extract_audio_mp3(src, mp3)
            first_tr = groq_transcribe(mp3)
        tr_text = (first_tr or {}).get("text", "").strip() if first_tr else ""
        # Les YEUX : vision sur TOUTE la vidéo (plusieurs lots de 5 images).
        vision = None
        try:
            vision = groq_vision_full(src, work, d, tr_text, scenecuts=cuts)
        except Exception as e:
            print("vision:", e, file=sys.stderr)
        plan = groq_plan(facts, tr_text, context, vision)
        update_job(job["id"], {"plan": plan})
        det = "parole détectée" if tr_text else "pas de parole détectée"
        if vision:
            det += (f" · {vision.get('frames_analyzed', 0)} images analysées"
                    f" · type: {vision.get('video_type', '?')}"
                    f" · {len(cuts)} plan(s)")
        steps.done("analyze", det)

        cur = src
        tr1_words = (first_tr or {}).get("words") or []

        # 1. Coupe des silences ET des "euh/hum" (uniquement s'il y a de la parole)
        if plan.get("cut_silences") and tr_text and (silences or tr1_words):
            steps.start("cut", "Coupe des temps morts et des « euh »…")
            out = os.path.join(work, "cut.mp4")
            # Garde-fou : "captivante" ne suffit pas — il faut du VRAI mouvement tôt
            # ou une parole qui démarre vite. Un visage figé n'est pas captivant.
            keep = (vision or {}).get("opening_captivating")
            if keep:
                early_motion = any(s.get("motion") and float(s.get("t", 9)) <= 1.6
                                   for s in (vision or {}).get("scenes") or [])
                early_speech = bool(tr1_words) and float(tr1_words[0].get("start", 9)) < 1.0
                if not (early_motion or early_speech):
                    keep = False
            extra_cuts = filler_spans(tr1_words) + head_tail_spans(
                tr1_words, facts["duration"], silences, keep_opening=keep)
            if cut_spans(cur, out, silences, extra_cuts, facts["duration"]):
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

        # 3. B-roll inséré avec une transition premium (choisie par l'IA selon le ton)
        brolls, broll_cuts = [], []
        br_fam = resolve_transition(plan.get("transition"), seed)
        if plan.get("broll_keywords"):
            steps.start("broll", "Recherche de plans d'illustration…")
            # 1 seul plan d'illustration max : un effet à la fois à l'écran
            brolls = pexels_broll(plan["broll_keywords"], want=1)
            if brolls:
                out = os.path.join(work, "broll.mp4")
                broll_cuts = overlay_broll(cur, out, brolls, ffprobe_facts(cur)["duration"],
                                           transition=br_fam, seed=seed)
                if broll_cuts:
                    cur = out
                steps.done("broll", f"{len(broll_cuts)} plan(s) inséré(s) (transition {br_fam})")
            else:
                steps.done("broll", "aucun plan adapté trouvé")
        else:
            steps.skip("broll", "Plans d'illustration", "pas utile pour cette vidéo")

        # 3b. Texte 3D DERRIÈRE la personne (détourage IA — marche sans fond vert).
        # Remplace le hook classique quand il est appliqué.
        bg_until = 1.0
        if plan.get("bg_text") and str((vision or {}).get("face_y") or ""):
            dur_now = ffprobe_facts(cur)["duration"]
            if dur_now > 4.5:
                steps.start("depth", "Texte 3D derrière le sujet…")
                outd = os.path.join(work, "depth.mp4")
                if depth_text(cur, outd, str(plan["bg_text"]), work,
                              face_y=str(vision.get("face_y")), duration=dur_now):
                    cur = outd
                    bg_until = 3.6  # pas d'effet 'côté' pendant le texte 3D
                    plan["hook_text"] = ""
                    steps.done("depth", f"« {str(plan['bg_text']).upper()} »")
                else:
                    steps.done("depth", "non applicable (personne pas assez visible)")

        # 4. Transcription finale (timings exacts sur la vidéo coupée)
        words = []
        if plan.get("subtitles") and facts["has_audio"]:
            mp3b = os.path.join(work, "b.mp3")
            extract_audio_mp3(cur, mp3b)
            tr2 = groq_transcribe(mp3b)
            words = (tr2 or {}).get("words") or []

        # 5. Montage dynamique : mots forts, effet "la vidéo se pousse sur le côté",
        #    zooms avant/arrière + whoosh + pops. Timeline inchangée -> timings des
        #    sous-titres valides ; on zoome AVANT d'incruster les sous-titres.
        kws = keyword_times(words, plan.get("keywords"))
        # Position des sous-titres : évite le VISAGE repéré par l'analyse visuelle
        face = str((vision or {}).get("face_y") or "").lower()
        bands = [1430, 1180] if face in ("middle", "top") else ([960, 620] if face == "bottom" else None)
        layout = sentence_layout(words, str(plan.get("sub_position") or "dynamic"), seed, bands=bands)
        slide = None
        music_fg = False  # musique au premier plan (mode sans voix)
        if len(words) >= 6 and ffprobe_facts(cur)["duration"] > 6:
            steps.start("fx", "Montage dynamique (zooms, effets, sons)…")
            try:
                dur_cur = ffprobe_facts(cur)["duration"]
                # Effet "côté" sur le 1er mot fort court (ex: 0€), hors début/fin
                # et JAMAIS pendant un b-roll (un seul effet à la fois à l'écran)
                cand = [k for k in kws if len(k["text"]) <= 7 and bg_until < k["start"] < dur_cur - 3.0
                        and not any(bc - 1.8 < k["start"] < bc + 1.8 for bc in broll_cuts)]
                if cand:
                    t1 = max(0.5, cand[0]["start"] - 0.15)
                    outs = os.path.join(work, "slide.mp4")
                    t2 = slide_aside(cur, outs, t1)
                    cur = outs
                    slide = (t1, t2, cand[0]["text"])
                out = os.path.join(work, "fx.mp4")
                emo = emoji_events(words, plan.get("emojis"), work, layout)
                # GROS objets animés : logos officiels des marques citées + objets emoji.
                # Ils traversent l'écran (glissent, s'arrêtent, repartent).
                obj_span = OBJ_IN + OBJ_HOLD + OBJ_OUT
                objs = brand_events(words, plan.get("brands"), work) + \
                       object_events(words, plan.get("objects"), work)
                busy0 = ([(slide[0] - 0.3, slide[1] + 0.3)] if slide else []) + \
                        [(bc - 0.3, bc + 1.6) for bc in broll_cuts]
                objs = [o for o in objs if 1.2 < o[0] < dur_cur - obj_span - 0.4
                        and not any(a - 0.5 <= o[0] <= b + 0.5 for (a, b) in busy0)]
                sel, last_t = [], -9.0
                for (ot, op) in sorted(objs):  # espacés d'au moins 3 s
                    if ot - last_t >= 3.0:
                        sel.append((ot, op))
                        last_t = ot
                objs = sel[:3]
                # Un seul effet à la fois : pas d'émoji pendant 'côté', b-roll ou objet
                busy = busy0 + [(ot - 0.3, ot + obj_span + 0.3) for (ot, _p) in objs]
                emo = [e for e in emo if not any(a <= e[0] <= b for (a, b) in busy)]
                sfx_ev = sfx_event_times(words, plan.get("sfx"), kws)
                sfx_ev += [(t, "pop") for (t, _p, _y) in emo
                           if not any(abs(t - e[0]) < 0.4 for e in sfx_ev)]
                # whoosh à l'ENTRÉE et à la SORTIE de chaque objet animé
                for (ot, _p) in objs:
                    sfx_ev += [(ot, "whoosh"), (ot + OBJ_IN + OBJ_HOLD, "whoosh")]
                # Chaque transition de b-roll a SON bruitage (flash->appareil photo,
                # chromatique->glitch, noir->impact, balayage->whoosh, reveal->magic)
                tr_snd = TR_SOUND.get(br_fam)
                if tr_snd:
                    for bc in broll_cuts:
                        sfx_ev += [(bc, tr_snd), (bc + BROLL_SEG, tr_snd)]
                wh_extra = [slide[0], slide[1] - 0.25] if slide else []
                # Whoosh sur les scènes en mouvement repérées par la vision
                # (timestamps de la vidéo ORIGINALE : valides seulement si on n'a pas coupé)
                if vision and cur == src:
                    dur_c = ffprobe_facts(cur)["duration"]
                    wh_extra += [float(s.get("t", 0)) for s in (vision.get("scenes") or [])
                                 if s.get("motion") and 1.0 < float(s.get("t", 0)) < dur_c - 1.5][:4]
                if zoom_punch(cur, out, words, facts["has_audio"], work,
                              sfx_events=sorted(sfx_ev),
                              extra_whooshes=wh_extra or None,
                              avoid=(slide[0], slide[1]) if slide else None, seed=seed):
                    cur = out
                if objs:  # après les zooms : les objets restent stables à l'écran
                    outo = os.path.join(work, "objs.mp4")
                    if overlay_objects(cur, outo, objs, seed=seed):
                        cur = outo
                if emo:
                    oute = os.path.join(work, "emoji.mp4")
                    if overlay_emojis(cur, oute, emo):
                        cur = oute
                detail = "zooms + sons"
                if slide:
                    detail += f" + focus « {slide[2]} »"
                if kws:
                    detail += f" + {len(kws)} mot(s) fort(s)"
                if emo:
                    detail += f" + {len(emo)} émoji(s)"
                if objs:
                    detail += f" + {len(objs)} objet(s)/logo(s) animé(s)"
                steps.done("fx", detail)
            except Exception as e:
                print("fx:", e, file=sys.stderr)
                steps.done("fx", "effets non appliqués (on continue sans)")
        elif ffprobe_facts(cur)["duration"] > 4 and (cuts or beats or facts["has_audio"]):
            # ── MONTAGE SANS VOIX : le rythme vient de la MUSIQUE et de l'IMAGE ──
            # (vlog muet, edit esthétique, ambiance…). Pas de mots -> on cale les
            # zooms et les transitions sur les BEATS et les CHANGEMENTS DE PLAN.
            steps.start("fx", "Montage rythmé (beats + plans + sons)…")
            try:
                dur_cur = ffprobe_facts(cur)["duration"]
                music_fg = True
                vtype = str((vision or {}).get("video_type") or "energetic")
                # Les beats/plans ont été mesurés sur la vidéo ORIGINALE : ils ne sont
                # valides que si la timeline n'a pas changé (pas de coupe).
                timeline_intact = abs(dur_cur - d) < 0.4
                src_beats = beats if timeline_intact else []
                src_cuts = cuts if timeline_intact else []
                # Points de rythme : beats musicaux en priorité, sinon plans détectés,
                # sinon grille régulière calée sur le style de la vidéo.
                rhythm = [b for b in src_beats if 0.3 < b < dur_cur - 0.4]
                if len(rhythm) < 3:
                    rhythm = [c for c in src_cuts if 0.3 < c < dur_cur - 0.4]
                if len(rhythm) < 3:
                    every = 3.5 if vtype in ("luxury_aesthetic", "story") else 2.2
                    rhythm = [round(t, 2) for t in _frange(0.6, dur_cur - 0.6, every)]
                # Pas trop serré : un zoom toutes ~1.4 s max (sinon illisible)
                thinned, lastb = [], -9.0
                for b in rhythm:
                    if b - lastb >= 1.3:
                        thinned.append(b)
                        lastb = b
                rhythm = thinned[:40]
                # Whoosh sur chaque changement de plan + impact sur les temps forts
                best = [float(x) for x in ((vision or {}).get("best_moments") or []) if timeline_intact and 0.4 < float(x) < dur_cur - 0.4]
                sfx_ev = [(c, "whoosh") for c in src_cuts if 0.4 < c < dur_cur - 0.4][:12]
                sfx_ev += [(t, "impact") for t in best][:4]
                out = os.path.join(work, "fx.mp4")
                if zoom_punch(cur, out, [], facts["has_audio"], work,
                              sfx_events=sorted(sfx_ev), seed=seed,
                              bounds_override=rhythm):
                    cur = out
                # Gros objets/logos si des marques sont citées à l'écran (sans parole)
                objs = brand_events([{"start": (best[0] if best else 1.5)}], plan.get("brands"), work) if plan.get("brands") else []
                if objs:
                    objs = [(min(dur_cur - (OBJ_IN + OBJ_HOLD + OBJ_OUT) - 0.3, max(1.0, o[0])), o[1]) for o in objs][:1]
                    outo = os.path.join(work, "objs.mp4")
                    if overlay_objects(cur, outo, objs, seed=seed):
                        cur = outo
                steps.done("fx", f"{len(rhythm)} accents rythmés + {len(sfx_ev)} son(s) · type {vtype}")
            except Exception as e:
                print("fx-novoice:", e, file=sys.stderr)
                steps.done("fx", "montage rythmé non appliqué (on continue)")
        else:
            steps.skip("fx", "Montage dynamique", "vidéo trop courte")

        # 6. Sous-titres + hook incrustés par-dessus
        if words:
            steps.start("subs", "Sous-titres animés…")
            presubs = cur  # gardé pour le re-rendu si le contrôle qualité corrige

            def render_subs(lay, dst_name):
                ass_p = os.path.join(work, dst_name + ".ass")
                with open(ass_p, "w", encoding="utf-8") as f:
                    f.write(build_ass(words, str(plan.get("hook_text") or ""), keywords=kws, slide=slide,
                                      sub_position=str(plan.get("sub_position") or "dynamic"),
                                      highlight=str(plan.get("highlight") or "yellow"),
                                      sub_style=str(plan.get("sub_style") or "group"),
                                      style_id=plan.get("sub_style_id") or 0,
                                      layout=lay, seed=seed))
                out_p = os.path.join(work, dst_name + ".mp4")
                burn_subs(presubs, out_p, ass_p, grade=str(plan.get("color_grade") or ""))
                return out_p

            cur = render_subs(layout, "subs")
            steps.done("subs", f"{len(words)} mots synchronisés")

            # 6b. CONTRÔLE QUALITÉ : le worker regarde son propre rendu et corrige.
            steps.start("qc", "Contrôle qualité : l'IA vérifie le rendu…")
            try:
                mids = [float(words[len(words) // 3]["start"]) + 0.1,
                        float(words[(2 * len(words)) // 3]["start"]) + 0.1]
                qc = groq_qc(extract_frames(cur, mids, work, width=540))
                if qc and (qc.get("face_covered") or qc.get("subs_visible") is False):
                    fix_lay = sentence_layout(words, "bottom", seed, bands=[1430, 1560])
                    cur = render_subs(fix_lay, "subs_fix")
                    steps.done("qc", "corrigé : sous-titres repositionnés en bas")
                elif qc:
                    steps.done("qc", "rendu validé" + (f" · note: {qc.get('issue')}" if qc.get("issue") else ""))
                else:
                    steps.done("qc", "vérification indisponible")
            except Exception as e:
                print("qc:", e, file=sys.stderr)
                steps.done("qc", "vérification indisponible")
        elif plan.get("subtitles") and facts["has_audio"]:
            steps.done("subs", "transcription indisponible")
        else:
            # Pas de sous-titres (vidéo sans voix) : on applique quand même le hook
            # texte que l'IA a déduit de ce qu'elle a VU, + l'étalonnage couleur.
            steps.skip("subs", "Sous-titres", "pas de parole — pas de sous-titres")
            hook = str(plan.get("hook_text") or "").strip()
            grade = str(plan.get("color_grade") or "")
            if hook or grade:
                steps.start("look", "Accroche + étalonnage…")
                try:
                    ass_p = os.path.join(work, "look.ass")
                    with open(ass_p, "w", encoding="utf-8") as f:
                        f.write(build_ass([], hook, style_id=plan.get("sub_style_id") or 0, seed=seed))
                    out_l = os.path.join(work, "look.mp4")
                    burn_subs(cur, out_l, ass_p, grade=grade)
                    cur = out_l
                    steps.done("look", (f"« {hook} »" if hook else "") + (" · couleurs" if grade else ""))
                except Exception as e:
                    print("look:", e, file=sys.stderr)
                    steps.done("look", "non appliqué")

        # 5. Musique + normalisation du son
        steps.start("audio", "Mixage du son…")
        music = pick_music(str(plan.get("music_mood") or ""))
        out = os.path.join(work, "final.mp4")
        loudnorm(cur, out, music_path=music, music_foreground=music_fg and not words)
        cur = out
        if music:
            steps.done("audio", "musique au premier plan" if (music_fg and not words) else "musique ajoutée")
        else:
            steps.done("audio", "son normalisé")

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
