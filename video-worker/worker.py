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


def sentence_layout(words, sub_position="dynamic", seed=0):
    """Position Y du sous-titre pour CHAQUE mot (change à chaque phrase).
    Partagé entre les sous-titres et les émojis (collés au-dessus du texte)."""
    sp = str(sub_position).lower()
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
    """Effet 'la vidéo se pousse sur le côté' : fond = la vidéo zoomée-floutée
    (aucune bordure noire), la vidéo rétrécit à droite, gros texte ajouté via
    l'ASS au même moment. Timeline inchangée."""
    facts = ffprobe_facts(src)
    W, H = facts["width"], facts["height"]
    t2 = t1 + dur
    bw, bh = int(W * 1.25) // 2 * 2, int(H * 1.25) // 2 * 2
    fw, fh = int(W * 0.62) // 2 * 2, int(H * 0.62) // 2 * 2
    fc = (f"[0:v]split=3[base][b1][b2];"
          f"[b1]scale={bw}:{bh},boxblur=22:2,crop={W}:{H}[bg];"
          f"[b2]scale={fw}:{fh}[fg];"
          f"[bg][fg]overlay=x={W - fw - 30}:y=(H-h)/2[slide];"
          f"[base][slide]overlay=enable='between(t,{t1:.3f},{t2:.3f})'[v]")
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", dst])
    return t2


def zoom_punch(src, dst, words, has_audio, work, sfx_events=None, extra_whooshes=None, avoid=None, seed=0):
    """Zooms dynamiques : punch-in/out alterné à chaque phrase, la caméra GLISSE
    latéralement pendant les segments zoomés (panoramique), whoosh aux punchs et
    bruitages contextuels (typing/ding/cash/…) bien audibles sur les mots forts.
    La timeline ne change pas -> timings des sous-titres valides.
    `sfx_events` = [(t, nom_du_son)] ; `avoid` = fenêtre sans punch (effet 'côté')."""
    facts = ffprobe_facts(src)
    duration, W, H = facts["duration"], facts["width"], facts["height"]
    bounds = zoom_boundaries(words, duration)
    if avoid:
        bounds = [b for b in bounds if not (avoid[0] - 0.5 <= b <= avoid[1] + 0.5)] or [0.0]
    if len(bounds) < 2 or len(bounds) > 60:
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
        for (t, name) in (sfx_events or [])[:10]:
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


def loudnorm(src, dst, music_path=None, music_gain_db=-21):
    """Normalise la voix à -14 LUFS ; mixe la musique en dessous si fournie."""
    # Le tag 'skillora-improved' permet de refuser une 2e amélioration (doublons de sous-titres).
    if music_path:
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


