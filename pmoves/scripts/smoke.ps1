# PowerShell smoke tests for PMOVES.AI
# Mirrors the Makefile `smoke` target without requiring make or jq
# Usage: pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1

param(
  [int]$TimeoutSec = 60,
  [int]$RetryDelayMs = 1000
)

$ErrorActionPreference = 'Stop'
$Script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$Script:ComposeProject = if ([string]::IsNullOrWhiteSpace($env:COMPOSE_PROJECT_NAME)) { 'pmoves' } else { $env:COMPOSE_PROJECT_NAME }
$Script:ProbeService = $null
$Script:ProbeContainer = $null

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

function Get-EnvFileValue {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Key
  )
  if (-not (Test-Path $Path)) { return $null }
  $match = Get-Content -Path $Path | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
  if (-not $match) { return $null }
  $value = $match.Substring($Key.Length + 1).Trim()
  if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
    $value = $value.Substring(1, $value.Length - 2)
  }
  return $value
}

function Resolve-SupabaseRestUrl {
  $direct = $env:SUPA_REST_URL
  if ([string]::IsNullOrWhiteSpace($direct)) { $direct = $env:SUPABASE_REST_URL }
  if (-not [string]::IsNullOrWhiteSpace($direct)) {
    return $direct.TrimEnd('/')
  }

  $runtimeOverlay = Join-Path $Script:ProjectRoot 'env.supa.runtime'
  $overlayRest = Get-EnvFileValue -Path $runtimeOverlay -Key 'SUPA_REST_URL'
  if (-not [string]::IsNullOrWhiteSpace($overlayRest)) {
    return $overlayRest.TrimEnd('/')
  }

  $statusFile = Join-Path $Script:ProjectRoot '.supabase.status.env'
  $apiUrl = Get-EnvFileValue -Path $statusFile -Key 'API_URL'
  if (-not [string]::IsNullOrWhiteSpace($apiUrl)) {
    return ("{0}/rest/v1" -f $apiUrl.TrimEnd('/'))
  }

  return 'http://localhost:3010'
}

function Escape-ShSingleQuotes {
  param([Parameter(Mandatory)][string]$Value)
  $replacement = "'" + '"' + "'" + '"' + "'"
  return $Value.Replace("'", $replacement)
}

function Resolve-ContainerName {
  param([Parameter(Mandatory)][string]$Service)
  $names = (& docker ps --format '{{.Names}}')
  $project = [regex]::Escape($Script:ComposeProject)
  $svc = [regex]::Escape($Service)
  foreach ($name in $names) {
    if ($name -match "^$project[-_]$svc[-_]\d+$") { return $name }
  }
  foreach ($name in $names) {
    if ($name -eq $Service) { return $name }
  }
  throw "No running container found for service '$Service' in project '$($Script:ComposeProject)'"
}

function Invoke-ContainerExec {
  param(
    [Parameter(Mandatory)][string]$Container,
    [Parameter(Mandatory)][string]$Command
  )
  $output = & docker exec $Container sh -lc $Command
  if ($LASTEXITCODE -ne 0) {
    throw "docker exec failed for container '$Container'"
  }
  return $output
}

function Resolve-ProbeService {
  if (-not [string]::IsNullOrWhiteSpace($Script:ProbeService)) {
    return $Script:ProbeService
  }
  foreach ($candidate in @('hi-rag-gateway-v2', 'agent-zero', 'archon')) {
    try {
      $container = Resolve-ContainerName -Service $candidate
      Invoke-ContainerExec -Container $container -Command "command -v curl >/dev/null" | Out-Null
      $Script:ProbeService = $candidate
      $Script:ProbeContainer = $container
      return $Script:ProbeService
    } catch {}
  }
  throw "No running probe service with curl found (tried: hi-rag-gateway-v2, agent-zero, archon)"
}

