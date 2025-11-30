Param(
  [Parameter(Mandatory=$false)][string]$File = "pmoves/contracts/samples/content.published.v1.sample.json",
  [Parameter(Mandatory=$false)][string]$BaseUrl = $env:AGENT_ZERO_BASE_URL
)

if (-not $BaseUrl) { $BaseUrl = 'http://localhost:8080' }
if (-not (Test-Path $File)) { Write-Error "Sample file not found: $File"; exit 1 }

try {
  $payload = Get-Content -Raw -Path $File | ConvertFrom-Json
} catch {
  Write-Error "Failed to read JSON: $($_.Exception.Message)"; exit 1
}

$envelope = @{ topic = 'content.published.v1'; payload = $payload } | ConvertTo-Json -Depth 8

try {
  $resp = Invoke-RestMethod -Method Post -Uri ("$BaseUrl/events/publish") -ContentType 'application/json' -Body $envelope -TimeoutSec 15 -ErrorAction Stop
  $resp | ConvertTo-Json -Depth 8
} catch {
  Write-Error ("Request failed: " + $_.Exception.Message)
  exit 2
}

