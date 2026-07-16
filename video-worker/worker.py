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
# Canal PAYANT : les mêmes yeux Gemini via OpenRouter — AUCUNE limite du gratuit.
# Priorité : OpenRouter d'abord, Gemini gratuit en secours si OpenRouter échoue.
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
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


def flat_spans(path, min_len=0.5):
    """Détecte les passages où l'écran est une COULEUR UNIE (image noire, verte,
    blanche, écran vide…) : rien à montrer -> temps mort, quelle que soit la bande
    son. Mesure la plage de luminance (YMAX-YMIN) image par image : un écran plat
    a une plage quasi nulle, une vraie scène jamais. Échantillonné à 4 img/s.
    (Un flash blanc de transition dure ~2 images : min_len=0.5 s le protège.)"""
    try:
        safe = path.replace("\\", "/").replace("'", r"\'")
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-f", "lavfi",
             "-i", f"movie='{safe}',fps=4,signalstats",
             "-show_entries", "frame=pts_time:frame_tags=lavfi.signalstats.YMIN,lavfi.signalstats.YMAX",
             "-of", "csv=p=0"],
            capture_output=True, text=True, timeout=600)
        spans, start, last_t = [], None, 0.0
        for line in p.stdout.splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                t, ymin, ymax = float(parts[0]), float(parts[1]), float(parts[2])
            except ValueError:
                continue
            last_t = t
            if (ymax - ymin) <= 26:          # écran (quasi) uni, peu importe la couleur
                if start is None:
                    start = t
            else:
                if start is not None and t - start >= min_len:
                    spans.append((max(0.0, start - 0.05), t))
                start = None
        if start is not None and last_t - start >= min_len:
            spans.append((max(0.0, start - 0.05), last_t + 0.3))
        return spans
    except Exception as e:
        print("flat_spans:", e, file=sys.stderr)
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
    # SYNCHRO LABIALE GARANTIE : découpe par segments trim/atrim + concat.
    # (L'ancienne méthode select + setpts=N/FRAME_RATE/TB supposait une cadence
    # d'images CONSTANTE ; or les vidéos de téléphone sont à cadence VARIABLE ->
    # l'image dérivait par rapport au son après chaque coupe, de pire en pire.)
    keep = keep[:80]  # garde-fou ffmpeg (jamais atteint en pratique)
    fc = []
    for i, (a, b) in enumerate(keep):
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    pairs = "".join(f"[v{i}][a{i}]" for i in range(len(keep)))
    fc.append(f"{pairs}concat=n={len(keep)}:v=1:a=1[vo][ao]")
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", ";".join(fc),
         "-map", "[vo]", "-map", "[ao]",
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
        vol = 0.5 + (i % 3) * 0.08  # le bruitage SOULIGNE, il ne domine jamais la voix
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


def mix_sfx_at(src, dst, events, work):
    """ÉDITEUR TIMELINE : mixe des bruitages à des instants PRÉCIS choisis par le
    créateur (timeline inchangée, vidéo copiée sans ré-encodage)."""
    bank = make_sfx_bank(work)
    evs = [(float(t), str(sn)) for (t, sn) in events if str(sn) in bank][:10]
    if not evs:
        return False
    inputs = ["-i", src]
    fc, amaps = [], []
    for i, (t, sname) in enumerate(evs):
        p = bank[sname][i % len(bank[sname])]
        inputs += ["-i", p]
        ms = max(0, int(t * 1000))
        fc.append(f"[{i + 1}:a]adelay={ms}|{ms},volume=0.55[s{i}]")
        amaps.append(f"[s{i}]")
    fc.append("[0:a]" + "".join(amaps) +
              f"amix=inputs={len(evs) + 1}:duration=first:dropout_transition=0:normalize=0[a]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", dst])
    return True


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
        # matching SOUPLE : exact d'abord, sinon préfixe/contenu (l'oreille de
        # Gemini et la transcription écrivent parfois le même mot différemment —
        # avant, le son disparaissait alors en silence)
        hit = None
        for w in words or []:
            t = float(w.get("start", 0))
            if t in used_ts:
                continue
            wt = norm_token(w.get("word", ""))
            if wt == target:
                hit = t
                break
            if hit is None and len(target) >= 4 and (wt.startswith(target[:4]) or target[:4] in wt):
                hit = t  # candidat approché, gardé si aucun exact ensuite
        if hit is not None:
            events.append((hit, sound))
            used_ts.add(hit)
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
            # SVG rendu en 300 px puis réduit à l'écran -> NET (le PNG 72 px agrandi était flou)
            try:
                svg = os.path.join(work, f"emoji_{i}.svg")
                download(EMOJI_SVG.format(code), svg)
                run(["rsvg-convert", "-w", "300", "-o", p, svg], timeout=60)
                assert os.path.exists(p) and os.path.getsize(p) > 500
            except Exception:
                download(EMOJI_CDN.format(code), p)  # repli 72px
            hit_i = None
            for idx, w in enumerate(words or []):
                wt = norm_token(w.get("word", ""))
                if wt == target:
                    hit_i = idx
                    break
                if hit_i is None and len(target) >= 4 and (wt.startswith(target[:4]) or target[:4] in wt):
                    hit_i = idx  # match approché (transcription ≠ oreille de Gemini)
            if hit_i is not None:
                w = words[hit_i]
                suby = layout[hit_i] if layout and hit_i < len(layout) else 1430
                y = max(150, suby - 265)  # collé au-dessus de la ligne de texte
                events.append((float(w["start"]), p, y))
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


def _obj_free_y(face_y):
    """Hauteur (en fraction de H) où poser un objet/logo SANS couvrir le visage
    ni les sous-titres (bas). Le placement dépend d'où est le visage."""
    f = str(face_y or "").lower()
    if f == "top":
        return 0.50   # visage en haut -> objet sous le visage, au-dessus des sous-titres
    if f == "bottom":
        return 0.14   # visage en bas -> objet en haut
    if f == "middle":
        return 0.12   # visage au centre -> objet tout en haut
    return 0.20       # pas de visage -> tiers haut classique


