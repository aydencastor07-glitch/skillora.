#!/usr/bin/env bash
# Skillora video-worker — installation tout-en-un.
# À lancer sur un serveur Ubuntu neuf (Hetzner) en root :
#
#   curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/bootstrap.sh -o s.sh && bash s.sh
#
# Le script installe ffmpeg + Python, télécharge le worker, te demande tes 2 clés
# (Supabase service_role et Groq), puis lance le service en continu.
set -euo pipefail

SUPABASE_URL="https://fkjqlmtugzdluzshxqsk.supabase.co"
RAW="https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/worker.py"

echo ""
echo "======================================================"
echo "   Skillora — installation du worker vidéo"
echo "======================================================"
echo ""

echo "[1/5] Installation de ffmpeg et Python…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ffmpeg fonts-dejavu-core fontconfig python3 python3-pip curl librsvg2-bin >/dev/null
# Détourage IA (texte 3D derrière la personne) — optionnel : le worker marche sans
pip3 install -q --break-system-packages rembg onnxruntime pillow >/dev/null 2>&1 || \
  echo "      (rembg non installé : l'effet 'texte derrière la personne' sera sauté)"
# Polices Google Fonts (licence OFL) : les looks du catalogue de sous-titres
mkdir -p /usr/share/fonts/truetype/custom
GF="https://raw.githubusercontent.com/google/fonts/main"
for f in "ofl/anton/Anton-Regular.ttf" \
         "apache/luckiestguy/LuckiestGuy-Regular.ttf" \
         "ofl/pacifico/Pacifico-Regular.ttf" \
         "ofl/orbitron/Orbitron%5Bwght%5D.ttf" \
         "ofl/courierprime/CourierPrime-Regular.ttf" \
         "ofl/courierprime/CourierPrime-Bold.ttf" \
         "ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"; do
  curl -fsSL "$GF/$f" -o "/usr/share/fonts/truetype/custom/$(basename "${f//%5B/_}" | sed 's/%5D//')" || true
done
fc-cache -f >/dev/null 2>&1 || true
echo "      ✅ fait"

echo "[2/5] Téléchargement du worker…"
install -d /opt/skillora-worker
curl -fsSL "$RAW" -o /opt/skillora-worker/worker.py
echo "      ✅ fait"

echo ""
echo "[3/5] Tes clés (elles restent sur CE serveur, colle-les puis Entrée) :"
echo ""
echo "   • Clé Supabase service_role"
echo "     (Supabase > Settings > API > service_role, la clé 'secret')"
printf "   Colle-la ici : "
read -r SRK
echo ""
echo "   • Clé Groq (console.groq.com > API Keys)"
printf "   Colle-la ici : "
read -r GROQ
echo ""
echo "   • Clé Pexels pour les plans b-roll — OPTIONNELLE"
echo "     (pexels.com/api — laisse vide et Entrée si tu ne l'as pas encore)"
printf "   Colle-la ici : "
read -r PEXELS
echo ""
echo "   • Clé ElevenLabs pour des sous-titres TRÈS précis (Scribe) — OPTIONNELLE"
echo "     (elevenlabs.io > API Keys — laisse vide et Entrée sinon, Whisper prend le relais)"
printf "   Colle-la ici : "
read -r ELEVEN
echo ""
echo "   • Clé Gemini pour l'analyse vidéo complète (les yeux) — OPTIONNELLE"
echo "     (aistudio.google.com > Get API key — GRATUIT, sans carte — laisse vide sinon)"
printf "   Colle-la ici : "
read -r GEMINI

if [ -z "${SRK:-}" ] || [ -z "${GROQ:-}" ]; then
  echo ""
  echo "❌ La clé Supabase et la clé Groq sont obligatoires. Relance le script."
  exit 1
fi

echo ""
echo "[4/5] Création du service…"
cat > /etc/systemd/system/skillora-worker.service <<EOF
[Unit]
Description=Skillora video worker
After=network-online.target
Wants=network-online.target

[Service]
Environment=SUPABASE_URL=${SUPABASE_URL}
Environment=SUPABASE_SERVICE_ROLE_KEY=${SRK}
Environment=GROQ_API_KEY=${GROQ}
Environment=PEXELS_API_KEY=${PEXELS}
Environment=ELEVENLABS_API_KEY=${ELEVEN}
Environment=GEMINI_API_KEY=${GEMINI}
ExecStart=/usr/bin/python3 -u /opt/skillora-worker/worker.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
chmod 600 /etc/systemd/system/skillora-worker.service
systemctl daemon-reload
systemctl enable --now skillora-worker >/dev/null 2>&1
echo "      ✅ fait"

echo ""
echo "[5/5] Vérification…"
sleep 2
if systemctl is-active --quiet skillora-worker; then
  echo "      ✅ Le worker tourne !"
else
  echo "      ⚠️  Le service ne s'est pas lancé. Logs :"
  journalctl -u skillora-worker -n 20 --no-pager || true
fi

echo ""
echo "======================================================"
echo "   Terminé. Le worker attend les vidéos à améliorer."
echo "   Voir les logs en direct :"
echo "     journalctl -u skillora-worker -f"
echo "======================================================"
echo ""
