# PMOVES Environment Preflight Check (PowerShell 7+)
# Usage:
#   pwsh -File scripts/env_check.ps1            # full scan
#   pwsh -File scripts/env_check.ps1 -Quick     # faster, fewer scans
#   pwsh -File scripts/env_check.ps1 -Json      # machine-readable JSON output

param(
  [switch]$Quick,
  [switch]$Json
)

$ErrorActionPreference = 'SilentlyContinue'

function Get-CmdInfo {
  param([string]$Name)
  $present = $false; $version = $null
  try {
    $cmd = Get-Command $Name -ErrorAction Stop
    if ($cmd) { $present = $true }
  } catch {}
  if ($present) {
    try {
      $p = New-Object System.Diagnostics.Process
      $p.StartInfo.FileName = $Name
      $p.StartInfo.Arguments = '--version'
      $p.StartInfo.UseShellExecute = $false
      $p.StartInfo.RedirectStandardOutput = $true
      $p.StartInfo.RedirectStandardError = $true
      $p.StartInfo.CreateNoWindow = $true
      $p.Start() | Out-Null
      $out = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd()
      $p.WaitForExit()
      $version = ($out -split "`r?`n")[0].Trim()
    } catch {}
  }
  [pscustomobject]@{ name=$Name; present=$present; version=$version }
}

function Test-JsonFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return [pscustomobject]@{ path=$Path; exists=$false; valid=$false; keys=@() } }
  try {
    $text = Get-Content -Raw -Path $Path -Encoding UTF8
    $obj = $text | ConvertFrom-Json -AsHashtable
    $keys = @()
    if ($obj -is [hashtable]) { $keys = $obj.Keys | Sort-Object }
    [pscustomobject]@{ path=$Path; exists=$true; valid=$true; keys=$keys }
  } catch {
    [pscustomobject]@{ path=$Path; exists=$true; valid=$false; keys=@() }
  }
}

function Get-EnvKeysFromDotenv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @() }
  $lines = Get-Content -Path $Path -Encoding UTF8
  $keys = @()
  foreach ($ln in $lines) {
    $t = $ln.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $eq = $t.IndexOf('=')
    if ($eq -gt 0) {
      $keys += $t.Substring(0,$eq).Trim()
    }
  }
  ($keys | Sort-Object -Unique)
}

function Test-PortOpen {
  param([int]$Port)
  try {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
    return $conns.Count -gt 0
  } catch { return $false }
}

# Basic info
$info = [ordered]@{
  cwd        = (Get-Location).Path
  os         = (Get-CimInstance Win32_OperatingSystem).Caption
  ps_version = $PSVersionTable.PSVersion.ToString()
  timestamp  = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
}

# Commands presence
$cmds = @('rg','git','python','python3','pip','uv','poetry','conda','node','npm','make','docker')
$cmdResults = @{}
foreach ($c in $cmds) { $cmdResults[$c] = Get-CmdInfo -Name $c }

# Docker compose plugin or v1
$compose = $null
if ($cmdResults['docker'].present) {
  try {
    $composeVer = (& docker compose version) 2>$null
    if ($LASTEXITCODE -eq 0) { $compose = [pscustomobject]@{ present=$true; version=($composeVer -split "`n")[0].Trim() } }
  } catch {}
}
if (-not $compose) {
  $dc = Get-CmdInfo -Name 'docker-compose'
  $compose = [pscustomobject]@{ present=$dc.present; version=$dc.version }
}

# Docker engine status (optional quick)
$dockerInfo = $null
if ($cmdResults['docker'].present -and -not $Quick) {
  try { $dockerInfo = (& docker info --format '{{json .ServerVersion}}') } catch {}
}

# Repo shape
$shape = [ordered]@{
  has_services = Test-Path 'services'
  has_contracts = Test-Path 'contracts'
  has_schemas = Test-Path 'schemas'
  has_supabase = Test-Path 'supabase'
  has_neo4j = Test-Path 'neo4j'
  has_n8n = Test-Path 'n8n'
  has_comfyui = Test-Path 'comfyui'
  has_datasets = Test-Path 'datasets'
  has_docs = Test-Path 'docs'
}

$topics = Test-JsonFile -Path 'contracts/topics.json'

# Ports we expect the stack to use
$ports = @(6333, 7474, 8088, 8085, 3000, 8087, 8084, 7700)
$portStatus = @{}
foreach ($p in $ports) { $portStatus[$p] = if (Test-PortOpen -Port $p) { 'LISTENING' } else { 'free' } }

