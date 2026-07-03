#!/usr/bin/env bash
# Skillora video-worker — installation en 1 commande sur un serveur Ubuntu/Debian neuf.
#
#   1. Crée un serveur (Hetzner CX22 conseillé, Ubuntu 24.04).
#   2. Copie ce dossier dessus :  scp -r video-worker root@IP:/opt/
#   3. Connecte-toi :             ssh root@IP
#   4. Renseigne les clés puis :  cd /opt/video-worker && bash install.sh
#
set -euo pipefail

: "${SUPABASE_URL:?Définis SUPABASE_URL (ex: export SUPABASE_URL=https://xxxx.supabase.co)}"
: "${SUPABASE_SERVICE_ROLE_KEY:?Définis SUPABASE_SERVICE_ROLE_KEY (Supabase > Settings > API)}"

apt-get update
apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core python3

install -d /opt/skillora-worker
cp "$(dirname "$0")/worker.py" /opt/skillora-worker/worker.py

cat > /etc/systemd/system/skillora-worker.service <<EOF
[Unit]
Description=Skillora video worker
After=network-online.target

[Service]
Environment=SUPABASE_URL=${SUPABASE_URL}
Environment=SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
Environment=GROQ_API_KEY=${GROQ_API_KEY:-}
Environment=PEXELS_API_KEY=${PEXELS_API_KEY:-}
ExecStart=/usr/bin/python3 -u /opt/skillora-worker/worker.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now skillora-worker
echo "✅ Worker lancé. Logs en direct : journalctl -u skillora-worker -f"
