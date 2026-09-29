#!/usr/bin/env bash
# Насби systemd-и хидмат ва watchdog + restart бо коди нав.
# Аз ~/Hrcontrol иҷро кунед:   sudo bash deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."

install -m 644 -o root -g root hrcontrol.service                /etc/systemd/system/hrcontrol.service
install -m 755 -o root -g root deploy/hrcontrol-watchdog.sh      /usr/local/sbin/hrcontrol-watchdog
install -m 644 -o root -g root deploy/hrcontrol-watchdog.service /etc/systemd/system/hrcontrol-watchdog.service
install -m 644 -o root -g root deploy/hrcontrol-watchdog.timer   /etc/systemd/system/hrcontrol-watchdog.timer

systemctl daemon-reload
systemctl enable hrcontrol.service
systemctl reset-failed hrcontrol.service 2>/dev/null || true
systemctl restart hrcontrol.service
systemctl enable --now hrcontrol-watchdog.timer

echo "✅ hrcontrol.service (enabled, restarted) ва hrcontrol-watchdog.timer насб шуданд"
