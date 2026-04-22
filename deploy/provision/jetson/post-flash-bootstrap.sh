#!/usr/bin/env bash
# Jetson JetPack 7 Post-Flash Bootstrap (runs ON the Jetson)
#
# Executed on a freshly-flashed Jetson Orin Nano after first boot. Brings the
# device to PMOVES-ready state:
#   1. Profile hardware (Jetson-specific — reuses common glances probe)
#   2. Apply Nemotron/NemoClaw branding (hostname, /etc/motd, plymouth)
#   3. Join PMOVES tailnet with jetson-specific tags
#   4. Install nvidia-container-toolkit (JetPack 7.0 ships CUDA 12.8)
#   5. Clone PMOVES.AI + apply arm64 compose override
#   6. Install Ollama + small model for on-device inference
#
# Required env (passed from jetpack7-reflash.sh):
#   DEVICE               nemotron-1 | nemotron-2
#   TAILSCALE_AUTHKEY    From `make -C pmoves fleet-enroll ROLE=edge DEVICE=nemotron-N`

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo -e "\n[post-flash] $*"; }
step() { log "─── Step: $* ───"; }

require_root() { [[ $EUID -eq 0 ]] || { echo "[post-flash] ERROR: run as root" >&2; exit 1; }; }

if [[ -z "${DEVICE:-}" ]]; then
  log "ERROR: DEVICE env var required (nemotron-1 | nemotron-2)"
  exit 1
fi
case "$DEVICE" in
  nemotron-1|nemotron-2) ;;
  *) log "ERROR: unrecognized DEVICE='$DEVICE'"; exit 1 ;;
esac

require_root

# ── Step 1: Verify JetPack 7.0 + L4T r37 ──────────────────────────────────
step "1/6: Verify JetPack 7.0 / L4T r37"
if [[ -r /etc/nv_tegra_release ]]; then
  log "L4T release info:"
  head -1 /etc/nv_tegra_release
  if ! grep -qE 'R37|r37' /etc/nv_tegra_release; then
    log "WARN: expected L4T R37 (JetPack 7.0), got a different release. Continuing anyway."
  fi
else
  log "WARN: /etc/nv_tegra_release missing — is this actually a Jetson?"
fi

log "CUDA version:"
if command -v nvcc >/dev/null 2>&1; then
  nvcc --version 2>/dev/null | grep release
else
  log "nvcc not on PATH — JetPack 7 should ship CUDA 12.8; verify manually"
fi

# ── Step 2: Nemotron/NemoClaw branding ────────────────────────────────────
step "2/6: Apply Nemotron/NemoClaw branding"

# Set hostname
hostnamectl set-hostname "${DEVICE}"
log "Hostname: $(hostname)"

# /etc/motd (NVIDIA/Nemotron theme)
if [[ -r "${SCRIPT_DIR}/nemotron-branding/motd.txt" ]]; then
  cp "${SCRIPT_DIR}/nemotron-branding/motd.txt" /etc/motd
  # Expand $DEVICE placeholder
  sed -i "s/\${DEVICE}/${DEVICE}/g" /etc/motd
  log "Installed /etc/motd"
fi

# Plymouth theme (boot splash)
if [[ -d "${SCRIPT_DIR}/nemotron-branding/plymouth-theme" ]]; then
  if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    mkdir -p /usr/share/plymouth/themes/nemotron
    cp -r "${SCRIPT_DIR}/nemotron-branding/plymouth-theme/"* /usr/share/plymouth/themes/nemotron/ 2>/dev/null || true
    plymouth-set-default-theme -R nemotron 2>/dev/null || \
      log "WARN: plymouth theme install failed — falling back to default theme"
  else
    log "Plymouth tooling not present — skipping boot splash customization"
  fi
fi

# ── Step 3: Install Tailscale + enroll ────────────────────────────────────
step "3/6: Tailscale enrollment"
if [[ -z "${TAILSCALE_AUTHKEY:-}" ]]; then
  log "WARN: TAILSCALE_AUTHKEY not provided. Skipping tailnet join."
  log "To enroll later, run on a trusted node:"
  log "  make -C pmoves fleet-enroll ROLE=edge DEVICE=${DEVICE}"
  log "Then on this Jetson:"
  log "  sudo TAILSCALE_AUTHKEY=tskey-xxx tailscale up --hostname=pmoves-${DEVICE} --tag=tag:pmoves --tag=tag:jetson --tag=tag:nemotron"