def groq_vision(frames, transcript_text, duration):
    """Les YEUX du worker : décrit l'ouverture (captivante ou pas), les scènes,
    les mouvements et les objets visibles. None si pas de clé / échec."""
    if not GROQ_KEY or not frames:
        return None
    content = [{"type": "text", "text": (
        "Tu es un monteur vidéo pro. Analyse ces images extraites d'une vidéo courte "
        f"({duration:.0f}s) avec leur timestamp, plus le début de la transcription.\n"
        f"Transcription: {transcript_text[:600] or '(aucune parole)'}\n\n"
        "Réponds UNIQUEMENT ce JSON:\n"
        "{\"opening_captivating\": bool,  // les 1res secondes montrent-elles une action/un visuel qui accroche ? false si personnage figé/statique\n"
        " // ATTENTION: un visage qui regarde la caméra sans bouger/parler n'est PAS captivant\n"
        " \"opening_note\": \"pourquoi, en 1 phrase\",\n"
        " \"scenes\": [{\"t\": secondes, \"action\": \"description courte\", \"motion\": bool}],  // une entrée par image\n"
        " \"objects\": [\"objets/éléments importants visibles\"]}"
    )}]
    for (t, p) in frames:
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
                print("groq_vision: modèle OK ->", model, file=sys.stderr)
            return json.loads(out["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()[:200]
            except Exception:
                body = ""
            print("groq_vision HTTP", e.code, "(", model, "):", body, file=sys.stderr)
            if e.code in (400, 404, 422):
                continue  # modèle inconnu/décommissionné -> on tente le suivant
            return None
        except Exception as e:
            print("groq_vision:", e, file=sys.stderr)
            return None
    return None


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
        "sub_position": "dynamic",
        "sub_style": "group",
        "highlight": "yellow",
        "broll_keywords": [],
    }
    if not GROQ_KEY:
        return fallback
    niche = str(context.get("niche", "") or "")
    feedback = str(context.get("feedback", "") or "")
    vis_txt = ""
    if vision:
        sc = "; ".join(f"t={s.get('t', 0)}s {s.get('action', '')}" + (" (mouvement)" if s.get("motion") else "")
                       for s in (vision.get("scenes") or [])[:8])
        vis_txt = ("Analyse VISUELLE de la vidéo : ouverture captivante: "
                   f"{'oui' if vision.get('opening_captivating') else 'non'} ({vision.get('opening_note', '')}). "
                   f"Scènes: {sc or 'n/a'}. Objets visibles: {', '.join((vision.get('objects') or [])[:8]) or 'n/a'}.\n")
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
        " \"hook_text\": \"accroche ultra courte (<=42 caractères, langue de la transcription) ou vide\",\n"
        " \"music_mood\": \"chill|hype|emotional|cinematic|dark|vlog|luxury|funny|tech|epic — choisis presque toujours une ambiance adaptée au contenu (fond musical discret sous la voix) ; vide UNIQUEMENT si la vidéo contient déjà de la musique\",\n"
        " \"keywords\": [\"3-6 mots EXACTS de la transcription à mettre en avant (prix, chiffres, mots forts : '0€', 'gratuit', 'secret'…) — copie-les tels quels\"],\n"
        " \"sfx\": [{\"word\": \"mot EXACT de la transcription\", \"sound\": \"typing|click|pop|whoosh|cash|ding|impact|explosion|magic|glitch|camera|beep|scratch|applause|fail|scream|heartbeat|riser|airhorn|boom\"}],  // 3-7 bruitages qui renforcent le SENS de la vidéo (monteur pro) : taper->typing, cliquer->click, argent/prix->cash, bonne réponse/chiffre->ding, punchline/choc->impact, révélation->magic, bug/tech->glitch, photo->camera, gros mot censuré->beep, échec drôle->fail, applaudir/gagner->applause, montée de tension->riser, transition->whoosh\n"
        " \"emojis\": [{\"word\": \"mot EXACT de la transcription\", \"emoji\": \"un seul émoji\"}],  // 3-6 émojis : TOUT ce qui s'illustre (téléphone->📱, courir->🏃, rire->😂, sport->🏋️, champion->🏆, argent->💰, feu->🔥, idée->💡)\n"
        " \"sub_position\": \"dynamic|bottom|middle\",  // dynamic par défaut ; bottom si des éléments importants occupent le centre de l'image ; middle pour les vidéos très rythmées\n"
        " \"sub_style\": \"group|word\",  // group = 3 mots à la fois (défaut) ; word = mot par mot, pour les vidéos punchy et rapides\n"
        " \"highlight\": \"yellow|green|red|cyan\",  // couleur des mots forts, adaptée à l'ambiance\n"
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
        for k in ("subtitles", "cut_silences", "hook_text", "music_mood", "keywords", "sfx",
                  "emojis", "sub_position", "sub_style", "highlight", "broll_keywords"):
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
HI_COLORS = {"yellow": "&H0000D4FF&", "green": "&H0084DC3D&",
             "red": "&H004040FF&", "cyan": "&H00FFD400&"}


def build_ass(words, hook_text, keywords=None, slide=None, sub_position="dynamic",
              highlight="yellow", sub_style="group", layout=None, play_w=1080, play_h=1920):
    """Sous-titres 'montage dynamique' (style CapCut) :
    - MAJUSCULES, très gros, blanc, contour noir épais, pop d'apparition ;
    - le mot fort de la phrase en JAUNE ;
    - un mot-clé seul = affiché GÉANT au centre ;
    - la position alterne par phrase (bas / milieu / haut) ;
    - pendant l'effet 'côté', gros texte jaune dans la zone libre à gauche."""
    kwhits = {round(k["start"], 2) for k in (keywords or [])}
    HI = HI_COLORS.get(str(highlight).lower(), YELLOW)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},124,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,10,3,5,40,40,0,1
