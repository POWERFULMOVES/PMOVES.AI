# ═══════════════════════════════════════════════════════════════════════════════
# PMOVES.AI -- Z890 Host Network Setup
# ═══════════════════════════════════════════════════════════════════════════════
#
# One-time host-side setup for Z890 node. Configures netsh port proxies so
# Docker containers (running behind WSL2's virtual network) can reach the
# 5090 NATS hub via host.docker.internal.
#
# Requires: Admin PowerShell
# Idempotent: safe to re-run -- skips rules that already exist.
#
# Usage:
#   make -C pmoves z890-host-setup
#   # or directly:
#   powershell -ExecutionPolicy Bypass -File pmoves/scripts/z890_host_setup.ps1
#
# To remove all rules:
#   powershell -ExecutionPolicy Bypass -File pmoves/scripts/z890_host_setup.ps1 -Remove
# ═══════════════════════════════════════════════════════════════════════════════

Param(
  [switch]$Remove,
  [switch]$Verify,
  [string]$UpstreamIP
)

# ── Upstream IP detection ─────────────────────────────────────────────────
# Priority: 1) Explicit -UpstreamIP param  2) Env var  3) Tailscale DNS  4) Hardcoded default

if (-not $UpstreamIP) {
  $UpstreamIP = $env:PMOVES_5090_IP
}

if (-not $UpstreamIP) {
  # Try Tailscale DNS resolution (if Tailscale is installed)
  try {
    $resolved = [System.Net.Dns]::GetHostAddresses("pmoves-5090") |
      Where-Object { $_.AddressFamily -eq 'InterNetwork' } |
      Select-Object -First 1
    if ($resolved) {
      $UpstreamIP = $resolved.IPAddressToString
      Write-Host "[AUTO] Resolved upstream from Tailscale DNS: $UpstreamIP" -ForegroundColor Cyan
    }
  } catch {
    # Tailscale DNS not available, fall through
  }
}

if (-not $UpstreamIP) {
  $UpstreamIP = "192.168.1.65"
  Write-Host "[WARN] Using hardcoded default upstream IP: $UpstreamIP" -ForegroundColor Yellow
  Write-Host "       Set PMOVES_5090_IP env var or pass -UpstreamIP to override." -ForegroundColor Yellow
}

$ErrorActionPreference = 'Stop'

# ── Admin check ─────────────────────────────────────────────────────────────

function Is-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $Verify -and -not (Is-Admin)) {
  Write-Host "[ERROR] This script requires Administrator privileges." -ForegroundColor Red
  Write-Host "        Right-click PowerShell -> 'Run as Administrator', then re-run." -ForegroundColor Yellow
  exit 1
}

# ── Port proxy rules ────────────────────────────────────────────────────────
# Each entry: [listenport, connectport, connectaddress, description]

$rules = @(
  ,@(7422, 7422, $UpstreamIP, "NATS leafnode (z890 leaf -> 5090 hub)")
  ,@(7474, 7474, "127.0.0.1", "Neo4j HTTP (graph queries from tailnet)")
  ,@(7687, 7687, "127.0.0.1", "Neo4j Bolt (driver connections from tailnet)")
  ,@(4222, 4222, "127.0.0.1", "NATS (event bus from tailnet)")
  ,@(8083, 8083, "127.0.0.1", "Extract-worker (doc ingestion from tailnet)")
  ,@(8086, 8086, "127.0.0.1", "Hi-RAG v2 CPU (queries from tailnet)")
)

# ── Helpers ──────────────────────────────────────────────────────────────────

function Get-ExistingProxies {
  $raw = netsh interface portproxy show v4tov4 2>&1
  return $raw
}

function Test-RuleExists {
  Param([int]$Port)
  $proxies = Get-ExistingProxies
  foreach ($line in $proxies) {
    if ($line -match "0\.0\.0\.0\s+$Port\s+") {
      return $true
    }
  }
  return $false
}