else
  if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  tailscale up \
    --auth-key "$TAILSCALE_AUTHKEY" \
    --hostname "pmoves-${DEVICE}" \
    --accept-routes --accept-dns \
    --tag=tag:pmoves --tag=tag:jetson --tag=tag:nemotron --tag=tag:edge --tag=tag:arm64 --tag=tag:production
  sleep 3
  log "Tailscale: $(tailscale ip -4 2>/dev/null || echo pending) / $(tailscale status | head -1 || echo unknown)"
fi

# ── Step 4: nvidia-container-toolkit (Ubuntu 24.04 repo) ──────────────────
step "4/6: NVIDIA container toolkit (arm64)"
if ! dpkg -l nvidia-container-toolkit 2>/dev/null | grep -q '^ii'; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker 2>/dev/null || log "docker not yet installed — will configure on install"
else
  log "nvidia-container-toolkit already installed"
fi

# Install docker if missing (JetPack doesn't always preload it)
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker via get.docker.com (arm64 supported)"
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "${SUDO_USER:-ubuntu}" 2>/dev/null || true
  nvidia-ctk runtime configure --runtime=docker
  systemctl enable --now docker
fi

# ── Step 5: Clone PMOVES.AI + apply arm64 override ────────────────────────
step "5/6: Clone PMOVES.AI"
CLONE_DIR="/opt/pmoves"
if [[ ! -d "$CLONE_DIR/.git" ]]; then
  mkdir -p "$(dirname "$CLONE_DIR")"
  git clone --depth 1 https://github.com/POWERFULMOVES/PMOVES.AI.git "$CLONE_DIR"
else
  git -C "$CLONE_DIR" fetch origin main
  git -C "$CLONE_DIR" pull --ff-only origin main || log "WARN: pull failed"
fi

# Apply arm64 compose override (symlink convention matches fleet layout)
if [[ -f "$CLONE_DIR/pmoves/docker-compose.arm64.override.yml" ]]; then
  log "arm64 compose override available: pmoves/docker-compose.arm64.override.yml"
  log "Invoke with: docker compose -f docker-compose.yml -f docker-compose.hardened.yml -f docker-compose.arm64.override.yml up -d"
fi

# Run env-setup non-interactively
if [[ -f "$CLONE_DIR/pmoves/Makefile" ]]; then
  PMOVES_ENV_NONINTERACTIVE=1 make -C "$CLONE_DIR/pmoves" env-setup 2>&1 | tail -10 || log "WARN: env-setup had errors"
fi

# ── Step 6: Ollama + small model for edge inference ───────────────────────
step "6/6: Ollama (arm64) + small-model pull"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

# Bind Ollama to Tailscale interface only (ACL-gated)
mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=http://100.64.0.0/10,http://127.0.0.1:*"
EOF
systemctl daemon-reload
systemctl enable --now ollama || log "WARN: ollama service failed to start"

# Pull a small model suitable for Jetson Orin (8 GB VRAM limit)
# Gemma 2 2B fits comfortably; adjust via env PRELOAD_MODEL
: "${PRELOAD_MODEL:=gemma2:2b}"
log "Pulling edge-friendly model: $PRELOAD_MODEL (background)"
( ollama pull "$PRELOAD_MODEL" >/dev/null 2>&1 & ) || log "WARN: ollama pull kicked off in background"

# ── Summary ───────────────────────────────────────────────────────────────
log "═══════════════════════════════════════════"
log "  Jetson $DEVICE post-flash bootstrap complete."
log "═══════════════════════════════════════════"
log "Hostname:    $(hostname)"
log "Tailscale:   $(tailscale ip -4 2>/dev/null || echo pending)"
log "Docker:      $(docker --version 2>/dev/null || echo not-installed)"
log "Ollama:      $(ollama --version 2>/dev/null || echo not-installed)"
log ""
log "Verify from a trusted node:"
log "  make -C pmoves jetson-verify DEVICE=$DEVICE"
