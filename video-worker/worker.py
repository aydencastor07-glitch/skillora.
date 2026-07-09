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
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")  # Scribe : sous-titres au mot très précis
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")  # yeux : analyse vidéo
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
MUSIC_BUCKET = os.environ.get("MUSIC_BUCKET", "music-library")
STYLE_BUCKET = os.environ.get("STYLE_BUCKET", "style-library")  # styles appris des vidéos virales
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


def freeze_spans(path, noise="-58dB", d=1.0):
    """Détecte les passages où l'image est FIGÉE (logo de fin, carte statique,
    écran gelé) via freezedetect. Retourne [(début, fin|None)] ; fin=None = gel
    qui va jusqu'au bout de la vidéo."""
    try:
        p = subprocess.run(["ffmpeg", "-i", path, "-vf", f"freezedetect=n={noise}:d={d}",
                            "-map", "0:v:0", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=600)
        out = p.stderr
        starts = [float(m) for m in re.findall(r"lavfi\.freezedetect\.freeze_start[=:] ?([\d.]+)", out)]
        if not starts:
            starts = [float(m) for m in re.findall(r"freeze_start[=:] ?([\d.]+)", out)]
        ends = [float(m) for m in re.findall(r"freeze_end[=:] ?([\d.]+)", out)]
        spans = []
        for i, s in enumerate(starts):
            spans.append((s, ends[i] if i < len(ends) else None))
        return spans
    except Exception as e:
        print("freeze_spans:", e, file=sys.stderr)
        return []


def dead_time_spans(duration, silences, freezes, min_len=1.2):
    """Temps MORTS à couper (partout, même sans parole) : un passage est mort s'il
    est À LA FOIS figé (image gelée) ET silencieux. Cible surtout les logos/cartes
    de fin sans son. Retourne des plages [(début, fin)] à retirer."""
    sils = [(float(s), float(e)) for (s, e) in (silences or [])]

    def silent_frac(a, b):
        if b <= a:
            return 0.0
        cov = sum(max(0.0, min(b, e) - max(a, s)) for (s, e) in sils)
        return cov / (b - a)

    spans = []
    for (s, e) in (freezes or []):
        end = duration if e is None else e
        if end - s < min_len:
            continue
        # figé + majoritairement silencieux -> mort. Un gel jusqu'à la fin (logo
        # de fin) est coupé même sans info de silence précise.
        if silent_frac(s, end) >= 0.6 or (e is None and silent_frac(s, min(end, s + 3)) >= 0.5):
            spans.append((max(0.0, s - 0.1), end))
    return spans


def frame_colors(src, duration, work, n=6):
    """Mesure les couleurs moyennes de la vidéo (luminosité, saturation, chaleur)
    sur n images réparties. Utilise PIL. Retourne un dict ou {} si indispo."""
    try:
        from PIL import Image
    except Exception:
        return {}
    times = [duration * (k + 0.5) / n for k in range(n)]
    frames = extract_frames(src, [t for t in times if t < duration - 0.1], work, width=160)
    if not frames:
        return {}
    br, sat, warm, samp = 0.0, 0.0, 0.0, 0
    for (_t, p) in frames:
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        px = list(im.getdata())
        if not px:
            continue
        step = max(1, len(px) // 800)  # échantillonne ~800 pixels
        px = px[::step]
        for (r, g, b) in px:
            mx, mn = max(r, g, b), min(r, g, b)
            br += (r + g + b) / 3.0
            sat += (mx - mn) / (mx + 1e-6)
            warm += (r - b)
        samp += len(px)
    if not samp:
        return {}
    return {"brightness": round(br / samp / 255.0, 3),   # 0..1
            "saturation": round(sat / samp, 3),           # 0..1
            "warmth": round(warm / samp / 255.0, 3)}       # -1..1 (chaud>0, froid<0)


def color_to_grade(colors):
    """Traduit une signature couleur (frame_colors) en un étalonnage du catalogue."""
    if not colors:
        return ""
    b, s, w = colors.get("brightness", 0.5), colors.get("saturation", 0.3), colors.get("warmth", 0.0)
    if s < 0.10:
        return "bw_horror"          # quasi noir et blanc
    if b < 0.32:
        return "dark_moody"         # sombre
    if w > 0.10 and s > 0.22:
        return "warm_luxury"        # chaud et riche
    if w < -0.06:
        return "cold_cinematic"     # froid / bleuté
    if s > 0.42:
        return "vibrant_pop"        # très saturé
    return ""


def analyze_reference(src, work, category=""):
    """Extrait le STYLE mesurable d'une vidéo virale de référence :
    cadence de coupe, couleurs (étalonnage), énergie / rythme, mouvement.
    -> profil de style réutilisable pour améliorer les vidéos de cette catégorie.
    N'utilise PAS Groq (la catégorie est fournie) : rapide et gratuit."""
    facts = ffprobe_facts(src)
    d = facts["duration"] or 1.0
    cuts = scene_cuts(src)
    gaps = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)] if len(cuts) >= 2 else []
    cadence = sorted(gaps)[len(gaps) // 2] if gaps else d
    cut_s = round(min(4.0, max(1.4, cadence)), 2)
    colors = frame_colors(src, d, work)
    grade = color_to_grade(colors)
    beats = detect_beats(src, d) if facts["has_audio"] else []
    energy = audio_energy(src, d) if facts["has_audio"] else []
    avg_e = round(sum(lv for _t, lv in energy) / len(energy), 3) if energy else 0.0
    music_driven = len(beats) >= max(6, d / 1.4)
    shots_per_min = round(len(cuts) / (d / 60.0), 1) if d else 0
    intensity = round(min(1.0, 0.4 + shots_per_min / 40.0 + avg_e * 0.4), 2)
    return {
        "category": str(category or "").strip().lower(),
        "duration": round(d, 1),
        "cut_s": cut_s,
        "shots_per_min": shots_per_min,
        "grade": grade,
        "colors": colors,
        "music_driven": bool(music_driven),
        "avg_energy": avg_e,
        "intensity": intensity,
    }


def merge_profiles(profiles):
    """Agrège plusieurs profils d'une même catégorie -> un profil moyen robuste."""
    profiles = [p for p in profiles if p]
    if not profiles:
        return {}
    n = len(profiles)

    def avg(key, default=0.0):
        vals = [float(p.get(key, default) or 0) for p in profiles]
        return sum(vals) / n

    grades = [p.get("grade") for p in profiles if p.get("grade")]
    grade = max(set(grades), key=grades.count) if grades else ""
    return {
        "category": profiles[0].get("category", ""),
        "samples": n,
        "cut_s": round(avg("cut_s", 2.6), 2),
        "shots_per_min": round(avg("shots_per_min"), 1),
        "grade": grade,
        "music_driven": sum(1 for p in profiles if p.get("music_driven")) > n / 2,
        "avg_energy": round(avg("avg_energy"), 3),
        "intensity": round(avg("intensity", 0.6), 2),
    }


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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", dst])
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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
    return t2


# ── RECETTES DE MONTAGE PAR TYPE DE VIDÉO (issues de la recherche pro) ──────────
# Chaque style a son pacing, son intensité de zoom, son étalonnage par défaut,
# sa famille de transition, sa densité de bruitages. L'IA choisit le type ;
# ces réglages traduisent le type en montage concret.
#   zooms   : profil de zoom (1.0 = pas de zoom ; >1 = punch-in)
#   cut_s   : cadence de coupe cible (secondes) pour le montage sans voix
#   grade   : étalonnage par défaut si l'IA n'en a pas choisi
#   trans   : famille de transition par défaut pour les b-rolls
#   sfx     : "high"/"med"/"low" — densité des bruitages de transition
#   slowmo  : True = ralenti d'emphase autorisé sur le meilleur moment
RECIPES = {
    # Transitions par défaut = FONDU propre (les slides/zooms brusques faisaient
    # "cheap"/horrible). L'IA peut choisir plus punchy si le style s'y prête.
    # SFX en 'low' partout : les sons soulignent, ils n'envahissent pas.
    "energetic":        dict(zooms=[1.0, 1.14, 1.0, 1.18], cut_s=2.4, grade="vibrant_pop",
                             trans="fade", sfx="med", slowmo=True,
                             effects=["hdr"]),
    "vlog":             dict(zooms=[1.0, 1.09, 1.0, 1.12], cut_s=2.8, grade="",
                             trans="fade", sfx="low", slowmo=True,
                             effects=["hdr"]),
    "talk_facecam":     dict(zooms=[1.0, 1.08, 1.0, 1.12], cut_s=3.0, grade="",
                             trans="fade", sfx="low", slowmo=False,
                             effects=["hdr"]),
    "horror":           dict(zooms=[1.0, 1.06, 1.0, 1.26], cut_s=3.6, grade="bw_horror",
                             trans="dip_black", sfx="low", slowmo=True,
                             effects=["grain_vignette"]),
    "luxury_aesthetic": dict(zooms=[1.0, 1.05, 1.0, 1.04], cut_s=3.4, grade="warm_luxury",
                             trans="fade", sfx="low", slowmo=True,
                             effects=["glow", "vignette"]),
    # Danse / performance : laisser respirer. Quasi aucun effet, pas de bruitages.
    "dance":            dict(zooms=[1.0, 1.03, 1.0, 1.03], cut_s=3.6, grade="",
                             trans="fade", sfx="none", slowmo=False,
                             effects=[]),
    "product":          dict(zooms=[1.0, 1.12, 1.0, 1.16], cut_s=2.6, grade="cold_cinematic",
                             trans="fade", sfx="low", slowmo=False,
                             effects=["hdr"]),
    "story":            dict(zooms=[1.0, 1.07, 1.0, 1.11], cut_s=3.4, grade="cold_cinematic",
                             trans="fade", sfx="low", slowmo=False,
                             effects=["grain", "vignette"]),
    "other":            dict(zooms=[1.0, 1.11, 1.0, 1.16], cut_s=2.8, grade="",
                             trans="fade", sfx="low", slowmo=False,
                             effects=["hdr"]),
}


def recipe_for(video_type):
    return RECIPES.get(str(video_type or "").lower(), RECIPES["other"])


# ── MOTEUR D'EFFETS (catalogue style CapCut -> familles FFmpeg réalisables) ─────
# Rattache chaque nom du catalogue à une famille implémentée. Dosage subtil/pro.
EFFECTS_NEAR = {
    # groupe RYTHME / IMPACT (le plus utilisé — sport, énergique, viral)
    "shake_blur_impact": "shake", "pure_camera_shake": "shake",
    "earthquake_heavy_shake": "shake", "rhythmic_bass_shake": "shake",
    "scale_bounce_impact": "bounce", "snap_zoom_bounce": "bounce",
    "white_exposure_flash": "flash", "smooth_white_pulse": "flash",
    "black_fade_pulse": "flash_black", "black_strobe_pulse": "flash_black",
    "strobe_light_flash": "strobe",
    "chromatic_aberration_loop": "rgbsplit", "glitch_shake_distortion": "rgbsplit",
    "chromatic_shatter_flash": "flash", "warp_glitch_flare": "rgbsplit",
    "radial_zoom_blur_v2": "zoomblur",
    # groupe AMBIANCE / ESTHÉTIQUE
    "vignette_shadow_focus": "vignette", "grainy_vignette_vintage": "grain_vignette",
    "grunge_texture_overlay": "grain_vignette", "god_rays_volumetric": "godrays",
    "dreamy_glow_soft": "glow", "neon_glow_v2": "glow", "edge_glow_neon_line": "glow",
    "dust_particles_float": "grain", "vintage_film_projector": "grain_vignette",
    # groupe OPTIMISATION IMAGE (utile partout)
    "hdr_sharpen_contrast": "hdr", "vibrant_hdr_boost": "hdr",
    # groupe RÉTRO / GLITCH
    "retro_crt_tv_glitch": "rgbsplit", "sci_fi_glitch_flash": "flash",
    "light_leak_orange_burn": "grain", "light_leak_cold_neon": "grain",
}
# Effets "look" continus (une passe -vf) vs "impact" ponctuels (fenêtres de temps)
LOOK_EFFECTS = {"hdr", "vignette", "grain_vignette", "grain", "glow", "godrays"}
IMPACT_EFFECTS = {"shake", "bounce", "flash", "flash_black", "strobe", "rgbsplit", "zoomblur"}


def resolve_effects(names):
    """Noms du catalogue (ou familles) -> familles implémentées, dédupliquées."""
    out = []
    for n in (names or []):
        f = str(n or "").strip().lower()
        f = f if (f in LOOK_EFFECTS or f in IMPACT_EFFECTS) else EFFECTS_NEAR.get(f)
        if f and f not in out:
            out.append(f)
    return out


def look_chain(effects, intensity=1.0):
    """Chaîne -vf LINÉAIRE des effets 'look' CONTINUS (netteté HDR, grain,
    vignette) — subtile et pro, composable avec les sous-titres en une passe.
    Le glow/god-rays (graphes blend) sont gérés à part (look_glow). '' si aucun."""
    fx = [e for e in (effects or []) if e in LOOK_EFFECTS]
    if not fx:
        return ""
    parts = []
    if "hdr" in fx:
        # aspect '4K' : micro-contraste + netteté + couleurs vives (sans surcharge)
        parts.append(f"unsharp=5:5:{0.7 * intensity:.2f}:5:5:0.0")
        parts.append(f"eq=contrast={1 + 0.06 * intensity:.3f}:saturation={1 + 0.14 * intensity:.3f}:gamma=0.98")
    if "grain" in fx or "grain_vignette" in fx:
        parts.append(f"noise=alls={max(1, int(8 * intensity))}:allf=t")
    if "vignette" in fx or "grain_vignette" in fx:
        parts.append(f"vignette=PI/{5.0 - 0.6 * intensity:.2f}")
    return ",".join(parts)


def enhance_chain(enh):
    """Chaîne -vf d'amélioration IMAGE recommandée par Gemini après avoir VU la
    vidéo (luminosité, contraste, saturation, chaleur, netteté). '' si neutre.
    Rend TOUTE vidéo visiblement plus nette et plus 'punchy' — même les vidéos
    qu'on ne monte pas (danse, paysage)."""
    if not isinstance(enh, dict):
        enh = {}

    def clamp(v, lo, hi, d):
        try:
            return max(lo, min(hi, float(v)))
        except Exception:
            return d
    br = clamp(enh.get("brightness", 0), -0.15, 0.15, 0.0)
    co = clamp(enh.get("contrast", 1), 0.9, 1.25, 1.0)
    sa = clamp(enh.get("saturation", 1), 0.9, 1.35, 1.0)
    wa = clamp(enh.get("warmth", 0), -0.15, 0.15, 0.0)
    sh = clamp(enh.get("sharpen", 0), 0.0, 1.0, 0.0)
    parts = []
    # RESTAURATION (ordre pro) : 1) débruitage, 2) netteté adaptative CAS (nette
    # SANS halos), 3) micro-détail à l'unsharp. Récupère un maximum de netteté
    # perçue sur les vidéos basse qualité / recadrées.
    parts.append("hqdn3d=2:1.5:5:5")                          # débruitage (nettoie avant d'affiner)
    parts.append(f"cas=strength={0.35 + 0.45 * sh:.2f}")     # netteté adaptative au contraste
    parts.append(f"unsharp=3:3:{0.2 + 0.45 * sh:.2f}:3:3:0.0")  # micro-détail
    if abs(br) > 0.005 or abs(co - 1) > 0.005 or abs(sa - 1) > 0.005:
        parts.append(f"eq=brightness={br:.3f}:contrast={co:.3f}:saturation={sa:.3f}")
    if abs(wa) > 0.01:  # chaleur : + = plus chaud (rouge↑ bleu↓)
        parts.append(f"colorbalance=rs={wa * 0.4:.3f}:rm={wa * 0.3:.3f}:bs={-wa * 0.4:.3f}")
    return ",".join(parts)


def look_glow(src, dst, kind="glow", intensity=1.0):
    """Effets 'look' à base de blend (lueur onirique / rayons divins) — une passe
    dédiée. kind = 'glow' (halo doux) ou 'godrays' (faisceaux lumineux)."""
    if kind == "godrays":
        graph = (f"[0:v]split[ro][rl];[rl]gblur=sigma=14,eq=brightness={0.06 * intensity:.3f}[rll];"
                 f"[ro][rll]blend=all_mode=screen:all_opacity={0.34 * intensity:.2f}[v]")
    else:
        graph = (f"[0:v]split[go][gb];[gb]gblur=sigma={7 * intensity:.1f}[gbb];"
                 f"[go][gbb]blend=all_mode=screen:all_opacity={0.26 * intensity:.2f}[v]")
    try:
        run(["ffmpeg", "-y", "-i", src, "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
        return os.path.exists(dst) and os.path.getsize(dst) > 40000
    except Exception as e:
        print("look_glow:", e, file=sys.stderr)
        return False


def impact_fx(src, dst, shakes=None, flashes=None, blacks=None, splits=None, seed=0):
    """Effets d'IMPACT ponctuels calés sur les beats/temps forts, en UNE passe :
    - shakes  : secousse de caméra brève (bass hit) — subtile
    - flashes : flash blanc doux sur le beat
    - blacks  : micro-coupure au noir
    - splits  : décalage RGB (glitch) bref
    Dosage pro : amplitudes modérées. False si rien à faire."""
    shakes, flashes = shakes or [], flashes or []
    blacks, splits = blacks or [], splits or []
    if not (shakes or flashes or blacks or splits):
        return False
    facts = ffprobe_facts(src)
    W, H = facts["width"] or 1080, facts["height"] or 1920
    fc = []
    # 1) Secousse : on agrandit de 6% pour avoir de la marge, puis on décale le
    #    cadrage avec une oscillation amortie pendant chaque fenêtre de shake.
    sw, sh = (W * 106) // 100 // 2 * 2, (H * 106) // 100 // 2 * 2
    def osc(axis_phase):
        terms = []
        for k, t in enumerate(shakes[:8]):
            a = 15 - (k % 3) * 2  # amplitude px, légèrement variable
            terms.append(f"{a}*sin({38 + (seed + k) % 7}*(t-{t:.3f})+{axis_phase})"
                         f"*exp(-6*(t-{t:.3f}))*between(t,{t:.3f},{t + 0.5:.3f})")
        return "(" + "+".join(terms) + ")" if terms else "0"
    xexpr = f"(iw-{W})/2+{osc(0)}" if shakes else f"(iw-{W})/2"
    yexpr = f"(ih-{H})/2+{osc(1.6)}" if shakes else f"(ih-{H})/2"
    fc.append(f"[0:v]scale={sw}:{sh},crop={W}:{H}:'{xexpr}':'{yexpr}'[base]")
    last = "[base]"
    inputs = ["-i", src]
    idx = 1
    # 2) Flashs (blanc doux) et micro-noirs
    for kind, times, amp in (("white", flashes, 0.55), ("black", blacks, 0.85)):
        for t in times[:8]:
            dur_f = 0.20
            start = max(0.0, t - 0.04)
            inputs += ["-f", "lavfi", "-i", f"color={kind}:s={W}x{H}:r=30:d={dur_f + 0.05:.2f}"]
            fc.append(f"[{idx}:v]format=yuva420p,colorchannelmixer=aa={amp:.2f},"
                      f"fade=t=in:d=0.05:alpha=1,fade=t=out:st=0.06:d={dur_f - 0.06:.2f}:alpha=1,"
                      f"setpts=PTS+{start:.3f}/TB[fx{idx}]")
            nxt = f"[c{idx}]"
            fc.append(f"{last}[fx{idx}]overlay=0:0:enable='between(t,{start:.3f},{start + dur_f:.3f})':eof_action=pass{nxt}")
            last = nxt
            idx += 1
    # 3) Décalage RGB (glitch) bref
    if splits:
        en = "+".join(f"between(t,{t - 0.03:.3f},{t + 0.12:.3f})" for t in splits[:8])
        fc.append(f"{last}rgbashift=rh=14:bh=-14:enable='{en}'[v]")
        last = "[v]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", last, "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-c:a", "copy", dst])
    return True


def speed_ramp(src, dst, segments):
    """Vitesse dynamique : applique un facteur de vitesse par segment, le reste à
    1x. segments = [(start, end, factor)] (factor<1 = ralenti, >1 = accéléré).
    Recompose la vidéo (setpts) ET l'audio (atempo) puis concatène. La timeline
    change -> à réserver aux vidéos SANS sous-titres. False si rien à faire."""
    facts = ffprobe_facts(src)
    dur, has_a = facts["duration"], facts["has_audio"]
    segs = sorted((max(0.0, s), min(dur, e), f) for (s, e, f) in segments
                  if e - s > 0.15 and 0.25 <= f <= 4.0 and s < dur)
    if not segs:
        return False
    # Construit la liste complète des tranches (1x entre les segments ralentis)
    slices, cursor = [], 0.0
    for (s, e, f) in segs:
        if s > cursor + 0.05:
            slices.append((cursor, s, 1.0))
        slices.append((s, e, f))
        cursor = max(cursor, e)
    if cursor < dur - 0.05:
        slices.append((cursor, dur, 1.0))
    fc, vmaps, amaps = [], [], []
    for i, (s, e, f) in enumerate(slices):
        fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=(PTS-STARTPTS)/{f:.3f}[v{i}]")
        vmaps.append(f"[v{i}]")
        if has_a:
            # atempo n'accepte que 0.5..2.0 -> on chaîne pour les gros facteurs
            tempo, chain = f, []
            while tempo < 0.5:
                chain.append("atempo=0.5")
                tempo /= 0.5
            while tempo > 2.0:
                chain.append("atempo=2.0")
                tempo /= 2.0
            chain.append(f"atempo={tempo:.4f}")
            fc.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                      + ",".join(chain) + f"[a{i}]")
            amaps.append(f"[a{i}]")
    n = len(slices)
    if has_a:
        fc.append("".join(f"{vmaps[i]}{amaps[i]}" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
        maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac"]
    else:
        fc.append("".join(vmaps) + f"concat=n={n}:v=1:a=0[v]")
        maps = ["-map", "[v]"]
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", ";".join(fc), *maps,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", dst])
    return True


