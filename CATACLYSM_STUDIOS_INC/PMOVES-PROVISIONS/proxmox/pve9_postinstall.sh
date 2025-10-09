#!/usr/bin/env bash
# Run after installing Proxmox VE 9 from ISO
set -euo pipefail

log() {
  echo -e "\n[pmoves] $*"
}

configure_rustdesk_server() {
  local image="${RUSTDESK_SERVER_IMAGE:-rustdesk/rustdesk-server:latest}"
  local data_root="${RUSTDESK_DATA_DIR:-/var/lib/rustdesk}"
  local env_file="/etc/default/rustdesk-server"

  log "Provisioning RustDesk relay/ID services (hbbs/hbbr) via Docker (${image})."

  mkdir -p "${data_root}/hbbs" "${data_root}/hbbr"

  if [[ ! -f "${env_file}" ]]; then
    cat <<'EOF' | tee "${env_file}" > /dev/null
# Environment overrides for RustDesk relay services.
# Modify HBBS_ARGS / HBBR_ARGS to pass additional flags (e.g. --relay my.domain.com).
# Ports default to upstream recommendations but can be changed when needed.
HBBS_ARGS=""
HBBR_ARGS=""
RUSTDESK_PORT_HBBS_TCP=21115
RUSTDESK_PORT_HBBS_RELAY_TCP=21116
RUSTDESK_PORT_HBBS_RELAY_UDP=21116
RUSTDESK_PORT_HBBS_API=21118
RUSTDESK_PORT_HBBR_TCP=21117
RUSTDESK_PORT_HBBR_REVERSE=21119
EOF
  fi

  cat <<EOF | tee /etc/systemd/system/rustdesk-hbbs.service > /dev/null
[Unit]
Description=RustDesk Rendezvous Server (hbbs)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/rustdesk-server
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker pull ${image}
ExecStartPre=/usr/bin/docker rm -f rustdesk-hbbs >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name rustdesk-hbbs --rm \\
  -v ${data_root}/hbbs:/root \\
  -p \${RUSTDESK_PORT_HBBS_TCP}:21115 \\
  -p \${RUSTDESK_PORT_HBBS_RELAY_TCP}:21116 \\
  -p \${RUSTDESK_PORT_HBBS_RELAY_UDP}:21116/udp \\
  -p \${RUSTDESK_PORT_HBBS_API}:21118 \\
  ${image} hbbs \${HBBS_ARGS}"
ExecStop=/usr/bin/docker stop rustdesk-hbbs

[Install]
WantedBy=multi-user.target
EOF

  cat <<EOF | tee /etc/systemd/system/rustdesk-hbbr.service > /dev/null
[Unit]
Description=RustDesk Relay Server (hbbr)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/rustdesk-server
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker pull ${image}
ExecStartPre=/usr/bin/docker rm -f rustdesk-hbbr >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name rustdesk-hbbr --rm \\
  -v ${data_root}/hbbr:/root \\
  -p \${RUSTDESK_PORT_HBBR_TCP}:21117 \\
  -p \${RUSTDESK_PORT_HBBR_REVERSE}:21119 \\
  ${image} hbbr \${HBBR_ARGS}"
ExecStop=/usr/bin/docker stop rustdesk-hbbr

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now rustdesk-hbbs.service rustdesk-hbbr.service
  log "RustDesk services enabled. Keys live under ${data_root}/hbbs (id_ed25519*)."
}

apt update && apt -y full-upgrade

# Enable non-subscription repo (pve-no-subscription)
cat >/etc/apt/sources.list.d/pve-no-subscription.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF

apt update

# Basic QoL
apt -y install curl gnupg tmux htop jq

# Docker CE (for RustDesk containers)
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker CE for RustDesk relay containers."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  if [[ ! -f /etc/apt/sources.list.d/docker.list ]]; then
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $VERSION_CODENAME stable" \
      | tee /etc/apt/sources.list.d/docker.list > /dev/null
  fi
  apt update
  apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed; skipping CE setup."
fi

systemctl enable --now docker

configure_rustdesk_server

# Tailscale on host (optional but convenient)
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo "Now run: tailscale up --ssh --accept-routes"