def overlay_objects(src, dst, events, seed=0, face_y=None):
    """Objets/logos animés façon monteur PRO :
    - 3 animations différentes, alternées (jamais deux fois la même à la suite) :
        0 = glisse latérale avec LÉGER DÉPASSEMENT puis retour (ease-out-back)
        1 = tombe du haut et REBONDIT en place, repart vers le haut
        2 = monte du bas, se pose en douceur, sort par le côté
    - placement INTELLIGENT : jamais sur le visage (face_y), jamais sur les
      sous-titres — hauteurs en fraction de H (marche à toutes les résolutions)."""
    if not events:
        return False
    yf = _obj_free_y(face_y)
    fc, last = [], "[0:v]"
    inputs = []
    for i, (t, png) in enumerate(events[:3]):
        inputs += ["-i", png]
        t_out = t + OBJ_IN + OBJ_HOLD
        t_end = t_out + OBJ_OUT
        style = (seed + i) % 3
        sgn = 1 if (seed + i) % 2 == 0 else -1
        # p = progression d'entrée (0..1), q = progression de sortie (0..1)
        p = f"min((t-{t:.3f})/{OBJ_IN}\\,1)"
        q = f"max(0\\,(t-{t_out:.3f})/{OBJ_OUT})"
        # ease-out-back : dépasse la cible de ~8 % puis revient (rendu 'monteur pro')
        eb = f"(1 + 2.6*pow({p}-1\\,3) + 1.6*pow({p}-1\\,2))"
        if style == 0:
            # glisse latérale avec dépassement, sort de l'autre côté
            x = (f"(W-w)/2 - ({sgn})*(W+w)/2*(1-{eb})"
                 f" + ({sgn})*(W+w)/2*pow({q}\\,2)")
            y = f"H*{yf:.3f}"
        elif style == 1:
            # tombe du haut avec rebond (dépassement vers le bas puis retour), sort vers le haut
            x = "(W-w)/2"
            y = (f"H*{yf:.3f} - (H*{yf:.3f}+h)*(1-{eb})"
                 f" - (H*{yf:.3f}+h)*pow({q}\\,2)")
        else:
            # monte du bas (depuis sous la zone sous-titres), se pose, sort latéralement
            x = f"(W-w)/2 + ({sgn})*(W+w)/2*pow({q}\\,2)"
            y = f"H*{yf:.3f} + (H*0.78-H*{yf:.3f})*(1-{eb})"
        fc.append(f"[{i + 1}:v]scale=300:-1[ob{i}]")
        nxt = f"[oo{i}]"
        fc.append(f"{last}[ob{i}]overlay=x='{x}':y='{y}':"
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


def detect_content_crop(path):
    """Détecte les BANDES NOIRES (film horizontal collé dans un cadre vertical,
    letterbox/pillarbox) via cropdetect. Renvoie (w, h, x, y) de l'image réelle,
    ou None si pas de bandes significatives."""
    try:
        p = subprocess.run(["ffmpeg", "-ss", "1", "-t", "6", "-i", path,
                            "-vf", "cropdetect=18:2:0", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=180)
        crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", p.stderr or "")
        if not crops:
            return None
        w, h, x, y = map(int, crops[-1])
        if w < 64 or h < 64:
            return None
        return (w, h, x, y)
    except Exception as e:
        print("detect_content_crop:", e, file=sys.stderr)
        return None


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


def _step_expr(points, var="t", default=0.0, min_jump=40.0):
    """Expression ffmpeg en ESCALIER : à chaque point (t, valeur) le cadre SAUTE
    à la nouvelle position et y RESTE jusqu'au point suivant — le recadrage d'un
    monteur (on coupe, on recadre) au lieu d'un glissement qui laisse le sujet
    décentré pendant tout le trajet. Les micro-écarts (<min_jump px) sont ignorés
    pour éviter les sauts nerveux inutiles."""
    pts = sorted((float(t), float(v)) for (t, v) in points)
    if not pts:
        return f"{default}"
    kept = [pts[0]]
    for (t, v) in pts[1:]:
        if abs(v - kept[-1][1]) >= min_jump:
            kept.append((t, v))
    expr = f"{kept[0][1]:.2f}"
    for (t, v) in kept[1:]:
        expr = f"if(lt({var},{t:.3f}),{expr},{v:.2f})"
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
        # ESCALIER : saut net à chaque point de track (recadrage de monteur),
        # fini le panoramique qui laisse le sujet hors-centre entre deux points
        xexpr = _step_expr(pts, var="t", default=room / 2)
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
        # DUCKING de studio : la musique s'abaisse automatiquement dès que la voix
        # parle (sidechain) et remonte dans les respirations — le réflexe d'un pro.
        run(["ffmpeg", "-y", "-i", src, "-stream_loop", "-1", "-i", music_path,
             "-filter_complex",
             f"[1:a]volume={music_gain_db}dB[m];"
             "[0:a]asplit=2[voz][key];"
             "[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=120:release=500[md];"
             "[voz][md]amix=inputs=2:duration=first:dropout_transition=3:normalize=0,"
             "loudnorm=I=-14:TP=-1.5:LRA=11[a]",
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


OR_MODELS = ("google/gemini-2.5-flash", "google/gemini-2.0-flash-001")


def _video_proxy(path, max_mb=18):
    """Si la vidéo est trop lourde pour un envoi base64, fabrique une copie
    allégée (640 px de haut) — largement suffisant pour l'ANALYSE. Renvoie
    (chemin, est_temporaire)."""
    try:
        if os.path.getsize(path) <= max_mb * 1024 * 1024:
            return path, False
        small = tempfile.mktemp(suffix=".mp4")
        run(["ffmpeg", "-y", "-i", path, "-vf", "scale=-2:640",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
             "-c:a", "aac", "-b:a", "64k", small], timeout=600)
        if os.path.exists(small) and os.path.getsize(small) > 10000:
            return small, True
    except Exception as e:
        print("_video_proxy:", e, file=sys.stderr)
    return path, False


def or_generate(prompt, video_path=None, video_url=None, json_out=True):
    """Canal PAYANT (OpenRouter) : mêmes yeux Gemini, sans limites du gratuit.
    Vidéo locale -> data-URL base64 (compressée si lourde) ; lien YouTube ->
    passé tel quel. Renvoie le JSON décodé (ou le texte), sinon None."""
    if not OPENROUTER_KEY:
        return None
    content = [{"type": "text", "text": prompt}]
    proxy, is_tmp = None, False
    try:
        if video_path:
            proxy, is_tmp = _video_proxy(video_path)
            with open(proxy, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content.append({"type": "video_url",
                            "video_url": {"url": "data:video/mp4;base64," + b64}})
        elif video_url:
            content.append({"type": "video_url", "video_url": {"url": video_url}})
        body = {"model": OR_MODELS[0],
                "models": list(OR_MODELS),  # repli automatique côté OpenRouter
                "messages": [{"role": "user", "content": content}],
                "temperature": 0.2}
        if json_out:
            body["response_format"] = {"type": "json_object"}
        st, raw = http("POST", "https://openrouter.ai/api/v1/chat/completions",
                       {"Authorization": "Bearer " + OPENROUTER_KEY,
                        "X-Title": "Skillora"}, body, timeout=300)
        out = json.loads(raw)
        txt = (((out.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        if not txt:
            print("or_generate: réponse vide:", str(out)[:250], file=sys.stderr)
            return None
        if json_out:
            t = txt.strip()
            if t.startswith("```"):
                t = re.sub(r"^```[a-z]*\s*|\s*```$", "", t)
            return json.loads(t)
        return txt
    except urllib.error.HTTPError as e:
        try:
            print("or_generate HTTP", e.code, ":", e.read().decode()[:250], file=sys.stderr)
        except Exception:
            print("or_generate HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("or_generate:", e, file=sys.stderr)
        return None
    finally:
        if is_tmp and proxy and os.path.exists(proxy):
            try:
                os.remove(proxy)
            except Exception:
                pass


def gemini_analyze_video(path, duration, user_styles=None, style_library=None):
    """LES YEUX : Gemini regarde la vidéo ENTIÈRE et renvoie une compréhension
    complète + les temps morts précis. Format aligné sur notre 'vision' + extras.
    `user_styles` = profils des vidéos VIRALES du créateur (sa mémoire perso) ;
    `style_library` = l'ÉCOLE : les styles viraux appris par niche sur internet
    (avec leurs techniques signature). Gemini s'en inspire pour diriger le montage.
    None si pas de clé / échec (on retombe sur l'analyse Groq par images)."""
    if not (GEMINI_KEY or OPENROUTER_KEY):
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
    if style_library:
        try:
            summ = json.dumps(style_library, ensure_ascii=False)[:3000]
            mem += ("ÉCOLE — voici les STYLES VIRAUX appris automatiquement par NICHE "
                    "(vidéos qui ont explosé sur internet), avec leurs TECHNIQUES SIGNATURE. "
                    "Identifie la niche de la vidéo à monter et INSPIRE-toi du style gagnant "
                    "de cette niche (rythme, étalonnage, sous-titres, techniques) :\n"
                    + summ + "\n\n")
        except Exception:
            pass
    prompt = (
        mem +
        "Tu es un MONTEUR PROFESSIONNEL EXPERT, niveau CapCut Pro. "
        f"Regarde cette vidéo courte ({duration:.0f}s) en ENTIER (image ET son), puis "
        "DIRIGE le montage — on exécute fidèlement chacune de tes décisions.\n\n"
        "LA CHARTE DU MONTEUR (permanente — chaque règle est un OUTIL que tu doses "
        "selon ce que TU VOIS dans CETTE vidéo et ce que l'école t'a appris) :\n"
        "1. RÉTENTION : sur une vidéo parlée, l'image ne reste jamais identique plus de ~4 s "
        "(punch-ins aux phrases fortes) — sauf si la vidéo est déjà rythmée par ses plans.\n"
        "2. SON : quelqu'un parle -> la voix est REINE (pas de musique, ou tapis émotionnel "
        "whisper) ; personne ne parle -> la musique est le MOTEUR. Bruitages : une vidéo "
        "parlée RYTHMÉE en a presque toujours 1-3, PILE aux moments qui comptent (chiffre, "
        "punchline, révélation) — 0 seulement si le ton est calme/émotionnel. Jamais "
        "d'ambiance plage sur un propos sérieux.\n"
        "3. CADRAGE : la personne qui parle est ENTIÈRE et CENTRÉE à CHAQUE instant. "
        "Donne un point de track à CHAQUE changement de plan (appuie-toi sur tes scenes) — "
        "une tête coupée est INACCEPTABLE. Deux personnes en même temps -> split-screen.\n"
        "4. SOUS-TITRES : découpe par pensées ou mot-par-mot selon le débit ; style choisi "
        "selon le contenu (jamais 0 par réflexe) ; TOUJOURS dans la langue parlée.\n"
        "5. DÉCORATIONS (émojis, objets, logos, b-roll, texte 3D) : des outils, pas des "
        "obligations — chacun quand il illustre vraiment, à sa juste place. Une vidéo "
        "parlée dynamique SANS aucun émoji ni relief est fade : vise 1-3 émojis bien "
        "placés quand le contenu s'y prête.\n"
        "6. ACCROCHE TEXTE : un OUTIL PONCTUEL, pas un réflexe — mets-la SEULEMENT si elle "
        "crée une vraie curiosité que la 1re phrase ne crée pas déjà. Beaucoup de vidéos "
        "n'en ont PAS besoin : hook_text vide alors.\n"
        "7. TRANSITIONS : la famille qui colle au ton, variée d'une vidéo à l'autre.\n"
        "8. ÉTALONNAGE : un look qui sert l'histoire, ou none si l'image est déjà bien.\n"
        "9. QUALITÉ D'IMAGE : sacrée — jamais un choix qui rend la vidéo floue.\n"
        "10. OBJECTIF : une vidéo publiable à 8+/10 — pro, virale, fidèle au créateur.\n"
        "Réponds UNIQUEMENT ce JSON:\n"
        "{\"video_type\": \"talk_facecam|vlog|horror|luxury_aesthetic|energetic|dance|product|story|other\",\n"
        " \"niche\": \"le SUJET en 1 mot simple minuscule (ex: football, basketball, gym, edit, food, comedy, gaming, cars, fashion, motivation, lifestyle, horror, dance, luxe...)\",\n"
        " \"audio_type\": \"voice|music|none\",  // voice=quelqu'un PARLE/explique ; music=CHANSON/musique (ne PAS sous-titrer) ; none=pas de son utile\n"
        " \"edit_intensity\": \"minimal|moderate|dynamic\",  // TRÈS IMPORTANT. minimal=vidéo déjà esthétique/fluide (danse, paysage, cinématique) -> on coupe juste les temps morts, PAS de zooms ni de bruitages ; moderate=talking-head/vlog -> RÈGLE DE RÉTENTION d'un monteur pro : l'image ne reste JAMAIS identique plus de ~4 s — punch-in à chaque phrase forte, 2-4 bruitages qui SOULIGNENT le sens, 1-3 émojis quand ça illustre, un plan d'illustration si un objet/lieu est cité ; dynamic=edit punchy/hype qui RÉCLAME des effets et des sons rythmés partout\n"
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
        " \"subject_track\": [{\"t\": s, \"x\": 0.0}],  // si needs_reframe : position HORIZONTALE du sujet principal (x: 0=gauche, 0.5=centre, 1=droite) à 8-12 instants répartis sur TOUTE la durée. RÈGLE ABSOLUE : la PERSONNE doit être ENTIÈRE et CENTRÉE à chaque instant. La vidéo peut CHANGER DE PLAN : mets un point de track À CHAQUE changement de plan (sers-toi de tes scenes) + un juste après — c'est là que les têtes se font couper. Épaules sans tête = inacceptable. Si DEUX personnes (une de dos/épaule, une de face) : cadre TOUJOURS celle qui est DE FACE et bien visible — jamais le dos ou l'épaule de l'autre ; [] sinon\n"
        " \"bg_text\": \"MOT ou phrase TRÈS courte (<=16 caractères), DANS LA LANGUE PARLÉE de la vidéo, à afficher en GÉANT DERRIÈRE la personne (effet 3D pro, style 'ME AT 7:00') — UNIQUEMENT si une personne est nettement visible en buste/pied face caméra ET qu'un mot fort résume le sujet. Vide sinon (ne force pas)\",\n"
        " \"two_people\": bool,  // true UNIQUEMENT si DEUX personnes parlent et sont visibles EN MÊME TEMPS (podcast/interview côte à côte) -> on fera un split-screen (1re en haut, 2e en bas)\n"
        " \"person_a_x\": 0.0,  // si two_people : centre horizontal (0..1) de la 1re personne (souvent à gauche ~0.25)\n"
        " \"person_b_x\": 0.0,  // si two_people : centre horizontal (0..1) de la 2e personne (souvent à droite ~0.75)\n"
        " \"scenes\": [{\"t\": s, \"action\": \"ce qu'on voit\", \"motion\": bool, \"interest\": 0-10}],\n"
        " \"best_moments\": [s, ...],  // 0-4 instants VRAIMENT forts, ou [] si la vidéo est régulière\n"
        " \"hook_text\": \"RÈGLE 6 : SEULEMENT si elle apporte une curiosité que la 1re phrase ne donne pas — sinon VIDE (la plupart des vidéos n'en ont pas besoin). <=42 caractères, DANS LA LANGUE PARLÉE de la vidéo\",\n"
        "// --- TES DÉCISIONS DE MONTAGE (tu es le DIRECTEUR, on exécute fidèlement) ---\n"
        " \"subtitles\": bool,  // ajouter des sous-titres animés ? OUI dès que quelqu'un PARLE (talking-head, explication, vlog, tuto). NON si musique/chanson ou aucune parole\n"
        " \"burned_subs\": \"none|bottom|middle|top\",  // la vidéo contient-elle DÉJÀ des sous-titres incrustés dans l'image ? Donne leur ZONE (bottom = tiers bas, middle = au centre, top = en haut). none si aucun. REGARDE BIEN : beaucoup de vidéos en ont déjà\n"
        " \"sub_style\": \"group|word\",  // affichage des sous-titres : group = par pensées de 2-4 mots (défaut, posé) ; word = MOT PAR MOT qui claque (débit rapide, contenu punchy) — VARIE selon le rythme de la parole\n"
        " \"sub_style_id\": 0,  // INTERDIT de répondre 0 par réflexe (0 = seulement si AUCUN autre ne colle). Choisis comme un directeur artistique : 0=signature ; 2=bleu Hormozi (business/motivation/argent) ; 3=cartoon jaune (fun/vlog/humour) ; 4=script néon (mode/lifestyle) ; 5=vert tech (gadgets/tuto) ; 6=docu ombre (voyage/docu) ; 8=machine à écrire (mystère/storytelling) ; 10=dégradé or (luxe/flex) ; 12=karaoké (podcast/monologue) ; 15=glitch (gaming/IA/tech) ; 18=serif cinéma (histoire haut de gamme) ; 20=néon (musique/edit) ; 21=horreur rouge empilé (creepy/peur). Prends le style qui rendrait le mieux pour CETTE vidéo\n"
        " \"highlight\": \"yellow|green|red|cyan\",  // couleur des mots forts\n"
        " \"keywords\": [\"mots EXACTS prononcés à mettre en avant (prix, chiffres, mots-chocs), copiés tels qu'ils sont dits\"],\n"
        " \"emojis\": [{\"word\": \"mot exact prononcé\", \"emoji\": \"un émoji\"}],  // 2-5 émojis sur ce qui s'illustre\n"
        " \"objects\": [{\"word\": \"mot exact\", \"emoji\": \"émoji OBJET\"}],  // 0-2 gros objets animés si un objet important est cité\n"
        " \"brands\": [{\"word\": \"mot exact\", \"slug\": \"slug minuscule\"}],  // 0-2 logos de marques CITÉES (netflix, tiktok, temu…)\n"
        " \"sfx\": [{\"word\": \"mot exact prononcé\", \"sound\": \"typing|click|pop|whoosh|cash|ding|impact|magic|glitch|camera|beep|applause|riser|boom\"}],  // 0-3 MAX, placés comme un monteur pro : un seul aux ENDROITS QUI COMPTENT — un chiffre/prix révélé (cash/ding), LA punchline (impact), une révélation (whoosh). Un bruitage est RARE, c'est ce qui lui donne son impact. Sur quelqu'un qui parle calmement : souvent AUCUN. Dans le doute -> liste vide\n"
        " \"audio_action\": \"keep|replace_music|replace_all\",  // que faire du SON d'origine ? keep=on le garde tel quel ; replace_music=GARDER la voix mais RETIRER la musique de fond de la vidéo (elle est mauvaise/gênante) pour mettre la nôtre ; replace_all=le son est nul/inutile, on le COUPE entièrement et on met de la musique\n"
        " \"add_music\": bool,  // PENSE COMME UN CRÉATEUR : demande-toi ce que l'OREILLE doit suivre. Quelqu'un PARLE -> l'oreille suit la VOIX : pas de musique par défaut ; un tapis discret SEULEMENT s'il amplifie l'émotion du récit. Personne ne parle -> la musique EST le moteur, obligatoire\n"
        " \"music_volume\": \"whisper|low|full\",  // le DOSAGE d'un pro : whisper = tapis à peine audible sous la voix (récit émotionnel) ; low = fond présent mais la voix domine largement ; full = musique moteur, UNIQUEMENT si personne ne parle\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic\",  // choisis comme un directeur artistique : la musique raconte la MÊME histoire que l'image (sujet + énergie + émotion). Une fille qui raconte sa journée -> rien, ou un tapis doux discret ; un edit voiture -> hype/epic ; une histoire touchante -> emotional. JAMAIS une ambiance vacances/plage sur quelqu'un qui parle sérieusement\n"
        " \"color_grade\": \"dark_moody|warm_luxury|cold_cinematic|vibrant_pop|bw_horror|vintage_warm|none\",  // le LOOK couleur final que TU choisis après avoir vu l'image (none = image déjà parfaite ou étalonnage risqué)\n"
        " \"transition\": \"fade|whip|zoom_blur|white_flash|swipe|scale_reveal|glitch|blur_wipe|shake|color_flash|dip_black\"  // la famille de transition qui colle au ton : whip/zoom_blur=énergique ; fade/scale_reveal=posé ; white_flash/color_flash=punchy ; glitch=tech/gaming ; shake=impact/hype ; blur_wipe=doux moderne ; dip_black=dramatique\n"
        "}"
    )
    # PRIORITÉ au canal payant (OpenRouter) ; le gratuit ne sert que de secours.
    res = or_generate(prompt, video_path=path, json_out=True) if OPENROUTER_KEY else None
    if not isinstance(res, dict) and GEMINI_KEY:
        uri = gemini_upload(path)
        if uri:
            res = gemini_generate(prompt, file_uri=uri, mime="video/mp4", json_out=True)
    if not isinstance(res, dict):
        return None
    res["engine"] = "gemini"
    res["frames_analyzed"] = "toute la vidéo"
    return res


STUDY_DNA = ("video_type", "niche", "sub_style_id", "highlight", "edit_intensity",
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
        " \"niche\": \"le SUJET en 1 mot simple minuscule (football, basketball, gym, edit, food, comedy, gaming, cars, fashion, motivation, lifestyle...)\",\n"
        " \"sub_style_id\": 0,  // 0 signature ; 2 Hormozi ; 3 cartoon ; 4 néon ; 5 tech ; 6 docu ; 8 machine à écrire ; 10 or ; 12 karaoké ; 15 glitch ; 18 serif ; 20 néon ; 21 horreur\n"
        " \"highlight\": \"yellow|green|red|cyan\",\n"
        " \"edit_intensity\": \"minimal|moderate|dynamic\",\n"
        " \"color_grade\": \"|dark_moody|warm_luxury|cold_cinematic|vibrant_pop|bw_horror|vintage_warm\",\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic ou vide\",\n"
        " \"signature_moves\": [\"2-3 TECHNIQUES SIGNATURE précises qui font le succès du montage, avec le MOMENT (ex: 'ralenti x0.3 pile sur le but', 'zoom punch à chaque punchline', 'texte qui claque au drop')\"],\n"
        " \"why_viral\": \"ce qui rend cette vidéo accrocheuse, 1 phrase\"}"
    )
    low = url.lower()
    try:
        if "youtu" in low:
            res = or_generate(prompt, video_url=url, json_out=True) if OPENROUTER_KEY else None
            if not isinstance(res, dict) and GEMINI_KEY:
                res = gemini_generate(prompt, file_uri=url, mime=None, json_out=True)
            return res if isinstance(res, dict) else None
        tmp = tempfile.mktemp(suffix=".mp4")
        download(url, tmp)
        try:
            res = or_generate(prompt, video_path=tmp, json_out=True) if OPENROUTER_KEY else None
            if not isinstance(res, dict) and GEMINI_KEY:
                uri = gemini_upload(tmp)
                if uri:
                    res = gemini_generate(prompt, file_uri=uri, mime="video/mp4", json_out=True)
            return res if isinstance(res, dict) else None
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
    except Exception as e:
        print("gemini_study_url:", e, file=sys.stderr)
        return None


def gemini_qc(path, duration, had_subs=False, intent=""):
    """CONTRÔLE QUALITÉ : Gemini regarde la vidéo AMÉLIORÉE (le rendu final) et
    dit s'il reste des problèmes : temps mort/logo restant, sous-titres qui
    couvrent le visage ou mal synchro, montage trop chargé, son déséquilibré.
    Renvoie {ok, score, remaining_dead_time[], subs_cover_face, too_busy, note}.
    None si pas de clé / échec."""
    if not (GEMINI_KEY or OPENROUTER_KEY):
        return None
    intent_txt = (f"\nINTENTIONS DU DIRECTEUR (ce qui DEVAIT être fait) : {intent}\n"
                  "Vérifie que chaque intention est VISIBLE/AUDIBLE dans le rendu et bien exécutée — "
                  "cite précisément l'outil raté dans 'note' (ex: 'émoji absent', 'son au mauvais moment').\n"
                  ) if intent else ""
    prompt = (
        "Tu es un directeur de post-production TRÈS exigeant. Voici une vidéo courte "
        f"({duration:.0f}s) qui vient d'être montée automatiquement pour devenir un reel "
        f"viral.{intent_txt} CONTRÔLE-la et dis ce qui ne va ENCORE pas. Réponds UNIQUEMENT ce JSON:\n"
        "{\"score\": 0-10,  // qualité globale du montage\n"
        " \"ok\": bool,  // true si publiable tel quel\n"
        " \"remaining_dead_time\": [{\"start\": s, \"end\": s}],  // temps morts/logos/écrans de fin qu'il RESTE à couper (secondes précises), [] si aucun\n"
        + (" \"subs_cover_face\": bool,  // les sous-titres cachent-ils le visage ou un élément important ?\n" if had_subs else "")
        + " \"too_busy\": bool,  // le montage est-il TROP chargé (trop d'effets/zooms/sons) ?\n"
        " \"lips_desync\": bool,  // GRAVE : la bouche est-elle désynchronisée avec la voix à un moment ? Regarde attentivement au milieu ET à la fin\n"
        " \"music_mismatch\": bool,  // la musique de fond jure-t-elle avec le contenu (ex: ambiance plage sur quelqu'un qui parle sérieusement) ?\n"
        " \"subject_cut\": bool,  // GRAVE : la personne principale est-elle COUPÉE ou hors champ à un moment (tête tronquée, seulement les épaules) ?\n"
        " \"needs\": [\"more_dynamic|calmer|voice_louder|replace_bad_music\"],  // ORDONNANCE : ce que la vidéo RÉCLAME pour atteindre 8+/10 — more_dynamic = punch-ins/mouvement en plus ; calmer = trop chargé, alléger ; voice_louder = la voix doit dominer le mix ; replace_bad_music = la musique D'ORIGINE est mauvaise/trop forte, la remplacer. Liste vide si rien\n"
        " \"note\": \"le problème principal en 1 phrase, ou 'RAS'\"}"
    )
    res = or_generate(prompt, video_path=path, json_out=True) if OPENROUTER_KEY else None
    if not isinstance(res, dict) and GEMINI_KEY:
        uri = gemini_upload(path)
        if uri:
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
        _vobj = []
        for _o in (vision.get("objects") or [])[:10]:
            _t = _o if isinstance(_o, str) else str((_o or {}).get("word") or (_o or {}).get("emoji") or "")
            if _t.strip():
                _vobj.append(_t.strip())
        sc = "; ".join(f"t={s.get('t', 0)}s {s.get('action', '')}" + (" (mouvement)" if s.get("motion") else "")
                       for s in (vision.get("scenes") or [])[:12])
        vis_txt = ("Analyse VISUELLE de TOUTE la vidéo (" + str(vision.get("frames_analyzed", "?")) + " images) :\n"
                   f"- Type détecté: {vision.get('video_type', '?')} · ambiance: {vision.get('mood', '?')} · "
                   f"personne filmée: {'oui' if vision.get('has_person') else 'non'}.\n"
                   f"- Résumé: {vision.get('summary', 'n/a')}\n"
                   f"- Ouverture captivante: {'oui' if vision.get('opening_captivating') else 'non'} "
                   f"({vision.get('opening_note', '')}).\n"
                   f"- Scènes: {sc or 'n/a'}\n"
                   f"- Objets visibles: {', '.join(_vobj) if _vobj else 'n/a'}\n"
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
Style: Hook,Anton,94,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,5,2,8,70,70,165,1

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
    # ACCROCHE TEXTE DÉSACTIVÉE à la demande du client (rendu jugé moche et
    # répétitif) — une version graphique premium sera conçue plus tard.
    if False and hook_text:
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
        start = max(0.0, start - 0.12)  # pré-roll : le texte tombe PILE sur la voix
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

    # DÉCOUPAGE DE MONTEUR PRO : une ligne = une PENSÉE, pas un compteur de mots.
    # 1) coupure aux vraies pauses de parole et à la ponctuation ;
    # 2) une ligne ne se termine JAMAIS sur un mot de liaison (« and », « my »,
    #    « de », « que »…) : on attend le mot qui complète le sens.
    LINKERS = {
        "and", "but", "or", "so", "to", "of", "my", "your", "the", "a", "an", "i",
        "in", "on", "at", "we", "is", "are", "was", "it", "that", "this", "for",
        "with", "as", "by", "be", "im", "i'm", "you", "he", "she", "they",
        "et", "ou", "de", "du", "des", "le", "la", "les", "un", "une", "je", "tu",
        "il", "elle", "on", "que", "qui", "dans", "pour", "avec", "mais", "donc",
        "si", "au", "aux", "ce", "cette", "mon", "ma", "mes", "ton", "ta", "tes",
        "son", "sa", "ses", "est", "sont", "sur", "en", "ne", "pas", "plus", "très",
    }

    def _linker(it):
        return str(it.get("word", "")).strip().strip(",.;:!?…").lower() in LINKERS

    def _sentence_end(it):
        t = str(it.get("word", "")).strip()
        return bool(t) and t[-1] in ".!?…"

    for i, w in enumerate(words):
        ws = float(w["start"])
        if prev_end is not None and ws - prev_end > 0.55:
            flush()  # vraie pause de parole -> nouvelle pensée
        is_kw = round(ws, 2) in kwhits
        if is_kw and group:
            flush()
        if not group:
            gfirst = i
        group.append(w)
        if is_kw:
            flush()
        elif _sentence_end(w) and len(group) >= 2:
            flush()  # fin de phrase (ponctuation) -> on coupe au sens
        elif len(group) >= chunk:
            # taille atteinte MAIS jamais finir sur une liaison : on retient la
            # ligne un ou deux mots de plus, le temps que la pensée se termine.
            if _linker(w) and len(group) < chunk + 2 and i + 1 < len(words):
                pass
            else:
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
        if not anim and not spec.get("kar"):
            # pop d'apparition (le texte « tombe » avec un léger rebond) : fini les
            # sous-titres figés — chaque style a du mouvement par défaut
            anim = "\\fscx74\\fscy74\\t(0,90,\\fscx104\\fscy104)\\t(90,150,\\fscx100\\fscy100)"
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
                       "white_flash", "chroma_flash", "dip_black",
                       "glitch", "blur_wipe", "shake", "color_flash")
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
    # noms « CapCut Tendance » (fr) -> familles implémentées
    "bogue": "glitch", "glitch_burst": "glitch",
    "floutage": "blur_wipe", "floutage_vertical": "blur_wipe", "sortie_avec_floutage": "blur_wipe",
    "secouement": "shake", "secouer": "shake", "secouement_x": "shake",
    "zoom_tremblant": "shake", "claquement": "shake",
    "flash_et_couleurs": "color_flash", "flash_en_couleur": "color_flash",
    "flash_avec_couleur": "color_flash", "fondu_lumineux": "color_flash",
    "flash_blanc": "white_flash", "flash_basique": "white_flash",
    "fondu_au_noir": "dip_black", "noir_basique": "dip_black",
    "melange": "fade", "clignement": "dip_black",
}
# Le son de CHAQUE transition (réflexe de monteur : une transition s'entend).
TR_SOUND = {"whip": "whoosh", "swipe": "whoosh", "fade": "whoosh", "zoom_blur": "whoosh",
            "scale_reveal": "magic", "white_flash": "camera",
            "chroma_flash": "glitch", "dip_black": "impact",
            "glitch": "glitch", "blur_wipe": "whoosh", "shake": "impact",
            "color_flash": "camera"}
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
    blur_windows = []   # fenêtres de flou (blur_wipe)
    shake_windows = []  # fenêtres de tremblement (shake)
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
        elif fam == "glitch":
            # « Bogue » : double burst de décalage RGB + micro-flash discret
            flashes += [("white", t, 0.35), ("white", t2, 0.35)]
            shift_windows += [t, t + 0.1, t2, t2 + 0.1]
        elif fam == "blur_wipe":
            # « Floutage » : l'image devient floue au moment de la coupure
            blur_windows += [t, t2]
        elif fam == "shake":
            # « Secouement » : la caméra tremble à la coupure + petit flash
            flashes += [("white", t, 0.30), ("white", t2, 0.30)]
            shake_windows += [t, t2]
        elif fam == "color_flash":
            # « Flash et couleurs » : flash teinté (couleur alternée par job)
            col = ("orange", "cyan", "magenta")[seed % 3]
            flashes += [(col, t, 0.75), (col, t2, 0.75)]
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
    if blur_windows:
        en = "+".join(f"between(t,{tb - 0.18:.3f},{tb + 0.18:.3f})" for tb in blur_windows)
        fc.append(f"{last}gblur=sigma=13:enable='{en}'[vbl]")
        last = "[vbl]"
    if shake_windows:
        # tremblement : micro-rotation rapide, uniquement dans les fenêtres (angle nul sinon)
        cond = "+".join(f"between(t,{tb - 0.05:.3f},{tb + 0.28:.3f})" for tb in shake_windows)
        fc.append(f"{last}rotate='if({cond}\\,0.02*sin(t*85)\\,0)':ow=iw:oh=ih:c=black[vsk]")
        last = "[vsk]"
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


_STYLE_INDEX = {"at": 0.0, "data": None}


def load_style_index():
    """L'ÉCOLE en résumé : liste compacte de TOUS les styles appris par niche
    (style-library), avec leurs techniques signature. Donnée à Gemini quand il
    dirige un montage. Rafraîchie toutes les 30 min."""
    now = time.time()
    if _STYLE_INDEX["data"] is not None and now - _STYLE_INDEX["at"] < 1800:
        return _STYLE_INDEX["data"]
    out = []
    try:
        st, raw = http("POST", f"{SB_URL}/storage/v1/object/list/{STYLE_BUCKET}",
                       sb_headers(), {"prefix": "", "limit": 100}, timeout=20)
        for it in json.loads(raw):
            name = it.get("name", "")
            if not name.endswith(".json") or name.startswith("_"):
                continue
            cat = name[:-5]
            prof = load_style_profile(cat)
            if not prof:
                continue
            entry = {"niche": cat}
            for k in ("edit_intensity", "color_grade", "sub_style_id", "music_mood", "cut_s"):
                if prof.get(k) not in (None, ""):
                    entry[k] = prof[k]
            moves = prof.get("signature_moves")
            if isinstance(moves, list) and moves:
                entry["techniques"] = moves[:3]
            out.append(entry)
    except Exception as e:
        print("load_style_index:", e, file=sys.stderr)
    _STYLE_INDEX["data"] = out
    _STYLE_INDEX["at"] = now
    return out


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

        # GÉNÉRATEUR IA (« Copier une vidéo ») : on ne télécharge pas,
        # on GÉNÈRE une nouvelle vidéo depuis une idée / un lien.
        if context.get("mode") == "generate":
            generate_video_job(job, work, steps)
            return
        if context.get("mode") == "blueprint":
            generate_blueprint_job(job, steps)
            return

        steps.start("dl", "Téléchargement de ta vidéo…")
        src = os.path.join(work, "src.mp4")
        urllib.request.urlretrieve(job["source_url"], src)
        facts = ffprobe_facts(src)
        if facts["duration"] > MAX_DURATION_S:
            raise RuntimeError(f"Vidéo trop longue ({facts['duration']:.0f}s) — max {MAX_DURATION_S:.0f}s pour l'amélioration.")
        edl = context.get("edl") if isinstance(context.get("edl"), dict) else None
        if facts.get("improved") and not edl:
            raise RuntimeError("Cette vidéo a DÉJÀ été améliorée par Skillora. Renvoie la vidéo originale "
                               "(sans les sous-titres incrustés) — l'améliorer deux fois créerait des doublons.")
        # Graine propre à ce job : deux vidéos identiques ne sortent pas identiques
        # (ordre des zooms, position de départ des sous-titres…)
        seed = int(str(job["id"]).replace("-", "")[:8], 16) & 0xFFFF
        steps.done("dl", f"{facts['duration']:.0f}s · {facts['width']}x{facts['height']}")

        # ═══ ÉDITEUR TIMELINE (bouton « Modifier ») : le créateur a décidé, on
        # exécute SES décisions au millimètre — aucune IA, 100 % déterministe. ═══
        if edl:
            cur = src
            dur = facts["duration"]
            # 1) COUPES : segments gardés [[début, fin], …]
            keeps = []
            for seg in (edl.get("keep") or []):
                try:
                    a, b = float(seg[0]), float(seg[1])
                    if b - a >= 0.15:
                        keeps.append((max(0.0, a), min(dur, b)))
                except Exception:
                    pass
            if keeps:
                keeps.sort()
                remove, cursor = [], 0.0
                for (a, b) in keeps:
                    if a > cursor + 0.03:
                        remove.append((cursor, a))
                    cursor = max(cursor, b)
                if cursor < dur - 0.03:
                    remove.append((cursor, dur))
                if remove:
                    steps.start("cut", "Découpe selon ta timeline…")
                    outc = os.path.join(work, "edl_cut.mp4")
                    if cut_spans(cur, outc, [], remove, dur, keep_pad=0.0):
                        cur = outc
                        facts = ffprobe_facts(cur)
                    steps.done("cut", f"{len(keeps)} segment(s) gardé(s) · {facts['duration']:.0f}s")
            # 1b) FORMAT : recadrage au ratio choisi (sujet centré)
            fmt = str(edl.get("format") or "")
            RATIOS = {"9:16": 9/16, "1:1": 1.0, "4:5": 4/5}
            if fmt in RATIOS:
                steps.start("frame", "Recadrage au format " + fmt + "…")
                ff = ffprobe_facts(cur); W, H = ff["width"], ff["height"]
                if W and H:
                    tr = RATIOS[fmt]
                    tw, th = (W, int(round(W/tr))) if (W/H) > tr else (int(round(H*tr)), H)
                    tw, th = min(tw, W)//2*2, min(th, H)//2*2
                    outf = os.path.join(work, "edl_fmt.mp4")
                    run(["ffmpeg", "-y", "-i", cur, "-vf",
                         f"crop={tw}:{th}:(iw-ow)/2:(ih-oh)/2,scale=1080:-2:flags=lanczos",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outf])
                    cur = outf; facts = ffprobe_facts(cur)
                steps.done("frame", "format " + fmt)
            # 2) ÉTALONNAGE choisi
            gname = str(edl.get("grade") or "")
            gchain = GRADES.get(gname.lower())
            if gchain:
                steps.start("effects", "Ton étalonnage…")
                outg = os.path.join(work, "edl_grade.mp4")
                run(["ffmpeg", "-y", "-i", cur, "-vf", gchain, "-c:v", "libx264",
                     "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outg])
                cur = outg
                steps.done("effects", gname)
            # 3) SOUS-TITRES : le style que TU as choisi
            if edl.get("subtitles"):
                steps.start("subs", "Sous-titres avec TON style…")
                mp3e = os.path.join(work, "edl.mp3")
                extract_audio_mp3(cur, mp3e)
                tre = transcribe(mp3e)
                ewords = (tre or {}).get("words") or []
                if ewords:
                    asse = os.path.join(work, "edl.ass")
                    with open(asse, "w", encoding="utf-8") as f:
                        f.write(build_ass(ewords, "", keywords=[], slide=None,
                                          sub_position=str(edl.get("sub_position") or "dynamic"),
                                          highlight=str(edl.get("highlight") or "yellow"),
                                          sub_style=str(edl.get("sub_mode") or "group"),
                                          style_id=int(edl.get("sub_style_id") or 0),
                                          layout=None, seed=seed))
                    outs = os.path.join(work, "edl_subs.mp4")
                    burn_subs(cur, outs, asse)
                    cur = outs
                steps.done("subs", f"{len(ewords)} mots · style {edl.get('sub_style_id') or 0}")
            # 4) TEXTES à l'écran, aux instants choisis
            texts = [t for t in (edl.get("texts") or [])
                     if isinstance(t, dict) and str(t.get("text") or "").strip()][:8]
            if texts:
                steps.start("texts", "Tes textes à l'écran…")
                vf = []
                for t in texts:
                    try:
                        tt = max(0.0, float(t.get("t") or 0))
                        te = float(t.get("end") or (tt + 2.5))
                        yp = min(0.85, max(0.05, float(t.get("y") or 0.16)))
                        xp = min(0.95, max(0.05, float(t.get("x") or 0.5)))
                        anim = str(t.get("anim") or "fade").lower()
                        txt = re.sub(r"[^0-9A-Za-zÀ-ÿ !?.€$%+\-]", "", str(t.get("text"))[:60]).strip()
                        if not txt:
                            continue
                        DI, DO = 0.3, 0.28  # durées d'entrée / sortie (keyframes)
                        # p = progression d'entrée (0->1), q = progression de sortie (1->0)
                        p = f"min(1,(t-{tt:.2f})/{DI})"
                        q = f"min(1,({te:.2f}-t)/{DO})"
                        xbase, ybase = f"(w-text_w)/2+w*{xp-0.5:.3f}", f"h*{yp:.2f}"
                        alpha = f"min({p},{q})"  # fondu par défaut (entrée + sortie)
                        xexpr, yexpr = xbase, ybase
                        if anim == "slide_up":
                            yexpr = f"{ybase}+h*0.08*(1-{p})"
                        elif anim == "slide_left":
                            xexpr = f"{xbase}-w*0.12*(1-{p})"
                        elif anim == "pop":
                            # léger rebond vertical à l'entrée (keyframe de position)
                            yexpr = f"{ybase}-h*0.03*(1-{p})*(1-{p})"
                        vf.append("drawtext=font=Anton:text=" + txt.replace(" ", "\\ ") +
                                  f":fontsize=76:fontcolor=white:borderw=6:bordercolor=black"
                                  f":alpha='{alpha}':x='{xexpr}':y='{yexpr}'"
                                  f":enable='between(t,{tt:.2f},{te:.2f})'")
                    except Exception:
                        pass
                if vf:
                    outt = os.path.join(work, "edl_texts.mp4")
                    run(["ffmpeg", "-y", "-i", cur, "-vf", ",".join(vf), "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "18", "-c:a", "copy", outt])
                    cur = outt
                steps.done("texts", f"{len(vf)} texte(s)")
            # 5) BRUITAGES aux instants choisis
            sfx_pts = []
            for x in (edl.get("sfx") or []):
                try:
                    sfx_pts.append((float(x.get("t")), str(x.get("sound") or "pop")))
                except Exception:
                    pass
            if sfx_pts:
                steps.start("fx", "Tes bruitages…")
                outx = os.path.join(work, "edl_sfx.mp4")
                if mix_sfx_at(cur, outx, sfx_pts, work):
                    cur = outx
                steps.done("fx", f"{len(sfx_pts)} son(s) posé(s)")
            # 6) MUSIQUE : bibliothèque ou fichier uploadé, au volume choisi
            mus = edl.get("music") if isinstance(edl.get("music"), dict) else None
            music_path = None
            mdb = -21
            if mus:
                mdb = {"whisper": -30, "low": -21, "full": -14}.get(str(mus.get("volume") or "low"), -21)
                try:
                    if mus.get("name"):
                        music_path = os.path.join(work, "edl_music")
                        download(f"{SB_URL}/storage/v1/object/public/{MUSIC_BUCKET}/" +
                                 urllib.parse.quote(str(mus["name"])), music_path)
                    elif str(mus.get("url") or "").startswith(SB_URL + "/storage/v1/object/public/post-media/"):
                        music_path = os.path.join(work, "edl_music")
                        download(str(mus["url"]), music_path)
                except Exception as e:
                    print("edl music:", e, file=sys.stderr)
                    music_path = None
            steps.start("audio", "Mixage du son…")
            outm = os.path.join(work, "edl_final.mp4")
            loudnorm(cur, outm, music_path=music_path, music_gain_db=mdb,
                     music_foreground=bool(mus and mus.get("foreground")))
            cur = outm
            steps.done("audio", "ta musique mixée sous la voix" if music_path else "son normalisé")
            # 7) ENVOI
            steps.start("up", "Envoi de ta version…")
            url = upload_result(job, cur)
            steps.done("up")
            update_job(job["id"], {"status": "done", "result_url": url,
                                   "finished_at": "now()", "steps": steps.items})
            print("Job ÉDITEUR", job["id"], "terminé:", url)
            return

        # LES YEUX : Gemini regarde TOUTE la vidéo d'origine (image + son) et
        # renvoie sa compréhension complète + les temps morts PRÉCIS. Sur la vidéo
        # ORIGINALE (les timestamps seront reprojetés après la coupe).
        gem = None
        if GEMINI_KEY or OPENROUTER_KEY:
            steps.start("see", "Gemini regarde toute ta vidéo…")
            # MÉMOIRE : le style des vidéos VIRALES de ce créateur (s'il en a)
            user_styles = load_user_styles(job.get("user_id"))
            try:
                gem = gemini_analyze_video(src, facts["duration"], user_styles=user_styles or None,
                                           style_library=load_style_index() or None)
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
        # + écrans d'une couleur unie (noir/vert/blanc…) : morts par définition
        deads += flat_spans(src)
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
        # MODE SOBRE : si Gemini n'a pas VU la vidéo, on s'interdit les décorations
        # risquées (émojis, objets, logos, b-roll, texte 3D). Un montage propre et
        # sobre vaut toujours mieux qu'un montage décoré à l'aveugle.
        if not gem:
            for k in ("emojis", "objects", "brands", "broll_keywords", "bg_text"):
                plan.pop(k, None)
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
            for k in ("sub_style_id", "highlight", "sub_style"):
                if gem.get(k) not in (None, ""):
                    plan[k] = gem[k]
            for k in ("keywords", "emojis", "objects", "brands", "sfx"):
                if isinstance(gem.get(k), list):
                    plan[k] = gem[k]  # Gemini décide (liste vide = rien, volontaire)
            # ceinture : les mots-clés doivent être des TEXTES, même si l'IA renvoie des fiches
            plan["keywords"] = [x if isinstance(x, str) else str((x or {}).get("word") or "")
                                for x in (plan.get("keywords") or []) if x]
            for k in ("color_grade", "transition"):
                if str(gem.get(k) or "").strip().lower() not in ("", "none"):
                    plan[k] = str(gem[k]).strip().lower()
            if str(gem.get("color_grade") or "").strip().lower() == "none":
                plan["color_grade"] = "__none__"  # décision explicite : PAS d'étalonnage
            if "bg_text" in gem:
                plan["bg_text"] = str(gem.get("bg_text") or "")  # texte derrière la personne
            # MUSIQUE : Gemini a le contrôle TOTAL (fini la musique de plage forcée).
            plan["music_mood"] = str(gem.get("music_mood") or "") if gem.get("add_music") else ""
            plan["music_volume"] = str(gem.get("music_volume") or "").lower()
            # DOSAGE PRO (code) : sur quelqu'un qui PARLE face caméra, une musique
            # RYTHMÉE/ambiance (chill, hype, funny…) est hors sujet -> retirée. Un
            # tapis ÉMOTIONNEL (emotional/cinematic/dark) reste permis, mais à
            # peine audible (whisper) et il sera ducké sous la voix. La voix reste
            # le contenu — c'est comme ça qu'un vrai créateur mixe un récit parlé.
            if (str(gem.get("audio_type") or "") == "voice"
                    and str(gem.get("video_type") or "") in ("talk_facecam", "vlog", "story")
                    and str(gem.get("edit_intensity") or "") != "dynamic"):
                if str(plan.get("music_mood") or "") not in ("emotional", "cinematic", "dark", ""):
                    plan["music_mood"] = ""
                else:
                    plan["music_volume"] = "whisper"
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
        # STYLE APPRIS : d'abord le style de la NICHE précise (football, gym, edit…)
        # apprise par les agents, sinon celui du type de montage. Il PRIME sur les
        # réglages codés en dur.
        vniche = re.sub(r"[^a-z0-9_]", "", str((vision or {}).get("niche") or "").lower())
        learned = (load_style_profile(vniche) if vniche else None) or load_style_profile(vtype)
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
            gsid = (gem or {}).get("sub_style_id")
            if learned.get("sub_style_id") is not None and gsid in (None, "", 0):
                # Gemini n'a pas fait de vrai choix de style -> celui appris des
                # vidéos VIRALES de la niche (fini le style par défaut à répétition)
                plan["sub_style_id"] = learned["sub_style_id"]
            if not gem:
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

        # 1b. SOUS-TITRES DÉJÀ INCRUSTÉS (repérés par Gemini) : PAS de recadrage-zoom
        # (ça dégrade la qualité de l'image — refusé). En test, on pose nos sous-titres
        # propres par-dessus. PRÉVU : quand les sous-titres d'origine sont mauvais,
        # l'app demandera au créateur d'envoyer une version SANS sous-titres incrustés,
        # et le montage repartira de cette version propre.
        bsub = str((gem or {}).get("burned_subs") or "none").lower()
        if bsub in ("bottom", "top", "middle"):
            steps.skip("subclean", "Sous-titres d'origine",
                       f"détectés ({bsub}) — qualité d'image préservée, les nôtres posés proprement")

        # 1c. BANDES NOIRES : un film horizontal collé dans un cadre vertical n'est
        # PAS une vraie vidéo verticale. On extrait d'abord l'IMAGE RÉELLE, puis le
        # recadrage intelligent 9:16 (escalier + track) fait son vrai travail.
        try:
            cdrop = detect_content_crop(cur)
        except Exception:
            cdrop = None
        if cdrop:
            cw, ch, cx, cy = cdrop
            big_bars = (ch < facts["height"] * 0.82) or (cw < facts["width"] * 0.82)
            sane = (cw * ch) > (facts["width"] * facts["height"] * 0.25)
            if big_bars and sane:
                steps.start("letterbox", "Retrait des bandes noires…")
                outlb = os.path.join(work, "content.mp4")
                try:
                    run(["ffmpeg", "-y", "-i", cur, "-vf", f"crop={cw}:{ch}:{cx}:{cy}",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                         "-c:a", "copy", outlb])
                    cur = outlb
                    facts = ffprobe_facts(cur)
                    plan["reframe"] = True  # l'image réelle est horizontale -> recadrage intelligent
                    steps.done("letterbox", f"image réelle {cw}x{ch} extraite — le recadrage travaille enfin sur la VRAIE image")
                except Exception as e:
                    print("letterbox:", e, file=sys.stderr)
                    steps.done("letterbox", "détection incertaine, cadre conservé")

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
                # pas de pop automatique sur chaque émoji : réservé au montage dynamic
                if intensity_mode == "dynamic":
                    sfx_ev += [(t, "pop") for (t, _p, _y) in emo
                               if not any(abs(t - e[0]) < 0.4 for e in sfx_ev)]
                # whoosh à l'ENTRÉE et à la SORTIE de chaque objet animé
                for (ot, _p) in objs:
                    sfx_ev += [(ot, "whoosh")]  # un seul son à l'entrée, pas à la sortie
                # Chaque transition de b-roll a SON bruitage (flash->appareil photo,
                # chromatique->glitch, noir->impact, balayage->whoosh, reveal->magic)
                tr_snd = TR_SOUND.get(br_fam)
                if tr_snd:
                    for bc in broll_cuts:
                        sfx_ev += [(bc, tr_snd)]  # un seul son par plan inséré
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
                    if overlay_objects(cur, outo, objs, seed=seed, face_y=(vision or {}).get("face_y")):
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
                    if overlay_objects(cur, outo, objs, seed=seed, face_y=(vision or {}).get("face_y")):
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
                dets = []
                recooked = False
                for rnd in range(3):  # LE CHEF GOÛTE JUSQU'À 3 FOIS : goûte -> corrige -> regoûte
                    dur_qc = ffprobe_facts(cur)["duration"]
                    if dur_qc <= 2:
                        break
                    steps.start("gqc", f"Gemini goûte le résultat (passage {rnd + 1})…")
                    _intent = ("sous-titres style " + str(plan.get("sub_style_id")) +
                               " (" + str(plan.get("sub_style") or "group") + ")" +
                               ", transition " + str(plan.get("transition") or "-") +
                               ", étalonnage " + str(plan.get("color_grade") or "-") +
                               ", musique " + (str(plan.get("music_mood") or "aucune")) +
                               ", " + str(len(plan.get("sfx") or [])) + " bruitage(s), " +
                               str(len(plan.get("emojis") or [])) + " émoji(s)")
                    qcg = gemini_qc(cur, dur_qc, had_subs=bool(words), intent=_intent)
                    if not qcg:
                        break
                    sc = qcg.get("score")
                    fixed = []
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
                        outqc = os.path.join(work, f"qc_fix{rnd}.mp4")
                        if cut_spans(cur, outqc, [], rem, dur_qc):
                            cur = outqc
                            fixed.append(f"{sum(e - s for s, e in rem):.0f}s de temps mort")
                    # b) RE-CUISSON si trop chargé / note basse : version épurée (une seule fois)
                    too_busy = bool(qcg.get("too_busy"))
                    desync = bool(qcg.get("lips_desync"))
                    if desync:
                        dets.append("⚠ désynchro détectée par le chef")
                    if bool(qcg.get("subject_cut")):
                        dets.append("⚠ sujet coupé/hors champ signalé par le chef")
                    needs = set(str(x) for x in (qcg.get("needs") or []))
                    # ordonnances AUDIO : appliquées au mixage final (après la boucle)
                    if "voice_louder" in needs or "replace_bad_music" in needs:
                        plan["_qc_quiet_music"] = True
                        if "replace_bad_music" in needs:
                            plan["_qc_replace_music"] = True
                        fixed.append("mix voix d'abord programmé")
                    low = (isinstance(sc, (int, float)) and sc < 7) or desync
                    want_dyn = "more_dynamic" in needs and bool(words)
                    # « PLUS DYNAMIQUE » : on ajoute des punch-ins PAR-DESSUS la vidéo
                    # DÉJÀ cuisinée (émojis, sons, b-roll, effets CONSERVÉS). L'ancienne
                    # version repartait de la base nue et JETAIT tout le travail — c'est
                    # pour ça que les vidéos sortaient déshabillées.
                    if want_dyn and not recooked:
                        try:
                            outz = os.path.join(work, "boost_dyn.mp4")
                            if zoom_punch(cur, outz, words, ffprobe_facts(cur)["has_audio"],
                                          work, seed=seed + 1):
                                cur = outz
                                recooked = True
                                fixed.append("dynamisé : punch-ins ajoutés (tout le montage conservé)")
                        except Exception as ez:
                            print("boost dyn:", ez, file=sys.stderr)
                    # « TROP CHARGÉ » uniquement : là oui, on repart d'une base propre.
                    if too_busy and not recooked and ffprobe_facts(base_reframed)["duration"] > 1:
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
                            recooked = True
                            fixed.append("re-cuisiné en version épurée")
                        except Exception as e:
                            print("recook:", e, file=sys.stderr)
                    note = str(qcg.get("note") or "").strip()
                    det = (f"{sc}/10" if sc is not None else "vérifié")
                    if fixed:
                        det += " · corrigé : " + ", ".join(fixed)
                    elif note and note.upper() not in ("RAS", "R.A.S", "RAS."):
                        det += f" · {note}"
                    dets.append(det)
                    satisfied = (bool(qcg.get("ok")) or (isinstance(sc, (int, float)) and sc >= 8)) and not desync
                    if satisfied or not fixed:
                        break  # le chef est content, ou plus rien à corriger : inutile de regoûter
                steps.done("gqc", " → ".join(dets) if dets else "vérification indisponible")
            except Exception as e:
                print("gqc:", e, file=sys.stderr)
                steps.done("gqc", "vérification indisponible")

        # 5. SON : Gemini décide quoi faire du son d'origine.
        #    keep = on garde ; replace_music = on GARDE la voix mais on retire la
        #    musique de fond gênante (isolation ElevenLabs) et on met la nôtre ;
        #    replace_all = son nul -> on le COUPE et on met de la musique.
        steps.start("audio", "Mixage du son…")
        audio_action = str((gem or {}).get("audio_action") or "keep")
        # ordonnance du chef : musique d'origine mauvaise/trop forte -> on la remplace
        if plan.get("_qc_replace_music") and audio_action == "keep":
            audio_action = "replace_music"
            if not str(plan.get("music_mood") or ""):
                plan["music_mood"] = "cinematic"
        music = pick_music(str(plan.get("music_mood") or ""))
        # dosage décidé par le directeur : whisper = tapis discret, low = fond, full = moteur
        music_db = {"whisper": -30, "low": -21, "full": -14}.get(
            str(plan.get("music_volume") or "").lower(), -21)
        if plan.get("_qc_quiet_music"):
            music_db = min(music_db, -28)  # ordonnance du chef : la voix domine
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
                    loudnorm(novideo, out, music_path=music, music_gain_db=music_db, music_foreground=False)
                    cur = out
                    iso_ok = True
                    audio_note = "voix isolée · musique remplacée"
            except Exception as e:
                print("replace_music:", e, file=sys.stderr)
            if not iso_ok:
                loudnorm(cur, out, music_path=music, music_gain_db=music_db, music_foreground=music_fg and not words)
                cur = out
                audio_note = "musique ajoutée (isolation indispo)"
        else:
            loudnorm(cur, out, music_path=music, music_gain_db=music_db, music_foreground=music_fg and not words)
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

# DISJONCTEUR « les clients d'abord » : si Gemini refuse une étude (quota du niveau
# gratuit), l'ÉCOLE se met en pause 6 h pour garder tout le quota restant aux
# montages des clients. Sans ça, une grosse file d'étude peut vider le quota du
# jour et le montage suivant d'un client se fait « à l'aveugle » (vécu le 10/07).
GEMINI_REST_S = 6 * 3600
_gemini_rest_until = 0.0

# BUDGET QUOTIDIEN de l'école. Avec OpenRouter (payant, ~1 centime/étude) :
# 150/jour (~1,50 $/jour au pire) — assez pour avaler une récolte « lance tout »
# complète AVANT que les liens TikTok expirent (~24 h). Sans : 8/jour pour
# préserver le quota GRATUIT de Gemini pour les montages des clients.
STUDY_BUDGET_PER_DAY = 300 if OPENROUTER_KEY else 8


def _study_budget_left():
    """Nombre d'études encore autorisées aujourd'hui (état persisté côté storage)."""
    try:
        st = _read_style_json(STYLE_BUCKET, "_scout_state.json") or {}
        today = time.strftime("%Y-%m-%d")
        if st.get("study_day") != today:
            return STUDY_BUDGET_PER_DAY
        return max(0, STUDY_BUDGET_PER_DAY - int(st.get("study_count") or 0))
    except Exception:
        return STUDY_BUDGET_PER_DAY


def _study_budget_spend():
    """Note qu'une étude a été consommée aujourd'hui."""
    try:
        st = _read_style_json(STYLE_BUCKET, "_scout_state.json") or {}
        today = time.strftime("%Y-%m-%d")
        if st.get("study_day") != today:
            st["study_day"], st["study_count"] = today, 0
        st["study_count"] = int(st.get("study_count") or 0) + 1
        _write_style_json(STYLE_BUCKET, "_scout_state.json", st)
    except Exception as e:
        print("study budget:", e, file=sys.stderr)


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
    # techniques signature : on accumule les meilleures trouvailles (8 max)
    moves = prof.get("signature_moves") if isinstance(prof.get("signature_moves"), list) else []
    for m in (dna.get("signature_moves") or []):
        m = str(m).strip()
        if m and m not in moves:
            moves.append(m)
    prof["signature_moves"] = moves[-8:]
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


def _deep_media(o, depth=0):
    """Cherche un lien mp4 n'importe où dans une réponse (video_versions, playable_url…)."""
    if depth > 6:
        return None
    if isinstance(o, list):
        for it in o:
            r = _deep_media(it, depth + 1)
            if r:
                return r
        return None
    if isinstance(o, dict):
        vv = o.get("video_versions")
        if isinstance(vv, list) and vv and isinstance(vv[0], dict) and str(vv[0].get("url", "")).startswith("http"):
            return vv[0]["url"]
        for k, v in o.items():
            if isinstance(v, str) and v.startswith("http") and re.search(
                    r"playable_url|^video_url$|browser_native_hd|browser_native_sd", k, re.I):
                return v
        for v in o.values():
            if isinstance(v, (dict, list)):
                r = _deep_media(v, depth + 1)
                if r:
                    return r
    return None


def sv_fresh_media(page_url):
    """Redemande à SociaVault un lien mp4 FRAIS (les liens CDN TikTok/Instagram
    expirent au bout de quelques heures). None si pas de clé / échec."""
    if not SOCIAVAULT_KEY:
        return None
    if "tiktok.com" in page_url:
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
            return _deep_media(d)
        except Exception as e:
            print("sv_fresh_media tiktok:", e, file=sys.stderr)
        return None
    if "instagram.com" in page_url:
        try:
            req = urllib.request.Request(
                "https://api.sociavault.com/v1/scrape/instagram/post-info?url=" + urllib.parse.quote(page_url, safe=""),
                headers={"X-API-Key": SOCIAVAULT_KEY})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            return _deep_media(data.get("data") or data)
        except Exception as e:
            print("sv_fresh_media instagram:", e, file=sys.stderr)
    return None


def _study_fail(row, msg):
    """Échec d'étude : on REMET EN FILE (3 essais max) — souvent c'est juste le quota
    Gemini gratuit qui demande de patienter, pas une vraie erreur."""
    attempts = int(row.get("attempts") or 0) + 1
    if attempts < 3:
        mark_winner(row["id"], {"status": "queued", "attempts": attempts, "error": msg[:200]})
        print(f"Éclaireur: étude reportée (essai {attempts}/3): {msg[:80]}")
    else:
        mark_winner(row["id"], {"status": "error", "attempts": attempts,
                                "error": msg[:500], "finished_at": "now()"})


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
                def _is_video(p):
                    # les liens expirés renvoient des pages d'erreur parfois > 50 Ko :
                    # seul ffprobe fait foi (vraie vidéo lisible, durée > 0,5 s)
                    try:
                        return os.path.getsize(p) > 50000 and ffprobe_facts(p)["duration"] > 0.5
                    except Exception:
                        return False
                got = False
                for cand in candidates:
                    try:
                        download(cand, tmp)
                        if _is_video(tmp):
                            got = True
                            break
                    except Exception:
                        pass
                if not got:
                    fresh = sv_fresh_media(url)
                    if fresh:
                        download(fresh, tmp)
                        got = _is_video(tmp)
                if not got:
                    raise RuntimeError("téléchargement impossible (lien expiré ?)")
                dur = ffprobe_facts(tmp)["duration"]
                gem = gemini_analyze_video(tmp, dur)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        if not gem or not isinstance(gem, dict):
            global _gemini_rest_until
            _gemini_rest_until = time.time() + GEMINI_REST_S
            _study_fail(row, "Gemini n'a pas pu analyser (quota ? on réessaiera).")
            print("Éclaireur: quota Gemini atteint -> école en pause 6 h (le quota restant est réservé aux clients).")
            return
        niche = re.sub(r"[^a-z0-9_]", "",
                       str(row.get("niche") or gem.get("niche") or gem.get("video_type") or "other").lower()) or "other"
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
        _study_fail(row, str(e))


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
    # clé "v2" : les niches ont été élargies -> on relance une exploration tout de suite
    if now - float(state.get("last_explore_v2", 0)) > _EXPLORE_EVERY_S:
        _invoke_edge("scout-explore")
        state["last_explore_v2"] = now
        changed = True
    if changed:
        try:
            _write_style_json(STYLE_BUCKET, "_scout_state.json", state)
        except Exception as e:
            print("scout_tick state:", e, file=sys.stderr)


def recover_orphans():
    """Au démarrage : un seul worker tourne, donc tout job encore 'processing'
    est un ORPHELIN (le worker a été redémarré en plein montage). On le remet
    en file : il repart tout seul, et le client n'est plus jamais bloqué par
    « une amélioration est déjà en cours »."""
    try:
        http("PATCH", SB_URL + "/rest/v1/video_jobs?status=eq.processing",
             sb_headers({"Prefer": "return=minimal"}),
             {"status": "queued", "started_at": None})
    except Exception as e:
        print("recover_orphans:", e, file=sys.stderr)


# ==========================================================================
#  GÉNÉRATEUR IA — le produit « colle un lien / donne une idée -> on te
#  reproduit TA version dans ce format viral ». Pipeline en 4 temps :
#    1. LE DIRECTEUR (ci-dessous)   : idée/lien -> plan de génération JSON
#    2. LES IMAGES (Nano Banana 2)  : chaque scène -> image nette + cohérence
#    3. L'ANIMATION (image -> vidéo): Veo3 / Kling 3.0 / Veo Lite par scène
#    4. LE MONTAGE FINAL            : clips + voix ElevenLabs + SFX + subs
# ==========================================================================

# Modèle image (on génère d'abord les images, puis on les anime)
OR_IMAGE_MODEL = "google/gemini-3.1-flash-image"  # « Nano Banana 2 »

# Générateurs vidéo (image -> vidéo) via OpenRouter. Le directeur choisit la
# clé selon le besoin ; on ne garde QUE des clés valides. Chaque modèle a une
# durée MAX par génération : on peut donc mettre plusieurs plans dans une
# seule génération (batch) puis découper -> plus rapide et moins cher.
OR_VIDEO_MODELS = {
    "veo_lite": "google/veo-3.1-fast",   # le moins cher (voix off / faceless)
    "veo3":     "google/veo-3.1",        # perso qui parle FR (voix + lip-sync)
    "kling3":   "kwaivgi/kling-v3.0-std", # perso qui parle EN/ES (top lip-sync)
    "wan":      "alibaba/wan-2.7",        # histoires / plans larges
}
# Durée max générable d'un coup, par modèle (secondes) — endpoint async
# POST /api/v1/videos, on soumet puis on interroge (poll) jusqu'à completed.
OR_VIDEO_MAXLEN = {"veo_lite": 8, "veo3": 8, "kling3": 10, "wan": 6}
_LAST_VIDEO_ERR = ""  # dernière erreur de l'API vidéo (remontée jusqu'au job)

# Bornes de sécurité du plan
GEN_MIN_CLIP_S = 4
GEN_MAX_CLIP_S = 8
GEN_MAX_TOTAL_S = 120


def _gen_model_for(talking, language, proposed):
    """Règle langue -> modèle pour un plan où un personnage PARLE :
    français -> Veo3 ; anglais/espagnol -> Kling 3.0. Sinon on respecte le
    choix du directeur (sinon le moins cher)."""
    if talking:
        lang = (language or "").lower()[:2]
        if lang == "fr":
            return "veo3"
        if lang in ("en", "es"):
            return "kling3"
    p = str(proposed or "").strip()
    return p if p in OR_VIDEO_MODELS else "veo_lite"


def _gen_clamp_scene(sc):
    """Une SCÈNE = un DÉCOR = UNE image. On garde le prompt d'image et la liste
    des personnages présents (pour la cohérence)."""
    if not isinstance(sc, dict):
        return None
    sc["image_prompt"] = str(sc.get("image_prompt") or "").strip()
    chars = sc.get("characters")
    sc["characters"] = [str(x) for x in chars] if isinstance(chars, list) else []
    return sc if sc["image_prompt"] else None


def _gen_clamp_shot(sh, language, n_scenes):
    """Un PLAN (shot) = un CLIP animé qui réutilise l'image d'une scène."""
    if not isinstance(sh, dict):
        return None
    try:
        dur = float(sh.get("duration_s") or 5)
    except Exception:
        dur = 5.0
    sh["duration_s"] = max(GEN_MIN_CLIP_S, min(GEN_MAX_CLIP_S, dur))
    try:
        sc = int(sh.get("scene"))
    except Exception:
        sc = 0
    sh["scene"] = sc if 0 <= sc < n_scenes else 0
    sh["talking"] = bool(sh.get("talking"))
    sh["video_model"] = _gen_model_for(sh["talking"], language, sh.get("video_model"))
    sh["camera"] = str(sh.get("camera") or "").strip()
    sh["motion_prompt"] = str(sh.get("motion_prompt") or "").strip()
    sh["speaker"] = str(sh.get("speaker") or "").strip()
    sh["spoken_text"] = str(sh.get("spoken_text") or "").strip()
    sfx = sh.get("sfx")
    sh["sfx"] = [str(x) for x in sfx] if isinstance(sfx, list) else []
    caps = sh.get("captions")
    sh["captions"] = [str(x) for x in caps] if isinstance(caps, list) else []
    return sh


def _dl_video(url):
    """Télécharge une vidéo depuis un lien de PAGE (TikTok, Instagram, Reels…)
    via yt-dlp — indispensable car Gemini ne peut pas « lire » une page web,
    seulement une vraie vidéo. Renvoie un chemin mp4, ou None."""
    if not url:
        return None
    d = tempfile.mkdtemp(prefix="dl-")
    ytdlp = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
    try:
        run([ytdlp, "--no-playlist", "--merge-output-format", "mp4",
             "-f", "mp4/bv*+ba/best", "-o", os.path.join(d, "v.%(ext)s"), url],
            timeout=240)
        cand = [os.path.join(d, f) for f in os.listdir(d)]
        cand = [c for c in cand if os.path.getsize(c) > 10000]
        if cand:
            return max(cand, key=os.path.getsize)
    except Exception as e:
        print("_dl_video:", e, file=sys.stderr)
    return None


def _analyze_source(prompt, source_url):
    """Fait REGARDER la vidéo à Gemini : télécharge d'abord les liens de page
    (TikTok/Insta…), sinon passe l'URL directe / YouTube telle quelle."""
    su = (source_url or "").lower()
    direct = su.endswith((".mp4", ".mov", ".webm", ".m4v")) or "/storage/v1/object/public/" in su
    youtube = "youtube.com" in su or "youtu.be" in su
    local = None
    if source_url and not direct and not youtube:
        local = _dl_video(source_url)
    try:
        if local:
            return or_generate(prompt, video_path=local, json_out=True)
        return or_generate(prompt, video_url=source_url, json_out=True)
    finally:
        if local and os.path.exists(local):
            try:
                os.remove(local)
            except Exception:
                pass


def gen_director_plan(idea, source_url=None):
    """LE CERVEAU / DIRECTEUR. Regarde la vidéo de référence PLAN PAR PLAN (ou
    part d'une idée) et renvoie un PLAN structuré à DEUX niveaux :
      - characters : les personnages (id + description réutilisable) ;
      - scenes     : les DÉCORS -> UNE image générée par scène ;
      - shots      : les PLANS animés ; chaque plan RÉUTILISE l'image d'une
                     scène (champ 'scene') -> une seule image peut servir à
                     plusieurs plans (gros plan, contrechamp, plan large…).
    Renvoie None si pas de clé / échec."""
    if not OPENROUTER_KEY:
        return None
    idea = (idea or "").strip()
    charter = (
        "Tu es un DIRECTEUR VIDÉO IA de niveau studio. On te donne une vidéo "
        "(ou une idée) et tu dois la REPRODUIRE FIDÈLEMENT sous forme d'une "
        "nouvelle version générée par IA (images puis animation).\n\n"
        "REGARDE la vidéo de référence PLAN PAR PLAN : qui est présent, QUI "
        "parle et QUAND, ce que chacun dit MOT POUR MOT, les mouvements et "
        "gestes exacts, les angles de caméra, l'enchaînement des plans, le "
        "décor, la lumière. Reproduis CES actions et CET enchaînement le plus "
        "fidèlement possible — c'est une COPIE, sois précis.\n\n"
        "DEUX NIVEAUX (essentiel pour la qualité ET le coût) :\n"
        "• SCÈNES = des DÉCORS. On génère UNE image par scène. Une même scène "
        "(donc UNE seule image) peut servir à PLUSIEURS plans : gros plan sur "
        "un perso, puis CONTRECHAMP sur l'autre, plan large, etc. Ne crée une "
        "NOUVELLE scène (nouvelle image) QUE si le décor OU les personnages "
        "changent vraiment. Regroupe un MAXIMUM de plans sur PEU de scènes.\n"
        "• PLANS (shots) = les CLIPS animés. Chaque plan réutilise l'image "
        "d'une scène (champ 'scene' = l'index de la scène) et l'anime avec son "
        "angle de caméra + son mouvement + ce qui est dit. PLUSIEURS plans "
        "pointent souvent vers la MÊME scène.\n\n"
        "COHÉRENCE : liste les PERSONNAGES dans 'characters' (un id court + une "
        "description TRÈS précise et réutilisable : visage, âge, cheveux, "
        "tenue, couleurs). Réutilise ces MÊMES personnages d'une scène à "
        "l'autre pour qu'ils restent IDENTIQUES. Dans chaque scène, indique "
        "quels personnages apparaissent (leurs id).\n\n"
        "AUDIO — une seule branche :\n"
        "• 'native' : un personnage parle À L'IMAGE -> pour CHAQUE plan parlé "
        "mets talking=true, speaker=l'id du perso qui parle, spoken_text=le "
        "TEXTE EXACT qu'il dit (mot pour mot), motion_prompt=ses gestes et son "
        "expression. RÈGLE LANGUE : français -> Veo3 ; anglais/espagnol -> "
        "Kling (indique juste talking=true et la langue).\n"
        "• 'voiceover' : narration off, on ne voit personne parler -> "
        "talking=false partout, voix off ElevenLabs (voiceover_script complet) "
        "+ musique + effets.\n\n"
        "Chaque plan dure 4 à 8 s. Vise 4 à 8 PLANS répartis sur 3 à 5 SCÈNES "
        "(donc seulement 3 à 5 images).\n\n"
        "RENDS UNIQUEMENT ce JSON (aucun texte autour) :\n"
        "{\n"
        "  \"video_type\": \"talking_head|conversation|story|faceless|product|other\",\n"
        "  \"audio_mode\": \"native|voiceover\",\n"
        "  \"language\": \"fr|en|es|...\",\n"
        "  \"title\": \"...\",\n"
        "  \"hook\": \"la 1re phrase qui accroche\",\n"
        "  \"voiceover_script\": \"texte complet si voiceover, sinon vide\",\n"
        "  \"music_mood\": \"aucune|douce|epique|tendue|joyeuse|...\",\n"
        "  \"characters\": [{\"id\": \"c1\", \"description\": \"desc precise reutilisable\"}],\n"
        "  \"scenes\": [\n"
        "    {\"index\": 0, \"image_prompt\": \"decor + personnages, nette et detaillee\",\n"
        "     \"characters\": [\"c1\", \"c2\"]}\n"
        "  ],\n"
        "  \"shots\": [\n"
        "    {\"index\": 0, \"scene\": 0, \"duration_s\": 5,\n"
        "     \"camera\": \"gros plan sur c1\",\n"
        "     \"motion_prompt\": \"mouvement/gestes/camera precis, fideles a la video\",\n"
        "     \"talking\": true, \"speaker\": \"c1\", \"spoken_text\": \"ce que c1 dit, mot pour mot\",\n"
        "     \"video_model\": \"veo3\", \"sfx\": [], \"captions\": [\"bout de sous-titre\"]}\n"
        "  ],\n"
        "  \"total_duration_s\": 30\n"
        "}\n"
    )
    if source_url:
        prompt = (charter + "\nVIDÉO DE RÉFÉRENCE à reproduire fidèlement "
                  "(regarde-la plan par plan) — consigne du client : "
                  + (idea or "reproduis ce format à l'identique."))
        plan = _analyze_source(prompt, source_url)
    else:
        prompt = charter + "\nIDÉE DU CLIENT : " + (idea or "surprends-moi.")
        plan = or_generate(prompt, json_out=True)
    if not isinstance(plan, dict):
        return None
    language = str(plan.get("language") or "").strip() or "fr"
    plan["language"] = language
    # Personnages
    chars = plan.get("characters")
    plan["characters"] = [c for c in chars if isinstance(c, dict) and c.get("id")] \
        if isinstance(chars, list) else []
    # Scènes (images) — réindexées
    raw_scenes = plan.get("scenes") if isinstance(plan.get("scenes"), list) else []
    scenes = []
    for sc in raw_scenes:
        c = _gen_clamp_scene(sc)
        if c:
            c["index"] = len(scenes)
            scenes.append(c)
    plan["scenes"] = scenes
    if not scenes:
        return None
    # Plans (shots) — réindexés, référence de scène bornée
    raw_shots = plan.get("shots") if isinstance(plan.get("shots"), list) else []
    shots = []
    for sh in raw_shots:
        c = _gen_clamp_shot(sh, language, len(scenes))
        if c and (c["motion_prompt"] or c["camera"] or c["spoken_text"]):
            c["index"] = len(shots)
            shots.append(c)
    # Repli : si le directeur n'a pas listé de plans, un plan par scène.
    if not shots:
        for sc in scenes:
            shots.append(_gen_clamp_shot(
                {"scene": sc["index"], "duration_s": 5,
                 "motion_prompt": sc["image_prompt"][:120]}, language, len(scenes)))
        for i, sh in enumerate(shots):
            sh["index"] = i
    plan["shots"] = shots
    am = str(plan.get("audio_mode") or "").strip()
    plan["audio_mode"] = am if am in ("native", "voiceover") else "voiceover"
    total = sum(s["duration_s"] for s in shots)
    plan["total_duration_s"] = min(GEN_MAX_TOTAL_S, round(total)) if total else 0
    return plan


def _decode_data_url(u):
    """data:image/...;base64,xxx -> octets ; ou vraie URL http -> télécharge."""
    try:
        if u.startswith("data:"):
            return base64.b64decode(u.split(",", 1)[1])
        if u.startswith("http"):
            _st, raw = http("GET", u, timeout=120)
            return raw
    except Exception as e:
        print("_decode_data_url:", e, file=sys.stderr)
    return None


def _extract_image_url(out):
    """Trouve l'URL de l'image générée dans une réponse OpenRouter, quelle que
    soit la forme (message.images[], ou content sous forme de parts)."""
    try:
        choices = out.get("choices") or []
        if not choices:
            return None
        msg = choices[0].get("message") or {}
        imgs = msg.get("images")
        if isinstance(imgs, list) and imgs:
            it = imgs[0]
            if isinstance(it, dict):
                iu = it.get("image_url") or {}
                if isinstance(iu, dict) and iu.get("url"):
                    return iu["url"]
                if it.get("url"):
                    return it["url"]
            if isinstance(it, str):
                return it
        cont = msg.get("content")
        if isinstance(cont, list):
            for p in cont:
                if isinstance(p, dict) and p.get("type") in (
                        "image_url", "output_image", "image"):
                    iu = p.get("image_url") or {}
                    if isinstance(iu, dict) and iu.get("url"):
                        return iu["url"]
                    if p.get("url"):
                        return p["url"]
    except Exception as e:
        print("_extract_image_url:", e, file=sys.stderr)
    return None


def or_generate_image(prompt, ref_paths=None, out_path=None, timeout=240):
    """NANO BANANA 2 (google/gemini-3.1-flash-image via OpenRouter). Génère UNE
    image nette depuis un prompt. `ref_paths` = images de référence (ex. le
    visage du personnage) pour la COHÉRENCE inter-plans. Écrit dans out_path.
    Renvoie le chemin, sinon None."""
    if not OPENROUTER_KEY:
        return None
    content = [{"type": "text", "text": prompt}]
    for rp in (ref_paths or []):
        if not rp:
            continue
        try:
            with open(rp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = "png" if rp.lower().endswith(".png") else "jpeg"
            content.append({"type": "image_url",
                            "image_url": {"url": "data:image/%s;base64,%s" % (ext, b64)}})
        except Exception:
            pass
    body = {"model": OR_IMAGE_MODEL,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"]}
    try:
        st, raw = http("POST", "https://openrouter.ai/api/v1/chat/completions",
                       {"Authorization": "Bearer " + OPENROUTER_KEY, "X-Title": "Skillora"},
                       body, timeout=timeout)
        out = json.loads(raw)
        url = _extract_image_url(out)
        if not url:
            print("or_generate_image: aucune image:", str(out)[:300], file=sys.stderr)
            return None
        data = _decode_data_url(url)
        if not data:
            return None
        if not out_path:
            out_path = tempfile.mktemp(suffix=".png")
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path if os.path.getsize(out_path) > 500 else None
    except urllib.error.HTTPError as e:
        try:
            print("or_generate_image HTTP", e.code, ":", e.read().decode()[:250], file=sys.stderr)
        except Exception:
            print("or_generate_image HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("or_generate_image:", e, file=sys.stderr)
        return None


def gen_images(plan, workdir):
    """ÉTAPE 2 — génère UNE image par SCÈNE (décor). COHÉRENCE : la 1re image
    où un personnage apparaît devient sa RÉFÉRENCE de visage, passée aux scènes
    suivantes où il revient -> même tête d'une scène à l'autre. Renvoie
    {index_de_scène: chemin_image}."""
    imgs = {}
    scenes = plan.get("scenes") or []
    if not scenes:
        return imgs
    try:
        os.makedirs(workdir, exist_ok=True)
    except Exception:
        pass
    chars = {str(c.get("id")): str(c.get("description") or "")
             for c in (plan.get("characters") or []) if isinstance(c, dict)}
    char_ref = {}  # id perso -> 1re image où il apparaît (ancre du visage)
    for sc in scenes:
        idx = sc["index"]
        present = [c for c in (sc.get("characters") or []) if c in chars]
        desc = " ".join(chars[c] for c in present if chars.get(c)).strip()
        prompt = sc["image_prompt"]
        if desc and desc[:30] not in prompt:
            prompt = desc + ". " + prompt
        prompt = ("Image ultra nette et haute qualité, cadrage vertical 9:16, "
                  "ÉCLAIRAGE CINÉMATOGRAPHIQUE soigné, ombres réalistes et "
                  "naturelles (jamais plat ni cramé), arrière-plan détaillé "
                  "JAMAIS flou, rendu photographique réaliste quand la scène "
                  "l'exige, aucun artefact « IA ». " + prompt)
        refs = [char_ref[c] for c in present if c in char_ref]
        out = os.path.join(workdir, "img_%03d.png" % idx)
        got = or_generate_image(prompt, ref_paths=refs or None, out_path=out)
        if got:
            imgs[idx] = got
            for c in present:
                char_ref.setdefault(c, got)
        else:
            print("gen_images: échec scène", idx, file=sys.stderr)
    return imgs


def sb_upload_public(path, key, content_type="image/png"):
    """Envoie un fichier dans le bucket public post-media et renvoie son URL
    publique — nécessaire pour donner une image de départ aux générateurs
    vidéo (ils veulent une URL, pas un fichier local)."""
    try:
        with open(path, "rb") as f:
            blob = f.read()
        http("POST", "%s/storage/v1/object/post-media/%s" % (SB_URL, key),
             sb_headers({"Content-Type": content_type, "x-upsert": "true"}),
             blob, timeout=300)
        return "%s/storage/v1/object/public/post-media/%s" % (SB_URL, key)
    except Exception as e:
        print("sb_upload_public:", e, file=sys.stderr)
        return None


def or_generate_video(model_key, prompt, seconds, image_url=None, ref_urls=None,
                      generate_audio=False, aspect_ratio="9:16", out_path=None,
                      poll_timeout=1200):
    """ÉTAPE 3 (coeur) — génération vidéo via l'API asynchrone d'OpenRouter :
    POST /api/v1/videos (soumission), puis poll GET jusqu'à 'completed', puis
    téléchargement du MP4. `image_url` = première image (image->vidéo).
    Renvoie le chemin du MP4, sinon None."""
    global _LAST_VIDEO_ERR
    if not OPENROUTER_KEY:
        return None
    model = OR_VIDEO_MODELS.get(model_key) or OR_VIDEO_MODELS["veo_lite"]
    dur = int(max(GEN_MIN_CLIP_S, min(OR_VIDEO_MAXLEN.get(model_key, 8),
                                      round(seconds or 4))))
    body = {"model": model, "prompt": prompt, "duration": dur,
            "aspect_ratio": aspect_ratio, "generate_audio": bool(generate_audio)}
    if model.startswith("google/veo"):
        # Veo/Vertex BLOQUE les personnes par défaut -> on autorise (sinon tout
        # plan avec un visage échoue). 720p = coût ~2x moindre, suffisant en 9:16.
        body["resolution"] = "720p"
        body["provider"] = {"options": {"google-vertex":
                            {"parameters": {"personGeneration": "allow"}}}}
    if image_url:
        body["frame_images"] = [{"type": "image_url",
                                 "image_url": {"url": image_url},
                                 "frame_type": "first_frame"}]
    if ref_urls:
        body["input_references"] = [{"type": "image_url", "image_url": {"url": u}}
                                    for u in ref_urls if u]
    hdr = {"Authorization": "Bearer " + OPENROUTER_KEY,
           "Content-Type": "application/json", "X-Title": "Skillora"}
    # Soumission
    try:
        st, raw = http("POST", "https://openrouter.ai/api/v1/videos", hdr, body, timeout=120)
        job = json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()[:300]
        except Exception:
            b = ""
        _LAST_VIDEO_ERR = "%s HTTP %s: %s" % (model, getattr(e, "code", "?"), b)
        print("or_generate_video submit", _LAST_VIDEO_ERR, file=sys.stderr)
        return None
    except Exception as e:
        _LAST_VIDEO_ERR = "soumission %s: %s" % (model, str(e)[:200])
        print("or_generate_video submit:", e, file=sys.stderr)
        return None
    jid = job.get("id")
    poll = job.get("polling_url") or (("https://openrouter.ai/api/v1/videos/" + str(jid)) if jid else None)
    if not poll:
        _LAST_VIDEO_ERR = "réponse inattendue (%s): %s" % (model, str(job)[:200])
        print("or_generate_video: pas de polling_url:", str(job)[:200], file=sys.stderr)
        return None
    # Poll jusqu'à état terminal
    deadline = time.time() + poll_timeout
    status, info = "pending", {}
    while time.time() < deadline:
        time.sleep(15)
        try:
            st, raw = http("GET", poll, hdr, timeout=60)
            info = json.loads(raw)
            status = str(info.get("status") or "").lower()
        except Exception as e:
            print("or_generate_video poll:", e, file=sys.stderr)
            continue
        if status == "completed":
            break
        if status in ("failed", "cancelled", "expired"):
            _LAST_VIDEO_ERR = "%s %s: %s" % (model, status, str(info.get("error"))[:200])
            print("or_generate_video:", status, "-", str(info.get("error"))[:200], file=sys.stderr)
            return None
    if status != "completed":
        _LAST_VIDEO_ERR = "%s: timeout après %ds" % (model, poll_timeout)
        print("or_generate_video: timeout après %ds" % poll_timeout, file=sys.stderr)
        return None
    # Téléchargement
    if not out_path:
        out_path = tempfile.mktemp(suffix=".mp4")
    url = None
    uns = info.get("unsigned_urls")
    if isinstance(uns, list) and uns:
        url = uns[0]
    try:
        if url:
            st, raw = http("GET", url, hdr, timeout=600)
        else:
            st, raw = http("GET", "https://openrouter.ai/api/v1/videos/%s/content?index=0" % jid,
                           hdr, timeout=600)
        with open(out_path, "wb") as f:
            f.write(raw)
        return out_path if os.path.getsize(out_path) > 2000 else None
    except Exception as e:
        _LAST_VIDEO_ERR = "téléchargement %s: %s" % (model, str(e)[:150])
        print("or_generate_video download:", e, file=sys.stderr)
        return None


def _ff_trim(src, start, end, dst, mirror=False):
    """Découpe [start, end] de src -> dst (ré-encodage, précis). Miroir option."""
    dur = max(0.1, float(end) - float(start))
    cmd = ["ffmpeg", "-y", "-ss", "%.3f" % float(start), "-i", src, "-t", "%.3f" % dur]
    if mirror:
        cmd += ["-vf", "hflip"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-movflags", "+faststart", dst]
    try:
        run(cmd, timeout=300)
    except Exception as e:
        print("_ff_trim:", e, file=sys.stderr)
    return dst if (os.path.exists(dst) and os.path.getsize(dst) > 1000) else None


def animate_shots(plan, images, workdir, uid="anon", job_id="gen"):
    """ÉTAPE 3 — anime chaque PLAN (shot) à partir de l'image de SA scène.
    Plusieurs plans peuvent réutiliser la MÊME image (gros plan, contrechamp,
    plan large…) : l'image n'est uploadée qu'UNE fois par scène. Renvoie une
    liste ORDONNÉE de (index_du_plan, chemin_clip)."""
    clips = []
    shots = plan.get("shots") or []
    try:
        os.makedirs(workdir, exist_ok=True)
    except Exception:
        pass
    uploaded = {}  # index_de_scène -> URL publique (upload une seule fois)
    for sh in shots:
        sidx = sh.get("scene", 0)
        img = images.get(sidx)
        if img and sidx not in uploaded:
            uploaded[sidx] = sb_upload_public(
                img, "gen/%s/%s/img_%03d.png" % (uid, job_id, sidx))
        img_url = uploaded.get(sidx)
        talking = bool(sh.get("talking"))
        prompt = " ".join(x for x in [sh.get("camera"), sh.get("motion_prompt")]
                          if x).strip() or "Plan cinématographique fidèle à la scène."
        if talking and sh.get("spoken_text"):
            who = (" (%s)" % sh["speaker"]) if sh.get("speaker") else ""
            prompt = prompt + " Le personnage%s parle et dit exactement : « %s »." % (
                who, sh["spoken_text"])
        out = os.path.join(workdir, "shot_%03d.mp4" % sh["index"])
        got = or_generate_video(sh.get("video_model", "veo_lite"), prompt,
                                sh.get("duration_s", 5), image_url=img_url,
                                generate_audio=talking, out_path=out)
        if got:
            clips.append((sh["index"], got))
        else:
            print("animate_shots: échec plan", sh["index"], file=sys.stderr)
    return clips


ELEVEN_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
_MOOD_MAP = {"douce": "calm", "epique": "epic", "épique": "epic",
             "tendue": "tension", "joyeuse": "happy", "energique": "hype",
             "énergique": "hype", "triste": "sad", "mysterieuse": "mystery"}


def eleven_tts(text, out_path, voice_id=None, model_id="eleven_multilingual_v2"):
    """VOIX OFF (ElevenLabs Text-to-Speech, multilingue FR/EN/ES). Écrit un MP3
    dans out_path. None si pas de clé / texte vide / échec."""
    if not (ELEVEN_KEY and text and text.strip()):
        return None
    vid = voice_id or ELEVEN_VOICE_ID
    body = {"text": text.strip(), "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    try:
        st, raw = http("POST", "https://api.elevenlabs.io/v1/text-to-speech/%s" % vid,
                       {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json",
                        "Accept": "audio/mpeg"}, body, timeout=300)
        if not raw or len(raw) < 1500:
            return None
        with open(out_path, "wb") as f:
            f.write(raw)
        return out_path if os.path.getsize(out_path) > 1500 else None
    except urllib.error.HTTPError as e:
        try:
            print("eleven_tts HTTP", e.code, ":", e.read().decode()[:200], file=sys.stderr)
        except Exception:
            print("eleven_tts HTTP", e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("eleven_tts:", e, file=sys.stderr)
        return None


def _sec_to_ass(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def _build_gen_ass(spans, out_ass, w=1080, h=1920):
    """Sous-titres propres pour la vidéo générée : centrés bas, Anton blanc,
    contour noir. `spans` = liste de (start, end, texte)."""
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\n"
            "WrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, "
            "PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
            "MarginV, Encoding\nStyle: Cap,Anton,90,&H00FFFFFF,&H00FFFFFF,"
            "&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,6,3,2,80,80,260,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, "
            "MarginR, MarginV, Effect, Text\n" % (w, h))
    lines = [head]
    for (a, b, txt) in spans:
        if b <= a or not str(txt).strip():
            continue
        t = str(txt).replace("\n", " ").replace("{", "(").replace("}", ")").strip().upper()
        lines.append("Dialogue: 0,%s,%s,Cap,,0,0,0,,%s" % (_sec_to_ass(a), _sec_to_ass(b), t))
    with open(out_ass, "w") as f:
        f.write("\n".join(lines))
    return out_ass


def _concat_video(paths, out, w=1080, h=1920, fps=30):
    """Concatène les clips en une vidéo MUETTE 9:16 normalisée."""
    paths = [p for p in paths if p and os.path.exists(p)]
    if not paths:
        return None
    ins = []
    for p in paths:
        ins += ["-i", p]
    parts = ["[%d:v]scale=%d:%d:force_original_aspect_ratio=increase,"
             "crop=%d:%d,setsar=1,fps=%d[v%d]" % (i, w, h, w, h, fps, i)
             for i in range(len(paths))]
    fc = ";".join(parts) + ";" + "".join("[v%d]" % i for i in range(len(paths))) + \
        "concat=n=%d:v=1:a=0[v]" % len(paths)
    cmd = ["ffmpeg", "-y"] + ins + ["-filter_complex", fc, "-map", "[v]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    try:
        run(cmd, timeout=1800)
    except Exception as e:
        print("_concat_video:", e, file=sys.stderr)
    return out if (os.path.exists(out) and os.path.getsize(out) > 3000) else None


def _concat_clip_audio(paths, out):
    """Concatène l'audio NATIF des clips (voix + lip-sync du modèle), avec du
    silence pour les clips sans piste audio -> une seule piste alignée."""
    segs = []
    workdir = os.path.dirname(out) or "."
    for i, p in enumerate(paths):
        try:
            f = ffprobe_facts(p)
            d, ha = f["duration"] or 0, f["has_audio"]
        except Exception:
            d, ha = 0, False
        seg = os.path.join(workdir, "na_%03d.wav" % i)
        if ha and d > 0:
            try:
                run(["ffmpeg", "-y", "-i", p, "-vn", "-ac", "2", "-ar", "48000", seg], timeout=180)
            except Exception:
                ha = False
        if not (os.path.exists(seg) and os.path.getsize(seg) > 200):
            dd = d if d > 0 else 3.0
            try:
                run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                     "-t", "%.3f" % dd, seg], timeout=60)
            except Exception:
                continue
        segs.append(seg)
    if not segs:
        return None
    ins = []
    for s in segs:
        ins += ["-i", s]
    fc = "".join("[%d:a]" % i for i in range(len(segs))) + \
        "concat=n=%d:v=0:a=1[a]" % len(segs)
    try:
        run(["ffmpeg", "-y"] + ins + ["-filter_complex", fc, "-map", "[a]", out], timeout=600)
    except Exception as e:
        print("_concat_clip_audio:", e, file=sys.stderr)
        return None
    return out if os.path.exists(out) else None


def _mux_audio(video, main_audio, music, out, total):
    """Mixe la piste principale (voix off ou audio natif) + un tapis musical
    discret sous la vidéo. Renvoie out, ou None si rien à mixer."""
    if not main_audio and not music:
        return None
    cmd = ["ffmpeg", "-y", "-i", video]
    idx = 1
    pre, labels = [], []
    if main_audio:
        cmd += ["-i", main_audio]
        pre.append("[%d:a]aresample=48000,apad,atrim=0:%.3f[main]" % (idx, total))
        labels.append("[main]")
        idx += 1
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        pre.append("[%d:a]aresample=48000,atrim=0:%.3f,volume=0.14[mus]" % (idx, total))
        labels.append("[mus]")
        idx += 1
    if len(labels) == 1:
        fc = ";".join(pre) + ";" + labels[0] + "anull[aout]"
    else:
        fc = ";".join(pre) + ";" + "".join(labels) + \
            "amix=inputs=%d:duration=first:dropout_transition=0[aout]" % len(labels)
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", "%.3f" % total, "-movflags", "+faststart", out]
    try:
        run(cmd, timeout=900)
    except Exception as e:
        print("_mux_audio:", e, file=sys.stderr)
        return None
    return out if (os.path.exists(out) and os.path.getsize(out) > 3000) else None


def assemble_generated(plan, clips, job, workdir):
    """ÉTAPE 4 — MONTAGE FINAL : concatène les clips des PLANS (dans l'ordre),
    ajoute la voix off (ElevenLabs) ou garde l'audio natif des avatars, pose un
    tapis musical, incruste les sous-titres, upload. `clips` = liste ordonnée
    de (index_du_plan, chemin). Renvoie l'URL, ou None."""
    if not clips:
        return None
    shots = {s["index"]: s for s in (plan.get("shots") or [])}
    try:
        os.makedirs(workdir, exist_ok=True)
    except Exception:
        pass
    ordered = [p for (_i, p) in clips]
    # durées réelles -> spans de sous-titres
    spans, t = [], 0.0
    for (idx, p) in clips:
        sh = shots.get(idx, {})
        try:
            d = ffprobe_facts(p)["duration"] or sh.get("duration_s", 4)
        except Exception:
            d = sh.get("duration_s", 4)
        caps = sh.get("captions") or []
        if caps and d > 0:
            step = d / len(caps)
            for i, c in enumerate(caps):
                spans.append((t + i * step, t + (i + 1) * step - 0.05, c))
        t += d
    total = max(1.0, t)
    # vidéo muette concaténée
    silent = os.path.join(workdir, "base_silent.mp4")
    if not _concat_video(ordered, silent):
        return None
    # audio principal
    mode = plan.get("audio_mode", "voiceover")
    main_audio = None
    if mode == "voiceover" and plan.get("voiceover_script"):
        main_audio = eleven_tts(plan["voiceover_script"], os.path.join(workdir, "voice.mp3"))
    if main_audio is None and mode != "voiceover":
        main_audio = _concat_clip_audio(ordered, os.path.join(workdir, "native.wav"))
    # musique
    music = None
    mood = str(plan.get("music_mood") or "").lower().strip()
    if mood and mood not in ("aucune", "none", ""):
        music = pick_music(mood) or pick_music(_MOOD_MAP.get(mood, ""))
    # mux
    with_audio = os.path.join(workdir, "base_audio.mp4")
    if not _mux_audio(silent, main_audio, music, with_audio, total):
        with_audio = silent
    # sous-titres
    final = os.path.join(workdir, "final.mp4")
    try:
        ass = _build_gen_ass(spans, os.path.join(workdir, "gen.ass"))
        burn_subs(with_audio, final, ass)
        if not (os.path.exists(final) and os.path.getsize(final) > 3000):
            final = with_audio
    except Exception as e:
        print("assemble_generated burn:", e, file=sys.stderr)
        final = with_audio
    try:
        return upload_result(job, final)
    except Exception as e:
        print("assemble_generated upload:", e, file=sys.stderr)
        return None


def generate_video_job(job, work, steps):
    """ORCHESTRATEUR du GÉNÉRATEUR IA (« Copier une vidéo »).
    Directeur (personnages + scènes + plans) -> Images (1/scène) ->
    Animation (1/plan, plusieurs plans par image) -> Montage -> upload."""
    context = job.get("context") or {}
    idea = str(context.get("idea") or "").strip()
    source_url = (str(context.get("source_url") or "").strip()
                  or str(job.get("source_url") or "").strip() or None)
    uid = str(job.get("user_id") or "anon")
    jid = str(job.get("id") or "gen")
    if not OPENROUTER_KEY:
        raise RuntimeError("La génération IA n'est pas encore activée (crédits manquants).")
    if not (idea or source_url):
        raise RuntimeError("Donne une idée ou colle le lien d'une vidéo à reproduire.")

    steps.start("plan", "Le directeur regarde et écrit le plan…")
    plan = gen_director_plan(idea, source_url=source_url)
    if not plan or not plan.get("scenes") or not plan.get("shots"):
        raise RuntimeError("Le directeur n'a pas pu établir de plan à partir de ça.")
    update_job(jid, {"plan": {"gen": plan}})
    steps.done("plan", "%d images · %d plans · %s" % (
        len(plan["scenes"]), len(plan["shots"]),
        "voix off" if plan.get("audio_mode") == "voiceover" else "voix native"))

    steps.start("img", "Génération des images (Nano Banana)…")
    imgs = gen_images(plan, os.path.join(work, "img"))
    if not imgs:
        raise RuntimeError("La génération des images a échoué.")
    steps.done("img", "%d images" % len(imgs))

    steps.start("anim", "Animation des plans…")
    clips = animate_shots(plan, imgs, os.path.join(work, "clips"), uid, jid)
    if not clips:
        raise RuntimeError("L'animation des plans a échoué. " + (_LAST_VIDEO_ERR or "(raison inconnue)"))
    steps.done("anim", "%d plans animés" % len(clips))

    steps.start("mux", "Montage final (voix, musique, sous-titres)…")
    url = assemble_generated(plan, clips, job, os.path.join(work, "final"))
    if not url:
        raise RuntimeError("Le montage final a échoué.")
    steps.done("mux", "Terminé")

    update_job(jid, {"status": "done", "result_url": url,
                     "finished_at": "now()", "steps": steps.items})
    print("Génération", jid, "terminée:", url)
    return url


def gen_blueprint(idea, source_url=None):
    """« REPRODUIRE UNE VIDÉO » — version PLAN (pas de génération, ~0,01 $).
    Regarde la vidéo de référence (ou part d'une idée) et rend un GUIDE
    COMPLET, prêt à suivre par le créateur : analyse, script, plans (avec
    images à générer + comment animer), montage, conseils d'adaptation.
    Renvoie un dict lisible, ou None."""
    if not OPENROUTER_KEY:
        return None
    idea = (idea or "").strip()
    charter = (
        "Tu es un COACH VIDÉO expert (montage viral). On te donne une vidéo "
        "(ou une idée) et tu dois livrer un PLAN DE REPRODUCTION complet, clair "
        "et actionnable, pour qu'un créateur refasse SA version de cette vidéo. "
        "Tu ne génères rien : tu EXPLIQUES tout, étape par étape.\n\n"
        "Si une vidéo est fournie, REGARDE-la plan par plan : le hook, le "
        "format, le rythme, qui parle et quoi, les mouvements, la caméra, le "
        "décor, la lumière, les sous-titres, la musique. Explique pourquoi ça "
        "marche, puis donne le plan exact pour la refaire.\n\n"
        "Écris en français, simple et direct. Le script doit être PRÊT À LIRE. "
        "Les prompts d'images doivent être assez précis pour être collés tels "
        "quels dans un générateur d'images.\n\n"
        "RENDS UNIQUEMENT ce JSON (aucun texte autour) :\n"
        "{\n"
        "  \"titre\": \"titre court de la vidéo à reproduire\",\n"
        "  \"format\": \"ex : histoire faceless, tête parlante, conversation…\",\n"
        "  \"duree_conseillee_s\": 30,\n"
        "  \"pourquoi_ca_marche\": \"2-3 phrases : le hook, le rythme, l'émotion\",\n"
        "  \"accroche\": \"la 1re phrase/plan qui retient dans les 2 premières secondes\",\n"
        "  \"script\": \"le script COMPLET prêt à lire (voix off ou dialogues)\",\n"
        "  \"plans\": [\n"
        "    {\"n\": 1, \"duree_s\": 4, \"scene\": \"le décor\",\n"
        "     \"action\": \"ce qui se passe à l'écran\",\n"
        "     \"camera\": \"cadrage / mouvement de caméra\",\n"
        "     \"dialogue\": \"ce qui est dit sur ce plan (ou vide)\",\n"
        "     \"image_a_generer\": \"prompt d'image précis à coller dans un générateur\",\n"
        "     \"comment_animer\": \"comment donner vie à l'image (mouvement, zoom…)\"}\n"
        "  ],\n"
        "  \"montage\": {\n"
        "    \"sous_titres\": \"style + règles (gros mots clés, couleur…)\",\n"
        "    \"musique\": \"type d'ambiance + où la baisser\",\n"
        "    \"transitions\": \"les coupes/effets entre plans\",\n"
        "    \"effets\": \"zooms, secousses, flashs éventuels\",\n"
        "    \"rythme\": \"tempo des coupes\"\n"
        "  },\n"
        "  \"conseils_adaptation\": [\"comment l'adapter à TA niche / ton compte\"],\n"
        "  \"materiel\": {\"nb_images\": 5,\n"
        "     \"outils_conseilles\": [\"générateur d'images\", \"voix IA\", \"CapCut\"]}\n"
        "}\n"
    )
    if source_url:
        prompt = (charter + "\nVIDÉO DE RÉFÉRENCE à analyser (regarde-la) — "
                  "consigne du client : " + (idea or "explique comment la reproduire."))
        g = _analyze_source(prompt, source_url)
    else:
        prompt = charter + "\nIDÉE DU CLIENT : " + (idea or "propose une vidéo virale.")
        g = or_generate(prompt, json_out=True)
    if not isinstance(g, dict):
        return None
    # Nettoyage défensif des plans
    plans = g.get("plans")
    clean = []
    if isinstance(plans, list):
        for i, p in enumerate(plans):
            if not isinstance(p, dict):
                continue
            p["n"] = i + 1
            for k in ("scene", "action", "camera", "dialogue", "image_a_generer", "comment_animer"):
                p[k] = str(p.get(k) or "").strip()
            try:
                p["duree_s"] = max(1, min(60, int(float(p.get("duree_s") or 4))))
            except Exception:
                p["duree_s"] = 4
            if p["image_a_generer"] or p["action"]:
                clean.append(p)
    g["plans"] = clean
    if not (g.get("script") or clean):
        return None
    return g


def generate_blueprint_job(job, steps):
    """« Reproduire une vidéo » — traite un job mode='blueprint' : analyse la
    vidéo/idée et stocke le GUIDE dans job.plan.blueprint (aucune génération,
    donc quasi gratuit). Le front l'affiche joliment."""
    context = job.get("context") or {}
    idea = str(context.get("idea") or "").strip()
    source_url = (str(context.get("source_url") or "").strip()
                  or str(job.get("source_url") or "").strip() or None)
    jid = str(job.get("id") or "bp")
    steps.items = [{"key": "wait", "label": "En file d'attente…", "state": "done"}]
    if not OPENROUTER_KEY:
        raise RuntimeError("L'analyse n'est pas encore activée (crédits manquants).")
    if not (idea or source_url):
        raise RuntimeError("Donne une idée ou colle le lien d'une vidéo.")
    steps.start("bp", "Analyse de la vidéo & rédaction du plan…")
    guide = gen_blueprint(idea, source_url=source_url)
    if not guide:
        raise RuntimeError("Je n'ai pas réussi à analyser ça. Réessaie avec un autre lien.")
    steps.done("bp", "%d plans" % len(guide.get("plans") or []))
    update_job(jid, {"status": "done", "plan": {"blueprint": guide},
                     "finished_at": "now()", "steps": steps.items})
    print("Blueprint", jid, "terminé.")
    return guide


def main():
    print("Skillora video-worker démarré.",
          "Groq:", "oui" if GROQ_KEY else "NON (plan IA désactivé)",
          "· Yeux:", ("Gemini via OpenRouter (PAYANT, sans limite) + secours gratuit" if OPENROUTER_KEY
                      else ("Gemini gratuit (vidéo entière)" if GEMINI_KEY else "Groq (images)")),
          "· Transcription:", "ElevenLabs Scribe" if ELEVEN_KEY else "Whisper (Groq)",
          "· Pexels:", "oui" if PEXELS_KEY else "non",
          "· Émojis nets (rsvg):", "oui" if shutil.which("rsvg-convert") else "NON — installe librsvg2-bin !")
    recover_orphans()  # les jobs interrompus par un redémarrage repartent seuls
    while True:
        job = claim_job()
        if job:
            print("Job réclamé:", job["id"])
            process(job)
            continue
        # Au repos : 1) réveiller les agents si c'est l'heure ; 2) faire étudier UNE gagnante par Gemini.
        scout_tick()
        school_open = ((GEMINI_KEY or OPENROUTER_KEY) and time.time() >= _gemini_rest_until
                       and _study_budget_left() > 0)
        win = claim_winner() if school_open else None
        if win:
            print("Éclaireur: gagnante réclamée:", win.get("video_url", "")[:60],
                  "· budget du jour restant:", _study_budget_left() - 1)
            _study_budget_spend()
            study_winner(win)
            # PAUSE entre deux études : 8 s en payant (OpenRouter n'impose pas de rythme),
            # 45 s en gratuit (le quota Gemini punit la vitesse).
            time.sleep(8 if OPENROUTER_KEY else 45)
            continue
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
