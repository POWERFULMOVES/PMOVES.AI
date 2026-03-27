# ═══════════════════════════════════════════════════════════════════════════════
# PMOVES.AI -- 4090 Laptop Host Network Hardening
# ═══════════════════════════════════════════════════════════════════════════════
#
# Disables SMB, NetBIOS, WSDAPI, LLMNR, and Network Discovery on the 4090
# laptop to enforce the mesh-only privacy policy.  All inter-host communication
# should go through Tailscale mesh or Docker networks.
#
# Requires: Admin PowerShell
# Idempotent: safe to re-run -- skips items already in the target state.
#
# Usage:
#   make -C pmoves laptop-harden
#   # or directly:
#   powershell -ExecutionPolicy Bypass -File pmoves/scripts/laptop_4090_host_harden.ps1
#
# To verify current state (no changes):
#   powershell -ExecutionPolicy Bypass -File pmoves/scripts/laptop_4090_host_harden.ps1 -Verify
#
# To reverse all changes:
#   powershell -ExecutionPolicy Bypass -File pmoves/scripts/laptop_4090_host_harden.ps1 -Remove
# ═══════════════════════════════════════════════════════════════════════════════

Param(
  [switch]$Remove,
  [switch]$Verify
)

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

# ── Counters ─────────────────────────────────────────────────────────────────

$script:okCount = 0
$script:changeCount = 0
$script:failCount = 0

# ── Helpers ──────────────────────────────────────────────────────────────────

function Set-ServiceState {
  Param(
    [string]$Name,
    [string]$DisplayName,
    [bool]$ShouldDisable  # $true = disable (harden), $false = enable (remove)
  )

  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if (-not $svc) {
    Write-Host "[SKIP] Service '$Name' not found on this system." -ForegroundColor Yellow
    return
  }

  $targetStartup = if ($ShouldDisable) { 'Disabled' } else { 'Automatic' }
  $targetRunning = -not $ShouldDisable

  if ($Verify) {
    $isDisabled = $svc.StartType -eq 'Disabled'
    $isStopped = $svc.Status -eq 'Stopped'
    if ($ShouldDisable -and $isDisabled -and $isStopped) {
      Write-Host "[OK]   $DisplayName ($Name) -- Disabled + Stopped" -ForegroundColor Green
      $script:okCount++
    } elseif (-not $ShouldDisable -and -not $isDisabled) {
      Write-Host "[OK]   $DisplayName ($Name) -- Enabled ($($svc.StartType))" -ForegroundColor Green
      $script:okCount++
    } else {
      Write-Host "[MISS] $DisplayName ($Name) -- StartType=$($svc.StartType), Status=$($svc.Status)" -ForegroundColor Red
      $script:failCount++
    }
    return
  }

  try {
    if ($ShouldDisable) {
      if ($svc.Status -ne 'Stopped') {
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
      }
      Set-Service -Name $Name -StartupType Disabled
      Write-Host "[OK]   Disabled $DisplayName ($Name)" -ForegroundColor Green
    } else {
      Set-Service -Name $Name -StartupType Automatic
      Write-Host "[OK]   Re-enabled $DisplayName ($Name)" -ForegroundColor Green
    }
    $script:changeCount++
  } catch {
    Write-Host "[FAIL] Could not configure $DisplayName ($Name): $_" -ForegroundColor Red
    $script:failCount++
  }
}

function Set-RegistryValue {
  Param(
    [string]$Path,
    [string]$Name,
    [int]$DisableValue,
    [int]$EnableValue,
    [string]$Description,
    [bool]$ShouldDisable
  )

  $targetValue = if ($ShouldDisable) { $DisableValue } else { $EnableValue }

  if ($Verify) {
    try {
      $current = Get-ItemProperty -Path $Path -Name $Name -ErrorAction Stop
      if ($current.$Name -eq $targetValue) {
        Write-Host "[OK]   $Description -- Value=$targetValue" -ForegroundColor Green
        $script:okCount++
      } else {
        Write-Host "[MISS] $Description -- Value=$($current.$Name) (expected $targetValue)" -ForegroundColor Red
        $script:failCount++
      }
    } catch {
      if ($ShouldDisable) {
        Write-Host "[MISS] $Description -- Registry key not set" -ForegroundColor Red
        $script:failCount++
      } else {
        Write-Host "[OK]   $Description -- Registry key absent (default = enabled)" -ForegroundColor Green
        $script:okCount++
      }
    }
    return
  }

  try {
    if (-not (Test-Path $Path)) {
      New-Item -Path $Path -Force | Out-Null
    }
    Set-ItemProperty -Path $Path -Name $Name -Value $targetValue -Type DWord
    Write-Host "[OK]   $Description -- Set to $targetValue" -ForegroundColor Green
    $script:changeCount++
  } catch {
    Write-Host "[FAIL] $Description: $_" -ForegroundColor Red
    $script:failCount++
  }
}

# ── Main ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "== PMOVES 4090 Laptop Host Network Hardening ==" -ForegroundColor Cyan
Write-Host "   Hostname: $env:COMPUTERNAME"
Write-Host ""

$action = if ($Remove) { "REMOVING" } elseif ($Verify) { "VERIFYING" } else { "APPLYING" }
$shouldDisable = -not $Remove

Write-Host "--- $action: SMB Server (port 445) ---" -ForegroundColor Cyan
Set-ServiceState -Name "LanmanServer" -DisplayName "SMB Server" -ShouldDisable $shouldDisable

