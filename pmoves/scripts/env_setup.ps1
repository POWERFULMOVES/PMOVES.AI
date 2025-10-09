# PMOVES Interactive .env Setup (PowerShell 7+)
# See usage by running: pwsh -File scripts/env_setup.ps1 -?

param(
  [switch]$Force,
  [switch]$NonInteractive,
  [switch]$Defaults,
  [ValidateSet('none','doppler','infisical','1password','sops')]
  [string]$From = 'none',
  [string]$EnvPath = '.env',
  [string]$LocalPath = '.env.local'
)

$ErrorActionPreference = 'Stop'

Write-Host "PMOVES .env Setup (initializing)"

function Read-DotenvKeys {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @() }
  $lines = Get-Content -Path $Path -Encoding UTF8
  $keys = @()
  foreach ($ln in $lines) {
    $t = $ln.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $eq = $t.IndexOf('=')
    if ($eq -gt 0) { $keys += $t.Substring(0,$eq).Trim() }
  }
  ($keys | Sort-Object -Unique)
}

function Read-DotenvMap {
  param([string]$Path)
  $map = @{}
  if (-not (Test-Path $Path)) { return $map }
  $lines = Get-Content -Path $Path -Encoding UTF8
  foreach ($ln in $lines) {
    $t = $ln.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $eq = $t.IndexOf('=')
    if ($eq -gt 0) {
      $k = $t.Substring(0,$eq).Trim()
      $v = $t.Substring($eq+1)
      $map[$k] = $v
    }
  }
  return $map
}

function Is-SecretKey {
  param([string]$Key)
  return ($Key -match '(?i)(SECRET|TOKEN|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE|WEBHOOK)')
}

function Suggest-Default {
  param([string]$Key)
  if ($Key -match '(?i)PRESIGN_SHARED_SECRET') { return [Convert]::ToBase64String([Guid]::NewGuid().ToByteArray()) }
  if ($Key -match '(?i)MINIO_ACCESS_KEY') { return 'pmoves' }
  if ($Key -match '(?i)MINIO_SECRET_KEY') { return 'password' }
  if ($Key -match '(?i)NATS_URL') { return 'nats://nats:4222' }
  if ($Key -match '(?i)JELLYFIN_URL') { return 'http://jellyfin:8096' }
  if ($Key -match '(?i)AWS_DEFAULT_REGION') { return 'us-east-1' }
  return ''
}

function Pull-FromProvider {
  param([string]$Provider,[string]$OutPath)
  switch ($Provider) {
    'doppler' {
      try {
        & doppler secrets download --no-file --format env > $OutPath
        Write-Host "Imported secrets from Doppler -> $OutPath" -ForegroundColor Green
      } catch { Write-Warning "Doppler CLI not found or failed. Skipping import." }
    }
    'infisical' {
      try {
        & infisical export --format=dotenv > $OutPath
        Write-Host "Imported secrets from Infisical -> $OutPath" -ForegroundColor Green
      } catch { Write-Warning "Infisical CLI not found or failed. Skipping import." }
    }
    '1password' {
      try {
        # Expect an item named PMOVES_ENV containing key/values. Users can customize.
        $json = & op item get PMOVES_ENV --format json
        if ($LASTEXITCODE -eq 0 -and $json) {
          $obj = $json | ConvertFrom-Json
          $pairs = @()
          foreach ($f in $obj.fields) { if ($f.id -and $f.value) { $pairs += ("{0}={1}" -f $f.id, $f.value) } }
          $pairs -join "`n" | Set-Content -NoNewline -Encoding UTF8 -Path $OutPath
          Write-Host "Imported secrets from 1Password -> $OutPath" -ForegroundColor Green
        }
      } catch { Write-Warning "1Password CLI not found or failed. Skipping import." }
    }
    'sops' {
      try {
        & sops -d .env.sops > $OutPath
        Write-Host "Decrypted secrets with SOPS -> $OutPath" -ForegroundColor Green
      } catch { Write-Warning "SOPS not found or .env.sops missing. Skipping import." }
    }
    default {}
  }
}

Write-Host "== PMOVES .env Setup ==" -ForegroundColor Cyan
Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location ..  # move to pmoves/

if (-not (Test-Path '.env.example')) {
  Write-Error ".env.example not found in pmoves/. Aborting."
  exit 1
}

# Optional provider import to .env.generated (ignored by git)
$generatedPath = '.env.generated'
if ($From -ne 'none') {
  Pull-FromProvider -Provider $From -OutPath $generatedPath
}

$exampleKeys = Read-DotenvKeys -Path '.env.example'
$envMap = Read-DotenvMap -Path $EnvPath

$added = @()
foreach ($key in $exampleKeys) {
  $exists = $envMap.ContainsKey($key) -and ($envMap[$key] -ne '')
  if ($exists -and -not $Force) { continue }
  $default = ''
  if ($envMap.ContainsKey($key) -and $envMap[$key] -ne '') { $default = $envMap[$key] }
  if (-not $default) { $default = [Environment]::GetEnvironmentVariable($key, 'Process') }
  if (-not $default) { $default = Suggest-Default -Key $key }

  $value = $default
  if (-not $NonInteractive) {
    if (Is-SecretKey -Key $key) {
      $prompt = if ($default) { "Enter value for $key [hidden, has default]" } else { "Enter value for $key [hidden]" }
      $sec = Read-Host -Prompt $prompt -AsSecureString
      $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
      if ($plain) { $value = $plain }
    } else {
      $prompt = if ($default) { "Enter value for $key [$default]" } else { "Enter value for $key" }
      $inp = Read-Host -Prompt $prompt
      if ($inp) { $value = $inp }
    }
  } elseif ($Defaults -and -not $value) {
    $value = Suggest-Default -Key $key
  }

  if (-not $value) { $value = '' }
  $added += @{ k=$key; v=$value }
}

if ($added.Count -eq 0) {
  Write-Host "Nothing to add; $EnvPath already covers .env.example keys." -ForegroundColor Green
} else {
  if (-not (Test-Path $EnvPath)) { New-Item -ItemType File -Path $EnvPath | Out-Null }
  $content = Get-Content -Path $EnvPath -Encoding UTF8
  $content += "# --- Added by env_setup to align with .env.example (local dev defaults) ---"
  foreach ($pair in $added) { $content += ("{0}={1}" -f $pair.k, $pair.v) }
  $content | Set-Content -Encoding UTF8 -Path $EnvPath
  Write-Host ("Updated {0} with {1} keys." -f $EnvPath, $added.Count) -ForegroundColor Green
}

Write-Host "Running preflight check..." -ForegroundColor Yellow
& pwsh -NoProfile -File scripts/env_check.ps1 -Quick | Out-Host

Pop-Location