Style: Mega,{FONT},185,{YELLOW.rstrip('&')},&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,1,0,1,12,4,5,40,40,0,1
Style: Hook,{FONT},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,1,0,3,14,0,8,60,60,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    POP = "\\fad(25,35)\\t(0,100,\\fscx115\\fscy115)\\t(100,180,\\fscx100\\fscy100)"
    MEGAPOP = "\\fad(20,40)\\t(0,120,\\fscx130\\fscy130)\\t(120,220,\\fscx100\\fscy100)"
    # Position par mot (partagée avec les émojis) + style : groupes de 3 ou mot-par-mot
    if layout is None:
        layout = sentence_layout(words, sub_position)
    chunk = 1 if str(sub_style).lower() == "word" else 3
    lines = []
    if hook_text:
        safe = str(hook_text).upper().replace("{", "").replace("}", "").replace("\n", " ")
        lines.append(f"Dialogue: 2,0:00:00.15,0:00:03.00,Hook,,0,0,0,,{{\\fad(140,200)}}{safe}")

    # Découpe en groupes ; la position vient de `layout` (partagé avec les émojis).
    # On collecte d'abord les cues, puis on VERROUILLE : un sous-titre se termine
    # toujours AVANT que le suivant apparaisse (jamais deux à l'écran).
    prev_end = None
    group, gfirst = [], 0
    cues = []  # (start, end, mega, y, txt)

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
        parts = []
        for it in g:
            word = str(it["word"]).strip().upper().replace("{", "").replace("}", "").strip(",.;:!?")
            if round(float(it["start"]), 2) in kwhits and not solo_kw:
                parts.append(f"{{\\c{HI}}}{word}{{\\c&H00FFFFFF&}}")
            else:
                parts.append(word)
        txt = " ".join(parts)
        if slide and slide[0] <= start <= slide[1]:
            return  # pendant l'effet 'côté', pas de sous-titre normal (le Mega est affiché)
        y = layout[gfirst] if gfirst < len(layout) else 1430
        cues.append([start, end, solo_kw, y, txt])

    for i, w in enumerate(words):
        ws = float(w["start"])
        if prev_end is not None and ws - prev_end > 0.8:
            flush()  # nouvelle phrase
        is_kw = round(ws, 2) in kwhits
        if is_kw and group:  # le mot fort a son propre affichage géant
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
    for (start, end, mega, y, txt) in cues:
        if mega:
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Mega,,0,0,0,,"
                         f"{{\\an5\\pos(540,960){MEGAPOP}}}{txt}")
        else:
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,"
                         f"{{\\an5\\pos(540,{y}){POP}}}{txt}")

    # Texte géant pendant l'effet 'la vidéo se pousse sur le côté'
    if slide:
        t1, t2, text = slide
        safe = str(text).upper().replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 3,{ass_time(t1 + 0.10)},{ass_time(t2)},Mega,,0,0,0,,"
                     f"{{\\an5\\pos(210,960)\\fs150{MEGAPOP}}}{safe}")
    return head + "\n".join(lines) + "\n"


