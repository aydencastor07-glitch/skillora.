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

## Mise à jour automatique (à faire une fois)

Une seule commande, sur le serveur. Ensuite le worker se met à jour tout seul,
toutes les 10 minutes — plus rien à taper après chaque correction :

```bash
curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/install-auto-update.sh | bash
```

Deux garde-fous : le service n'est **redémarré que si le fichier a réellement
changé**, et une version qui ne compile pas est **refusée** — elle ne remplace
jamais celle qui tourne. L'ancienne version est conservée dans
`worker.py.precedent`.

Suivre les mises à jour : `journalctl -u skillora-maj -f`

## Mettre à jour à la main (si besoin)

**Depuis le serveur lui-même** (pas depuis ta machine — il n'y a rien à copier) :

```bash
# 1. yt-dlp à jour : c'est lui qui récupère les vidéos. Une version ancienne
#    fait échouer YouTube en silence -> plans sans images de référence.
pip3 install --break-system-packages -U yt-dlp

# 2. Dernière version du worker
curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/worker.py \
  -o /opt/skillora-worker/worker.py

# 3. Redémarrage + vérification
systemctl restart skillora-worker
journalctl -u skillora-worker -f
```

Le fichier installé est `/opt/skillora-worker/worker.py` et le service
s'appelle `skillora-worker`.

## Images de référence : ce que tu obtiens selon la source

| Source | Téléchargement de la vidéo | Images de référence |
|---|---|---|
| **Fichier importé** | direct depuis le stockage | **une capture par plan** (idéal) |
| **TikTok** | oui | **une capture par plan** |
| **YouTube** | bloqué (IP de centre de données) | affiche de la vidéo, sauf si cookies |
| **Instagram** | souvent bloqué | affiche de la publication |
| **Facebook** | souvent bloqué | affiche de la publication |

Quand le téléchargement échoue, le worker ne rend **jamais** un plan sans image :
il récupère l'affiche par trois voies successives — identifiant YouTube, miniature
déclarée par yt-dlp, puis la balise `og:image` que **toutes** les plateformes
publient pour l'affichage des liens partagés. Cette dernière ne demande ni compte
ni cookie, et couvre Instagram, Facebook, TikTok et X.

Pour obtenir **une capture par plan** partout, deux leviers : importer le fichier
plutôt que coller un lien (toujours parfait), ou fournir des cookies (ci-dessous).

## YouTube et Instagram : « Sign in to confirm you're not a bot »

YouTube bloque les adresses de **centre de données** (Hetzner, AWS…). Le
téléchargement de la vidéo échoue donc, même avec un yt-dlp à jour. Ce n'est
pas un bug : c'est une protection anti-robot liée à l'IP du serveur.

Sans rien faire, le worker s'en sort quand même : il récupère l'**affiche
officielle** de la vidéo (servie publiquement par YouTube à partir de
l'identifiant, sans aucune vérification) et la donne comme image de référence.
Le plan n'est jamais livré sans image.

Pour récupérer **une capture par plan** sur YouTube, il faut des cookies :

1. Sur ton ordinateur, connecte-toi à YouTube et exporte les cookies au format
   Netscape (extension « Get cookies.txt LOCALLY » par exemple).
2. Dépose le fichier sur le serveur, ex. `/opt/skillora-worker/cookies.txt`.
3. Ajoute la variable au service :

```bash
systemctl edit skillora-worker
# puis, dans l'éditeur :
[Service]
Environment=YTDLP_COOKIES=/opt/skillora-worker/cookies.txt
```

4. `systemctl restart skillora-worker`

Les cookies expirent au bout de quelques semaines : si la plateforme redemande
une connexion, ré-exporte-les. Le même fichier sert à YouTube et à Instagram.
TikTok fonctionne sans.

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