def zoom_punch(src, dst, words, has_audio, work, sfx_events=None, extra_whooshes=None,
               avoid=None, seed=0, bounds_override=None, zooms=None):
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
    base_zooms = list(zooms) if zooms else [1.0, 1.13, 1.0, 1.2]  # profil de la recette
    r = seed % len(base_zooms)
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
                      f",scale={W}:{H}:flags=lanczos")
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
        # SOBRIÉTÉ : PAS de whoosh sur chaque zoom (c'était du bruit partout).
        # Whoosh UNIQUEMENT sur les vraies transitions (b-roll, effet 'côté'),
        # peu nombreuses. Les bruitages de SENS (typing/cash/ding…) viennent de
        # sfx_events, eux aussi limités.
        events = [(t, "whoosh") for t in list(extra_whooshes or [])[:4]]
        for (t, name) in (sfx_events or [])[:6]:
            events.append((t, name if name in bank else "pop"))
        # Repli des intentions non présentes dans la banque -> son le plus proche
        NEAR = {"explosion": "impact", "boom": "impact", "glitch": "beep", "camera": "click",
                "scratch": "whoosh", "applause": "magic", "fail": "pop", "scream": "impact",
                "heartbeat": "impact", "riser": "whoosh", "airhorn": "ding", "beep": "pop"}
        events = [(t, name if name in bank else NEAR.get(name, "pop")) for (t, name) in events]
        # Volumes DISCRETS : les sons soulignent, ils ne dominent pas la vidéo.
        VOL = {"whoosh": 0.32, "pop": 0.5, "click": 0.6, "typing": 0.6, "ding": 0.55,
               "cash": 0.58, "magic": 0.55, "impact": 0.62, "explosion": 0.62, "glitch": 0.55,
               "camera": 0.58, "beep": 0.55, "scratch": 0.55, "applause": 0.5, "fail": 0.58,
               "scream": 0.58, "heartbeat": 0.42, "riser": 0.5, "airhorn": 0.6, "boom": 0.62}
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
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", dst]
    run(cmd)
    return True


VIZ_COLORS = {"cyan": "0x22D3EE", "white": "0xFFFFFF", "pink": "0xFF5FA2",
              "green": "0x3DDC84", "violet": "0x9D5CFF", "gold": "0xFFC542"}


