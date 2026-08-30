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
apt -y install curl gnupg tmux htop jq pciutils

# --- NVIDIA Container Toolkit (GPU passthrough prerequisites) ---
install_nvidia_container_toolkit() {
  if command -v nvidia-container-toolkit >/dev/null 2>&1; then
    log "NVIDIA container toolkit already installed."
    return 0
  fi

  log "Installing NVIDIA container toolkit for GPU passthrough."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
  apt update
  apt -y install nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  log "NVIDIA container toolkit installed."
}

# --- GPU Orchestrator container ---
configure_gpu_orchestrator() {
  local image="${GPU_ORCH_IMAGE:-pmoves/gpu-orchestrator:latest}"
  local data_root="${GPU_ORCH_DATA_DIR:-/var/lib/gpu-orchestrator}"

  log "Provisioning GPU Orchestrator service (${image})."

  mkdir -p "${data_root}"

  cat <<EOF | tee /etc/systemd/system/gpu-orchestrator.service > /dev/null
[Unit]
Description=PMOVES GPU Orchestrator
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/gpu-orchestrator
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker rm -f gpu-orchestrator >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name gpu-orchestrator --rm \\
  --gpus device=\${GPU_ORCHESTRATOR_GPU_INDEX:-0} \\
  --network pmoves-net \\
  -p 8200:8200 \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  -v ${data_root}:/app/data \\
  -e GPU_ORCHESTRATOR_HOST=0.0.0.0 \\
  -e GPU_ORCHESTRATOR_PORT=8200 \\
  -e GPU_ORCHESTRATOR_NATS_URL=\${GPU_ORCHESTRATOR_NATS_URL:-nats://nats:pmoves@nats:4222} \\
  -e GPU_ORCHESTRATOR_GPU_INDEX=\${GPU_ORCHESTRATOR_GPU_INDEX:-0} \\
  -e GPU_ORCHESTRATOR_VLLM_URL=\${GPU_ORCHESTRATOR_VLLM_URL:-http://host.docker.internal:8100} \\
  -e GPU_ORCHESTRATOR_OLLAMA_URL=\${GPU_ORCHESTRATOR_OLLAMA_URL:-http://pmoves-ollama:11434} \\
  ${image}"
ExecStop=/usr/bin/docker stop gpu-orchestrator

[Install]
WantedBy=multi-user.target
EOF

  cat <<'EOF' | tee /etc/default/gpu-orchestrator > /dev/null
# GPU Orchestrator configuration (env_prefix = GPU_ORCHESTRATOR_)
# NATS URL default for local dev only; production overrides via secrets-funnel-injected env.
GPU_ORCHESTRATOR_GPU_INDEX=0
GPU_ORCHESTRATOR_NATS_URL=nats://nats:pmoves@nats:4222
GPU_ORCHESTRATOR_VLLM_URL=http://host.docker.internal:8100
GPU_ORCHESTRATOR_OLLAMA_URL=http://pmoves-ollama:11434
EOF

  systemctl daemon-reload
  systemctl enable gpu-orchestrator.service
  log "GPU Orchestrator service configured (start with: systemctl start gpu-orchestrator)."
}

# --- Ollama GPU container ---
configure_ollama_gpu() {
  local image="${OLLAMA_IMAGE:-ollama/ollama:latest}"
  local data_root="${OLLAMA_DATA_DIR:-/var/lib/ollama}"

  log "Provisioning Ollama GPU container (${image})."

  mkdir -p "${data_root}"

  cat <<EOF | tee /etc/systemd/system/ollama-gpu.service > /dev/null
[Unit]
Description=PMOVES Ollama GPU
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/ollama-gpu
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker rm -f pmoves-ollama >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name pmoves-ollama --rm \\
  --gpus all \\
  --network pmoves-net \\
  -p 11434:11434 \\
  -v ${data_root}:/root/.ollama \\
  -e OLLAMA_HOST=0.0.0.0 \\
  -e OLLAMA_ORIGINS='*' \\
  ${image}"
ExecStop=/usr/bin/docker stop pmoves-ollama

[Install]
WantedBy=multi-user.target
EOF

  cat <<'EOF' | tee /etc/default/ollama-gpu > /dev/null
# Ollama GPU configuration
EOF

  systemctl daemon-reload
  systemctl enable ollama-gpu.service
  log "Ollama GPU service configured (start with: systemctl start ollama-gpu)."
}

# --- PMOVES docker network ---
setup_pmoves_network() {
  log "Creating PMOVES Docker networks."
  docker network create pmoves-net 2>/dev/null || true
  docker network create pmoves-local-models 2>/dev/null || true
  log "Docker networks ready."
}

# Docker CE
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker CE."
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

# GPU stack prerequisites
install_nvidia_container_toolkit

# PMOVES networking
setup_pmoves_network

# GPU services (Ollama + Orchestrator)
configure_ollama_gpu
configure_gpu_orchestrator

# RustDesk relay
configure_rustdesk_server

# Tailscale on host (idempotent)
if ! command -v tailscale >/dev/null 2>&1; then
  log "Installing Tailscale."
  curl -fsSL https://tailscale.com/install.sh | sh
else
  log "Tailscale already installed."
fi
systemctl enable --now tailscaled

if tailscale status >/dev/null 2>&1; then
  log "Tailscale already joined to tailnet: $(tailscale ip -4 2>/dev/null || echo 'unknown')"
else
  echo "Now run: tailscale up --ssh --accept-routes --tag=tag:pmoves --tag=tag:pve --tag=tag:production"
fi

# CHIT-signed completion beacon — best-effort
if [[ -x /opt/pmoves/pmoves/tools/sign_trail.py ]] && [[ -n "${CHIT_PASSPHRASE:-}" ]]; then
  log "Emitting CHIT completion beacon."
  python3 /opt/pmoves/pmoves/tools/sign_trail.py \
    --agent-id "pve9-postinstall" \
    --summary "PVE 9 post-install completed on $(hostname)" \
    --phase "Phase A" 2>/dev/null || log "Beacon emit failed (non-fatal)."
else
  log "CHIT beacon skipped (sign_trail.py or CHIT_PASSPHRASE absent)."
fi

log "PVE 9 post-install complete. Review: systemctl list-unit-files | grep -E 'rustdesk|gpu-orchestrator|ollama-gpu'"
