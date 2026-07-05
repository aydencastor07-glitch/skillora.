"""
Skillora — découpe un gros fichier de bruitages en clips nommés.
================================================================
Tu as UN seul fichier (ex: pack.mp3) qui enchaîne ~40 bruitages. Ce script le
découpe automatiquement en 40 fichiers nommés et les téléverse dans le bucket
public 'sfx-library'. Le worker les reconnaît ensuite par mots-clés.

Utilisation (sur le serveur, dans Termius) :
  1. Téléverse ton gros fichier dans le bucket 'sfx-library' en le nommant  pack.mp3
  2. curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/slice_sfx.py -o /opt/skillora-worker/slice_sfx.py
     python3 /opt/skillora-worker/slice_sfx.py

La clé service_role est lue automatiquement depuis le service systemd
(pas besoin de la retaper).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "https://fkjqlmtugzdluzshxqsk.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
UNIT = "/etc/systemd/system/skillora-worker.service"
BUCKET = "sfx-library"
PACK = os.environ.get("SFX_PACK", "pack.mp3")

# Récupère la clé depuis le service systemd si absente de l'env.
if not KEY and os.path.exists(UNIT):
    for line in open(UNIT):
        m = re.search(r"SUPABASE_SERVICE_ROLE_KEY=(.+)", line.strip())
        if m:
            KEY = m.group(1).strip()
            break
if not KEY:
    print("❌ Clé Supabase introuvable. Lance : SUPABASE_SERVICE_ROLE_KEY=... python3 slice_sfx.py")
    sys.exit(1)

# (nom, début_s, fin_s) — d'après la liste horodatée du pack.
CLIPS = [
    ("keyboard_typing-01.mp3", 0, 3), ("pop-01.mp3", 3, 4),
    ("cinematic_whoosh_hit_low-01.mp3", 4, 11), ("whoosh_short_fast-01.mp3", 11, 13),
    ("pop_whoosh-01.mp3", 13, 16), ("dramatic_hit_bass-01.mp3", 16, 19),
    ("smartphone_typing-01.mp3", 19, 31), ("explosion-01.mp3", 31, 35),
    ("quick_whoosh-01.mp3", 35, 38), ("teleren_hack_glitch-01.mp3", 38, 42),
    ("swish_whoosh-01.mp3", 42, 44), ("correct_answer_chime-01.mp3", 44, 46),
    ("censure_beep-01.mp3", 46, 49), ("fast_whoosh-01.mp3", 49, 52),
    ("pc_typing_mechanical-01.mp3", 52, 54), ("mouse_click-01.mp3", 54, 55),
    ("camera_flash_shutter-01.mp3", 55, 62), ("heavy_brass_crisis-01.mp3", 62, 68),
    ("damage_punch_hit-01.mp3", 68, 71), ("heartbeat_loop-01.mp3", 71, 82),
    ("metallic_riser-01.mp3", 82, 85), ("camera_shutter_stinger-01.mp3", 85, 88),
    ("record_scratch-01.mp3", 88, 90), ("cash_register-01.mp3", 90, 92),
    ("fart_sound-01.mp3", 92, 93), ("comic_failure_trumpet-01.mp3", 93, 97),
    ("single_keyboard_press-01.mp3", 97, 99), ("damage_punch_hit-02.mp3", 99, 101),
    ("glockenspiel_note-01.mp3", 101, 104), ("cute_glitter_chime-01.mp3", 104, 109),
    ("male_scream_horror-01.mp3", 109, 113), ("cash_register-02.mp3", 113, 115),
    ("ding_bell-01.mp3", 115, 117), ("money_shaking_glitch-01.mp3", 117, 120),
    ("cheers_and_applause-01.mp3", 120, 125), ("heavy_brass_crisis-02.mp3", 125, 132),
    ("bell_ring_ding-01.mp3", 132, 135), ("comic_whistle-01.mp3", 135, 137),
    ("magic_reveal-01.mp3", 137, 140), ("surprised_horror_synth-01.mp3", 140, 145),
]

work = tempfile.mkdtemp(prefix="sfx-")
local = os.path.join(work, "pack.mp3")
# Le pack peut être dans sfx-library OU music-library (on cherche aux deux endroits).
print(f"[1/3] Recherche de {PACK}…")
found = False
for src_bucket in (BUCKET, "music-library"):
    pub = f"{SB_URL}/storage/v1/object/public/{src_bucket}/{PACK}"
    try:
        req = urllib.request.Request(pub, headers={"User-Agent": "Mozilla/5.0 Skillora"})
        with urllib.request.urlopen(req, timeout=120) as r, open(local, "wb") as f:
            f.write(r.read())
        print(f"      trouvé dans '{src_bucket}'")
        found = True
        break
    except Exception:
        continue
if not found:
    print(f"❌ '{PACK}' introuvable dans 'sfx-library' ni 'music-library'.")
    print("   Vérifie le nom exact du fichier (pack.mp3) dans un de ces buckets.")
    sys.exit(1)

# Durée réelle du pack (on ignore les clips au-delà)
try:
    dur = float(subprocess.run(["ffprobe", "-v", "quiet", "-of", "csv=p=0",
                                "-show_entries", "format=duration", local],
                               capture_output=True, text=True).stdout.strip() or 0)
except Exception:
    dur = 0
print(f"      pack = {dur:.0f}s")

print(f"[2/3] Découpage + envoi de {len(CLIPS)} bruitages…")
ok = 0
for (name, a, b) in CLIPS:
    if dur and a >= dur - 0.3:
        continue
    b = min(b, dur) if dur else b
    out = os.path.join(work, name)
    fade = max(0.05, min(0.25, (b - a) * 0.15))
    r = subprocess.run(["ffmpeg", "-y", "-ss", str(a), "-to", str(b), "-i", local,
                        "-af", f"afade=t=out:st={max(0, (b - a) - fade):.2f}:d={fade:.2f}",
                        "-ar", "44100", "-ac", "2", "-b:a", "160k", out],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("   ⚠️", name, "découpe échouée"); continue
    with open(out, "rb") as f:
        blob = f.read()
    up = urllib.request.Request(
        f"{SB_URL}/storage/v1/object/{BUCKET}/{urllib.parse.quote(name)}",
        data=blob, method="POST",
        headers={"Authorization": "Bearer " + KEY, "apikey": KEY,
                 "Content-Type": "audio/mpeg", "x-upsert": "true"})
    try:
        urllib.request.urlopen(up, timeout=60)
        ok += 1
        print("   ✅", name)
    except Exception as e:
        print("   ⚠️", name, "envoi échoué:", e)

print(f"[3/3] Terminé : {ok}/{len(CLIPS)} bruitages dans le bucket '{BUCKET}'.")
print("   (Tu peux supprimer 'pack.mp3' du bucket, il n'est plus utile.)")
