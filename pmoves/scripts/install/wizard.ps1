$ErrorActionPreference = "Stop"
Write-Host "PMOVES First-Run Wizard (PowerShell)"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pmovesRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$envFile = Join-Path $pmovesRoot ".env.local"
$baseEnv = Join-Path $pmovesRoot ".env.example"

if (-not (Test-Path $baseEnv)) {
  throw "Missing base env template at $baseEnv"
}

if (-not (Test-Path $envFile)) {
  Copy-Item $baseEnv $envFile
}

function Invoke-Make {
  param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Target
  )
  Push-Location $pmovesRoot
  try {
    & make $Target
    $code = $LASTEXITCODE
    if ($code -ne 0) {
      throw "make $Target exited with code $code"
    }
  } finally {
    Pop-Location
  }
}

$mode = Read-Host "Stack mode: [1] Full  [2] Minimal (no n8n/yt/comfy)"
$extS = Read-Host "Use external Supabase? (y/N)"
$extN = Read-Host "Use external Neo4j?    (y/N)"
$extM = Read-Host "Use external Meili?     (y/N)"
$extQ = Read-Host "Use external Qdrant?    (y/N)"
$gpu  = Read-Host "Enable GPU profile now? (y/N)"

(Get-Content $envFile) |
  ForEach-Object {
    $_ -replace '^EXTERNAL_SUPABASE=.*', ('EXTERNAL_SUPABASE=' + ($(if ($extS -eq 'y') {'true'} else {'false'}))) `
       -replace '^EXTERNAL_NEO4J=.*',    ('EXTERNAL_NEO4J='    + ($(if ($extN -eq 'y') {'true'} else {'false'}))) `
       -replace '^EXTERNAL_MEILI=.*',    ('EXTERNAL_MEILI='    + ($(if ($extM -eq 'y') {'true'} else {'false'}))) `
       -replace '^EXTERNAL_QDRANT=.*',   ('EXTERNAL_QDRANT='   + ($(if ($extQ -eq 'y') {'true'} else {'false'})))
  } | Set-Content $envFile

$durl = Read-Host "DISCORD_WEBHOOK_URL (empty to skip)"
if ($durl) {
  (Get-Content $envFile) -replace '^DISCORD_WEBHOOK_URL=.*', ("DISCORD_WEBHOOK_URL="+$durl) | Set-Content $envFile
}

if ($gpu -eq 'y') { try { Invoke-Make -Target 'up-gpu' } catch {} } else { try { Invoke-Make -Target 'up' } catch {} }
if ($mode -eq '1') {
  try { Invoke-Make -Target 'up-n8n' } catch {}
  try { Invoke-Make -Target 'up-yt' } catch {}
  try { Invoke-Make -Target 'up-comfy' } catch {}
}
try { Invoke-Make -Target 'flight-check' } catch {}
Write-Host "Wizard complete."
