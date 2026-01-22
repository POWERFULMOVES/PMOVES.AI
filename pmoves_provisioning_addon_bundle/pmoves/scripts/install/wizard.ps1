$ErrorActionPreference = "Stop"
Write-Host "PMOVES First-Run Wizard (PowerShell)"

$envFile = "pmoves/.env.local"
$baseEnv = "pmoves/.env.example"
if (-not (Test-Path $envFile)) { Copy-Item $baseEnv $envFile }

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

if ($gpu -eq 'y') { & make up-gpu } else { & make up }
if ($mode -eq '1') {
  try { & make up-n8n } catch {}
  try { & make up-yt } catch {}
  try { & make up-comfy } catch {}
}
try { & make flight-check } catch {}
Write-Host "Wizard complete."
