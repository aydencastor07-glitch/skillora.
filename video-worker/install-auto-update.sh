#!/usr/bin/env bash
# À lancer UNE SEULE FOIS sur le serveur. Ensuite le worker se met à jour seul.
#
#   curl -fsSL https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker/install-auto-update.sh | bash
#
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/aydencastor07-glitch/skillora./main/video-worker"

echo "[1/3] Installation du script de mise à jour…"
install -d /opt/skillora-worker
curl -fsSL "$RAW_BASE/auto-update.sh" -o /opt/skillora-worker/auto-update.sh
chmod +x /opt/skillora-worker/auto-update.sh

echo "[2/3] Création de la tâche planifiée…"
cat > /etc/systemd/system/skillora-maj.service <<'EOF'
[Unit]
Description=Mise a jour du worker Skillora
After=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/skillora-worker/auto-update.sh
EOF

cat > /etc/systemd/system/skillora-maj.timer <<'EOF'
[Unit]
Description=Verifie les mises a jour du worker Skillora

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[3/3] Activation…"
systemctl daemon-reload
systemctl enable --now skillora-maj.timer
/opt/skillora-worker/auto-update.sh || true

echo ""
echo "✅ Terminé. Le worker se met désormais à jour tout seul, toutes les 10 minutes."
echo "   Voir les mises à jour : journalctl -u skillora-maj -f"
echo "   Prochaine vérification : systemctl list-timers skillora-maj"
