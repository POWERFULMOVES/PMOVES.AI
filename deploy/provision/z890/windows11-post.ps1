# ══════════════════════════════════════════════════════════════════════════
# PMOVES.AI — Z890 Windows 11 Post-Install Orchestrator
# ══════════════════════════════════════════════════════════════════════════
#
# Extends the existing pmoves/scripts/windows_bootstrap.ps1 (Chocolatey toolchain)
# and pmoves/scripts/z890_host_setup.ps1 (netsh portproxy) with additional
# post-install tasks specific to a fresh Windows 11 install on the Z890
# multi-boot NVMe:
#   - Install Chocolatey if absent
#   - Baseline packages via windows_bootstrap.ps1 (python, git, make, jq)
#   - Enable WSL2 + Ubuntu 24.04 distro
#   - Install Docker Desktop
#   - Install NVIDIA driver (Studio Driver preferred over GRD for workloads)
#   - Install Tailscale Windows client
#   - Apply netsh portproxy rules via z890_host_setup.ps1
#   - Clone PMOVES.AI to D:\PMOVES.AI\PMOVES.AI (matches existing dev layout)
#
# REQUIRES: Elevated PowerShell (Run as Administrator).
# IDEMPOTENT: Safe to re-run; each step checks state before mutating.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File deploy/provision/z890/windows11-post.ps1
#   # Skip steps:
#   powershell -ExecutionPolicy Bypass -File windows11-post.ps1 -SkipWSL -SkipDockerDesktop
# ══════════════════════════════════════════════════════════════════════════

Param(
  [switch]$SkipChocoBootstrap,
  [switch]$SkipWSL,
  [switch]$SkipDockerDesktop,
  [switch]$SkipNvidia,
  [switch]$SkipTailscale,
  [switch]$SkipRepoClone,
  [switch]$SkipNetsh,
  [string]$RepoClonePath = "D:\PMOVES.AI\PMOVES.AI",
  [string]$TailscaleAuthKey
)

$ErrorActionPreference = 'Continue'

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Log-Step  { Param($msg) Write-Host ("`n[win11-post] === " + $msg + " ===") -ForegroundColor Cyan }
function Log-Info  { Param($msg) Write-Host ("[win11-post] " + $msg) -ForegroundColor Green }
function Log-Warn  { Param($msg) Write-Host ("[win11-post] WARN: " + $msg) -ForegroundColor Yellow }
function Log-Error { Param($msg) Write-Host ("[win11-post] ERROR: " + $msg) -ForegroundColor Red }

if (-not (Test-Admin)) {
  Log-Error "This script requires Administrator privileges."
  exit 1
}

# ── Script locations ────────────────────────────────────────────────────────
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PmovesScripts = Join-Path (Split-Path -Parent (Split-Path -Parent $ScriptDir)) "pmoves\scripts"
# When running from a fresh Windows install where the repo isn't cloned yet,
# windows_bootstrap.ps1 may not exist on disk. Handle both cases.
$BootstrapPs1  = Join-Path $PmovesScripts "windows_bootstrap.ps1"
$HostSetupPs1  = Join-Path $PmovesScripts "z890_host_setup.ps1"

Log-Info ("Script dir:   " + $ScriptDir)
Log-Info ("Repo scripts: " + $PmovesScripts)

# ── 1. Chocolatey + baseline packages ──────────────────────────────────────
Log-Step "1/7: Chocolatey + baseline (python, git, make, jq)"
if (-not $SkipChocoBootstrap) {
  if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Log-Info "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = 3072
    iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
  } else {
    Log-Info "Chocolatey already installed."
  }
  if (Test-Path $BootstrapPs1) {
    & $BootstrapPs1 -Force
  } else {
    Log-Warn "windows_bootstrap.ps1 not found at $BootstrapPs1 — installing packages inline."
    foreach ($pkg in @('python','git','make','jq','curl')) {
      if (-not (choco list --local-only | Select-String -Pattern ("^" + [regex]::Escape($pkg) + " "))) {
        choco install $pkg -y
      }
    }
  }
} else {
  Log-Info "Skipped (-SkipChocoBootstrap)"
}

# ── 2. WSL2 + Ubuntu 24.04 ──────────────────────────────────────────────────
Log-Step "2/7: WSL2 + Ubuntu 24.04 distro"
if (-not $SkipWSL) {
  $wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux 2>$null
  $vmFeature  = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform 2>$null
  if ($wslFeature.State -ne 'Enabled' -or $vmFeature.State -ne 'Enabled') {
    Log-Info "Enabling WSL + VirtualMachinePlatform features (reboot will be required)..."
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart | Out-Null
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart | Out-Null
  }
  try {
    wsl --set-default-version 2 2>$null | Out-Null
    $installed = wsl --list --quiet 2>$null
    if ($installed -notmatch 'Ubuntu-24.04') {
      Log-Info "Installing Ubuntu-24.04 via wsl --install..."
      wsl --install -d Ubuntu-24.04 --no-launch
    } else {
      Log-Info "Ubuntu-24.04 already installed in WSL."
    }
  } catch {
    Log-Warn ("WSL install failed: " + $_.Exception.Message + " — reboot may be needed first.")
  }
} else {
  Log-Info "Skipped (-SkipWSL)"
}

