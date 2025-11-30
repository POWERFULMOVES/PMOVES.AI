Param(
  [Parameter(Mandatory=$false)][string]$Title = "Demo",
  [Parameter(Mandatory=$false)][string]$Url = "s3://outputs/demo/example.png",
  [Parameter(Mandatory=$false)][string]$Namespace = "pmoves"
)

if (-not $Env:SUPABASE_SERVICE_ROLE_KEY -or [string]::IsNullOrWhiteSpace($Env:SUPABASE_SERVICE_ROLE_KEY)) {
  Write-Error "SUPABASE_SERVICE_ROLE_KEY is not set"
  exit 1
}

$base = if ($Env:SUPABASE_REST_URL) { $Env:SUPABASE_REST_URL } elseif ($Env:SUPA_REST_URL) { $Env:SUPA_REST_URL } else { 'http://localhost:65421/rest/v1' }
$key = $Env:SUPABASE_SERVICE_ROLE_KEY

$payload = @{ status = 'approved'; content_url = $Url; title = $Title; namespace = $Namespace; meta = @{} } | ConvertTo-Json -Depth 4

try {
  $resp = Invoke-RestMethod -Method Post -Uri ("$base/studio_board") -ContentType 'application/json' -Body $payload -Headers @{ 'prefer' = 'return=representation'; 'apikey' = $key; 'Authorization' = "Bearer $key" } -TimeoutSec 20 -ErrorAction Stop
  $resp | ConvertTo-Json -Depth 8
} catch {
  Write-Error ("Failed to seed studio_board: " + $_.Exception.Message)
  exit 2
}

