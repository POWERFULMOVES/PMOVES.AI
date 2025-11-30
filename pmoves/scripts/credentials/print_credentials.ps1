$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pmovesRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$envFile = Join-Path $pmovesRoot ".env.local"
$sharedFile = Join-Path $pmovesRoot "env.shared"
$sharedTemplate = Join-Path $pmovesRoot "env.shared.example"

function Get-ValueFromFile {
  param(
    [string]$Key,
    [string]$Path
  )
  if (Test-Path $Path) {
    $line = Get-Content $Path | Where-Object { $_ -match "^$Key=" } | Select-Object -Last 1
    if ($line) { return ($line -split "=", 2)[1] }
  }
  return ""
}

function Get-EnvValue { param([string]$Key) Get-ValueFromFile -Key $Key -Path $envFile }
function Get-SharedValue {
  param([string]$Key)
  $value = Get-ValueFromFile -Key $Key -Path $sharedFile
  if (-not $value) {
    $value = Get-ValueFromFile -Key $Key -Path $sharedTemplate
  }
  return $value
}

function DefaultIfEmpty {
  param(
    [string]$Value,
    [string]$Fallback
  )
  if ([string]::IsNullOrEmpty($Value)) { return $Fallback }
  return $Value
}

Write-Host "PMOVES Provisioned Services — Default Login Summary"
Write-Host "---------------------------------------------------"

$wgerUrl = DefaultIfEmpty (Get-SharedValue WGER_BASE_URL) "http://localhost:8000"
$fireflyUrl = DefaultIfEmpty (Get-SharedValue FIREFLY_BASE_URL) "http://localhost:8082"
$jellyfinUrl = DefaultIfEmpty (Get-SharedValue JELLYFIN_PUBLISHED_URL) "http://localhost:8096"
$jellyfinApi = DefaultIfEmpty (Get-SharedValue JELLYFIN_API_KEY) "<not set>"
$supaRest = DefaultIfEmpty (Get-SharedValue SUPABASE_URL) "http://localhost:3000"
$supaAnon = DefaultIfEmpty (Get-SharedValue SUPABASE_ANON_KEY) "<not set>"
$supaService = DefaultIfEmpty (Get-SharedValue SUPABASE_SERVICE_ROLE_KEY) "<not set>"
$minioEndpoint = DefaultIfEmpty (Get-EnvValue MINIO_ENDPOINT) "http://localhost:9000"
$discordWebhook = DefaultIfEmpty (Get-SharedValue DISCORD_WEBHOOK_URL) "<not set>"

Write-Host "Wger         : URL=$wgerUrl | admin / adminadmin"
Write-Host "Firefly III  : URL=$fireflyUrl | First user you register becomes admin"
Write-Host "Jellyfin     : URL=$jellyfinUrl | Set on first run; API key: $jellyfinApi"
Write-Host "Supabase     : REST=$supaRest | anon=$supaAnon service=$supaService"
Write-Host "MinIO        : URL=$minioEndpoint | minioadmin / minioadmin"
Write-Host "Discord Webhook: $discordWebhook"
