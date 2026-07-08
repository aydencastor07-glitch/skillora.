"""
Skillora — Agent Analyste : apprend le STYLE des vidéos GAGNANTES d'un créateur.
==============================================================================
On donne les vidéos d'un créateur qui ont fait BEAUCOUP de vues (ses gagnantes),
Gemini les ÉTUDIE une par une, et on construit sa MÉMOIRE de style par niche :
  user-styles/{user_id}/{niche}.json
Le worker charge ensuite cette mémoire et monte les nouvelles vidéos du créateur
DANS le style qui a cartonné pour lui.

Entrée : un JSON (chemin en argument, ou stdin) de la forme
  {
    "user_id": "uuid-du-créateur",
    "min_views": 50000,
    "videos": [
      {"url": "https://....mp4", "views": 620000, "niche": "energetic"},
      {"url": "https://....mp4", "views": 1200000}
    ]
  }
(la niche est optionnelle : Gemini la détecte. On n'étudie que views >= min_views.)

Usage (serveur) :
  curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/study_winners.py -o /opt/skillora-worker/study_winners.py
  python3 /opt/skillora-worker/study_winners.py winners.json
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
os.environ.setdefault("SUPABASE_URL", "https://fkjqlmtugzdluzshxqsk.supabase.co")
# Récupère les clés depuis le service systemd si absentes (comme les autres scripts)
if os.path.exists(UNIT):
    for line in open(UNIT):
        for var in ("SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            m = re.match(rf"Environment={var}=(.+)", line.strip())
            if m and not os.environ.get(var):
                os.environ[var] = m.group(1).strip()
KEY = KEY or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worker

SB = worker.SB_URL
OUT_BUCKET = worker.USERSTYLE_BUCKET
# champs de style (les décisions de montage) qu'on retient d'une vidéo gagnante
DNA = ("video_type", "sub_style_id", "highlight", "edit_intensity",
       "color_grade", "music_mood", "audio_action")

if not KEY:
    print("❌ Clé Supabase introuvable."); sys.exit(1)
if not worker.GEMINI_KEY:
    print("❌ Clé Gemini introuvable (GEMINI_API_KEY)."); sys.exit(1)

# --- entrée ---
raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
cfg = json.loads(raw)
user_id = str(cfg.get("user_id") or "").strip()
min_views = int(cfg.get("min_views") or 50000)
videos = cfg.get("videos") or []
if not user_id or not videos:
    print("❌ Il faut user_id et videos[]."); sys.exit(1)

winners = [v for v in videos if int(v.get("views") or 0) >= min_views]
print(f"[1/3] {len(winners)}/{len(videos)} vidéo(s) gagnante(s) (>= {min_views} vues) à étudier.")
if not winners:
    print("   Aucune vidéo au-dessus du seuil. Rien à apprendre pour l'instant.")
    sys.exit(0)

work = tempfile.mkdtemp(prefix="study-")
by_niche = {}  # niche -> liste de (dna, views)
for i, v in enumerate(winners):
    url = str(v.get("url") or "")
    views = int(v.get("views") or 0)
    if not url:
        continue
    local = os.path.join(work, f"w{i}.mp4")
    try:
        print(f"   ⏳ étude {i + 1}/{len(winners)} ({views} vues)…")
        worker.download(url, local)
        d = worker.ffprobe_facts(local)["duration"]
        gem = worker.gemini_analyze_video(local, d)
        if not gem:
            print("      ⚠️ Gemini n'a pas pu analyser, on saute."); continue
        niche = str(v.get("niche") or gem.get("video_type") or "other").lower()
        dna = {k: gem.get(k) for k in DNA if gem.get(k) not in (None, "")}
        dna["video_type"] = niche
        by_niche.setdefault(niche, []).append((dna, views))
        print(f"      ✅ {niche} · style {dna.get('sub_style_id', '?')} · {dna.get('edit_intensity', '?')}")
    except Exception as e:
        print(f"      ⚠️ {url[:50]}… : {e}")
    finally:
        if os.path.exists(local):
            os.remove(local)

print(f"[2/3] Agrégation par niche ({len(by_niche)} niche(s))…")


def most_common(vals):
    vals = [x for x in vals if x not in (None, "")]
    return max(set(vals), key=vals.count) if vals else None


profiles = {}
for niche, items in by_niche.items():
    dnas = [d for d, _ in items]
    prof = {"video_type": niche, "samples": len(items),
            "avg_views": int(sum(vw for _, vw in items) / len(items))}
    for k in DNA:
        mc = most_common([d.get(k) for d in dnas])
        if mc is not None:
            prof[k] = mc
    profiles[niche] = prof

print("[3/3] Enregistrement de la mémoire du créateur…")
ok = 0
for niche, prof in profiles.items():
    blob = json.dumps(prof, ensure_ascii=False).encode()
    key = f"{user_id}/{niche}.json"
    up = urllib.request.Request(
        f"{SB}/storage/v1/object/{OUT_BUCKET}/{urllib.parse.quote(key)}",
        data=blob, method="POST",
        headers={"Authorization": "Bearer " + KEY, "apikey": KEY,
                 "Content-Type": "application/json", "x-upsert": "true"})
    try:
        urllib.request.urlopen(up, timeout=60)
        ok += 1
        print(f"   ✅ {key}  (style {prof.get('sub_style_id', '?')} · "
              f"{prof.get('edit_intensity', '?')} · {prof['samples']} vidéo(s) · "
              f"~{prof['avg_views']} vues)")
    except Exception as e:
        print(f"   ⚠️ {key} : {e}")

print(f"\nTerminé : {ok} niche(s) apprise(s) pour ce créateur.")
print("Rappel : crée le bucket 'user-styles' en PUBLIC. Le worker l'utilise tout seul.")
