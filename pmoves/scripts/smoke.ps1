# PowerShell smoke tests for PMOVES.AI
# Mirrors the Makefile `smoke` target without requiring make or jq
# Usage: pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1

param(
  [int]$TimeoutSec = 60,
  [int]$RetryDelayMs = 1000
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-OK($msg='OK') { Write-Host $msg -ForegroundColor Green }
function Write-Warn($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host $msg -ForegroundColor Red }

function Invoke-With-Retry {
  param(
    [Parameter(Mandatory)][scriptblock]$Script,
    [int]$TimeoutSec = 30,
    [int]$DelayMs = 1000
  )
  $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSec)
  do {
    try {
      return & $Script
    } catch {
      if ([DateTime]::UtcNow -ge $deadline) { throw }
      Start-Sleep -Milliseconds $DelayMs
    }
  } while ($true)
}

function Test-Http200 {
  param(
    [Parameter(Mandatory)][string]$Url,
    [hashtable]$Headers
  )
  $irParams = @{ Uri = $Url; Method = 'GET'; UseBasicParsing = $true }
  if ($Headers) { $irParams['Headers'] = $Headers }
  $resp = Invoke-WebRequest @irParams
  if ($resp.StatusCode -lt 200 -or $resp.StatusCode -ge 300) {
    throw "Non-2xx status: $($resp.StatusCode)"
  }
  return $true
}

function Invoke-PostJson {
  param(
    [Parameter(Mandatory)][string]$Url,
    [Parameter(Mandatory)][string]$BodyJson,
    [hashtable]$Headers
  )
  $headersMerged = @{ 'Content-Type' = 'application/json' }
  if ($Headers) { $Headers.GetEnumerator() | ForEach-Object { $headersMerged[$_.Key] = $_.Value } }
  $resp = Invoke-RestMethod -Uri $Url -Method POST -Body $BodyJson -Headers $headersMerged
  return $resp
}

function Invoke-GetJson {
  param(
    [Parameter(Mandatory)][string]$Url,
    [hashtable]$Headers
  )
  $resp = Invoke-RestMethod -Uri $Url -Method GET -Headers $Headers
  return $resp
}

function Test-QdrantReady {
  try { Test-Http200 -Url 'http://localhost:6333/ready' | Out-Null; return $true } catch {}
  try { Test-Http200 -Url 'http://localhost:6333/readyz' | Out-Null; return $true } catch {}
  try {
    $resp = Invoke-RestMethod -Uri 'http://localhost:6333/collections' -Method GET -UseBasicParsing
    if ($resp) { return $true }
  } catch {}
  throw 'Qdrant not ready yet'
}

try {
  # 1. Qdrant ready
  Write-Step "[1/9] Qdrant ready..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-QdrantReady } | Out-Null
  Write-OK

  # 2. Meilisearch health (warn if missing)
  Write-Step "[2/9] Meilisearch ready..."
  try {
    Invoke-With-Retry -TimeoutSec 10 -DelayMs 1000 -Script { Test-Http200 -Url 'http://localhost:7700/health' } | Out-Null
    Write-OK
  } catch { Write-Warn "WARN: skipping; $_" }

  # 3. Neo4j UI (warn if not reachable)
  Write-Step "[3/9] Neo4j UI..."
  try {
    Test-Http200 -Url 'http://localhost:7474' | Out-Null
    Write-OK
  } catch { Write-Warn "WARN: UI not reachable; $_" }

  # 4. presign health
  Write-Step "[4/9] presign health..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200 -Url 'http://localhost:8088/healthz' } | Out-Null
  Write-OK

  # 5. render-webhook health
  Write-Step "[5/9] render-webhook health..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200 -Url 'http://localhost:8085/healthz' } | Out-Null
  Write-OK

  # 6. PostgREST reachable
  Write-Step "[6/9] PostgREST reachable..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200 -Url 'http://localhost:3000' } | Out-Null
  Write-OK

  # 7. Insert via render-webhook
  Write-Step "[7/9] Insert via render-webhook..."
  $renderSecret = $env:RENDER_WEBHOOK_SHARED_SECRET
  if ([string]::IsNullOrWhiteSpace($renderSecret)) { $renderSecret = 'change_me' }
  $headers = @{ 'Authorization' = "Bearer $renderSecret" }
  $payload = '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","presigned_get":null,"title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}'
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJson -Url 'http://localhost:8085/comfy/webhook' -BodyJson $payload -Headers $headers } | Out-Null
  Write-OK

  # 8. Verify studio_board row
  Write-Step "[8/9] Verify studio_board row..."
  $rows = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-GetJson -Url 'http://localhost:3000/studio_board?order=id.desc&limit=1' }
  if ($null -eq $rows -or $rows.Count -lt 1 -or $null -eq $rows[0].title) { throw 'No row with title found' }
  Write-OK

  # 9. Hi-RAG v2 query
  Write-Step "[9/9] Hi-RAG v2 query..."
  $hiragPayload = '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}'
  $resp = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJson -Url 'http://localhost:8087/hirag/query' -BodyJson $hiragPayload }
  if ($null -eq $resp -or $null -eq $resp.hits) { throw 'Response missing .hits' }
  Write-OK

  Write-Host 'Smoke tests passed.' -ForegroundColor Green
  exit 0
} catch {
  Write-Fail "Smoke tests failed: $_"
  exit 1
}
