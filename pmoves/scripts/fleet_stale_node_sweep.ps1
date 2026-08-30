# Weekly Tailscale stale-node sweep: identify nodes offline > N days, post to Discord.
# Cloud routines can't reach the tailnet (no Tailscale MCP connector available),
# so this runs locally via Windows Task Scheduler against the host's authenticated tailscale CLI.
# Pairs with the `/fleet:stale-nodes` skill -- this is the unattended cron variant.

Param(
  [int]$StaleDays = 60,
  [string]$LogDir = "D:\PMOVES.AI\PMOVES.AI\pmoves\logs",
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$logFile = Join-Path $LogDir ("fleet_sweep_" + (Get-Date -Format 'yyyy-MM-dd') + ".log")
Start-Transcript -Path $logFile -Force | Out-Null

# tailscale status --json gives full peer inventory
$statusJson = & tailscale status --json 2>$null
if ($LASTEXITCODE -ne 0 -or -not $statusJson) {
  Write-Error "tailscale status failed -- is Tailscale running and authenticated?"
  Stop-Transcript | Out-Null
  exit 1
}

$status = $statusJson -join "`n" | ConvertFrom-Json

$now = Get-Date
$staleThreshold = $now.AddDays(-$StaleDays)

$peers = @()
foreach ($prop in $status.Peer.PSObject.Properties) {
  $peer = $prop.Value
  if (-not $peer.LastSeen) { continue }
  $lastSeen = [DateTime]$peer.LastSeen
  $daysOffline = ($now - $lastSeen).TotalDays
  if ($lastSeen -lt $staleThreshold) {
    $peers += [PSCustomObject]@{
      Name        = $peer.HostName
      OS          = $peer.OS
      LastSeen    = $lastSeen
      DaysOffline = [Math]::Round($daysOffline, 1)
      ID          = $peer.ID
    }
  }
}

$total = ($status.Peer.PSObject.Properties | Measure-Object).Count
$stale = $peers.Count

$header = "**PMOVES Fleet Sweep -- $(Get-Date -Format 'yyyy-MM-dd')**"
$body = @()
$body += $header
$body += ""
$body += "Tailnet peers: $total | Stale (>$StaleDays days): $stale"

if ($stale -gt 0) {
  $body += ""
  $body += "Stale nodes:"
  foreach ($p in ($peers | Sort-Object DaysOffline -Descending | Select-Object -First 12)) {
    $body += "- $($p.Name) ($($p.OS), $($p.DaysOffline)d offline)"
  }
  if ($peers.Count -gt 12) { $body += "- ... and $($peers.Count - 12) more" }
  $body += ""
  $body += "Next step: run ``/fleet:stale-nodes`` locally to confirm and remove."
} else {
  $body += "All peers within freshness window."
}

$content = ($body -join "`n")
if ($content.Length -gt 1900) { $content = $content.Substring(0, 1897) + "..." }

Write-Host "--- Fleet sweep ---`n$content`n--- end ---"

if ($DryRun) {
  Write-Host "DryRun: not posting to Discord."
  Stop-Transcript | Out-Null
  exit 0
}

if (-not $Env:DISCORD_WEBHOOK_URL) {
  Write-Error "DISCORD_WEBHOOK_URL not set -- bake it into the scheduled task wrapper."
  Stop-Transcript | Out-Null
  exit 1
}

$payload = @{ content = $content; username = 'PMOVES Fleet Sweep' } | ConvertTo-Json -Compress
try {
  Invoke-RestMethod -Method Post -Uri $Env:DISCORD_WEBHOOK_URL -ContentType 'application/json' -Body $payload -TimeoutSec 20 | Out-Null
  Write-Host "Fleet sweep posted."
} catch {
  Write-Error "Discord post failed: $($_.Exception.Message)"
  Stop-Transcript | Out-Null
  exit 2
}

Stop-Transcript | Out-Null
