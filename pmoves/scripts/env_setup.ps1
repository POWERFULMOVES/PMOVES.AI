# PMOVES Interactive .env Setup (PowerShell 7+)
# See usage by running: pwsh -File scripts/env_setup.ps1 -?

param(
  [switch]$Force,
  [switch]$NonInteractive,
  [switch]$Defaults,
  [ValidateSet('none','doppler','infisical','1password','sops','github','docker','chit')]
  [string]$From = 'none',
  [string]$EnvPath = '.env',
  [string]$LocalPath = '.env.local'
)

$ErrorActionPreference = 'Stop'

Write-Host "PMOVES .env Setup (initializing)"

function Read-DotenvExample {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @() }
  $lines = Get-Content -Path $Path -Encoding UTF8
  $entries = @()
  foreach ($ln in $lines) {
    $t = $ln.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $eq = $t.IndexOf('=')
    if ($eq -lt 0) { continue }
    $key = $t.Substring(0,$eq).Trim()
    $value = ''
    if ($eq + 1 -lt $t.Length) { $value = $t.Substring($eq + 1) }
    $entries += [pscustomobject]@{ Key = $key; Default = $value }
  }
  return $entries
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
    'github' {
      # PMOVES.AI: Load credentials from GitHub Secrets (environment variables)
      # This works in GitHub Actions, Codespaces, or locally if secrets are exported
      $secretVars = @(
        'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'GEMINI_API_KEY',
        'OPENROUTER_API_KEY', 'VENICE_API_KEY', 'HUGGINGFACE_HUB_TOKEN', 'VOYAGE_API_KEY',
        'COHERE_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_BOT_NAME', 'DISCORD_BOT_TOKEN',
        'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'SUPABASE_ANON_KEY', 'RESEND_API_KEY',
        'TENSORZERO_API_KEY', 'OPEN_NOTEBOOK_API_KEY', 'E2B_API_KEY', 'JINA_API_KEY',
        'FIREWORKS_API_KEY', 'REPLICATE_API_TOKEN', 'LANGCHAIN_API_KEY', 'TAVILY_API_KEY',
        'SERPER_API_KEY', 'BRIGHTDATA_API_KEY'
      )
      $found = 0
      $pairs = @()
      foreach ($var in $secretVars) {
        $value = [Environment]::GetEnvironmentVariable($var, 'Process')
        if ($value) {
          $pairs += "$var=$value"
          Write-Host "  Loaded $var from environment" -ForegroundColor Cyan
          $found++
        }
      }
      if ($found -gt 0) {
        $pairs -join "`n" | Set-Content -Encoding UTF8 -Path $OutPath
        Write-Host "Imported $found secrets from GitHub Secrets (environment) -> $OutPath" -ForegroundColor Green
      } else {
        Write-Warning "No GitHub Secrets found in environment. Make sure secrets are exported or running in GitHub Actions/Codespaces."
      }
    }
    'docker' {
      # PMOVES.AI: Load credentials from Docker Secrets (/run/secrets/)
      $secretsDir = '/run/secrets'
      if (Test-Path $secretsDir) {
        $found = 0
        $pairs = @()
        Get-ChildItem -Path $secretsDir -Filter 'pmoves_*' -ErrorAction SilentlyContinue | ForEach-Object {
          $name = $_.Name
          # Convert pmoves_openai_api_key -> OPENAI_API_KEY
          $envName = $name -replace '^pmoves_', '' -replace '_', ' ' | ForEach-Object { (Get-Culture).TextInfo.ToTitleCase($_) } -replace ' ', '_'
          $value = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
          if ($value) {
            $pairs += "$envName=$value"
            $found++
          }
        }
        if ($found -gt 0) {
          $pairs -join "`n" | Set-Content -Encoding UTF8 -Path $OutPath
          Write-Host "Imported $found secrets from Docker Secrets -> $OutPath" -ForegroundColor Green
        } else {
          Write-Warning "No PMOVES Docker secrets found in $secretsDir"
        }
      } else {
        Write-Warning "Docker secrets directory not found: $secretsDir"
      }
    }
    'chit' {
      # PMOVES.AI: Load credentials from CHIT Geometry Packet
      $cgpPaths = @(
        'data/chit/env.cgp.json',
        'pmoves/data/chit/env.cgp.json',
        '../pmoves/data/chit/env.cgp.json',
        '../../pmoves/data/chit/env.cgp.json'
      )
      $cgpFile = $null
      foreach ($path in $cgpPaths) {
        if (Test-Path $path) {
          $cgpFile = $path
          break
        }
      }
      if ($cgpFile) {
        try {
          # Try Python CHIT decode
          $decoded = python3 -c @"
import sys, json
from pathlib import Path
repo_root = Path('$pwd').resolve().parent
for parent in [repo_root] + list(repo_root.parents):
    chit_path = parent / 'pmoves' / 'chit'
    if chit_path.exists():
        sys.path.insert(0, str(parent))
        break
try:
    from pmoves.chit import load_cgp, decode_secret_map
    cgp = load_cgp('$cgpFile')
    secrets = decode_secret_map(cgp)
    for k, v in sorted(secrets.items()):
        print(f'{k}={v}')
except ImportError:
    with open('$cgpFile') as f:
        cgp = json.load(f)
    for point in cgp.get('points', []):
        label = point['label']
        value = point.get('value', '')
        encoding = point.get('encoding', 'cleartext')
        if encoding == 'cleartext':
            print(f'{label}={value}')
"@ 2>&1
          if ($decoded) {
            $decoded | Set-Content -Encoding UTF8 -Path $OutPath
            $count = ($decoded -split "`n").Where({ $_ -match '^[A-Z_]+=' }).Count
            Write-Host "Decoded $count secrets from CHIT Geometry Packet -> $OutPath" -ForegroundColor Green
          } else {
            Write-Warning "CHIT decode failed. Make sure pmoves.chit module is available."
          }
        } catch {
          Write-Warning "CHIT decode error: $_"
        }
      } else {
        Write-Warning "No CHIT Geometry Packet found (searched: data/chit/env.cgp.json, pmoves/data/chit/)"
      }
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

$exampleEntries = Read-DotenvExample -Path '.env.example'
$envMap = Read-DotenvMap -Path $EnvPath

$added = @()
foreach ($entry in $exampleEntries) {
  $key = $entry.Key
  $sample = $entry.Default
  $exists = $envMap.ContainsKey($key) -and ($envMap[$key] -ne '')
  if ($exists -and -not $Force) { continue }
  $default = ''
  if ($envMap.ContainsKey($key) -and $envMap[$key] -ne '') { $default = $envMap[$key] }
  if (-not $default -and $sample) { $default = $sample }
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
  if (-not (Test-Path $EnvPath)) { New-Item -ItemType File -Path $EnvPath -Force | Out-Null }
  $comment = '# --- Added by env_setup to align with .env.example (local dev defaults) ---'
  $hasComment = $false
  try {
    $hasComment = Select-String -Path $EnvPath -Pattern $comment -SimpleMatch -Quiet
  } catch {
    $hasComment = $false
  }
  $needsNewline = $false
  $item = Get-Item -LiteralPath $EnvPath -ErrorAction SilentlyContinue
  if ($null -ne $item -and $item.Length -gt 0) {
    $lastLine = Get-Content -Path $EnvPath -Encoding UTF8 -Tail 1
    if ($lastLine -and $lastLine.TrimEnd() -ne '') { $needsNewline = $true }
  }
  if ($needsNewline) { Add-Content -Path $EnvPath -Encoding UTF8 -Value '' }
  if (-not $hasComment) { Add-Content -Path $EnvPath -Encoding UTF8 -Value $comment }
  foreach ($pair in $added) { Add-Content -Path $EnvPath -Encoding UTF8 -Value ("{0}={1}" -f $pair.k, $pair.v) }
  Write-Host ("Updated {0} with {1} keys." -f $EnvPath, $added.Count) -ForegroundColor Green
}

Write-Host "Running preflight check..." -ForegroundColor Yellow
& pwsh -NoProfile -File scripts/env_check.ps1 -Quick | Out-Host

Pop-Location