def music_visualizer(src, dst, work, accent="cyan", baseline_y=0.60):
    """Incruste un ÉGALISEUR réactif au son (barres qui montent avec la musique),
    pour les vidéos image+musique. Barres centrées, en bas, comme les lecteurs
    TikTok/Spotify. False si l'audio ne s'y prête pas."""
    facts = ffprobe_facts(src)
    if not facts["has_audio"]:
        return False
    W, H = facts["width"] or 1080, facts["height"] or 1920
    col = VIZ_COLORS.get(str(accent).lower(), VIZ_COLORS["cyan"])
    bw, bh = int(W * 0.74), 230
    y = int(H * baseline_y)
    x = (W - bw) // 2
    # showfreqs = spectre en barres. On booste la luminosité + un léger halo (glow)
    # pour que les barres ressortent quel que soit le fond, colorkey rend le noir
    # transparent, et on miroir verticalement (barres qui montent du centre).
    fc = (f"[0:a]showfreqs=s={bw}x{bh}:mode=bar:ascale=cbrt:fscale=log:"
          f"win_size=2048:colors={col}|0xFFFFFF,"
          f"format=rgba,eq=brightness=0.06:saturation=1.4,"
          f"split=2[bars][g];[g]gblur=sigma=6[glow];"
          f"[glow][bars]overlay=0:0[viz0];"
          f"[viz0]colorkey=0x000000:0.28:0.08,split=2[vz][vzm];[vzm]vflip[vzf];"
          f"[0:v][vz]overlay={x}:{y}:format=auto[a1];"
          f"[a1][vzf]overlay={x}:{y - bh + 4}:format=auto[v]")
    try:
        run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc,
             "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "18", "-c:a", "copy", dst], timeout=600)
        return os.path.exists(dst) and os.path.getsize(dst) > 50000
    except Exception as e:
        print("music_visualizer:", e, file=sys.stderr)
        return False


