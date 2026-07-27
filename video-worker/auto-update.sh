#!/usr/bin/env bash
# Mise à jour automatique du worker Skillora.
#
# Installé une fois, ce script tourne tout seul toutes les 10 minutes : il
# récupère la dernière version de worker.py, et ne redémarre le service QUE si
# le fichier a réellement changé ET que sa syntaxe est valide.
#
# Deux garde-fous qui comptent :
#   - on ne redémarre jamais pour rien (comparaison d'empreinte) ;
#   - on ne met jamais en service un fichier cassé (vérification Python avant
#     de remplacer). Un envoi défectueux laisse le worker en place au lieu de
#     l'arrêter net.
set -euo pipefail

RAW="https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/worker.py"
CIBLE="/opt/skillora-worker/worker.py"
SERVICE="skillora-worker"
TMP="$(mktemp /tmp/worker-XXXXXX.py)"
trap 'rm -f "$TMP"' EXIT

# 1. Téléchargement (silencieux, on abandonne proprement si le réseau tombe)
if ! curl -fsSL --max-time 60 "$RAW" -o "$TMP"; then
  echo "maj: téléchargement impossible, on garde la version en place"
  exit 0
fi

# 2. Fichier plausible ? (un worker.py fait plus de 100 Ko)
if [ ! -s "$TMP" ] || [ "$(stat -c%s "$TMP")" -lt 50000 ]; then
  echo "maj: fichier trop petit ou vide, ignoré"
  exit 0
fi

# 3. Rien de nouveau -> on ne touche à rien
if [ -f "$CIBLE" ] && [ "$(sha256sum < "$TMP" | cut -d' ' -f1)" = "$(sha256sum < "$CIBLE" | cut -d' ' -f1)" ]; then
  exit 0
fi

# 4. Syntaxe valide ? Sinon on ne remplace RIEN.
if ! python3 -m py_compile "$TMP" 2>/dev/null; then
  echo "maj: la nouvelle version ne compile pas, mise à jour annulée"
  exit 0
fi

# 5. On garde la version précédente, on installe, on redémarre
[ -f "$CIBLE" ] && cp -f "$CIBLE" "${CIBLE}.precedent"
install -m 644 "$TMP" "$CIBLE"
systemctl restart "$SERVICE"
echo "maj: worker mis à jour et redémarré le $(date '+%d/%m/%Y à %H:%M')"
