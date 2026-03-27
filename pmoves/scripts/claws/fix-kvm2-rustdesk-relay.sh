#!/usr/bin/env bash
# fix-kvm2-rustdesk-relay.sh — Add -r relay flag to KVM2 hbbs + restart
# Run from Z890: & "C:\Program Files\Git\bin\bash.exe" pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh

set -euo pipefail

KEY="${LOCALAPPDATA:-$HOME/AppData/Local}/Temp/hostinger_vps"
[ -f "$KEY" ] || KEY="/tmp/hostinger_vps"
[ -f "$KEY" ] || { echo "ERROR: SSH key not found at either path"; exit 1; }

KVM2="${HOSTINGER_KVM2_IP:?Set HOSTINGER_KVM2_IP (KVM2 public IP)}"

echo "Fixing hbbs relay config on KVM2..."
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "root@$KVM2" "
    sed -i 's|ExecStart=/opt/rustdesk-server/hbbs.*|ExecStart=/opt/rustdesk-server/hbbs -r $KVM2|' /etc/systemd/system/hbbs.service
    systemctl daemon-reload
    systemctl restart hbbs hbbr
    sleep 3
    echo '=== hbbs service ==='
    grep ExecStart /etc/systemd/system/hbbs.service
    echo '=== logs ==='
    journalctl -u hbbs -n 3 --no-pager 2>/dev/null | grep -E 'relay|Key|Start'
"
echo "Done."
