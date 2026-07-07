"""
Skillora — apprentissage de styles à partir de vidéos virales.
================================================================
Tu envoies des vidéos virales RANGÉES PAR CATÉGORIE dans le bucket 'references',
et ce script apprend leur style (rythme de coupe, couleurs, énergie) puis écrit
un profil par catégorie dans le bucket 'style-library'. Le worker applique
ensuite ce style aux vidéos des utilisateurs de la même catégorie.

Organisation du bucket 'references' (crée-le en PUBLIC dans Supabase) :
  references/energetic/video1.mp4
  references/energetic/video2.mp4
  references/horror/clip1.mp4
  references/luxury_aesthetic/reel1.mp4
  ...
Les CATÉGORIES doivent correspondre aux types du worker :
  energetic, vlog, talk_facecam, horror, luxury_aesthetic, product, story
(tu peux aussi mettre 'sport' -> il sera rangé sous 'energetic').

Utilisation (sur le serveur, dans Termius) :
  curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/learn_styles.py -o /opt/skillora-worker/learn_styles.py
  python3 /opt/skillora-worker/learn_styles.py

La clé service_role est lue automatiquement depuis le service systemd.
"""
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request

KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
UNIT = "/etc/systemd/system/skillora-worker.service"
# SUPABASE_URL par défaut (le script se lance à la main, hors du service systemd)
os.environ.setdefault("SUPABASE_URL", "https://fkjqlmtugzdluzshxqsk.supabase.co")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worker  # réutilise analyze_reference, merge_profiles, ffprobe_facts…

SB_URL = worker.SB_URL
REF_BUCKET = "references"
OUT_BUCKET = worker.STYLE_BUCKET
# Alias de catégories -> types reconnus par le worker
ALIAS = {
    "sport": "energetic", "gym": "energetic", "fitness": "energetic", "quete": "energetic",
    "motivation": "energetic", "gaming": "energetic",
    "histoire": "story", "storytelling": "story", "recit": "story",
    "luxe": "luxury_aesthetic", "luxury": "luxury_aesthetic", "aesthetic": "luxury_aesthetic",
    "lifestyle": "luxury_aesthetic", "mode": "luxury_aesthetic",
    "horreur": "horror", "creepy": "horror",
    "facecam": "talk_facecam", "talk": "talk_facecam", "parole": "talk_facecam",
    "produit": "product", "unboxing": "product", "avis": "product",
    "vlog": "vlog", "voyage": "vlog",
}
VALID = {"energetic", "vlog", "talk_facecam", "horror", "luxury_aesthetic", "product", "story", "other"}

if not KEY and os.path.exists(UNIT):
    for line in open(UNIT):
        m = re.search(r"SUPABASE_SERVICE_ROLE_KEY=(.+)", line.strip())
        if m:
            KEY = m.group(1).strip()
            break
if not KEY:
    print("❌ Clé Supabase introuvable.")
    sys.exit(1)


def sb_list(bucket, prefix=""):
    body = json.dumps({"prefix": prefix, "limit": 1000}).encode()
    req = urllib.request.Request(
        f"{SB_URL}/storage/v1/object/list/{bucket}", data=body, method="POST",
        headers={"Authorization": "Bearer " + KEY, "apikey": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def norm_cat(name):
    c = re.sub(r"[^a-z0-9_]", "", str(name).strip().lower())
    c = ALIAS.get(c, c)
    return c if c in VALID else ""


print("[1/3] Recherche des vidéos de référence dans 'references/'…")
# Le bucket est organisé references/{categorie}/fichier — on liste chaque dossier.
try:
    top = sb_list(REF_BUCKET, "")
except Exception as e:
    print(f"❌ Impossible de lister le bucket '{REF_BUCKET}': {e}")
    print("   Crée-le en PUBLIC et range tes vidéos dans references/<categorie>/")
    sys.exit(1)

cats = {}
folders = [it.get("name") for it in top if it.get("id") is None]  # dossiers = id null
if not folders:
    # peut-être des fichiers à plat nommés categorie_xxx.mp4 -> on tente aussi
    folders = sorted({it.get("name", "").split("/")[0] for it in top if "/" in it.get("name", "")})
for folder in folders:
    cat = norm_cat(folder)
    if not cat:
        print(f"   ⚠️ catégorie inconnue ignorée: '{folder}'")
        continue
    try:
        files = sb_list(REF_BUCKET, folder + "/")
    except Exception:
        continue
    vids = [f"{folder}/{it['name']}" for it in files
            if str(it.get("name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".webm"))]
    if vids:
        cats.setdefault(cat, []).extend(vids)

if not cats:
    print("❌ Aucune vidéo trouvée. Range-les dans references/<categorie>/fichier.mp4")
    sys.exit(1)

print(f"      {sum(len(v) for v in cats.values())} vidéo(s) dans {len(cats)} catégorie(s): "
      + ", ".join(f"{c}({len(v)})" for c, v in cats.items()))

print("[2/3] Analyse du style de chaque vidéo…")
work = tempfile.mkdtemp(prefix="learn-")
results = {}
for cat, keys in cats.items():
    profiles = []
    for key in keys:
        local = os.path.join(work, re.sub(r"[^a-zA-Z0-9.]", "_", key))
        pub = f"{SB_URL}/storage/v1/object/public/{REF_BUCKET}/{urllib.parse.quote(key)}"
        try:
            req = urllib.request.Request(pub, headers={"User-Agent": "Mozilla/5.0 Skillora"})
            with urllib.request.urlopen(req, timeout=300) as r, open(local, "wb") as f:
                f.write(r.read())
            prof = worker.analyze_reference(local, work, category=cat)
            profiles.append(prof)
            print(f"   ✅ {cat}: {os.path.basename(key)} "
                  f"(coupe/{prof['cut_s']}s, {prof['shots_per_min']} plans/min, "
                  f"grade={prof['grade'] or '—'}, intensité={prof['intensity']})")
        except Exception as e:
            print(f"   ⚠️ {key}: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)
    if profiles:
        results[cat] = worker.merge_profiles(profiles)

print("[3/3] Enregistrement des profils appris dans 'style-library/'…")
ok = 0
for cat, prof in results.items():
    blob = json.dumps(prof, ensure_ascii=False).encode()
    up = urllib.request.Request(
        f"{SB_URL}/storage/v1/object/{OUT_BUCKET}/{urllib.parse.quote(cat)}.json",
        data=blob, method="POST",
        headers={"Authorization": "Bearer " + KEY, "apikey": KEY,
                 "Content-Type": "application/json", "x-upsert": "true"})
    try:
        urllib.request.urlopen(up, timeout=60)
        ok += 1
        print(f"   ✅ {cat}.json  (coupe/{prof['cut_s']}s · grade={prof['grade'] or '—'} · "
              f"intensité={prof['intensity']} · {prof['samples']} réf.)")
    except Exception as e:
        print(f"   ⚠️ {cat}: envoi échoué: {e}")

print(f"\nTerminé : {ok} style(s) appris. Le worker les applique automatiquement.")
print("Rappel : crée le bucket 'style-library' en PUBLIC (comme 'references').")