# Disable SMB1 and SMB2 protocols via registry
Set-RegistryValue `
  -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" `
  -Name "SMB1" -DisableValue 0 -EnableValue 1 `
  -Description "SMB1 protocol" -ShouldDisable $shouldDisable
Set-RegistryValue `
  -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" `
  -Name "SMB2" -DisableValue 0 -EnableValue 1 `
  -Description "SMB2 protocol" -ShouldDisable $shouldDisable

Write-Host ""
Write-Host "--- $action: NetBIOS over TCP/IP (ports 137-139) ---" -ForegroundColor Cyan

# Disable NetBIOS on all adapters via registry
$netbtPath = "HKLM:\SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces"
if (Test-Path $netbtPath) {
  $interfaces = Get-ChildItem -Path $netbtPath
  foreach ($iface in $interfaces) {
    $ifaceName = $iface.PSChildName
    $ifacePath = "$netbtPath\$ifaceName"
    # NetbiosOptions: 0=default(DHCP), 1=enable, 2=disable
    Set-RegistryValue `
      -Path $ifacePath `
      -Name "NetbiosOptions" -DisableValue 2 -EnableValue 0 `
      -Description "NetBIOS on $ifaceName" -ShouldDisable $shouldDisable
  }
} else {
  Write-Host "[SKIP] NetBT interfaces registry path not found." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "--- $action: WSDAPI / Web Services Discovery (port 5357) ---" -ForegroundColor Cyan
Set-ServiceState -Name "fdPHost" -DisplayName "Function Discovery Provider Host" -ShouldDisable $shouldDisable
Set-ServiceState -Name "FDResPub" -DisplayName "Function Discovery Resource Publication" -ShouldDisable $shouldDisable

Write-Host ""
Write-Host "--- $action: LLMNR (Link-Local Multicast Name Resolution) ---" -ForegroundColor Cyan
Set-RegistryValue `
  -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient" `
  -Name "EnableMulticast" -DisableValue 0 -EnableValue 1 `
  -Description "LLMNR multicast" -ShouldDisable $shouldDisable

Write-Host ""
Write-Host "--- $action: Network Discovery firewall group ---" -ForegroundColor Cyan

if ($Verify) {
  try {
    $ndRules = Get-NetFirewallRule -DisplayGroup "Network Discovery" -ErrorAction Stop
    $enabledCount = ($ndRules | Where-Object { $_.Enabled -eq 'True' }).Count
    if ($shouldDisable -and $enabledCount -eq 0) {
      Write-Host "[OK]   Network Discovery firewall rules -- All disabled ($($ndRules.Count) rules)" -ForegroundColor Green
      $script:okCount++
    } elseif (-not $shouldDisable -and $enabledCount -gt 0) {
      Write-Host "[OK]   Network Discovery firewall rules -- $enabledCount enabled" -ForegroundColor Green
      $script:okCount++
    } else {
      Write-Host "[MISS] Network Discovery firewall rules -- $enabledCount of $($ndRules.Count) enabled" -ForegroundColor Red
      $script:failCount++
    }
  } catch {
    Write-Host "[SKIP] Could not query Network Discovery rules: $_" -ForegroundColor Yellow
  }
} else {
  try {
    $enableState = if ($shouldDisable) { 'False' } else { 'True' }
    Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled $enableState -ErrorAction Stop
    $verb = if ($shouldDisable) { "Disabled" } else { "Enabled" }
    Write-Host "[OK]   $verb Network Discovery firewall rules" -ForegroundColor Green
    $script:changeCount++
  } catch {
    Write-Host "[FAIL] Could not configure Network Discovery rules: $_" -ForegroundColor Red
    $script:failCount++
  }
}

# ── Tailscale status (informational) ──────────────────────────────────────────

Write-Host ""
Write-Host "--- Tailscale status (informational) ---" -ForegroundColor Cyan

$tailscaleSvc = Get-Service -Name "Tailscale" -ErrorAction SilentlyContinue
if ($tailscaleSvc -and $tailscaleSvc.Status -eq 'Running') {
  Write-Host "[OK]   Tailscale service is running" -ForegroundColor Green
  try {
    $tsStatus = & tailscale status 2>&1 | Select-Object -First 1
    Write-Host "       $tsStatus" -ForegroundColor Gray
  } catch { Write-Host "       (tailscale status unavailable: $_)" -ForegroundColor Gray }
} else {
  Write-Host "[WARN] Tailscale service not running -- mesh connectivity unavailable" -ForegroundColor Yellow
}

# ── Summary ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "== Summary ==" -ForegroundColor Cyan

if ($Verify) {
  Write-Host "   Checks passed: $script:okCount" -ForegroundColor Green
  if ($script:failCount -gt 0) {
    Write-Host "   Checks failed: $script:failCount" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Run 'make -C pmoves laptop-harden' to apply hardening." -ForegroundColor Yellow
    exit 1
  }
  Write-Host ""
  Write-Host "   All checks passed. Host is hardened." -ForegroundColor Green
} else {
  Write-Host "   Changes applied: $script:changeCount" -ForegroundColor Green
  if ($script:failCount -gt 0) {
    Write-Host "   Failures: $script:failCount" -ForegroundColor Red
    exit 1
  }
  $verb = if ($Remove) { "Hardening removed" } else { "Hardening applied" }
  Write-Host ""
  Write-Host "   $verb successfully." -ForegroundColor Green
  Write-Host "   Verify with: make -C pmoves laptop-harden-verify" -ForegroundColor Cyan
  if (-not $Remove) {
    Write-Host "   Revert with: make -C pmoves laptop-harden-remove" -ForegroundColor Cyan
  }
}

Write-Host ""
