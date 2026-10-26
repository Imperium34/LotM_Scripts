#!/usr/bin/env bash
# Haftalik zamanlayiciyi kurar (bir kez). Kaldirmak:
#   systemctl --user disable --now lotm-haftalik.timer
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ~/.config/systemd/user ../Reports/haftalik
ln -sf "$PWD/lotm-haftalik.service" ~/.config/systemd/user/
ln -sf "$PWD/lotm-haftalik.timer" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lotm-haftalik.timer
systemctl --user list-timers lotm-haftalik.timer
echo "Hemen denemek icin: systemctl --user start lotm-haftalik.service"