# .env sanity vs .env.example
$envKeys = Get-EnvKeysFromDotenv -Path '.env'
$envExampleKeys = Get-EnvKeysFromDotenv -Path '.env.example'
$missingEnvKeys = @()
if ($envExampleKeys.Count -gt 0) {
  $missingEnvKeys = @($envExampleKeys | Where-Object { $_ -notin $envKeys })
}

# MCP Docker plugin (optional)
$dockerMcp = $false
try {
  & docker mcp --help 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) { $dockerMcp = $true }
} catch {}

$result = [pscustomobject]@{
  info = $info
  commands = ($cmdResults.GetEnumerator() | Sort-Object Name | ForEach-Object { [pscustomobject]@{ name=$_.Key; present=$_.Value.present; version=$_.Value.version } })
  compose = $compose
  docker = [pscustomobject]@{ running = [bool]$dockerInfo; mcp_plugin = $dockerMcp; serverVersion=$dockerInfo }
  repo = $shape
  contracts = $topics
  ports = ($portStatus.GetEnumerator() | Sort-Object Name | ForEach-Object { [pscustomobject]@{ port=[int]$_.Key; status=$_.Value } })
  env = [pscustomobject]@{ env_present=(Test-Path '.env'); example_present=(Test-Path '.env.example'); missing_keys=$missingEnvKeys }
}

if ($Json) {
  $result | ConvertTo-Json -Depth 6
  exit 0
}

Write-Host "`n== PMOVES Environment Check ==" -ForegroundColor Cyan
"CWD: $($info.cwd)"
"OS:  $($info.os)"
"PS:  $($info.ps_version)"

""
Write-Host "Commands:" -ForegroundColor Yellow
foreach ($row in $result.commands) {
  $ok = if ($row.present) { '[OK]' } else { '[--]' }
  "{0} {1,-14} {2}" -f $ok, $row.name, ($row.version -replace '\s+',' ')
}
"{0} {1,-14} {2}" -f ($(if($result.compose.present){'[OK]'}else{'[--]'}) ), 'compose', ($result.compose.version -replace '\s+',' ')

""
Write-Host "Repo shape:" -ForegroundColor Yellow
$shape.GetEnumerator() | Sort-Object Name | ForEach-Object { "{0,-14} {1}" -f ($_.Name+':'), $_.Value }

""
Write-Host "Contracts:" -ForegroundColor Yellow
"contracts/topics.json: " + ($(if($topics.valid){'valid'} elseif($topics.exists){'invalid'} else {'missing'}))
if ($topics.valid -and $topics.keys -and -not $Quick) {
  "topics keys: {0}" -f (($topics.keys -join ', ')) | Write-Host
  # Ensure summary topics are present
  $need = @('health.weekly.summary.v1','finance.monthly.summary.v1')
  foreach ($t in $need) {
    try {
      $raw = Get-Content -Raw -Path 'contracts/topics.json' -Encoding UTF8
      $obj = $raw | ConvertFrom-Json -AsHashtable
      if (-not ($obj.topics.ContainsKey($t))) { Write-Host ("WARN: missing topic: {0}" -f $t) -ForegroundColor DarkYellow }
    } catch {}
  }
}

""
Write-Host "Ports:" -ForegroundColor Yellow
foreach ($p in $result.ports) { "{0,-6} {1}" -f ($p.port), $p.status }

""
Write-Host ".env status:" -ForegroundColor Yellow
".env present:       $($result.env.env_present)"
".env.example:       $($result.env.example_present)"
if ($missingEnvKeys.Count -gt 0) {
  Write-Host "Missing keys (present in .env.example but not in .env):" -ForegroundColor Red
  $missingEnvKeys | ForEach-Object { "- $_" }
}

if (-not $result.compose.present) {
  Write-Host "Hint: Docker Compose V2 plugin not detected. Install Docker Desktop or ensure 'docker compose' works." -ForegroundColor DarkYellow
}
if (-not $cmdResults['jq'].present) {
  Write-Host "Note: jq is recommended for Makefile smoke tests." -ForegroundColor DarkYellow
}

# Mapper helper presence
if (Test-Path 'tools/events_to_cgp.py') {
  Write-Host "events_to_cgp.py:   present" -ForegroundColor Green
} else {
  Write-Host "events_to_cgp.py:   missing" -ForegroundColor DarkYellow
}

Write-Host "\nDone." -ForegroundColor Green
