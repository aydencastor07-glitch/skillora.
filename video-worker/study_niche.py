"""
Skillora — Agent Analyste (internet) : apprend les STYLES VIRAUX par niche.
=========================================================================
Le site vient de se lancer : peu de créateurs, peu de vidéos gagnantes. Pour que
Gemini progresse VITE, on lui fait ÉTUDIER les meilleures vidéos VIRALES d'internet
(liens YouTube ou mp4), rangées par STYLE/niche. Gemini analyse chacune, on agrège,
et on écrit la bibliothèque GÉNÉRALE : style-library/{niche}.json.
Le worker l'applique ensuite à TOUS les créateurs (même les nouveaux, sans historique).

Entrée : un JSON (chemin en argument, ou stdin) de la forme
  {
    "energetic":        ["https://youtube.com/shorts/xxxx", "https://.../a.mp4"],
    "luxury_aesthetic": ["https://youtube.com/shorts/yyyy"],
    "story":            ["https://youtube.com/watch?v=zzzz"]
  }
Les liens YouTube sont analysés DIRECTEMENT par Gemini (pas de téléchargement).

Usage (serveur) :
  curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/study_niche.py -o /opt/skillora-worker/study_niche.py
  python3 /opt/skillora-worker/study_niche.py niches.json
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UNIT = "/etc/systemd/system/skillora-worker.service"
os.environ.setdefault("SUPABASE_URL", "https://fkjqlmtugzdluzshxqsk.supabase.co")
if os.path.exists(UNIT):
    for line in open(UNIT):
        for var in ("SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "PEXELS_API_KEY"):
            m = re.match(rf"Environment={var}=(.+)", line.strip())
            if m and not os.environ.get(var):
                os.environ[var] = m.group(1).strip()
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worker

SB = worker.SB_URL
OUT_BUCKET = worker.STYLE_BUCKET

if not KEY:
    print("❌ Clé Supabase introuvable."); sys.exit(1)
if not worker.GEMINI_KEY:
    print("❌ Clé Gemini introuvable (GEMINI_API_KEY)."); sys.exit(1)

raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
niches = json.loads(raw)
if not isinstance(niches, dict) or not niches:
    print("❌ Attendu un JSON {niche: [liens...]}."); sys.exit(1)


def most_common(vals):
    vals = [x for x in vals if x not in (None, "")]
    return max(set(vals), key=vals.count) if vals else None


total = sum(len(v) for v in niches.values())
print(f"[1/2] Étude de {total} vidéo(s) virale(s) sur {len(niches)} style(s)…")
profiles = {}
for niche, urls in niches.items():
    niche = re.sub(r"[^a-z0-9_]", "", str(niche).lower())
    dnas = []
    for url in urls:
        dna = worker.gemini_study_url(url)
        if dna and isinstance(dna, dict):
            dnas.append(dna)
            print(f"   ✅ {niche} ← {url[:45]}…  (style {dna.get('sub_style_id','?')}, "
                  f"{dna.get('edit_intensity','?')})")
        else:
            print(f"   ⚠️ {niche} ← {url[:45]}…  (non analysable)")
    if not dnas:
        continue
    prof = {"video_type": niche, "samples": len(dnas), "source": "viral_internet"}
    for k in worker.STUDY_DNA:
        mc = most_common([d.get(k) for d in dnas])
        if mc is not None:
            prof[k] = mc
    # cadence de coupe indicative selon l'intensité apprise
    prof["cut_s"] = {"minimal": 3.6, "moderate": 3.0, "dynamic": 2.3}.get(
        str(prof.get("edit_intensity") or "moderate"), 2.8)
    prof["grade"] = prof.get("color_grade") or ""
    prof["intensity"] = {"minimal": 0.4, "moderate": 0.6, "dynamic": 0.9}.get(
        str(prof.get("edit_intensity") or "moderate"), 0.6)
    profiles[niche] = prof

print("[2/2] Enregistrement de la bibliothèque de styles…")
ok = 0
for niche, prof in profiles.items():
    blob = json.dumps(prof, ensure_ascii=False).encode()
    up = urllib.request.Request(
        f"{SB}/storage/v1/object/{OUT_BUCKET}/{urllib.parse.quote(niche)}.json",
        data=blob, method="POST",
        headers={"Authorization": "Bearer " + KEY, "apikey": KEY,
                 "Content-Type": "application/json", "x-upsert": "true"})
    try:
        urllib.request.urlopen(up, timeout=60)
        ok += 1
        print(f"   ✅ {niche}.json  (style {prof.get('sub_style_id','?')} · "
              f"{prof.get('edit_intensity','?')} · coupe/{prof['cut_s']}s · {prof['samples']} réf.)")
    except Exception as e:
        print(f"   ⚠️ {niche} : {e}")

print(f"\nTerminé : {ok} style(s) viral(aux) appris. Le worker les applique à tous.")
print("Rappel : bucket 'style-library' en PUBLIC.")
