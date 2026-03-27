#!/usr/bin/env bash
# restart-jetson-rustdesk.sh — Write root config + restart RustDesk on Jetsons
# Usage: JETSON_IPS="x.x.x.x y.y.y.y" HOSTINGER_KVM2_IP=<ip> RUSTDESK_RELAY_KEY=<key> ./restart-jetson-rustdesk.sh
# Requires: JETSON_IPS (space-separated LAN IPs), HOSTINGER_KVM2_IP, RUSTDESK_RELAY_KEY
# Prompts for sudo password interactively.

set -euo pipefail

IFS=' ' read -ra JETSONS <<< "${JETSON_IPS:?Set JETSON_IPS as space-separated LAN IPs}"
USER="pmovesnvme"
KEY="${LOCALAPPDATA:-$HOME/AppData/Local}/Temp/hostinger_vps"
[ -f "$KEY" ] || KEY="/tmp/hostinger_vps"
[ -f "$KEY" ] || { echo "ERROR: SSH key not found at either path"; exit 1; }

RUSTDESK_SERVER="${HOSTINGER_KVM2_IP:?Set HOSTINGER_KVM2_IP (KVM2 public IP)}"
RUSTDESK_KEY="${RUSTDESK_RELAY_KEY:?Set RUSTDESK_RELAY_KEY (RustDesk server public key)}"

echo "Enter sudo password for pmovesnvme on Jetsons:"
read -s SUDO_PW
echo ""

for IP in "${JETSONS[@]}"; do
    echo "=== $IP ==="

    # 1. Write config to temp file (no sudo needed)
    echo -n "  write-tmp: "
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "$USER@$IP" "cat > /tmp/rustdesk_kvm2.toml << 'EOF'
rendezvous_server = '${RUSTDESK_SERVER}:21116'
nat_type = 1
serial = 0

[options]
custom-rendezvous-server = '${RUSTDESK_SERVER}'
key = '${RUSTDESK_KEY}'
relay-server = '${RUSTDESK_SERVER}'
allow-remote-config-modification = 'Y'
verification-method = 'use-permanent-password'
av1-test = 'Y'
EOF
echo 'ok'" && echo ""

    # 2. Stop service, copy to BOTH config locations, inject root SSH key, restart
    echo -n "  deploy: "
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "$USER@$IP" \
        "echo '${SUDO_PW}' | sudo -S bash -c '
            systemctl stop rustdesk
            mkdir -p /root/.config/rustdesk
            cp /tmp/rustdesk_kvm2.toml /root/.config/rustdesk/RustDesk2.toml
            cp /tmp/rustdesk_kvm2.toml /home/pmovesnvme/.config/rustdesk/RustDesk2.toml
            chown pmovesnvme:pmovesnvme /home/pmovesnvme/.config/rustdesk/RustDesk2.toml
            mkdir -p /root/.ssh && chmod 700 /root/.ssh
            grep -q pmoves-claw /root/.ssh/authorized_keys 2>/dev/null || echo \"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILwNwCmQKDS3c6LuRRLKf60yQHfLyUINnU1Z1eTytcrf pmoves-claw@pmoves.ai\" >> /root/.ssh/authorized_keys
            chmod 600 /root/.ssh/authorized_keys
            systemctl start rustdesk
            echo DONE
        ' 2>&1 | tail -1"

    # 3. Verify
    echo -n "  verify: "
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "$USER@$IP" \
        "echo '${SUDO_PW}' | sudo -S cat /root/.config/rustdesk/RustDesk2.toml 2>/dev/null | grep rendezvous | head -1"

    echo ""
done

echo "Checking KVM2 server registrations in 10 seconds..."
sleep 10
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i "$KEY" "root@$RUSTDESK_SERVER" \
    "journalctl -u hbbs --since '1 min ago' --no-pager 2>/dev/null | grep update_pk" 2>/dev/null || echo "No registrations yet"
