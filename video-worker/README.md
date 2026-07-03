# 🎬 Skillora video-worker — « Améliorer ma vidéo »

Le serveur qui améliore automatiquement les vidéos des utilisateurs :
il décide **ce qui manque** à chaque vidéo (selon la niche du créateur et les
retours du scan), puis applique uniquement ce qui est utile :

| Amélioration | Quand | Avec quoi | Coût |
|---|---|---|---|
| Sous-titres animés (karaoké) | s'il y a de la parole et pas déjà de sous-titres | Groq Whisper (clé déjà utilisée par l'app) + FFmpeg | ≈ gratuit |
| Coupe des temps morts | pauses > 0,7 s dans une vidéo parlée | FFmpeg | gratuit |
| Recadrage vertical 9:16 | vidéo horizontale | FFmpeg | gratuit |
| Accroche incrustée (hook) | décidé par l'IA | Groq LLM + FFmpeg | ≈ gratuit |
| Plans d'illustration (b-roll) | sujets visuels détectés dans la parole | API Pexels (gratuite, usage commercial autorisé) | gratuit |
| Musique adaptée à la vidéo | vidéos sans parole / ambiance | bucket `music-library` (pistes libres de droits) | gratuit |
| Normalisation du son | toujours | FFmpeg loudnorm −14 LUFS | gratuit |

L'app crée un job via l'edge function `video-improve` → le worker le réclame
(`claim_video_job()`), pousse chaque étape en direct dans `video_jobs.steps`
(l'app les affiche), puis dépose la vidéo améliorée dans
`post-media/improved/{user}/{job}.mp4`.

## Déploiement (Hetzner, ~5 €/mois — recommandé)

1. Crée un compte sur <https://www.hetzner.com/cloud>, projet → serveur
   **CX22** (2 vCPU / 4 Go), image **Ubuntu 24.04**.
2. Depuis ta machine : `scp -r video-worker root@IP_DU_SERVEUR:/opt/`
3. `ssh root@IP_DU_SERVEUR` puis :

```bash
export SUPABASE_URL=https://fkjqlmtugzdluzshxqsk.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=...   # Supabase > Settings > API > service_role
export GROQ_API_KEY=...                # la même que dans les secrets Supabase
export PEXELS_API_KEY=...              # gratuit sur https://www.pexels.com/api/
cd /opt/video-worker && bash install.sh
```

C'est tout : le service tourne en continu et redémarre tout seul
(`journalctl -u skillora-worker -f` pour les logs).

## Alternative Docker (Railway, Fly.io, n'importe où)

```bash
docker build -t skillora-worker .
docker run -d --restart=always \
  -e SUPABASE_URL=... -e SUPABASE_SERVICE_ROLE_KEY=... \
  -e GROQ_API_KEY=... -e PEXELS_API_KEY=... \
  skillora-worker
```

## Musique (optionnel)

Crée un bucket **public** `music-library` dans Supabase Storage avec des
pistes **libres de droits** (CC0 — Pixabay Music par ex.) et un
`manifest.json` :

```json
[
  { "file": "chill-01.mp3", "mood": "chill" },
  { "file": "hype-01.mp3",  "mood": "hype"  }
]
```

Sans bucket, le worker saute simplement l'étape musique.

## Réglages

| Variable | Défaut | Rôle |
|---|---|---|
| `POLL_SECONDS` | 3 | fréquence de vérification des jobs |
| `MAX_DURATION_S` | 300 | durée max acceptée (secondes) |
| `MUSIC_BUCKET` | music-library | bucket des musiques |
| `SUB_FONT` | DejaVu Sans | police des sous-titres |