def burn_subs(src, dst, ass_path):
    """Incruste les sous-titres + passe 'clarté' gratuite : léger débruitage,
    netteté et couleurs plus vives (compense les caméras moyennes)."""
    safe = ass_path.replace("\\", "/").replace(":", "\\:")
    run(["ffmpeg", "-y", "-i", src,
         "-vf", f"ass='{safe}',hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.5,eq=contrast=1.04:saturation=1.13",
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
    (jamais dans les 3 premières secondes : le hook doit rester le créateur).
    Retourne les instants de coupe (pour y mixer des whooshs de transition)."""
    if not brolls:
        return []
    seg = 1.3
    slots = []
    n = len(brolls)
    for i in range(n):
        t = 3.0 + (duration - 5.0) * (i + 1) / (n + 1)
        if t + seg < duration - 1.0:
            slots.append(t)
    if not slots:
        return []
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
        silences = detect_silences(src) if facts["has_audio"] else []
        first_tr = None
        if facts["has_audio"]:
            mp3 = os.path.join(work, "a.mp3")
            extract_audio_mp3(src, mp3)
            first_tr = groq_transcribe(mp3)
        tr_text = (first_tr or {}).get("text", "").strip() if first_tr else ""
        # Les YEUX : images clefs (ouverture x2 + réparties) -> analyse visuelle
        d = facts["duration"]
        ftimes = [0.3, 1.0] + [round(d * k / 6.0, 2) for k in range(2, 6)]
        vision = None
        try:
            vision = groq_vision(extract_frames(src, [t for t in ftimes if t < d - 0.2], work), tr_text, d)
        except Exception as e:
            print("vision:", e, file=sys.stderr)
        plan = groq_plan(facts, tr_text, context, vision)
        update_job(job["id"], {"plan": plan})
        det = "parole détectée" if tr_text else "pas de parole détectée"
        if vision:
            det += " · lecture visuelle OK" + ("" if vision.get("opening_captivating") else " · ouverture à couper")
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

        # 3. B-roll (les instants de coupe recevront un whoosh de transition)
        brolls, broll_cuts = [], []
        if plan.get("broll_keywords"):
            steps.start("broll", "Recherche de plans d'illustration…")
            # 1 seul plan d'illustration max : un effet à la fois à l'écran
            brolls = pexels_broll(plan["broll_keywords"], want=1)
            if brolls:
                out = os.path.join(work, "broll.mp4")
                broll_cuts = overlay_broll(cur, out, brolls, ffprobe_facts(cur)["duration"])
                if broll_cuts:
                    cur = out
                steps.done("broll", f"{len(broll_cuts)} plan(s) inséré(s)")
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

        # 5. Montage dynamique : mots forts, effet "la vidéo se pousse sur le côté",
        #    zooms avant/arrière + whoosh + pops. Timeline inchangée -> timings des
        #    sous-titres valides ; on zoome AVANT d'incruster les sous-titres.
        kws = keyword_times(words, plan.get("keywords"))
        slide = None
        if len(words) >= 6 and ffprobe_facts(cur)["duration"] > 6:
            steps.start("fx", "Montage dynamique (zooms, effets, sons)…")
            try:
                dur_cur = ffprobe_facts(cur)["duration"]
                # Effet "côté" sur le 1er mot fort court (ex: 0€), hors début/fin
                # et JAMAIS pendant un b-roll (un seul effet à la fois à l'écran)
                cand = [k for k in kws if len(k["text"]) <= 7 and 1.0 < k["start"] < dur_cur - 3.0
                        and not any(bc - 1.8 < k["start"] < bc + 1.8 for bc in broll_cuts)]
                if cand:
                    t1 = max(0.5, cand[0]["start"] - 0.15)
                    outs = os.path.join(work, "slide.mp4")
                    t2 = slide_aside(cur, outs, t1)
                    cur = outs
                    slide = (t1, t2, cand[0]["text"])
                out = os.path.join(work, "fx.mp4")
                layout = sentence_layout(words, str(plan.get("sub_position") or "dynamic"), seed)
                emo = emoji_events(words, plan.get("emojis"), work, layout)
                # Un seul effet à la fois : pas d'émoji pendant l'effet 'côté' ou un b-roll
                busy = ([(slide[0] - 0.3, slide[1] + 0.3)] if slide else []) + \
                       [(bc - 0.3, bc + 1.6) for bc in broll_cuts]
                emo = [e for e in emo if not any(a <= e[0] <= b for (a, b) in busy)]
                sfx_ev = sfx_event_times(words, plan.get("sfx"), kws)
                sfx_ev += [(t, "pop") for (t, _p, _y) in emo
                           if not any(abs(t - e[0]) < 0.4 for e in sfx_ev)]
                wh_extra = list(broll_cuts) + ([slide[0], slide[1] - 0.25] if slide else [])
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
                steps.done("fx", detail)
            except Exception as e:
                print("fx:", e, file=sys.stderr)
                steps.done("fx", "effets non appliqués (on continue sans)")
        else:
            steps.skip("fx", "Montage dynamique", "pas assez de parole")

        # 6. Sous-titres + hook incrustés par-dessus
        if words:
            steps.start("subs", "Sous-titres animés…")
            ass = os.path.join(work, "subs.ass")
            with open(ass, "w", encoding="utf-8") as f:
                f.write(build_ass(words, str(plan.get("hook_text") or ""), keywords=kws, slide=slide,
                                  sub_position=str(plan.get("sub_position") or "dynamic"),
                                  highlight=str(plan.get("highlight") or "yellow"),
                                  sub_style=str(plan.get("sub_style") or "group"),
                                  layout=sentence_layout(words, str(plan.get("sub_position") or "dynamic"), seed)))
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