function Add-ProxyRule {
  Param([int]$ListenPort, [int]$ConnectPort, [string]$ConnectAddr, [string]$Desc)

  if (Test-RuleExists -Port $ListenPort) {
    Write-Host ("[SKIP] Port $ListenPort already proxied -- $Desc") -ForegroundColor Green
    return
  }

  Write-Host ("[ADD]  0.0.0.0:$ListenPort -> ${ConnectAddr}:$ConnectPort -- $Desc") -ForegroundColor Cyan
  netsh interface portproxy add v4tov4 `
    listenport=$ListenPort listenaddress=0.0.0.0 `
    connectport=$ConnectPort connectaddress=$ConnectAddr | Out-Null

  if (Test-RuleExists -Port $ListenPort) {
    Write-Host ("[OK]   Rule added successfully.") -ForegroundColor Green
  } else {
    Write-Host ("[FAIL] Rule not created -- check netsh output.") -ForegroundColor Red
  }
}

function Remove-ProxyRule {
  Param([int]$ListenPort, [string]$Desc)

  if (-not (Test-RuleExists -Port $ListenPort)) {
    Write-Host ("[SKIP] Port $ListenPort not proxied -- nothing to remove.") -ForegroundColor Yellow
    return
  }

  Write-Host ("[DEL]  Removing proxy on port $ListenPort -- $Desc") -ForegroundColor Yellow
  netsh interface portproxy delete v4tov4 `
    listenport=$ListenPort listenaddress=0.0.0.0 | Out-Null

  if (-not (Test-RuleExists -Port $ListenPort)) {
    Write-Host ("[OK]   Rule removed.") -ForegroundColor Green
  } else {
    Write-Host ("[FAIL] Rule still exists.") -ForegroundColor Red
  }
}

function Test-Upstream {
  Param([string]$TargetHost, [int]$Port, [string]$Desc)

  Write-Host ("[TEST] ${TargetHost}:$Port -- $Desc") -ForegroundColor Cyan -NoNewline
  try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $result = $tcp.BeginConnect($TargetHost, $Port, $null, $null)
    $ok = $result.AsyncWaitHandle.WaitOne(2000)
    if ($ok -and $tcp.Connected) {
      $tcp.Close()
      Write-Host "  OPEN" -ForegroundColor Green
      return $true
    }
    $tcp.Close()
  } catch {}
  Write-Host "  CLOSED" -ForegroundColor Red
  return $false
}

# ── Main ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "== PMOVES Z890 Host Network Setup ==" -ForegroundColor Cyan
Write-Host ("   Upstream IP: {0}" -f $UpstreamIP)
Write-Host ""

if ($Remove) {
  Write-Host "--- Removing port proxy rules ---" -ForegroundColor Yellow
  foreach ($r in $rules) {
    Remove-ProxyRule -ListenPort $r[0] -Desc $r[3]
  }
} elseif ($Verify) {
  Write-Host "--- Verifying port proxy rules ---" -ForegroundColor Cyan
  foreach ($r in $rules) {
    $exists = Test-RuleExists -Port $r[0]
    if ($exists) {
      Write-Host ("[OK]   Port $($r[0]) proxied -- $($r[3])") -ForegroundColor Green
    } else {
      Write-Host ("[MISS] Port $($r[0]) NOT proxied -- $($r[3])") -ForegroundColor Red
    }
  }
} else {
  Write-Host "--- Configuring port proxy rules ---" -ForegroundColor Cyan
  foreach ($r in $rules) {
    Add-ProxyRule -ListenPort $r[0] -ConnectPort $r[1] -ConnectAddr $r[2] -Desc $r[3]
  }
}

# Always show current state and test connectivity
Write-Host ""
Write-Host "--- Current port proxies ---" -ForegroundColor Cyan
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "--- Upstream connectivity ---" -ForegroundColor Cyan
Test-Upstream -TargetHost $UpstreamIP -Port 7422 -Desc "5090 NATS leafnode"
Test-Upstream -TargetHost $UpstreamIP -Port 4222 -Desc "5090 NATS client"

Write-Host ""
Write-Host "Done. Next: docker compose -f docker-compose.z890.yml --env-file env.z890 up -d" -ForegroundColor Green
Write-Host "Or:   make -C pmoves up-z890" -ForegroundColor Green
Write-Host ""