def reframe_916(src, dst, w, h):
    """Passe au format 9:16 style clip : la vidéo entière au centre, et le fond
    (haut/bas) = la même vidéo zoomée-floutée. AUCUNE bordure noire."""
    run(["ffmpeg", "-y", "-i", src, "-filter_complex",
         "[0:v]split=2[bg][fg];"
         "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2[b];"
         "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[f];"
         "[b][f]overlay=(W-w)/2:(H-h)/2[v]",
         "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])


def _piecewise_expr(points, var="t", default=0.0):
    """Construit une expression ffmpeg interpolée linéairement entre des points
    (t, valeur) triés. Renvoie une chaîne utilisable dans crop/overlay."""
    pts = sorted((float(t), float(v)) for (t, v) in points)
    if not pts:
        return f"{default}"
    if len(pts) == 1:
        return f"{pts[0][1]:.2f}"
    expr = f"{pts[0][1]:.2f}"  # avant le 1er point : valeur du 1er point
    for i in range(len(pts) - 1):
        t0, v0 = pts[i]
        t1, v1 = pts[i + 1]
        if t1 - t0 < 0.05:
            continue
        slope = (v1 - v0) / (t1 - t0)
        seg = f"({v0:.2f}+({slope:.3f})*({var}-{t0:.3f}))"
        expr = f"if(lt({var},{t1:.3f}),{expr},{seg})"
    # après le dernier point : valeur du dernier point
    expr = f"if(gte({var},{pts[-1][0]:.3f}),{pts[-1][1]:.2f},{expr})"
    return expr


def smart_reframe(src, dst, track, target_w=1080, target_h=1920):
    """Recadrage 9:16 INTELLIGENT : la fenêtre verticale SUIT le sujet grâce au
    track de Gemini [{t, x}] (x = centre horizontal 0..1). Panoramique fluide,
    sujet toujours cadré. Retombe sur un crop centré si le track est vide.
    Idéal pour passer une vidéo horizontale/carrée en vertical sans perdre le sujet."""
    facts = ffprobe_facts(src)
    W, H = facts["width"], facts["height"]
    if not W or not H:
        return False
    # on met la source à la hauteur cible, la largeur suit le ratio
    scaled_w = max(target_w, int(round(target_h * W / H)))
    scaled_w = scaled_w // 2 * 2
    room = scaled_w - target_w  # marge horizontale disponible pour suivre le sujet
    if room <= 2:
        # déjà assez vertical -> pas de room : simple mise à l'échelle + crop centré
        room = 0
    # points (t, x_pixel_offset) : x_center*scaled_w - target_w/2, borné à [0, room]
    pts = []
    for p in (track or []):
        try:
            t = float(p.get("t"))
            x = min(1.0, max(0.0, float(p.get("x"))))
            off = min(room, max(0, x * scaled_w - target_w / 2))
            pts.append((t, off))
        except Exception:
            pass
    if room and pts:
        xexpr = _piecewise_expr(pts, var="t", default=room / 2)
    else:
        xexpr = f"{room // 2}"
    fc = (f"[0:v]scale={scaled_w}:{target_h}:flags=lanczos,"
          f"crop={target_w}:{target_h}:'{xexpr}':0[v]")
    try:
        run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
        return os.path.exists(dst) and os.path.getsize(dst) > 2000
    except Exception as e:
        print("smart_reframe:", e, file=sys.stderr)
        return False


def split_two_reframe(src, dst, xa, xb, target_w=1080, target_h=1920):
    """SPLIT-SCREEN 2 personnages (façon Opus Clip) : quand DEUX personnes parlent
    en même temps, on cadre la 1re en HAUT et la 2e en BAS, chacune bien centrée
    sur elle (xa, xb = centres horizontaux 0..1). Chaque moitié utilise toute la
    hauteur de la source -> recadrage moins agressif = meilleure qualité.
    False si impossible."""
    facts = ffprobe_facts(src)
    W, H = facts["width"], facts["height"]
    if not W or not H:
        return False
    half = target_h // 2  # 960 : hauteur de chaque personne
    cw = int(H * target_w / half) // 2 * 2  # largeur de crop (ratio 1080:960)
    cw = min(cw, W)

    def xoff(x):
        x = min(1.0, max(0.0, float(x)))
        return int(min(W - cw, max(0, x * W - cw / 2)))
    fc = (f"[0:v]split=2[a][b];"
          f"[a]crop={cw}:{H}:{xoff(xa)}:0,scale={target_w}:{half}:flags=lanczos[pa];"
          f"[b]crop={cw}:{H}:{xoff(xb)}:0,scale={target_w}:{half}:flags=lanczos[pb];"
          f"[pa][pb]vstack=inputs=2[v]")
    try:
        run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
        return os.path.exists(dst) and os.path.getsize(dst) > 2000
    except Exception as e:
        print("split_two_reframe:", e, file=sys.stderr)
        return False


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
        t1 = min(3.6, float(duration) - 0.6)
        if t1 - t0 < 1.2:
            return False
        y_center = {"top": 900, "middle": 620, "bottom": 460}.get(str(face_y).lower(), 700)
        txt_png = os.path.join(work, "bgtext.png")
        if not _bg_text_png(text, txt_png, y_center):
            return False
        dtd = os.path.join(work, "dt")
        os.makedirs(dtd, exist_ok=True)
        # Détourage en 720x1280 (bien plus net que 540 -> personne de qualité)
        RW, RH = 720, 1280
        run(["ffmpeg", "-y", "-i", src, "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}",
             "-vf", f"fps=30,scale={RW}:{RH}", os.path.join(dtd, "f_%03d.png")])
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
        cover = sum(1 for a in alpha.getdata() if a > 96) / (RW * RH)
        if cover < 0.04 or cover > 0.72:
            print(f"depth_text: personne non exploitable (aire {cover:.0%})", file=sys.stderr)
            return False
        D = t1 - t0
        # Texte : léger zoom d'entrée (pro) + fondus ; personne ré-agrandie proprement
        fc = (f"[1:v]format=rgba,fade=t=in:d=0.30:alpha=1,"
              f"fade=t=out:st={D - 0.35:.2f}:d=0.35:alpha=1,setpts=PTS+{t0:.2f}/TB[txt];"
              f"[2:v]format=rgba,scale=1080:1920:flags=lanczos,setpts=PTS-STARTPTS+{t0:.2f}/TB[per];"
              f"[0:v][txt]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})':eof_action=pass[a];"
              f"[a][per]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})':eof_action=pass[v]")
        run(["ffmpeg", "-y", "-i", src,
             "-loop", "1", "-t", f"{D + 0.05:.2f}", "-i", txt_png,
             "-framerate", "30", "-start_number", "1", "-i", os.path.join(dtd, "p_%03d.png"),
             "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])
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


def eleven_transcribe(path):
    """Transcription au mot TRÈS précise via ElevenLabs Scribe (verbatim, timings
    exacts, gère les répétitions) -> bien meilleurs sous-titres que Whisper.
    Renvoie {text, words:[{word,start,end}], language} au format du worker.
    None si pas de clé / échec (on retombe alors sur Whisper)."""
    if not ELEVEN_KEY:
        return None
    boundary = "----skillora-scribe" + str(int(time.time()))
    with open(path, "rb") as f:
        audio = f.read()
    parts = []
    for name, val in [("model_id", "scribe_v1"), ("timestamps_granularity", "word")]:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode())
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp3\"\r\n"
                  "Content-Type: audio/mpeg\r\n\r\n").encode() + audio + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    try:
        st, raw = http("POST", "https://api.elevenlabs.io/v1/speech-to-text",
                       {"xi-api-key": ELEVEN_KEY,
                        "Content-Type": f"multipart/form-data; boundary={boundary}"},
                       body, timeout=300)
        resp = json.loads(raw)
        words = [{"word": w["text"], "start": float(w["start"]), "end": float(w["end"])}
                 for w in resp.get("words", [])
                 if w.get("type", "word") == "word" and str(w.get("text", "")).strip()]
        if not words:
            return None
        return {"text": resp.get("text", ""), "words": words,
                "language": resp.get("language_code"), "engine": "scribe"}
    except urllib.error.HTTPError as e:
        try:
            print("eleven_transcribe HTTP", e.code, ":", e.read().decode()[:300], file=sys.stderr)
        except Exception:
            print("eleven_transcribe HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("eleven_transcribe:", e, file=sys.stderr)
        return None


def transcribe(path):
    """Transcripteur unifié : ElevenLabs Scribe en priorité (précision au mot),
    Whisper (Groq) en filet de sécurité. Renvoie le format {text, words[...]}."""
    tr = eleven_transcribe(path)
    if tr and tr.get("words"):
        return tr
    return groq_transcribe(path)


def eleven_isolate(src_audio, dst_audio):
    """Isole la VOIX en retirant la musique/bruit de fond (ElevenLabs Audio
    Isolation). Permet de GARDER la voix et REMPLACER la musique de la vidéo.
    True si réussi (dst_audio écrit), False sinon (clé absente / endpoint non
    activé / échec) -> on garde alors le son original."""
    if not ELEVEN_KEY:
        return False
    boundary = "----skillora-iso" + str(int(time.time()))
    with open(src_audio, "rb") as f:
        audio = f.read()
    body = ((f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; "
             "filename=\"a.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode()
            + audio + f"\r\n--{boundary}--\r\n".encode())
    try:
        st, raw = http("POST", "https://api.elevenlabs.io/v1/audio-isolation",
                       {"xi-api-key": ELEVEN_KEY,
                        "Content-Type": f"multipart/form-data; boundary={boundary}"},
                       body, timeout=300)
        if not raw or len(raw) < 2000:
            return False
        with open(dst_audio, "wb") as f:
            f.write(raw)
        return os.path.getsize(dst_audio) > 2000
    except urllib.error.HTTPError as e:
        try:
            print("eleven_isolate HTTP", e.code, ":", e.read().decode()[:200], file=sys.stderr)
        except Exception:
            print("eleven_isolate HTTP", e.code, file=sys.stderr)
        return False
    except Exception as e:
        print("eleven_isolate:", e, file=sys.stderr)
        return False


def classify_audio(tr, silences, beats, duration):
    """MUSIQUE ou VOIX ? Un créateur peut poser une CHANSON (paroles) sur sa vidéo :
    il ne faut SURTOUT PAS la sous-titrer comme une voix off. On distingue :
    - 'speech' : vraie voix off / narration (pauses naturelles, Whisper confiant)
    - 'music'  : chanson / musique (son continu, beat régulier, Whisper hésite)
    - 'silent' : rien d'exploitable
    Signaux acoustiques ; l'IA (champ audio_type) tranche les cas ambigus."""
    if not tr:
        return "silent"
    words = tr.get("words") or []
    text = (tr.get("text") or "").strip()
    if len(text) < 8 or len(words) < 4:
        return "silent"
    segs = tr.get("segments") or []
    nsp = [float(s.get("no_speech_prob", 0)) for s in segs if "no_speech_prob" in s]
    alp = [float(s.get("avg_logprob", 0)) for s in segs if "avg_logprob" in s]
    avg_nsp = sum(nsp) / len(nsp) if nsp else 0.0     # haut = pas de vraie parole
    avg_alp = sum(alp) / len(alp) if alp else 0.0     # bas = Whisper peu sûr (chant)
    sil = sum(e - s for (s, e) in (silences or []))
    sil_ratio = sil / duration if duration else 0     # parole = pauses ; musique = continu
    strong_beats = len(beats or []) >= max(6, duration / 1.2)
    score = 0
    if avg_nsp > 0.5:
        score += 2
    if avg_alp < -0.75:
        score += 1
    if sil_ratio < 0.08:
        score += 1
    if strong_beats:
        score += 1
    # Scribe ne fournit pas les indices de confiance de Whisper (segs vide) :
    # on s'appuie alors sur l'acoustique (son continu + beat régulier = musique).
    if not segs and strong_beats and sil_ratio < 0.05:
        score += 2
    return "music" if score >= 3 else "speech"


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


# ---------------------------------------------------------------- Gemini (les yeux)
GEMINI_BASE = "https://generativelanguage.googleapis.com"


def _gemini_auth(extra=None):
    # Les clés récentes (préfixe 'AQ.') s'authentifient par EN-TÊTE, pas par ?key=.
    h = {"x-goog-api-key": GEMINI_KEY}
    h.update(extra or {})
    return h


def gemini_upload(path, mime="video/mp4"):
    """Téléverse un fichier vers Gemini (Files API, protocole resumable) et renvoie
    son file_uri une fois ACTIF. None si échec / pas de clé."""
    if not GEMINI_KEY:
        return None
    try:
        size = os.path.getsize(path)
        # 1) démarrage : on récupère l'URL d'upload dans les en-têtes de réponse
        start = urllib.request.Request(
            f"{GEMINI_BASE}/upload/v1beta/files",
            data=json.dumps({"file": {"display_name": os.path.basename(path)}}).encode(),
            method="POST", headers=_gemini_auth({
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(size),
                "X-Goog-Upload-Header-Content-Type": mime,
                "Content-Type": "application/json"}))
        with urllib.request.urlopen(start, timeout=60) as r:
            upload_url = r.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            return None
        # 2) envoi des octets + finalisation
        with open(path, "rb") as f:
            blob = f.read()
        up = urllib.request.Request(upload_url, data=blob, method="POST", headers={
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
            "Content-Length": str(size)})
        with urllib.request.urlopen(up, timeout=600) as r:
            info = json.loads(r.read())
        fobj = info.get("file", info)
        name, uri, state = fobj.get("name"), fobj.get("uri"), fobj.get("state")
        # 3) attente de l'état ACTIVE (Gemini "digère" la vidéo)
        for _ in range(30):
            if state == "ACTIVE":
                return uri
            if state == "FAILED":
                return None
            time.sleep(2)
            st, raw = http("GET", f"{GEMINI_BASE}/v1beta/{name}", _gemini_auth(), None, timeout=30)
            fobj = json.loads(raw)
            state, uri = fobj.get("state"), fobj.get("uri", uri)
        return uri if state == "ACTIVE" else None
    except urllib.error.HTTPError as e:
        try:
            print("gemini_upload HTTP", e.code, ":", e.read().decode()[:250], file=sys.stderr)
        except Exception:
            print("gemini_upload HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("gemini_upload:", e, file=sys.stderr)
        return None


def gemini_generate(prompt, file_uri=None, mime="video/mp4", json_out=True):
    """Appelle generateContent (avec un fichier optionnel). Renvoie le texte/JSON
    décodé, ou None. Essaie les modèles dans l'ordre (repli automatique)."""
    if not GEMINI_KEY:
        return None
    parts = []
    if file_uri:
        fd = {"file_uri": file_uri}
        if mime:  # les liens YouTube n'ont pas besoin de mime_type
            fd["mime_type"] = mime
        parts.append({"file_data": fd})
    parts.append({"text": prompt})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2}}
    if json_out:
        body["generationConfig"]["response_mime_type"] = "application/json"
    for model in GEMINI_MODELS:
        try:
            st, raw = http("POST",
                           f"{GEMINI_BASE}/v1beta/models/{model}:generateContent",
                           _gemini_auth({"Content-Type": "application/json"}), body, timeout=180)
            out = json.loads(raw)
            cand = (out.get("candidates") or [{}])[0]
            txt = "".join(p.get("text", "") for p in (cand.get("content", {}).get("parts") or []))
            if not txt:
                continue
            return json.loads(txt) if json_out else txt
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                msg = e.read().decode()[:200]
            except Exception:
                msg = ""
            print("gemini_generate HTTP", code, "(", model, "):", msg, file=sys.stderr)
            if code in (404, 400):
                continue  # modèle indisponible -> suivant
            if code == 429:
                return None  # quota atteint
        except Exception as e:
            print("gemini_generate:", e, file=sys.stderr)
    return None


def gemini_analyze_video(path, duration, user_styles=None):
    """LES YEUX : Gemini regarde la vidéo ENTIÈRE et renvoie une compréhension
    complète + les temps morts précis. Format aligné sur notre 'vision' + extras.
    `user_styles` = profils des vidéos VIRALES du créateur (sa mémoire) : si la
    vidéo ressemble à l'une, Gemini monte DANS CE STYLE gagnant.
    None si pas de clé / échec (on retombe sur l'analyse Groq par images)."""
    if not GEMINI_KEY:
        return None
    uri = gemini_upload(path)
    if not uri:
        return None
    mem = ""
    if user_styles:
        try:
            summ = json.dumps(user_styles, ensure_ascii=False)[:2500]
            mem = ("MÉMOIRE — voici le STYLE des vidéos de CE créateur qui ont fait BEAUCOUP "
                   "DE VUES (ses vidéos gagnantes). Si la vidéo à monter ressemble à l'une de "
                   "ces niches, REPRODUIS ce style gagnant (mêmes choix de sous-titres, rythme, "
                   "effets, couleurs, hooks) en l'adaptant au contenu :\n" + summ + "\n\n")
        except Exception:
            mem = ""
    prompt = (
        mem +
        "Tu es un monteur vidéo professionnel EXIGENT et SOBRE. Regarde cette vidéo "
        f"courte ({duration:.0f}s) en ENTIER (image ET son). Ton rôle : dire ce qu'il "
        "faut VRAIMENT améliorer, sans surcharger. Beaucoup de vidéos ont juste besoin "
        "d'être RESSERRÉES (couper les temps morts) — pas d'effets partout.\n"
        "Réponds UNIQUEMENT ce JSON:\n"
        "{\"video_type\": \"talk_facecam|vlog|horror|luxury_aesthetic|energetic|dance|product|story|other\",\n"
        " \"audio_type\": \"voice|music|none\",  // voice=quelqu'un PARLE/explique ; music=CHANSON/musique (ne PAS sous-titrer) ; none=pas de son utile\n"
        " \"edit_intensity\": \"minimal|moderate|dynamic\",  // TRÈS IMPORTANT. minimal=vidéo déjà esthétique/fluide (danse, paysage, cinématique) -> on coupe juste les temps morts, PAS de zooms ni de bruitages ; moderate=talking-head/vlog -> zooms doux + sous-titres, sons rares ; dynamic=edit punchy/hype qui RÉCLAME des effets et des sons rythmés\n"
        " \"summary\": \"de quoi parle la vidéo, 1 phrase\",\n"
        " \"mood\": \"ambiance en 1-2 mots\",\n"
        " \"has_person\": bool,\n"
        " \"face_y\": \"top|middle|bottom|none\",\n"
        " \"opening_captivating\": bool,\n"
        " \"opening_note\": \"pourquoi (court)\",\n"
        " \"outro_start\": s_ou_null,  // LE PLUS IMPORTANT : la SECONDE EXACTE où commence l'écran de fin / l'outro / la carte avec un LOGO (Instagram, TikTok…) ou un @pseudo, MÊME s'il y a de la musique ou une animation dessus. Regarde bien la FIN. Si la vidéo se termine par un logo/pseudo/carte de fin, donne la seconde où ça commence pour qu'on le COUPE. null s'il n'y a pas d'écran de fin\n"
        " \"dead_time\": [{\"start\": s, \"end\": s}],  // AUTRES temps morts à couper (secondes précises) : intros lentes/vides, blancs, moments où il ne se passe rien\n"
        " \"enhance\": {\"brightness\": -0.15..0.15, \"contrast\": 0.9..1.25, \"saturation\": 0.9..1.35, \"warmth\": -0.15..0.15, \"sharpen\": 0..1},  // AMÉLIORATION IMAGE que tu recommandes APRÈS avoir VU la vidéo : corrige ce qui cloche (trop sombre -> brightness+ ; terne -> saturation+/contrast+ ; flou/pas net -> sharpen+ ; froid/chaud à corriger -> warmth). Valeurs neutres (0, 1, 1, 0, 0) si l'image est déjà parfaite. Sois utile : presque toutes les vidéos smartphone gagnent en netteté et en punch\n"
        " \"needs_reframe\": bool,  // true si la vidéo gagnerait à être recadrée en vertical en SUIVANT le sujet (source horizontale/carrée, OU sujet souvent décentré) ; false si déjà bien cadré vertical\n"
        " \"subject_track\": [{\"t\": s, \"x\": 0.0}],  // si needs_reframe : position HORIZONTALE du sujet principal (x: 0=tout à gauche, 0.5=centre, 1=tout à droite) à 6-10 instants répartis, pour que le cadrage le SUIVE ; [] sinon\n"
        " \"bg_text\": \"MOT ou phrase TRÈS courte (<=16 caractères) à afficher en GÉANT DERRIÈRE la personne (effet 3D pro, style 'ME AT 7:00') — UNIQUEMENT si une personne est nettement visible en buste/pied face caméra ET qu'un mot fort résume le sujet. Vide sinon (ne force pas)\",\n"
        " \"two_people\": bool,  // true UNIQUEMENT si DEUX personnes parlent et sont visibles EN MÊME TEMPS (podcast/interview côte à côte) -> on fera un split-screen (1re en haut, 2e en bas)\n"
        " \"person_a_x\": 0.0,  // si two_people : centre horizontal (0..1) de la 1re personne (souvent à gauche ~0.25)\n"
        " \"person_b_x\": 0.0,  // si two_people : centre horizontal (0..1) de la 2e personne (souvent à droite ~0.75)\n"
        " \"scenes\": [{\"t\": s, \"action\": \"ce qu'on voit\", \"motion\": bool, \"interest\": 0-10}],\n"
        " \"best_moments\": [s, ...],  // 0-4 instants VRAIMENT forts, ou [] si la vidéo est régulière\n"
        " \"hook_text\": \"accroche <=42 caractères déduite du contenu, ou vide\",\n"
        "// --- TES DÉCISIONS DE MONTAGE (tu es le DIRECTEUR, on exécute fidèlement) ---\n"
        " \"subtitles\": bool,  // ajouter des sous-titres animés ? OUI dès que quelqu'un PARLE (talking-head, explication, vlog, tuto). NON si musique/chanson ou aucune parole\n"
        " \"sub_style_id\": 0,  // CHOISIS le style qui COLLE VRAIMENT au contenu — VARIE, n'utilise PAS toujours 0 : 0=signature ; 2=bleu Hormozi (business/motivation/argent) ; 3=cartoon jaune (fun/vlog/humour) ; 4=script néon (mode/lifestyle) ; 5=vert tech (gadgets/tuto) ; 6=docu ombre (voyage/docu) ; 8=machine à écrire (mystère/storytelling) ; 10=dégradé or (luxe/flex) ; 12=karaoké (podcast/monologue) ; 15=glitch (gaming/IA/tech) ; 18=serif cinéma (histoire haut de gamme) ; 20=néon (musique/edit) ; 21=horreur rouge empilé (creepy/peur). Prends le style qui rendrait le mieux pour CETTE vidéo\n"
        " \"highlight\": \"yellow|green|red|cyan\",  // couleur des mots forts\n"
        " \"keywords\": [\"mots EXACTS prononcés à mettre en avant (prix, chiffres, mots-chocs), copiés tels qu'ils sont dits\"],\n"
        " \"emojis\": [{\"word\": \"mot exact prononcé\", \"emoji\": \"un émoji\"}],  // 2-5 émojis sur ce qui s'illustre\n"
        " \"objects\": [{\"word\": \"mot exact\", \"emoji\": \"émoji OBJET\"}],  // 0-2 gros objets animés si un objet important est cité\n"
        " \"brands\": [{\"word\": \"mot exact\", \"slug\": \"slug minuscule\"}],  // 0-2 logos de marques CITÉES (netflix, tiktok, temu…)\n"
        " \"sfx\": [{\"word\": \"mot exact prononcé\", \"sound\": \"typing|click|pop|whoosh|cash|ding|impact|magic|glitch|camera|beep|applause|riser|boom\"}],  // 0-5 bruitages qui RENFORCENT LE SENS, au bon endroit et adaptés au TON (un scientifique sérieux : très peu, sobres ; un edit fun : plus). taper->typing, argent/prix->cash, bonne réponse/chiffre->ding, choc/révélation->impact, tech/bug->glitch. Mets-en PEU et SEULEMENT si ça a du sens\n"
        " \"audio_action\": \"keep|replace_music|replace_all\",  // que faire du SON d'origine ? keep=on le garde tel quel ; replace_music=GARDER la voix mais RETIRER la musique de fond de la vidéo (elle est mauvaise/gênante) pour mettre la nôtre ; replace_all=le son est nul/inutile, on le COUPE entièrement et on met de la musique\n"
        " \"add_music\": bool,  // faut-il un fond musical ? false pour un talking-head sérieux (la voix suffit) ; true si un fond aide, ou obligatoire si audio_action=replace_all\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic\"  // si musique : ambiance ADAPTÉE au sujet (un scientifique -> cinematic/tech, PAS chill/plage) ; vide sinon\n"
        "}"
    )
    res = gemini_generate(prompt, file_uri=uri, mime="video/mp4", json_out=True)
    if not isinstance(res, dict):
        return None
    res["engine"] = "gemini"
    res["frames_analyzed"] = "toute la vidéo"
    return res


STUDY_DNA = ("video_type", "sub_style_id", "highlight", "edit_intensity",
             "color_grade", "music_mood")


def gemini_study_url(url):
    """Fait ÉTUDIER une vidéo virale de RÉFÉRENCE à Gemini depuis son LIEN.
    - lien YouTube : Gemini l'analyse DIRECTEMENT (pas de téléchargement) ;
    - autre lien mp4 : on télécharge puis on analyse.
    Retourne l'ADN de style {video_type, sub_style_id, edit_intensity, …} ou None.
    C'est ce qui permet à l'agent de faire 'visiter internet' à Gemini."""
    if not GEMINI_KEY or not url:
        return None
    prompt = (
        "Regarde cette vidéo courte VIRALE (elle a très bien marché). En monteur pro, "
        "décris SON STYLE DE MONTAGE pour qu'on puisse le reproduire. Réponds UNIQUEMENT ce JSON:\n"
        "{\"video_type\": \"talk_facecam|vlog|horror|luxury_aesthetic|energetic|dance|product|story|other\",\n"
        " \"sub_style_id\": 0,  // 0 signature ; 2 Hormozi ; 3 cartoon ; 4 néon ; 5 tech ; 6 docu ; 8 machine à écrire ; 10 or ; 12 karaoké ; 15 glitch ; 18 serif ; 20 néon ; 21 horreur\n"
        " \"highlight\": \"yellow|green|red|cyan\",\n"
        " \"edit_intensity\": \"minimal|moderate|dynamic\",\n"
        " \"color_grade\": \"|dark_moody|warm_luxury|cold_cinematic|vibrant_pop|bw_horror|vintage_warm\",\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic ou vide\",\n"
        " \"why_viral\": \"ce qui rend cette vidéo accrocheuse, 1 phrase\"}"
    )
    low = url.lower()
    try:
        if "youtu" in low:
            return gemini_generate(prompt, file_uri=url, mime=None, json_out=True)
        tmp = tempfile.mktemp(suffix=".mp4")
        download(url, tmp)
        uri = gemini_upload(tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass
        if not uri:
            return None
        return gemini_generate(prompt, file_uri=uri, mime="video/mp4", json_out=True)
    except Exception as e:
        print("gemini_study_url:", e, file=sys.stderr)
        return None


def gemini_qc(path, duration, had_subs=False):
    """CONTRÔLE QUALITÉ : Gemini regarde la vidéo AMÉLIORÉE (le rendu final) et
    dit s'il reste des problèmes : temps mort/logo restant, sous-titres qui
    couvrent le visage ou mal synchro, montage trop chargé, son déséquilibré.
    Renvoie {ok, score, remaining_dead_time[], subs_cover_face, too_busy, note}.
    None si pas de clé / échec."""
    if not GEMINI_KEY:
        return None
    uri = gemini_upload(path)
    if not uri:
        return None
    prompt = (
        "Tu es un directeur de post-production TRÈS exigeant. Voici une vidéo courte "
        f"({duration:.0f}s) qui vient d'être montée automatiquement pour devenir un reel "
        "viral. CONTRÔLE-la et dis ce qui ne va ENCORE pas. Réponds UNIQUEMENT ce JSON:\n"
        "{\"score\": 0-10,  // qualité globale du montage\n"
        " \"ok\": bool,  // true si publiable tel quel\n"
        " \"remaining_dead_time\": [{\"start\": s, \"end\": s}],  // temps morts/logos/écrans de fin qu'il RESTE à couper (secondes précises), [] si aucun\n"
        + (" \"subs_cover_face\": bool,  // les sous-titres cachent-ils le visage ou un élément important ?\n" if had_subs else "")
        + " \"too_busy\": bool,  // le montage est-il TROP chargé (trop d'effets/zooms/sons) ?\n"
        " \"note\": \"le problème principal en 1 phrase, ou 'RAS'\"}"
    )
    res = gemini_generate(prompt, file_uri=uri, mime="video/mp4", json_out=True)
    return res if isinstance(res, dict) else None


def remap_after_cut(t, deads):
    """Reprojette un timestamp de la vidéo ORIGINALE vers la vidéo COUPÉE
    (après retrait des plages `deads`). None si le point tombe dans une coupe."""
    if t is None:
        return None
    t = float(t)
    off = 0.0
    for (s, e) in sorted(deads or []):
        if e <= t:
            off += (e - s)
        elif s < t < e:
            return None
    return max(0.0, round(t - off, 3))


def remap_vision(vision, deads):
    """Applique remap_after_cut à tous les timestamps d'une analyse (scènes,
    meilleurs moments, temps morts) après une coupe."""
    if not vision or not deads:
        return vision
    v = dict(vision)
    v["scenes"] = [dict(s, t=remap_after_cut(s.get("t"), deads))
                   for s in (vision.get("scenes") or [])
                   if remap_after_cut(s.get("t"), deads) is not None]
    v["best_moments"] = [x for x in (remap_after_cut(b, deads) for b in (vision.get("best_moments") or []))
                         if x is not None]
    v["subject_track"] = [dict(p, t=remap_after_cut(p.get("t"), deads))
                          for p in (vision.get("subject_track") or [])
                          if remap_after_cut(p.get("t"), deads) is not None]
    v["dead_time"] = []  # déjà coupés
    return v


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
        "audio_type": "voice" if transcript_text else "none",
        "effects": [],
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
        " \"audio_type\": \"voice|music|none\",  // 'voice' = vraie voix off / narration / quelqu'un qui EXPLIQUE ou PARLE ; 'music' = CHANSON / musique avec des paroles chantées (À NE PAS sous-titrer !) ; 'none' = pas de son utile. Regarde le texte : des instructions/explications = voice ; des paroles de chanson = music\n"
        " \"hook_text\": \"accroche ultra courte (<=42 caractères). S'il y a de la parole, langue de la transcription. S'il N'Y A PAS de parole (vidéo muette/esthétique/musique), DÉDUIS une accroche de ce que l'IA a VU (résumé/scènes) — ex: 'POV: coucher de soleil à Bali', 'Le café parfait en 30s'. Vide seulement si vraiment rien à dire\",\n"
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
        " \"objects\": [{\"word\": \"mot EXACT de la transcription\", \"emoji\": \"un émoji OBJET\"}],  // 0-2 GROS objets animés qui traversent l'écran (voiture 🚗, téléphone 📱, produit 📦…) quand la parole cite un objet IMPORTANT — différent des petits émojis de sous-titres\n"
        " \"effects\": [\"hdr|shake|flash|rgbsplit|glow|godrays|grain|vignette|grain_vignette\"]}  // 0-3 effets vidéo SUBTILS et PRO adaptés au type : hdr=netteté/couleurs (presque toujours utile) ; shake=secousse sur les impacts (sport/énergique) ; flash=flash blanc sur un temps fort ; rgbsplit=glitch (tech/gaming/horreur) ; glow=lueur douce (beauté/luxe) ; godrays=rayons lumineux (lifestyle/motivation) ; grain+vignette=grain cinéma (docu/rétro/histoire). Reste SOBRE — jamais surchargé"
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
                  "broll_keywords", "transition", "color_grade", "bg_text", "objects",
                  "audio_type", "effects"):
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
    """Incruste les sous-titres (+ étalonnage optionnel SOUS le texte). La netteté
    et le punch sont gérés ailleurs (passe qualité 'enhance', une seule fois)."""
    safe = ass_path.replace("\\", "/").replace(":", "\\:")
    g = GRADES.get(str(grade or "").lower())
    pre = (g + ",") if g else ""
    run(["ffmpeg", "-y", "-i", src,
         "-vf", f"{pre}ass='{safe}'",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", dst])


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
         "-crf", "18", "-c:a", "copy", dst])
    return slots[:len(brolls)]


# ---------------------------------------------------------------- styles appris
_STYLE_CACHE = {}


def load_style_profile(category):
    """Charge le style APPRIS des vidéos virales pour cette catégorie
    (style-library/{categorie}.json). None si absent. Mis en cache."""
    cat = str(category or "").strip().lower()
    if not cat:
        return None
    if cat in _STYLE_CACHE:
        return _STYLE_CACHE[cat]
    prof = None
    try:
        url = f"{SB_URL}/storage/v1/object/public/{STYLE_BUCKET}/{urllib.parse.quote(cat)}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Skillora"})
        with urllib.request.urlopen(req, timeout=20) as r:
            prof = json.loads(r.read().decode())
    except Exception:
        prof = None  # pas de style appris pour cette catégorie -> défauts codés
    _STYLE_CACHE[cat] = prof
    return prof


USERSTYLE_BUCKET = os.environ.get("USERSTYLE_BUCKET", "user-styles")


def load_user_styles(user_id):
    """Charge les PROFILS DE STYLE PERSONNELS d'un créateur, appris de SES vidéos
    virales (user-styles/{user_id}/*.json). Retourne une liste (une entrée par
    niche) ou [] si aucun. C'est la MÉMOIRE : ce qui marche pour CETTE personne."""
    uid = str(user_id or "").strip()
    if not uid:
        return []
    out = []
    try:
        st, raw = http("POST", f"{SB_URL}/storage/v1/object/list/{USERSTYLE_BUCKET}",
                       sb_headers(), {"prefix": uid + "/", "limit": 50}, timeout=20)
        for it in json.loads(raw):
            name = it.get("name", "")
            if not name.endswith(".json"):
                continue
            try:
                url = f"{SB_URL}/storage/v1/object/public/{USERSTYLE_BUCKET}/{urllib.parse.quote(uid + '/' + name)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Skillora"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    out.append(json.loads(r.read().decode()))
            except Exception:
                pass
    except Exception as e:
        print("load_user_styles:", e, file=sys.stderr)
    return out


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

        # LES YEUX : Gemini regarde TOUTE la vidéo d'origine (image + son) et
        # renvoie sa compréhension complète + les temps morts PRÉCIS. Sur la vidéo
        # ORIGINALE (les timestamps seront reprojetés après la coupe).
        gem = None
        if GEMINI_KEY:
            steps.start("see", "Gemini regarde toute ta vidéo…")
            # MÉMOIRE : le style des vidéos VIRALES de ce créateur (s'il en a)
            user_styles = load_user_styles(job.get("user_id"))
            try:
                gem = gemini_analyze_video(src, facts["duration"], user_styles=user_styles or None)
            except Exception as e:
                print("gemini:", e, file=sys.stderr)
            note_mem = f" · style perso ({len(user_styles)} niche(s))" if user_styles else ""
            steps.done("see", ("vidéo comprise" + note_mem) if gem
                       else "vision Gemini indisponible (on continue)")

        # ÉTAPE 0 : couper les TEMPS MORTS. Priorité aux temps morts repérés par
        # Gemini (précis, il voit les blancs/intros lentes), sinon détection
        # figé+silencieux. Marche même sans parole.
        steps.start("trim", "Repérage des temps morts…")
        sil0 = detect_silences(src, noise_db=-40, min_d=0.5) if facts["has_audio"] else [(0.0, facts["duration"])]
        deads = dead_time_spans(facts["duration"], sil0, freeze_spans(src))
        if gem and gem.get("dead_time"):
            for dt in gem["dead_time"]:
                try:
                    a, b = float(dt.get("start")), float(dt.get("end"))
                    if b - a >= 0.6 and 0 <= a < facts["duration"]:
                        deads.append((max(0.0, a), min(facts["duration"], b)))
                except Exception:
                    pass
        # ÉCRAN DE FIN / LOGO : Gemini donne la seconde où l'outro commence -> on
        # coupe tout jusqu'à la fin (c'est le fix du logo Instagram qui restait).
        if gem and gem.get("outro_start") is not None:
            try:
                osec = float(gem["outro_start"])
                if 1.0 <= osec < facts["duration"] - 0.3:
                    deads.append((osec, facts["duration"]))
            except Exception:
                pass
        # fusionne + trie les plages
        deads = sorted(set((round(a, 2), round(b, 2)) for (a, b) in deads if b > a))
        applied_deads = []
        total_dead = sum(e - s for (s, e) in deads)
        if deads and total_dead < facts["duration"] * 0.45:
            outc = os.path.join(work, "trim.mp4")
            if cut_spans(src, outc, [], deads, facts["duration"]):
                src = outc
                applied_deads = deads
                facts = ffprobe_facts(src)
                steps.done("trim", f"{total_dead:.0f}s de temps mort retiré(s)")
            else:
                steps.done("trim", "aucun temps mort")
        else:
            steps.done("trim", "aucun temps mort")

        steps.start("analyze", "Analyse : le worker regarde et écoute ta vidéo…")
        d = facts["duration"]
        silences = detect_silences(src) if facts["has_audio"] else []
        # Changements de plan + énergie + rythme (ffmpeg, précis, sur la vidéo coupée).
        cuts = scene_cuts(src)
        beats = detect_beats(src, d) if facts["has_audio"] else []
        first_tr = None
        if facts["has_audio"]:
            mp3 = os.path.join(work, "a.mp3")
            extract_audio_mp3(src, mp3)
            first_tr = transcribe(mp3)
        tr_text = (first_tr or {}).get("text", "").strip() if first_tr else ""
        # Vision : Gemini (reprojeté après la coupe) en priorité, sinon Groq images.
        vision = None
        if gem:
            vision = remap_vision(gem, applied_deads)
        else:
            try:
                vision = groq_vision_full(src, work, d, tr_text, scenecuts=cuts)
            except Exception as e:
                print("vision:", e, file=sys.stderr)
        plan = groq_plan(facts, tr_text, context, vision)
        # ── GEMINI EST LE DIRECTEUR ──────────────────────────────────────────────
        # Il a VU et ENTENDU toute la vidéo : ses décisions de montage PRIMENT sur
        # celles de groq_plan (qui ne devient qu'un repli quand Gemini est absent).
        if gem:
            if gem.get("audio_type"):
                plan["audio_type"] = gem["audio_type"]
            if gem.get("hook_text") and not str(plan.get("hook_text") or "").strip():
                plan["hook_text"] = gem["hook_text"]
            # décisions directes : sous-titres, style, mots forts, émojis, objets, sons…
            if isinstance(gem.get("subtitles"), bool):
                plan["subtitles"] = gem["subtitles"]
            for k in ("sub_style_id", "highlight"):
                if gem.get(k) not in (None, ""):
                    plan[k] = gem[k]
            for k in ("keywords", "emojis", "objects", "brands", "sfx"):
                if isinstance(gem.get(k), list):
                    plan[k] = gem[k]  # Gemini décide (liste vide = rien, volontaire)
            if "bg_text" in gem:
                plan["bg_text"] = str(gem.get("bg_text") or "")  # texte derrière la personne
            # MUSIQUE : Gemini a le contrôle TOTAL (fini la musique de plage forcée).
            plan["music_mood"] = str(gem.get("music_mood") or "") if gem.get("add_music") else ""
            # replace_all impose une musique -> ambiance par défaut si Gemini a oublié
            if str(gem.get("audio_action") or "") == "replace_all" and not plan["music_mood"]:
                plan["music_mood"] = str(gem.get("music_mood") or "cinematic")
            eng_note = " · réalisé par Gemini"
        else:
            eng_note = ""
        # INTENSITÉ DE MONTAGE (décidée par Gemini) : combien la vidéo doit être
        # travaillée. minimal = on coupe juste les temps morts, RIEN d'autre ;
        # moderate = zooms doux + sous-titres ; dynamic = effets + sons rythmés.
        vtype = str((vision or {}).get("video_type") or "")
        intensity_mode = str((gem or {}).get("edit_intensity") or "").lower()
        if intensity_mode not in ("minimal", "moderate", "dynamic"):
            intensity_mode = {"dance": "minimal", "luxury_aesthetic": "minimal",
                              "story": "moderate", "energetic": "dynamic",
                              "product": "dynamic"}.get(vtype, "moderate")
        # Recette de montage selon le type de vidéo détecté : comble les choix que
        # l'IA n'a pas faits (étalonnage, transition) avec les réglages du style.
        rec = dict(recipe_for(vtype))
        # STYLE APPRIS : si tu as envoyé des vidéos virales de cette catégorie, le
        # worker applique leur style mesuré (cadence de coupe, étalonnage,
        # intensité) — il PRIME sur les réglages codés en dur.
        learned = load_style_profile(vtype)
        learn_note = ""
        if learned:
            if learned.get("cut_s"):
                rec["cut_s"] = float(learned["cut_s"])
            if learned.get("grade"):
                rec["grade"] = learned["grade"]
            # intensité apprise -> ampleur des zooms (montage nerveux vs posé)
            inten = float(learned.get("intensity") or 0.6)
            base = rec["zooms"]
            rec["zooms"] = [1.0 if z <= 1.0 else round(1.0 + (z - 1.0) * (0.6 + inten), 3) for z in base]
            # style de sous-titres / couleur / intensité APPRIS des vidéos virales
            # de cette niche : appliqués si Gemini ne l'a pas déjà décidé.
            if not gem:
                if learned.get("sub_style_id") is not None:
                    plan["sub_style_id"] = learned["sub_style_id"]
                if learned.get("highlight"):
                    plan["highlight"] = learned["highlight"]
                if learned.get("edit_intensity") in ("minimal", "moderate", "dynamic"):
                    intensity_mode = learned["edit_intensity"]
            learn_note = f" · style viral appris ({learned.get('samples', 1)} réf.)"
        if not str(plan.get("color_grade") or ""):
            plan["color_grade"] = rec["grade"]
        if not str(plan.get("transition") or ""):
            plan["transition"] = rec["trans"]
        # Effets vidéo : base de la recette + ce que l'IA a ajouté (subtil, pro)
        effects_sel = resolve_effects(list(rec["effects"]) + list(plan.get("effects") or []))
        # MUSIQUE ou VOIX ? Gemini a VU et ENTENDU la vidéo -> son avis PRIME.
        # (Bug corrigé : mon détecteur acoustique prenait une voix sur fond musical
        # pour une chanson et coupait les sous-titres.) L'acoustique n'est utilisée
        # QU'EN REPLI, quand Gemini n'a rien dit.
        gem_audio = str((gem or {}).get("audio_type") or "")
        if gem_audio == "voice":
            is_music = False
        elif gem_audio == "music":
            is_music = True
        else:
            acoustic = classify_audio(first_tr, silences, beats, d) if tr_text else "silent"
            is_music = (str(plan.get("audio_type") or "") == "music") or acoustic == "music"
        if is_music:
            plan["subtitles"] = False
            plan["cut_silences"] = False  # ne pas charcuter une chanson
            plan["music_mood"] = ""       # la chanson EST déjà la musique : pas d'ajout
            tr_text_sub = ""  # plus de texte de paroles pour les sous-titres
        else:
            tr_text_sub = tr_text
        # Image quasi fixe + musique -> on ajoutera un égaliseur réactif au son
        near_static = len(cuts) <= 2 and not any(
            s.get("motion") for s in (vision or {}).get("scenes") or [])
        want_visualizer = is_music and near_static and facts["has_audio"]
        update_job(job["id"], {"plan": plan})
        det = ("musique détectée (pas de sous-titres)" if is_music
               else ("voix détectée" if tr_text else "pas de parole détectée"))
        if vision:
            det += (f" · {vision.get('frames_analyzed', 0)} images analysées"
                    f" · type: {vision.get('video_type', '?')}"
                    f" · montage: {intensity_mode}"
                    f" · {len(cuts)} plan(s)")
        det += eng_note + learn_note
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

        # 2. Recadrage 9:16 — une vidéo HORIZONTALE devient verticale en REMPLISSANT
        # l'écran avec le sujet (crop intelligent), jamais le flou-bordures moche.
        # Suit le sujet si Gemini fournit un track, sinon crop centré. Le flou-bordures
        # n'est qu'un ultime repli si le crop échoue.
        gem_track = (vision or {}).get("subject_track") or []
        two_people = bool(gem and (gem or {}).get("two_people"))
        if two_people:
            # SPLIT-SCREEN : les deux personnes, l'une en haut, l'autre en bas
            out = os.path.join(work, "frame.mp4")
            xa = (gem or {}).get("person_a_x", 0.25)
            xb = (gem or {}).get("person_b_x", 0.75)
            steps.start("frame", "Split-screen : les 2 personnes cadrées…")
            if split_two_reframe(cur, out, xa, xb):
                cur = out
                steps.done("frame", "split-screen (2 personnes)")
            elif plan.get("reframe"):
                reframe_916(cur, out, facts["width"], facts["height"])
                cur = out
                steps.done("frame", "recadrage (repli)")
            else:
                steps.skip("frame", "Recadrage 9:16", "déjà au bon format")
        elif plan.get("reframe"):
            out = os.path.join(work, "frame.mp4")
            following = bool(gem and (gem or {}).get("needs_reframe") and gem_track)
            steps.start("frame", "Recadrage vertical qui SUIT le sujet…" if following
                        else "Recadrage vertical (sujet centré)…")
            if smart_reframe(cur, out, gem_track if following else []):
                cur = out
                steps.done("frame", "cadrage qui suit le sujet" if following
                           else "cadrage vertical plein écran (sujet centré)")
            else:
                reframe_916(cur, out, facts["width"], facts["height"])
                cur = out
                steps.done("frame", "recadrage (repli)")
        elif gem and (gem or {}).get("needs_reframe") and gem_track:
            # déjà vertical mais sujet décentré -> on recompose en le suivant
            out = os.path.join(work, "frame.mp4")
            steps.start("frame", "Recomposition (le sujet reste cadré)…")
            if smart_reframe(cur, out, gem_track):
                cur = out
                steps.done("frame", "sujet recadré")
            else:
                steps.skip("frame", "Recadrage 9:16", "déjà au bon format")
        else:
            steps.skip("frame", "Recadrage 9:16", "déjà au bon format")

        # Point de reprise « propre » (recadré, sans effets) : si Gemini juge le
        # montage TROP CHARGÉ, on re-cuisine une version épurée à partir d'ici.
        base_reframed = cur

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
            tr2 = transcribe(mp3b)
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
        impact_pts = []   # instants (timeline COURANTE) pour shake/flash/glitch
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
                              avoid=(slide[0], slide[1]) if slide else None, seed=seed,
                              zooms=rec["zooms"]):
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
                # Ancres d'impact (mots forts) pour d'éventuels effets shake/flash
                impact_pts = [float(k["start"]) for k in kws[:4]]
                steps.done("fx", detail)
            except Exception as e:
                print("fx:", e, file=sys.stderr)
                steps.done("fx", "effets non appliqués (on continue sans)")
        elif intensity_mode == "minimal":
            # Vidéo déjà esthétique/fluide (danse, paysage, cinématique) : on NE
            # touche PAS au rythme. Pas de zooms, PAS de bruitages. On laisse
            # respirer — les temps morts ont déjà été coupés, c'est l'essentiel.
            music_fg = True
            steps.skip("fx", "Montage rythmé", "vidéo déjà fluide — on la laisse respirer")
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
                    every = rec["cut_s"]  # cadence de coupe propre au style
                    rhythm = [round(t, 2) for t in _frange(0.6, dur_cur - 0.6, every)]
                # Pas trop serré : un zoom toutes ~1.4 s max (sinon illisible)
                thinned, lastb = [], -9.0
                for b in rhythm:
                    if b - lastb >= 1.3:
                        thinned.append(b)
                        lastb = b
                rhythm = thinned[:40]
                # SOBRIÉTÉ pilotée par l'intensité : 'dynamic' = quelques sons aux
                # vrais moments forts ; 'moderate' = presque rien (1 whoosh max).
                best = [float(x) for x in ((vision or {}).get("best_moments") or []) if timeline_intact and 0.4 < float(x) < dur_cur - 0.4]
                sfx_ev = []
                if intensity_mode == "dynamic":
                    lastw = -9.0
                    for c in [c for c in src_cuts if 0.4 < c < dur_cur - 0.4]:
                        if c - lastw >= 4.0:
                            sfx_ev.append((c, "whoosh"))
                            lastw = c
                        if len(sfx_ev) >= 3:
                            break
                    sfx_ev += [(t, "impact") for t in best[:2]]
                elif best:  # moderate : un seul accent, sur LE meilleur moment
                    sfx_ev = [(best[0], "impact")]
                out = os.path.join(work, "fx.mp4")
                if zoom_punch(cur, out, [], facts["has_audio"], work,
                              sfx_events=sorted(sfx_ev), seed=seed,
                              bounds_override=rhythm, zooms=rec["zooms"]):
                    cur = out
                # VITESSE DYNAMIQUE : ralenti d'emphase sur le meilleur moment
                # (réservé aux styles qui s'y prêtent, jamais avec des sous-titres).
                ramped = False
                if rec["slowmo"] and best and timeline_intact:
                    bm = best[0]
                    if 0.8 < bm < dur_cur - 1.2:
                        outr = os.path.join(work, "ramp.mp4")
                        if speed_ramp(cur, outr, [(bm - 0.15, bm + 0.55, 0.5)]):
                            cur = outr
                            ramped = True
                # Gros objets/logos si des marques sont citées à l'écran (sans parole)
                objs = brand_events([{"start": (best[0] if best else 1.5)}], plan.get("brands"), work) if plan.get("brands") else []
                if objs:
                    objs = [(min(dur_cur - (OBJ_IN + OBJ_HOLD + OBJ_OUT) - 0.3, max(1.0, o[0])), o[1]) for o in objs][:1]
                    outo = os.path.join(work, "objs.mp4")
                    if overlay_objects(cur, outo, objs, seed=seed):
                        cur = outo
                impact_pts = (best[:3] or rhythm[1:4])
                steps.done("fx", f"{len(rhythm)} accents rythmés + {len(sfx_ev)} son(s)"
                           + (" + ralenti" if ramped else "") + f" · type {vtype}")
            except Exception as e:
                print("fx-novoice:", e, file=sys.stderr)
                steps.done("fx", "montage rythmé non appliqué (on continue)")
        else:
            steps.skip("fx", "Montage dynamique", "vidéo trop courte")

        # 5b. EFFETS VIDÉO (subtils, pro) : look continu (HDR/grain/vignette/lueur)
        #     + impacts ponctuels (secousse/flash/glitch) calés sur les temps forts.
        if effects_sel:
            steps.start("effects", "Effets vidéo…")
            applied = []
            try:
                inten = 0.7 if str((vision or {}).get("video_type")) in ("luxury_aesthetic", "story", "talk_facecam") else 1.0
                # a) look continu linéaire (grain, vignette, HDR)
                lc = look_chain(effects_sel, intensity=inten)
                if lc:
                    outl = os.path.join(work, "look.mp4")
                    run(["ffmpeg", "-y", "-i", cur, "-vf", lc, "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outl])
                    cur = outl
                    applied.append("look")
                # b) lueur / rayons (passe blend dédiée)
                for gk in ("glow", "godrays"):
                    if gk in effects_sel:
                        outg = os.path.join(work, f"{gk}.mp4")
                        if look_glow(cur, outg, kind=gk, intensity=inten):
                            cur = outg
                            applied.append(gk)
                # c) impacts ponctuels (secousse/flash/glitch) : SEULEMENT en montage
                # dynamique. Sur une vidéo minimal/modérée, on n'en met pas (sobriété).
                dur_now = ffprobe_facts(cur)["duration"]
                pts = [t for t in (impact_pts or []) if 0.4 < float(t) < dur_now - 0.4][:4] \
                    if intensity_mode == "dynamic" else []
                sh = pts if "shake" in effects_sel else []
                fl = pts[:1] if "flash" in effects_sel else []
                sp = pts[:2] if "rgbsplit" in effects_sel else []
                if sh or fl or sp:
                    outi = os.path.join(work, "impact.mp4")
                    if impact_fx(cur, outi, shakes=sh, flashes=fl, splits=sp, seed=seed):
                        cur = outi
                        applied.append("impacts")
                steps.done("effects", " + ".join(applied) if applied else "aucun applicable")
            except Exception as e:
                print("effects:", e, file=sys.stderr)
                steps.done("effects", "effets non appliqués (on continue)")

        # 5b-bis. PASSE QUALITÉ (toujours) : netteté + couleurs réglées par Gemini
        # d'après ce qu'il a VU. Rend TOUTE vidéo visiblement meilleure — même
        # celles qu'on ne monte pas (danse, paysage). C'est le "on voit une
        # différence" même en mode minimal.
        if ffprobe_facts(cur)["duration"] > 0.5:
            steps.start("quality", "Amélioration de l'image (netteté, couleurs)…")
            try:
                ech = enhance_chain((gem or {}).get("enhance"))
                if ech:
                    outq = os.path.join(work, "quality.mp4")
                    run(["ffmpeg", "-y", "-i", cur, "-vf", ech, "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outq])
                    cur = outq
                    steps.done("quality", "image nettoyée et rehaussée")
                else:
                    steps.done("quality", "image déjà nickel")
            except Exception as e:
                print("quality:", e, file=sys.stderr)
                steps.done("quality", "non appliqué")

        # 5c. ÉGALISEUR réactif au son (image quasi fixe + musique -> on la fait vivre)
        if want_visualizer:
            steps.start("viz", "Égaliseur audio réactif…")
            mood = str((vision or {}).get("mood") or "").lower()
            accent = "cyan"
            for key, c in (("or", "gold"), ("lux", "gold"), ("rose", "pink"), ("pink", "pink"),
                           ("violet", "violet"), ("purple", "violet"), ("sombre", "violet"),
                           ("dark", "violet"), ("vert", "green"), ("green", "green")):
                if key in mood:
                    accent = c
                    break
            outv = os.path.join(work, "viz.mp4")
            if music_visualizer(cur, outv, work, accent=accent):
                cur = outv
                steps.done("viz", "barres synchronisées au son")
            else:
                steps.done("viz", "non applicable")

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

        # 6c. GEMINI GOÛTE LE PLAT (contrôle qualité) et, si ce n'est pas bon, il
        # RE-CUISINE : coupe les temps morts restants, et si le montage est jugé
        # TROP CHARGÉ (note < 7), il refait une version ÉPURÉE (juste qualité +
        # sous-titres) à partir du point de reprise propre. On garde le meilleur.
        if GEMINI_KEY and ffprobe_facts(cur)["duration"] > 2:
            steps.start("gqc", "Gemini goûte le résultat…")
            try:
                dur_qc = ffprobe_facts(cur)["duration"]
                qcg = gemini_qc(cur, dur_qc, had_subs=bool(words))
                fixed = []
                if qcg:
                    # a) couper les temps morts/logos que Gemini repère encore
                    rem = []
                    for dt in (qcg.get("remaining_dead_time") or []):
                        try:
                            a, b = float(dt.get("start")), float(dt.get("end"))
                            if b - a >= 0.6 and 0 <= a < dur_qc:
                                rem.append((max(0.0, a), min(dur_qc, b)))
                        except Exception:
                            pass
                    rem = sorted(set((round(a, 2), round(b, 2)) for (a, b) in rem))
                    if rem and sum(e - s for s, e in rem) < dur_qc * 0.4:
                        outqc = os.path.join(work, "qc_fix.mp4")
                        if cut_spans(cur, outqc, [], rem, dur_qc):
                            cur = outqc
                            fixed.append(f"{sum(e - s for s, e in rem):.0f}s de temps mort")
                    # b) RE-CUISSON si trop chargé / note basse : version épurée
                    sc = qcg.get("score")
                    too_busy = bool(qcg.get("too_busy"))
                    low = (isinstance(sc, (int, float)) and sc < 7)
                    if (too_busy or low) and ffprobe_facts(base_reframed)["duration"] > 1:
                        try:
                            clean = base_reframed
                            # qualité (netteté/couleurs) sur la base propre
                            ech = enhance_chain((gem or {}).get("enhance"))
                            if ech:
                                outc = os.path.join(work, "recook_q.mp4")
                                run(["ffmpeg", "-y", "-i", clean, "-vf", ech, "-c:v", "libx264",
                                     "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outc])
                                clean = outc
                            # sous-titres épurés (aucun zoom/effet/son parasite)
                            if words:
                                ass_c = os.path.join(work, "recook.ass")
                                with open(ass_c, "w", encoding="utf-8") as f:
                                    f.write(build_ass(words, str(plan.get("hook_text") or ""),
                                                      keywords=kws, slide=None,
                                                      sub_position=str(plan.get("sub_position") or "dynamic"),
                                                      highlight=str(plan.get("highlight") or "yellow"),
                                                      sub_style=str(plan.get("sub_style") or "group"),
                                                      style_id=plan.get("sub_style_id") or 0,
                                                      layout=None, seed=seed))
                                outc2 = os.path.join(work, "recook.mp4")
                                burn_subs(clean, outc2, ass_c, grade=str(plan.get("color_grade") or ""))
                                clean = outc2
                            cur = clean
                            fixed.append("re-cuisiné en version épurée")
                        except Exception as e:
                            print("recook:", e, file=sys.stderr)
                    note = str(qcg.get("note") or "").strip()
                    det = (f"note {sc}/10" if sc is not None else "vérifié")
                    if fixed:
                        det += " · corrigé : " + ", ".join(fixed)
                    elif note and note.upper() not in ("RAS", "R.A.S", "RAS."):
                        det += f" · {note}"
                    steps.done("gqc", det)
                else:
                    steps.done("gqc", "vérification indisponible")
            except Exception as e:
                print("gqc:", e, file=sys.stderr)
                steps.done("gqc", "vérification indisponible")

        # 5. SON : Gemini décide quoi faire du son d'origine.
        #    keep = on garde ; replace_music = on GARDE la voix mais on retire la
        #    musique de fond gênante (isolation ElevenLabs) et on met la nôtre ;
        #    replace_all = son nul -> on le COUPE et on met de la musique.
        steps.start("audio", "Mixage du son…")
        audio_action = str((gem or {}).get("audio_action") or "keep")
        music = pick_music(str(plan.get("music_mood") or ""))
        out = os.path.join(work, "final.mp4")
        audio_note = ""
        if audio_action == "replace_all":
            # Coupe le son d'origine, met la musique seule (ou silence si pas de musique)
            if music:
                run(["ffmpeg", "-y", "-i", cur, "-stream_loop", "-1", "-i", music,
                     "-filter_complex", "[1:a]loudnorm=I=-13:TP=-1.5:LRA=11[a]",
                     "-map", "0:v", "-map", "[a]", "-metadata", "comment=skillora-improved",
                     "-c:v", "copy", "-c:a", "aac", "-shortest", out])
                audio_note = "son d'origine remplacé par de la musique"
            else:
                run(["ffmpeg", "-y", "-i", cur, "-c:v", "copy", "-an",
                     "-metadata", "comment=skillora-improved", out])
                audio_note = "son d'origine retiré"
            cur = out
        elif audio_action == "replace_music" and words and ELEVEN_KEY:
            # GARDER la voix, RETIRER la musique de fond, remettre la nôtre dessous
            iso_ok = False
            try:
                cur_mp3 = os.path.join(work, "cur_audio.mp3")
                extract_audio_mp3(cur, cur_mp3)
                voice_wav = os.path.join(work, "voice_iso.mp3")
                if eleven_isolate(cur_mp3, voice_wav):
                    novideo = os.path.join(work, "voiced.mp4")
                    run(["ffmpeg", "-y", "-i", cur, "-i", voice_wav,
                         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                         "-shortest", novideo])
                    loudnorm(novideo, out, music_path=music, music_foreground=False)
                    cur = out
                    iso_ok = True
                    audio_note = "voix isolée · musique remplacée"
            except Exception as e:
                print("replace_music:", e, file=sys.stderr)
            if not iso_ok:
                loudnorm(cur, out, music_path=music, music_foreground=music_fg and not words)
                cur = out
                audio_note = "musique ajoutée (isolation indispo)"
        else:
            loudnorm(cur, out, music_path=music, music_foreground=music_fg and not words)
            cur = out
            audio_note = ("musique au premier plan" if (music_fg and not words)
                          else ("musique ajoutée" if music else "son normalisé"))
        steps.done("audio", audio_note)

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


# ==================================================================================
# Agent ÉCLAIREUR — consommateur : le worker fait ÉTUDIER les vidéos gagnantes au repos.
# La file `winning_videos` est remplie par l'edge function scout-winners (autonome).
# scope='creator' -> user-styles/{user_id}/{niche}.json ; scope='global' -> style-library/{niche}.json.
# ==================================================================================
CREATOR_DNA = ("video_type", "sub_style_id", "highlight", "edit_intensity",
               "color_grade", "music_mood", "audio_action")


def claim_winner():
    """Attribue atomiquement UNE vidéo gagnante à étudier (statut -> 'studying')."""
    try:
        st, raw = http("POST", SB_URL + "/rest/v1/rpc/claim_winning_video", sb_headers(), {})
        rows = json.loads(raw or b"[]")
        return rows[0] if rows else None
    except Exception as e:
        print("claim_winner:", e, file=sys.stderr)
        return None


def mark_winner(win_id, patch):
    try:
        http("PATCH", SB_URL + "/rest/v1/winning_videos?id=eq." + win_id,
             sb_headers({"Prefer": "return=minimal"}), patch)
    except Exception as e:
        print("mark_winner:", e, file=sys.stderr)


def _read_style_json(bucket, key):
    """Lit un profil de style existant (ou None) depuis le storage public."""
    try:
        url = f"{SB_URL}/storage/v1/object/public/{bucket}/{urllib.parse.quote(key)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Skillora"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _write_style_json(bucket, key, profile):
    http("POST", f"{SB_URL}/storage/v1/object/{bucket}/{urllib.parse.quote(key)}",
         sb_headers({"Content-Type": "application/json", "x-upsert": "true"}),
         json.dumps(profile, ensure_ascii=False).encode())


def merge_winner_style(bucket, key, niche, dna, views, scope):
    """Fusion INCRÉMENTALE d'une gagnante dans le profil de style (un vote par champ).
    On garde `_votes` (comptage par valeur) pour choisir la valeur majoritaire au fil de l'eau."""
    prof = _read_style_json(bucket, key) or {"video_type": niche, "samples": 0, "_votes": {}}
    votes = prof.get("_votes") or {}
    fields = CREATOR_DNA if scope == "creator" else STUDY_DNA
    for f in fields:
        val = dna.get(f)
        if val in (None, ""):
            continue
        vf = votes.setdefault(f, {})
        vf[str(val)] = vf.get(str(val), 0) + 1
        prof[f] = max(vf, key=vf.get)  # valeur la plus souvent gagnante
    # sub_style_id : on le garde numérique si possible
    if "sub_style_id" in prof:
        try:
            prof["sub_style_id"] = int(prof["sub_style_id"])
        except Exception:
            pass
    prof["_votes"] = votes
    prof["video_type"] = niche
    prof["samples"] = int(prof.get("samples", 0)) + 1
    prof["avg_views"] = int((int(prof.get("avg_views", 0)) * (prof["samples"] - 1) + int(views or 0)) / prof["samples"])
    prof["source"] = "scout_creator" if scope == "creator" else "scout_viral"
    # cadence/intensité indicatives déduites de l'intensité apprise (comme study_niche.py)
    inten = str(prof.get("edit_intensity") or "moderate")
    prof["cut_s"] = {"minimal": 3.6, "moderate": 3.0, "dynamic": 2.3}.get(inten, 2.8)
    prof["intensity"] = {"minimal": 0.4, "moderate": 0.6, "dynamic": 0.9}.get(inten, 0.6)
    prof["grade"] = prof.get("color_grade") or ""
    _write_style_json(bucket, key, prof)
    return prof


SOCIAVAULT_KEY = os.environ.get("SOCIAVAULT_API_KEY", "")


def sv_fresh_media(page_url):
    """Redemande à SociaVault un lien mp4 FRAIS pour une vidéo TikTok (les liens CDN
    expirent au bout de quelques heures). None si pas de clé / échec."""
    if not SOCIAVAULT_KEY or "tiktok.com" not in page_url:
        return None
    try:
        req = urllib.request.Request(
            "https://api.sociavault.com/v1/scrape/tiktok/video?url=" + urllib.parse.quote(page_url, safe=""),
            headers={"X-API-Key": SOCIAVAULT_KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        d = data.get("data") or data
        v = d.get("aweme_detail") or d.get("video") or d
        vid = v.get("video") or {}
        for cand in (vid.get("play_addr"), vid.get("download_addr"), vid.get("play_addr_h264")):
            urls = (cand or {}).get("url_list") or []
            urls = urls if isinstance(urls, list) else list(urls.values())
            for u in urls:
                if isinstance(u, str) and u.startswith("http"):
                    return u
    except Exception as e:
        print("sv_fresh_media:", e, file=sys.stderr)
    return None


def study_winner(row):
    """Fait étudier UNE vidéo gagnante par Gemini et enrichit la mémoire de style.
    YouTube : analyse directe du lien ; sinon téléchargement du mp4 (media_url) + analyse."""
    win_id = row["id"]
    url = row.get("video_url") or ""
    scope = row.get("scope") or "creator"
    views = int(row.get("views") or 0)
    try:
        low = url.lower()
        gem = None
        if "youtu" in low:
            gem = gemini_study_url(url)  # analyse directe, pas de téléchargement
        else:
            # ordre d'essai : mp4 direct connu -> lien page -> mp4 frais via SociaVault
            candidates = [u for u in (row.get("media_url"), url) if u]
            tmp = tempfile.mktemp(suffix=".mp4")
            try:
                got = False
                for cand in candidates:
                    try:
                        download(cand, tmp)
                        if os.path.getsize(tmp) > 50000:  # une vraie vidéo, pas une page d'erreur
                            got = True
                            break
                    except Exception:
                        pass
                if not got:
                    fresh = sv_fresh_media(url)
                    if fresh:
                        download(fresh, tmp)
                        got = os.path.getsize(tmp) > 50000
                if not got:
                    raise RuntimeError("téléchargement impossible (lien expiré ?)")
                dur = ffprobe_facts(tmp)["duration"]
                gem = gemini_analyze_video(tmp, dur)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        if not gem or not isinstance(gem, dict):
            mark_winner(win_id, {"status": "error", "error": "Gemini n'a pas pu analyser.",
                                 "finished_at": "now()"})
            return
        niche = re.sub(r"[^a-z0-9_]", "", str(row.get("niche") or gem.get("video_type") or "other").lower()) or "other"
        if scope == "creator" and row.get("user_id"):
            bucket, key = USERSTYLE_BUCKET, f"{row['user_id']}/{niche}.json"
        else:
            bucket, key = STYLE_BUCKET, f"{niche}.json"
        prof = merge_winner_style(bucket, key, niche, gem, views, scope)
        _STYLE_CACHE.pop(niche, None)  # invalide le cache pour usage immédiat
        mark_winner(win_id, {"status": "done", "niche": niche,
                             "study_result": {"sub_style_id": prof.get("sub_style_id"),
                                              "edit_intensity": prof.get("edit_intensity"),
                                              "samples": prof.get("samples")},
                             "finished_at": "now()"})
        print(f"Éclaireur: étudié {scope}/{niche} ({views} vues) -> {bucket}/{key}")
    except Exception as e:
        traceback.print_exc()
        mark_winner(win_id, {"status": "error", "error": str(e)[:500], "finished_at": "now()"})


# --- déclenchement automatique des agents (aucun cron à configurer) -------------
# Le worker tourne 24h/24 avec la clé service : c'est LUI qui réveille les agents.
#   scout-winners : ~1x/jour (les comptes connectés) ; scout-explore : ~1x/semaine (internet).
# L'horloge est PERSISTÉE dans style-library/_scout_state.json pour survivre aux redémarrages
# (sinon chaque restart relancerait une recherche = crédits SociaVault gaspillés).
_SCOUT_CHECK_S = 1800          # on regarde l'horloge au plus toutes les 30 min
_WINNERS_EVERY_S = 24 * 3600   # balayage des comptes connectés : 1x/jour
_EXPLORE_EVERY_S = 7 * 24 * 3600  # recherche internet : 1x/semaine
_scout_next_check = 0.0


def _invoke_edge(name):
    try:
        st, raw = http("POST", f"{SB_URL}/functions/v1/{name}", sb_headers(), {}, timeout=300)
        print(f"Agent {name}:", (raw or b"")[:200].decode(errors="replace"))
    except Exception as e:
        print(f"Agent {name}:", e, file=sys.stderr)


def scout_tick():
    """Réveille les agents Éclaireur/Chercheur quand c'est l'heure. Silencieux sinon."""
    global _scout_next_check
    now = time.time()
    if now < _scout_next_check:
        return
    _scout_next_check = now + _SCOUT_CHECK_S
    state = _read_style_json(STYLE_BUCKET, "_scout_state.json") or {}
    changed = False
    if now - float(state.get("last_winners", 0)) > _WINNERS_EVERY_S:
        _invoke_edge("scout-winners")
        state["last_winners"] = now
        changed = True
    if now - float(state.get("last_explore", 0)) > _EXPLORE_EVERY_S:
        _invoke_edge("scout-explore")
        state["last_explore"] = now
        changed = True
    if changed:
        try:
            _write_style_json(STYLE_BUCKET, "_scout_state.json", state)
        except Exception as e:
            print("scout_tick state:", e, file=sys.stderr)


def main():
    print("Skillora video-worker démarré.",
          "Groq:", "oui" if GROQ_KEY else "NON (plan IA désactivé)",
          "· Yeux:", "Gemini (vidéo entière)" if GEMINI_KEY else "Groq (images)",
          "· Transcription:", "ElevenLabs Scribe" if ELEVEN_KEY else "Whisper (Groq)",
          "· Pexels:", "oui" if PEXELS_KEY else "non")
    while True:
        job = claim_job()
        if job:
            print("Job réclamé:", job["id"])
            process(job)
            continue
        # Au repos : 1) réveiller les agents si c'est l'heure ; 2) faire étudier UNE gagnante par Gemini.
        scout_tick()
        win = claim_winner() if GEMINI_KEY else None
        if win:
            print("Éclaireur: gagnante réclamée:", win.get("video_url", "")[:60])
            study_winner(win)
            continue
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