function Invoke-ProbeStatus {
  param(
    [Parameter(Mandatory)][string]$Url,
    [ValidateSet('GET','POST','PATCH')][string]$Method = 'GET',
    [string]$BodyJson,
    [hashtable]$Headers
  )
  Resolve-ProbeService | Out-Null
  $probe = $Script:ProbeService
  $probeContainer = $Script:ProbeContainer
  $parts = @(
    "curl",
    "-sS",
    "-o /dev/null",
    "-w '%{http_code}'",
    "-X $Method"
  )
  $parts += "-H 'Accept: application/json'"
  if ($Headers) {
    foreach ($entry in $Headers.GetEnumerator()) {
      $headerValue = "{0}: {1}" -f $entry.Key, $entry.Value
      $parts += "-H '{0}'" -f (Escape-ShSingleQuotes -Value $headerValue)
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($BodyJson)) {
    $parts += "-H 'Content-Type: application/json'"
    $parts += "-d '{0}'" -f (Escape-ShSingleQuotes -Value $BodyJson)
  }
  $parts += "'{0}'" -f (Escape-ShSingleQuotes -Value $Url)
  $statusRaw = Invoke-ContainerExec -Container $probeContainer -Command ($parts -join ' ')
  $statusText = "$statusRaw".Trim()
  if ($statusText -notmatch '^\d{3}$') {
    throw "Invalid probe HTTP status from $probe for ${Url}: '$statusText'"
  }
  return [int]$statusText
}

function Test-Http200WithFallback {
  param(
    [Parameter(Mandatory)][string]$PrimaryUrl,
    [string]$ProbeUrl,
    [hashtable]$Headers
  )
  try {
    Test-Http200 -Url $PrimaryUrl -Headers $Headers | Out-Null
    return $true
  } catch {
    if ([string]::IsNullOrWhiteSpace($ProbeUrl)) { throw }
    $status = Invoke-ProbeStatus -Url $ProbeUrl -Method 'GET' -Headers $Headers
    if ($status -lt 200 -or $status -ge 300) {
      throw "Probe URL '$ProbeUrl' returned HTTP $status"
    }
    return $true
  }
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

function Invoke-PostJsonWithFallback {
  param(
    [Parameter(Mandatory)][string]$PrimaryUrl,
    [Parameter(Mandatory)][string]$BodyJson,
    [hashtable]$Headers,
    [string]$ProbeUrl
  )
  try {
    return Invoke-PostJson -Url $PrimaryUrl -BodyJson $BodyJson -Headers $Headers
  } catch {
    if ([string]::IsNullOrWhiteSpace($ProbeUrl)) { throw }
    $status = Invoke-ProbeStatus -Url $ProbeUrl -Method 'POST' -BodyJson $BodyJson -Headers $Headers
    if ($status -lt 200 -or $status -ge 300) {
      throw "Probe POST '$ProbeUrl' returned HTTP $status"
    }
    return @{ ok = $true; via = 'probe' }
  }
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
  $base = ($env:QDRANT_URL -as [string])
  if ([string]::IsNullOrWhiteSpace($base)) { $base = 'http://localhost:6333' }
  $base = $base.TrimEnd('/')
  foreach ($endpoint in @("$base/ready", "$base/readyz", "$base/collections")) {
    try { Test-Http200 -Url $endpoint | Out-Null; return $true } catch {}
  }
  foreach ($endpoint in @('http://qdrant:6333/ready', 'http://qdrant:6333/readyz', 'http://qdrant:6333/collections')) {
    try {
      $status = Invoke-ProbeStatus -Url $endpoint
      if ($status -ge 200 -and $status -lt 300) { return $true }
    } catch {}
  }
  throw 'Qdrant not ready yet'
}

try {
  $supaRestBase = Resolve-SupabaseRestUrl

  # 1. Qdrant ready
  Write-Step "[1/12] Qdrant ready..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-QdrantReady } | Out-Null
  Write-OK

  # 2. Meilisearch health (warn if missing)
  Write-Step "[2/12] Meilisearch ready..."
  try {
    Invoke-With-Retry -TimeoutSec 10 -DelayMs 1000 -Script { Test-Http200 -Url 'http://localhost:7700/health' } | Out-Null
    Write-OK
  } catch { Write-Warn "WARN: skipping; $_" }

  # 3. Neo4j UI (warn if not reachable)
  Write-Step "[3/12] Neo4j UI..."
  try {
    Test-Http200 -Url 'http://localhost:7474' | Out-Null
    Write-OK
  } catch { Write-Warn "WARN: UI not reachable; $_" }

  # 4. presign health
  Write-Step "[4/12] presign health..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200WithFallback -PrimaryUrl 'http://localhost:8088/healthz' -ProbeUrl 'http://presign:8080/healthz' } | Out-Null
  Write-OK

  # 5. render-webhook health
  Write-Step "[5/12] render-webhook health..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200WithFallback -PrimaryUrl 'http://localhost:8085/healthz' -ProbeUrl 'http://render-webhook:8085/healthz' } | Out-Null
  Write-OK

  # 6. PostgREST reachable
  Write-Step "[6/12] PostgREST reachable..."
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Test-Http200 -Url "$supaRestBase/" } | Out-Null
  Write-OK

  # 7. Insert via render-webhook
  Write-Step "[7/12] Insert via render-webhook..."
  $renderSecret = $env:RENDER_WEBHOOK_SHARED_SECRET
  if ([string]::IsNullOrWhiteSpace($renderSecret)) { $renderSecret = 'change_me' }
  $headers = @{ 'Authorization' = "Bearer $renderSecret" }
  $payload = '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","presigned_get":null,"title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}'
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJsonWithFallback -PrimaryUrl 'http://localhost:8085/comfy/webhook' -ProbeUrl 'http://render-webhook:8085/comfy/webhook' -BodyJson $payload -Headers $headers } | Out-Null
  Write-OK

  # 8. Verify studio_board row
  Write-Step "[8/12] Verify studio_board row..."
  $rows = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-GetJson -Url "$supaRestBase/studio_board?order=id.desc&limit=1" }
  if ($null -eq $rows -or $rows.Count -lt 1 -or $null -eq $rows[0].title) { throw 'No row with title found' }
  Write-OK

  # 9. Hi-RAG v2 query
  Write-Step "[9/12] Hi-RAG v2 query..."
  $hiragPayload = '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}'
  $resp = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJson -Url 'http://localhost:8086/hirag/query' -BodyJson $hiragPayload }
  if ($null -eq $resp -or $null -eq $resp.hits) { throw 'Response missing .hits' }
  Write-OK

  # 10. Agent Zero health (JetStream)
  Write-Step "[10/12] Agent Zero health..."
  $agentZeroHealth = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-GetJson -Url 'http://localhost:8080/healthz' }
  if ($null -eq $agentZeroHealth -or $null -eq $agentZeroHealth.nats) { throw 'Agent Zero health missing nats section' }
  if (-not $agentZeroHealth.nats.controller_started -or -not $agentZeroHealth.nats.use_jetstream) {
    throw 'Agent Zero JetStream controller not reported as started'
  }
  Write-OK

  # 11. Geometry event ingestion
  Write-Step "[11/12] Geometry event ingest..."
  $cid = ([Guid]::NewGuid().ToString('N')).Substring(0,8)
  $pointId = "p.smoke.$cid"
  $constId = "c.smoke.$cid"
  $refId = "yt:smoke-$cid"
  $cgp = @{
    spec = "chit.cgp.v0.1"
    meta = @{
      source = "smoke-test"
      namespace = "pmoves"
      run_id = $cid
    }
    super_nodes = @(
      @{
        id = "sn.smoke"
        constellations = @(
          @{
            id = $constId
            summary = "smoke geometry validation"
            radial_minmax = @(0.05, 0.85)
            spectrum = @(0.08,0.12,0.18,0.22,0.18,0.12,0.07,0.03)
            anchor = @(0.52,-0.41,0.23,0.11)
            points = @(
              @{
                id = $pointId
                modality = "video"
                ref_id = $refId
                t_start = 12.5
                frame_idx = 300
                proj = 0.82
                conf = 0.93
                text = "geometry smoke anchor"
              }
            )
          }
        )
      }
    )
  }
  $eventBody = @{ type = "geometry.cgp.v1"; data = $cgp } | ConvertTo-Json -Depth 10
  Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJson -Url 'http://localhost:8086/geometry/event' -BodyJson $eventBody } | Out-Null
  Write-OK

  # 12. Geometry jump + calibration
  Write-Step "[12/12] Geometry jump & calibration..."
  $jump = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-GetJson -Url ("http://localhost:8086/shape/point/{0}/jump" -f $pointId) }
  if ($null -eq $jump -or $jump.locator.ref_id -ne $refId) {
    throw "Jump endpoint mismatch (expected $refId)"
  }
  $cgpJson = $cgp | ConvertTo-Json -Depth 10
  $calib = Invoke-With-Retry -TimeoutSec $TimeoutSec -DelayMs $RetryDelayMs -Script { Invoke-PostJson -Url 'http://localhost:8086/geometry/calibration/report' -BodyJson $cgpJson }
  if ($null -eq $calib -or $null -eq $calib.constellations) {
    throw 'Calibration report missing constellations array'
  }
  Write-OK

  Write-Host 'Smoke tests passed.' -ForegroundColor Green
  exit 0
} catch {
  Write-Fail "Smoke tests failed: $_"
  exit 1
}
