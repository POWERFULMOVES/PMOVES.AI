Param(
  [Parameter(Mandatory=$false)][string]$Message = "PMOVES Discord wiring check"
)

if (-not $Env:DISCORD_WEBHOOK_URL -or [string]::IsNullOrWhiteSpace($Env:DISCORD_WEBHOOK_URL)) {
  Write-Error "DISCORD_WEBHOOK_URL is not set"
  exit 1
}

$username = if ($Env:DISCORD_WEBHOOK_USERNAME) { $Env:DISCORD_WEBHOOK_USERNAME } else { 'PMOVES Publisher' }
$payload = @{ content = $Message; username = $username } | ConvertTo-Json -Compress

try {
  $resp = Invoke-RestMethod -Method Post -Uri $Env:DISCORD_WEBHOOK_URL -ContentType 'application/json' -Body $payload -TimeoutSec 15 -ErrorAction Stop
  Write-Host "Discord webhook ping sent successfully."
} catch {
  Write-Error ("Failed to send Discord webhook ping: " + $_.Exception.Message)
  exit 2
}
