#!/usr/bin/env bash
# restart-jetson-rustdesk.sh — Restart RustDesk on Jetsons with sudo
# Usage: ./restart-jetson-rustdesk.sh
# Prompts for sudo password interactively.

set -euo pipefail

JETSONS=("192.168.1.110" "192.168.1.144")
USER="pmovesnvme"
KEY="${LOCALAPPDATA:-$HOME/AppData/Local}/Temp/hostinger_vps"
# Fallback for Git Bash
[ -f "$KEY" ] || KEY="/tmp/hostinger_vps"

echo "Enter sudo password for pmovesnvme on Jetsons:"
read -s SUDO_PW
echo ""

for IP in "${JETSONS[@]}"; do
    echo -n "$IP: "
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "$USER@$IP" \
        "echo '$SUDO_PW' | sudo -S systemctl restart rustdesk 2>/dev/null && echo 'restarted' || echo 'failed'"
done

echo ""
echo "Checking server registrations in 5 seconds..."
sleep 5
pm2 logs hbbs --lines 5 --nostream 2>&1 | grep "update_pk" | tail -5
