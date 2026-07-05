<#
.SYNOPSIS
  PMOVES.AI - RustDesk client enrollment for Windows (the "add a node like Tailscale" apply).

.DESCRIPTION
  Windows counterpart of pmoves/scripts/fleet/rustdesk-enroll.sh. Points this Windows
  node (Z890 / 5090 / 4090) at the self-hosted RustDesk server in one command - the
  RustDesk analogue of `tailscale up --authkey`. The issuance half is `fleet:enroll`
  (generate-enrollment.py, CHIT-signed token). This is the apply half.

  Writes the same proven RustDesk2.toml as restart-jetson-rustdesk.sh to the Windows
  config path(s) and restarts RustDesk.

.PARAMETER RdHost
  RustDesk ID/rendezvous server: the Tailscale hostname (e.g. pmoves-kvm2) for fleet
  nodes, or the KVM public IP for external nodes. Required unless -Token.

.PARAMETER Key
  RustDesk server Ed25519 public key. Required unless -Token.

.PARAMETER Relay
  Relay server (default: same as -RdHost; the server auto-relays via its -r flag).

.PARAMETER Token
  Path to a fleet.enrollment.v1 JSON (from generate-enrollment.py); reads
  .rustdesk.host / .key / .relay.

.PARAMETER DryRun
  Print the config + actions, change nothing.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File rustdesk-enroll.ps1 -RdHost pmoves-kvm2 -Key <pubkey>

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File rustdesk-enroll.ps1 -Token enrollment.json -DryRun
#>
Param(
  [string]$RdHost,
  [string]$Key,
  [string]$Relay,
  [string]$Token,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
function Info($m) { Write-Host "[info] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn] $m" -ForegroundColor Yellow }
function Err ($m) { Write-Host "[err]  $m" -ForegroundColor Red }
function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# --- Resolve from token if provided -----------------------------------------
if ($Token) {
  if (-not (Test-Path $Token)) { Err "token file not found: $Token"; exit 1 }
  $t = Get-Content -Raw -Path $Token | ConvertFrom-Json
  if (-not $RdHost) { $RdHost = $t.rustdesk.host }
  if (-not $Key)    { $Key    = $t.rustdesk.key }
  if (-not $Relay)  { $Relay  = $t.rustdesk.relay }
  $exp = [double]($t.expires_at)
  $now = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  if ($exp -gt 0 -and $exp -lt $now) {
    Warn "token EXPIRED (expires_at=$exp < now=$now) - applying anyway, but re-issue for audit."
  }
}

if (-not $RdHost) { Err "-RdHost required (or a -Token with .rustdesk.host)"; exit 1 }
if (-not $Key)    { Err "-Key required (or a -Token with .rustdesk.key)"; exit 1 }
if (-not $Relay)  { $Relay = $RdHost }

# --- Build RustDesk2.toml (matches restart-jetson-rustdesk.sh, proven) -------
$toml = @"
rendezvous_server = '$($RdHost):21116'
nat_type = 1
serial = 0

[options]
custom-rendezvous-server = '$RdHost'
key = '$Key'
relay-server = '$Relay'
allow-remote-config-modification = 'Y'
verification-method = 'use-permanent-password'
av1-test = 'Y'
"@

Step "Enrollment config"
$keyPrev = if ($Key.Length -gt 12) { $Key.Substring(0,12) } else { $Key }
Info "host=$RdHost  relay=$Relay  key=$keyPrev..."
if ($DryRun) { $toml -split "`n" | ForEach-Object { Write-Host "  | $_" } }

# --- Config paths (user install + service install fallback) ------------------
$cfgDirs = @("$env:APPDATA\RustDesk\config")
$svcProfile = "C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config"
if (Test-Path (Split-Path $svcProfile -Parent)) { $cfgDirs += $svcProfile }

Step "Apply (Windows)"
foreach ($d in $cfgDirs) {
  if ($DryRun) { Info "would write $d\RustDesk2.toml"; continue }
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  # UTF-8 without BOM (RustDesk's TOML parser rejects a BOM)
  [System.IO.File]::WriteAllText("$d\RustDesk2.toml", $toml, (New-Object System.Text.UTF8Encoding($false)))
  Info "wrote $d\RustDesk2.toml"
}

if ($DryRun) { Warn "dry-run: no restart performed."; exit 0 }

# --- Restart RustDesk (service if installed, else the tray process) ----------
Step "Restart RustDesk"
$svc = Get-Service -Name 'RustDesk' -ErrorAction SilentlyContinue
if ($svc) {
  Restart-Service -Name 'RustDesk' -Force
  Info "restarted RustDesk service"
} else {
  Get-Process -Name 'RustDesk' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  $exe = "$env:ProgramFiles\RustDesk\rustdesk.exe"
  if (Test-Path $exe) { Start-Process $exe; Info "relaunched RustDesk" }
  else { Warn "RustDesk.exe not found in Program Files - start RustDesk manually to finish registration." }
}
Write-Host ""
Info "Enrolled against $RdHost. Verify server-side registration:  /fleet:rustdesk-check"