# ── 3. Docker Desktop ───────────────────────────────────────────────────────
Log-Step "3/7: Docker Desktop"
if (-not $SkipDockerDesktop) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Log-Info "Installing Docker Desktop via Chocolatey..."
    choco install docker-desktop -y
    Log-Warn "Docker Desktop requires a sign-in on first launch. Launch it manually once, then re-run portions of this script."
  } else {
    Log-Info ("Docker present: " + (docker --version))
  }
} else {
  Log-Info "Skipped (-SkipDockerDesktop)"
}

# ── 4. NVIDIA driver (Studio Driver preferred) ──────────────────────────────
Log-Step "4/7: NVIDIA driver (Studio Driver channel)"
if (-not $SkipNvidia) {
  if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Log-Info "Installing NVIDIA Studio Driver via Chocolatey (nvidia-display-driver)..."
    choco install nvidia-display-driver -y
  } else {
    Log-Info ("nvidia-smi already available:`n" + (nvidia-smi -q -x 2>$null | Select-String 'driver_version' -Context 0,1 | Select-Object -First 1))
  }
} else {
  Log-Info "Skipped (-SkipNvidia)"
}

# ── 5. Tailscale Windows client ────────────────────────────────────────────
Log-Step "5/7: Tailscale Windows client"
if (-not $SkipTailscale) {
  if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) {
    Log-Info "Installing Tailscale via Chocolatey..."
    choco install tailscale -y
  } else {
    Log-Info "Tailscale already installed."
  }
  if ($TailscaleAuthKey) {
    Log-Info "Joining tailnet with provided auth key (hostname=pmoves-z890-windows)..."
    try {
      & "$env:ProgramFiles\Tailscale\tailscale.exe" up `
        --authkey=$TailscaleAuthKey `
        --hostname=pmoves-z890-windows `
        --accept-routes `
        --accept-dns
    } catch {
      Log-Warn ("Tailscale up failed: " + $_.Exception.Message)
    }
  } else {
    Log-Warn "No -TailscaleAuthKey provided. Generate one with: make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-windows"
  }
} else {
  Log-Info "Skipped (-SkipTailscale)"
}

# ── 6. Clone PMOVES.AI repo ────────────────────────────────────────────────
Log-Step ("6/7: Clone PMOVES.AI to " + $RepoClonePath)
if (-not $SkipRepoClone) {
  if (-not (Test-Path $RepoClonePath)) {
    Log-Info ("Creating parent and cloning repo...")
    $parent = Split-Path -Parent $RepoClonePath
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    git clone https://github.com/POWERFULMOVES/PMOVES.AI.git $RepoClonePath
  } else {
    Log-Info ("Repo present at " + $RepoClonePath + " — pulling latest.")
    git -C $RepoClonePath fetch origin main
    git -C $RepoClonePath merge --ff-only origin/main 2>&1 | Out-Host
  }
} else {
  Log-Info "Skipped (-SkipRepoClone)"
}

# ── 7. z890_host_setup.ps1 (netsh portproxy for NATS leafnode) ─────────────
Log-Step "7/7: Netsh portproxy rules (NATS leafnode -> 5090 hub)"
if (-not $SkipNetsh) {
  # Prefer the copy inside the cloned repo (kept up to date); fall back to
  # $HostSetupPs1 if present via an older deployment.
  $repoHostSetup = Join-Path $RepoClonePath "pmoves\scripts\z890_host_setup.ps1"
  if (Test-Path $repoHostSetup) {
    Log-Info "Running repo z890_host_setup.ps1..."
    & $repoHostSetup
  } elseif (Test-Path $HostSetupPs1) {
    Log-Info "Running local z890_host_setup.ps1..."
    & $HostSetupPs1
  } else {
    Log-Warn "z890_host_setup.ps1 not found. Run make -C pmoves z890-host-setup after repo clone completes."
  }
} else {
  Log-Info "Skipped (-SkipNetsh)"
}

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Windows 11 post-install complete." -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Next steps:"
Write-Host "    1. Reboot to finalize WSL2 + NVIDIA driver activation."
Write-Host "    2. Launch Docker Desktop once to accept the license + enable WSL2 integration."
Write-Host "    3. Open a new PowerShell and run:"
Write-Host "         cd $RepoClonePath"
Write-Host "         make -C pmoves env-setup"
Write-Host "         make -C pmoves secrets-funnel"
Write-Host "    4. Verify Tailscale status:  tailscale status"
Write-Host "    5. Verify full stack:        make -C pmoves z890-verify"
Write-Host ""
