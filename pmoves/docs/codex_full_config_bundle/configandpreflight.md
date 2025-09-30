PowerShell (save as scripts/env_check.ps1)
  # PMOVES env check (read-only). Requires PowerShell 7+                                                
  # Usage:                                                                                              
  #   pwsh -File scripts/env_check.ps1 -Json    # machine-readable
  #   pwsh -File scripts/env_check.ps1 -Quick   # faster, fewer scans

  param(                                                                                                
    [switch]$Json,                                                                                      
    [switch]$Quick                                                                                      
  )                                                                                                     
                                                                                                        
  $ErrorActionPreference = 'SilentlyContinue'                                                           
                                                                                                        
  function Get-CmdInfo {                                                                                
    param([string]$Name, [string[]]$Args = @('--version'))                                              
    $present = $false; $version = $null                                                                 
    try {                                                                                               
      $cmd = Get-Command $Name -ErrorAction Stop                                                        
      $present = $true                                                                                  
      try {                                                                                             
        $p = Start-Process -FilePath $cmd.Source -ArgumentList $Args -NoNewWindow -PassThru             
  -RedirectStandardOutput ([System.IO.Path]::GetTempFileName())                                         
        $p.WaitForExit()                                                                                
        $version = (Get-Content $p.RedirectStandardOutput).Trim() -join ' '                             
        Remove-Item $p.RedirectStandardOutput -Force                                                    
      } catch { }                                                                                       
    } catch { $present = $false }                                                                       
    [pscustomobject]@{ name=$Name; present=$present; version=$version }                                 
  }                                                                                                     
                                                                                                        
  function Test-JsonFile {                                                                              
    param([string]$Path)                                                                                
    if (-not (Test-Path $Path)) { return [pscustomobject]@{ path=$Path; exists=$false; valid=$false;    
  note='missing' } }                                                                                    
    try {                                                                                               
      $j = Get-Content -Raw -Path $Path | ConvertFrom-Json                                              
      [pscustomobject]@{ path=$Path; exists=$true; valid=$true; keys=($j.PSObject.Properties.Name) }    
    } catch {                                                                                           
      [pscustomobject]@{ path=$Path; exists=$true; valid=$false; note='invalid json' }                  
    }                                                                                                   
  }                                                                                                     
                                                                                                        
  function Count-Dirs {                                                                                 
    param([string]$Path)                                                                                
    if (Test-Path $Path) { (Get-ChildItem -Path $Path -Directory -ErrorAction SilentlyContinue).Count } 
  else { 0 }                                                                                            
  }                                                                                                     
                                                                                                        
  $info = [ordered]@{                                                                                   
    timestamp = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')                                             
    cwd       = (Get-Location).Path                                                                     
    os        = $PSVersionTable.OS                                                                      
    ps        = $PSVersionTable.PSVersion.ToString()                                                    
  }                                                                                                     
                                                                                                        
  # Commands to probe (read-only)                                                                       
  $cmds = @(                                                                                            
    'rg','git','python','python3','pip','uv','poetry','conda',                                          
    'node','npm','make','docker'                                                                        
  )                                                                                                     
  $cmdResults = @{}                                                                                     
  foreach ($c in $cmds) {                                                                               
    $cmdResults[$c] = Get-CmdInfo -Name $c                                                              
  }                                                                                                     
                                                                                                        
  # Docker compose (plugin or v1)                                                                       
  $compose = $null                                                                                      
  if ($cmdResults['docker'].present) {                                                                  
    try {                                                                                               
      $compose = Get-CmdInfo -Name 'docker' -Args @('compose','version')                                
      if (-not $compose.version) { $compose = Get-CmdInfo -Name 'docker-compose' }                      
    } catch { $compose = Get-CmdInfo -Name 'docker-compose' }                                           
  } else {                                                                                              
    $compose = Get-CmdInfo -Name 'docker-compose'                                                       
  }                                                                                                     
                                                                                                        
  # Repo shape checks (read-only)                                                                       
  $shape = [ordered]@{                                                                                  
    has_services  = Test-Path 'services'                                                                
    has_contracts = Test-Path 'contracts'                                                               
    has_schemas   = Test-Path 'schemas'                                                                 
    has_supabase  = Test-Path 'supabase'                                                                
    has_neo4j     = Test-Path 'neo4j'                                                                   
    has_n8n       = Test-Path 'n8n'                                                                     
    has_comfyui   = Test-Path 'comfyui'                                                                 
    has_datasets  = Test-Path 'datasets'                                                                
    has_docs      = Test-Path 'docs'                                                                    
    services_cnt  = Count-Dirs 'services'                                                               
  }                                                                                                     
                                                                                                        
  # Contracts sanity                                                                                    
  $topics = Test-JsonFile -Path 'contracts/topics.json'                                                 
                                                                                                        
  # Optional quick repo signals via ripgrep                                                             
  $signals = [ordered]@{}                                                                               
  if ($cmdResults['rg'].present -and -not $Quick) {                                                     
    try {                                                                                               
      $signals['fastapi_refs'] = (rg -n "FastAPI" services | Select-Object -First 8)                    
      $signals['dockerfiles']  = (rg -l "^FROM " -g "*/Dockerfile" | Measure-Object).Count              
      $signals['requirements'] = (rg -l "^fastapi|^uvicorn" -g "services/**/requirements*.txt" |        
  Measure-Object).Count                                                                                 
    } catch { }                                                                                         
  }                                                                                                     
                                                                                                        
  # Capability summary                                                                                  
  function Present { param($n) return ($cmdResults[$n] -and $cmdResults[$n].present) }                  
  $cap = [ordered]@{                                                                                    
    ripgrep   = Present 'rg'                                                                            
    git       = Present 'git'                                                                           
    python    = (Present 'python' -or Present 'python3')                                                
    docker    = Present 'docker'                                                                        
    compose   = ($compose.present -or ($compose -and $compose.version))                                 
    make      = Present 'make'                                                                          
  }                                                                                                     
                                                                                                        
  $result = [pscustomobject]@{                                                                          
    info        = $info                                                                                 
    commands    = $cmdResults                                                                           
    docker_compose = $compose                                                                           
    repo_shape  = $shape                                                                                
    contracts   = $topics                                                                               
    capability  = $cap                                                                                  
    signals     = $signals                                                                              
    recommendations = @(                                                                                
      if ($cap.docker -and $cap.compose) { "You can likely run: make up (or: docker compose up -d)" }   
      elseif ($cap.docker) { "Docker present; install compose plugin to use docker compose" }           
      else { "Install Docker Desktop (for make up/docker compose)" }                                    
      if (-not $cap.python) { "Install Python 3.10+ for running services locally" }                     
      if (-not $cap.ripgrep) { "Install ripgrep for fast code search (optional)" }                      
    )                                                                                                   
  }                                                                                                     
                                                                                                        
  } else {
    Write-Host "`n== PMOVES Environment Check ==" -ForegroundColor Cyan
    "{0,-12} {1}" -f "CWD:", $info.cwd
    "{0,-12} {1}" -f "OS:", $info.os
    "{0,-12} {1}" -f "PowerShell:", $info.ps
    ""
    Write-Host "Commands:" -ForegroundColor Cyan
    foreach ($k in $cmdResults.Keys | Sort-Object) {
      $r = $cmdResults[$k]
      $mark = if ($r.present) { "[OK]" } else { "[--]" }
      "{0} {1,-14} {2}" -f $mark, $k, ($r.version -replace '\s+',' ' | Select-Object -First 1)
    }
    "{0} {1,-14} {2}" -f ($(if($compose.present -or $compose.version){"[OK]"}else{"[--]"}) ), "compose",
  ($compose.version -replace '\s+',' ')
    ""
    Write-Host "Repo shape:" -ForegroundColor Cyan
    $shape.GetEnumerator() | Sort-Object Name | ForEach-Object { "{0,-14} {1}" -f ($_.Name+':'),        
  $_.Value }
    ""
    Write-Host "Contracts:" -ForegroundColor Cyan
    "{0,-22} {1}" -f "contracts/topics.json", ($(if($topics.valid){"valid"}elseif($topics.exists)
  {"invalid"}else{"missing"}))
    if ($topics.valid -and $topics.keys) { "topics keys: {0}" -f (($topics.keys -join ', ')) | Write-   
  Host }
    if ($signals.Keys.Count -gt 0) {
      ""
      Write-Host "Signals:" -ForegroundColor Cyan
      foreach ($s in $signals.Keys) { "{0,-14} {1}" -f ($s+':'), ($signals[$s] -join '; ') }
    }
    ""
    Write-Host "Recommendations:" -ForegroundColor Cyan
    ($result.recommendations | Where-Object { $_ } | Select-Object -Unique) | ForEach-Object { "- $_" } 
  }
  Bash (save as scripts/env_check.sh)
  #!/usr/bin/env bash
  # PMOVES env check (read-only)
  # Usage: bash scripts/env_check.sh [-q]
  set -euo pipefail                                                                                     
  quick=0                                                                                               
  [[ "${1:-}" == "-q" ]] && quick=1                                                                     
                                                                                                        
  have() { command -v "$1" >/dev/null 2>&1; }                                                           
  ver() { ($@ --version 2>/dev/null || true) | head -n1 | tr -s ' '; }                                  
                                                                                                        
  echo ""                                                                                               
  echo "== PMOVES Environment Check =="                                                                 
  echo "CWD: $(pwd)"                                                                                    
  echo "OS:  $(uname -a || true)"                                                                       
  echo ""                                                                                               
                                                                                                        
  printf "Commands:\n"                                                                                  
  for c in rg git python python3 pip uv poetry conda node npm make docker docker-compose; do            
    if have "$c"; then                                                                                  
      printf "[OK] %-15s %s\n" "$c" "$(ver "$c")"                                                       
    else                                                                                                
      printf "[--] %-15s \n" "$c"                                                                       
    fi                                                                                                  
  done                                                                                                  
  if have docker; then                                                                                  
    if docker compose version >/dev/null 2>&1; then                                                     
      printf "[OK] %-15s %s\n" "compose" "$(docker compose version | head -n1)"                         
    fi                                                                                                  
  fi                                                                                                    
                                                                                                        
  echo ""                                                                                               
  printf "Repo shape:\n"                                                                                
  for d in services contracts schemas supabase neo4j n8n comfyui datasets docs; do                      
    if [[ -d "$d" ]]; then                                                                              
      printf "%-14s %s\n" "$d:" "yes"                                                                   
    else                                                                                                
      printf "%-14s %s\n" "$d:" "no"                                                                    
    fi                                                                                                  
  done                                                                                                  
  svc_cnt=$(find services -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')              
  printf "%-14s %s\n" "services_cnt:" "$svc_cnt"                                                        
                                                                                                        
  echo ""                                                                                               
  printf "Contracts:\n"                                                                                 
  if [[ -f contracts/topics.json ]]; then                                                               
    if jq -e . >/dev/null 2>&1 < contracts/topics.json; then                                            
      printf "%-22s %s\n" "contracts/topics.json" "valid"                                               
      keys=$(jq -r 'keys | join(", ")' contracts/topics.json 2>/dev/null || true)                       
      [[ -n "$keys" ]] && echo "topics keys: $keys"                                                     
    else                                                                                                
      printf "%-22s %s\n" "contracts/topics.json" "invalid"                                             
    fi                                                                                                  
  else                                                                                                  
    printf "%-22s %s\n" "contracts/topics.json" "missing"                                               
  fi                                                                                                    
                                                                                                        
  if have rg && [[ "$quick" -eq 0 ]]; then                                                              
    echo ""                                                                                             
    printf "Signals:\n"                                                                                 
    fastapi=$(rg -n "FastAPI" services 2>/dev/null | head -n 5 | tr '\n' '; ')                          
  echo ""
  printf "Recommendations:\n"
  if have docker; then
    if docker compose version >/dev/null 2>&1 || have docker-compose; then
      echo "- You can likely run: make up (or: docker compose up -d)"
    else
      echo "- Docker present; install compose plugin to use docker compose"
    fi
    echo "- Install Docker Desktop (for make up/docker compose)"
  fi
  if ! have python && ! have python3; then
  if ! have python && ! have python3; then
    echo "- Install Python 3.10+ for running services locally"
  fi
    echo "- Install Python 3.10+ for running services locally"
  fi
  if ! have rg; then
  if ! have rg; then
    echo "- Install ripgrep for fast code search (optional)"
    echo "- Install ripgrep for fast code search (optional)"
  fi
  How to use

  fi
  How to use

  How to use


  - PowerShell: pwsh -File scripts/env_check.ps1 (add -Json for machine-readable).
  - Bash: bash scripts/env_check.sh (add -q for a quick run).
  - PowerShell: pwsh -File scripts/env_check.ps1 (add -Json for machine-readable).
  - Bash: bash scripts/env_check.sh (add -q for a quick run).

  - Bash: bash scripts/env_check.sh (add -q for a quick run).

  Want me to tailor this to a specific service (e.g., hi-rag-gateway or retrieval-eval) and add service-
  specific checks?

▌yes lets flight check b4 launch this can be tool helper for user to make sure everthying is configured 

  Want me to tailor this to a specific service (e.g., hi-rag-gateway or retrieval-eval) and add service-
  specific checks?

▌yes lets flight check b4 launch this can be tool helper for user to make sure everthying is configured 
▌right im thinking

  Want me to tailor this to a specific service (e.g., hi-rag-gateway or retrieval-eval) and add service-
  specific checks?

▌yes lets flight check b4 launch this can be tool helper for user to make sure everthying is configured 
▌right im thinking


▌yes lets flight check b4 launch this can be tool helper for user to make sure everthying is configured 
▌right im thinking

> I’m going to scan compose files and the Makefile to tailor a “flight check” script to your stack      
▌right im thinking

> I’m going to scan compose files and the Makefile to tailor a “flight check” script to your stack      
  (ports, profiles, services).

• Explored
> I’m going to scan compose files and the Makefile to tailor a “flight check” script to your stack      
  (ports, profiles, services).

• Explored
  └ Search never in **
    Search never in **
    Search never in ^
    Search never in .env.example
    Search never in }

> Great idea — let’s ship a “flight check” helper that validates prereqs, env, compose, and ports before
  you run make up.

  Here’s a single-file PowerShell tool you can drop into scripts/pmoves_flight_check.ps1. It’s read-only
  and cross-checks what your repo actually declares in docker-compose.yml.

  PowerShell (save as scripts/pmoves_flight_check.ps1)
  # PMOVES Flight Check (read-only)
  # Usage:
  #   pwsh -File scripts/pmoves_flight_check.ps1
  #   pwsh -File scripts/pmoves_flight_check.ps1 -Json
  #   pwsh -File scripts/pmoves_flight_check.ps1 -Quick
                                                                                                        
  param(                                                                                                
    [string]$ComposePath = "docker-compose.yml",                                                        
    [switch]$Json,                                                                                      
    [switch]$Quick                                                                                      
  )                                                                                                     
                                                                                                        
  $ErrorActionPreference = 'SilentlyContinue'                                                           
                                                                                                        
  function Get-CmdInfo {                                                                                
    param([string]$Name,[string[]]$Args=@('--version'))                                                 
    $present=$false;$version=$null                                                                      
    try {                                                                                               
      $cmd=Get-Command $Name -ErrorAction Stop                                                          
      $present=$true                                                                                    
      try {                                                                                             
        $p = Start-Process -FilePath $cmd.Source -ArgumentList $Args -NoNewWindow -PassThru             
  -RedirectStandardOutput ([System.IO.Path]::GetTempFileName())                                         
        $p.WaitForExit()                                                                                
        $version = (Get-Content $p.RedirectStandardOutput) -join ' ' -replace '\s+',' '                 
        Remove-Item $p.RedirectStandardOutput -Force                                                    
      } catch {}                                                                                        
    } catch { $present=$false }                                                                         
    [pscustomobject]@{ name=$Name; present=$present; version=$version }                                 
  }                                                                                                     
                                                                                                        
  function Parse-Compose {                                                                              
    param([string]$Path)                                                                                
    if (-not (Test-Path $Path)) {                                                                       
      return [pscustomobject]@{                                                                         
        exists=$false; services=@(); ports=@(); envRefs=@(); profiles=@{}                               
      }                                                                                                 
    }                                                                                                   
    $lines = Get-Content -Path $Path -Raw -EA SilentlyContinue -Encoding UTF8 -Delimiter "`n" | Out-    
  String                                                                                                
    $services = @()                                                                                     
    $ports    = @()                                                                                     
    $envRefs  = New-Object System.Collections.Generic.HashSet[string]                                   
    $profiles = @{}                                                                                     
    $svc = $null                                                                                        
                                                                                                        
    foreach ($line in ($lines -split "\r?\n")) {                                                        
      if ($line -match '^\s{2}([A-Za-z0-9_\-]+):\s*$' -and $svc -ne 'services') {                       
        # service block start (2-space indent)                                                          
        $svc = $matches[1]                                                                              
        if ($svc -ne '' -and $svc -ne 'services' -and $svc -ne 'volumes' -and $svc -ne 'networks') {    
          $services += $svc                                                                             
        }                                                                                               
      }                                                                                                 
      if ($line -match 'ports:\s*\[(.*)\]') {                                                           
        $inline = $matches[1] -split '\s*,\s*'                                                          
        foreach ($p in $inline) {                                                                       
          if ($p -match '"?(\d+):(\d+)"?') { $ports += [pscustomobject]@{ service=$svc;                 
  host=[int]$matches[1]; container=[int]$matches[2] } }                                                 
        }                                                                                               
      } elseif ($line -match '^\s{6,}-\s*"?(\d+):(\d+)"?\s*$') {                                        
        $ports += [pscustomobject]@{ service=$svc; host=[int]$matches[1]; container=[int]$matches[2] }  
      }                                                                                                 
      foreach ($m in [System.Text.RegularExpressions.Regex]::Matches($line, '\$\{([A-Z0-9_]+)')) {      
        [void]$envRefs.Add($m.Groups[1].Value)                                                          
      }                                                                                                 
      if ($line -match 'profiles:\s*\[(.+)\]') {                                                        
        $profiles[$svc] = ($matches[1] -split '\s*,\s*' | ForEach-Object { $_ -replace '"','' })        
      }                                                                                                 
    }                                                                                                   
    [pscustomobject]@{                                                                                  
      exists=$true; services=$services | Sort-Object -Unique;                                           
      ports=$ports; envRefs=$envRefs.ToArray() | Sort-Object -Unique; profiles=$profiles                
    }                                                                                                   
  }                                                                                                     
                                                                                                        
  function Get-EnvFile {                                                                                
    param([string]$Path='.env')                                                                         
    $kv=@{}                                                                                             
    if (-not (Test-Path $Path)) { return $kv }                                                          
    Get-Content $Path | ForEach-Object {                                                                
      $line = $_.Trim()                                                                                 
      if ($line -match '^\s*#' -or $line -eq '') { return }                                             
      $idx = $line.IndexOf('=')                                                                         
      if ($idx -gt 0) {                                                                                 
        $k = $line.Substring(0,$idx).Trim()                                                             
        $v = $line.Substring($idx+1).Trim()                                                             
        $kv[$k]=$v                                                                                      
      }                                                                                                 
    }                                                                                                   
    $kv                                                                                                 
  }                                                                                                     
                                                                                                        
  function Test-Port {                                                                                  
    param([int]$Port)                                                                                   
    try {                                                                                               
      if ($IsWindows) {                                                                                 
        $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue          
        return [bool]($c)                                                                               
      } else {                                                                                          
        $out = (lsof -iTCP:$Port -sTCP:LISTEN 2>$null)                                                  
        return [bool]$out                                                                               
      }                                                                                                 
    } catch { return $false }                                                                           
  }                                                                                                     
                                                                                                        
  # 1) System & toolchain                                                                               
  $info = [ordered]@{                                                                                   
    timestamp = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')                                             
    cwd = (Get-Location).Path                                                                           
    os  = $PSVersionTable.OS                                                                            
    ps  = $PSVersionTable.PSVersion.ToString()                                                          
  }                                                                                                     
  $cmds = 'docker','docker-compose','make','rg','python','python3','git'                                
  $cmdStatus = @{}                                                                                      
  foreach ($c in $cmds) { $cmdStatus[$c] = Get-CmdInfo -Name $c }                                       
                                                                                                        
  # Compose plugin detection                                                                            
  $composeOK=$false;$composeWhy=$null                                                                   
  if ($cmdStatus['docker'].present) {                                                                   
    try {                                                                                               
      $p = Start-Process -FilePath (Get-Command docker).Source -ArgumentList @('compose','version')     
  -NoNewWindow -PassThru -RedirectStandardOutput ([System.IO.Path]::GetTempFileName())                  
      $p.WaitForExit()                                                                                  
      $composeOK = ($p.ExitCode -eq 0)                                                                  
      Remove-Item $p.RedirectStandardOutput -Force                                                      
    } catch {}                                                                                          
  } elseif ($cmdStatus['docker-compose'].present) {                                                     
    $composeOK = $true                                                                                  
  }                                                                                                     
                                                                                                        
  # 2) Repo shape                                                                                       
  $shape = [ordered]@{                                                                                  
    services  = Test-Path 'services'                                                                    
    contracts = Test-Path 'contracts'                                                                   
    schemas   = Test-Path 'schemas'                                                                     
    supabase  = Test-Path 'supabase'                                                                    
    neo4j     = Test-Path 'neo4j'                                                                       
    n8n       = Test-Path 'n8n'                                                                         
    comfyui   = Test-Path 'comfyui'                                                                     
    datasets  = Test-Path 'datasets'                                                                    
    docs      = Test-Path 'docs'                                                                        
  }                                                                                                     
                                                                                                        
  # 3) Compose parsing, config validate, profiles                                                       
  $compose = Parse-Compose -Path $ComposePath                                                           
  $composeConfigOK = $null                                                                              
  if ($compose.exists -and $composeOK -and -not $Quick) {                                               
    try {                                                                                               
      $proc = Start-Process -FilePath (Get-Command docker).Source -ArgumentList @('compose','-f',       
  $ComposePath, 'config','-q') -NoNewWindow -PassThru                                                   
      $proc.WaitForExit()                                                                               
      $composeConfigOK = ($proc.ExitCode -eq 0)                                                         
    } catch {                                                                                           
      if ($cmdStatus['docker-compose'].present) {                                                       
        $proc = Start-Process -FilePath (Get-Command docker-compose).Source -ArgumentList @('-f',       
  $ComposePath, 'config','-q') -NoNewWindow -PassThru                                                   
        $proc.WaitForExit(); $composeConfigOK = ($proc.ExitCode -eq 0)                                  
      }                                                                                                 
    }                                                                                                   
  }                                                                                                     
                                                                                                        
  # 4) Env file coverage                                                                                
  $envActual = Get-EnvFile -Path '.env'                                                                 
  $requiredEnv = $compose.envRefs                                                                       
  $missingEnv  = @()                                                                                    
  foreach ($k in $requiredEnv) {                                                                        
    if (-not $envActual.ContainsKey($k)) { $missingEnv += $k }                                          
  }                                                                                                     
  $criticalEnv = @('PMOVES_CONTRACTS_DIR')                                                              
  $criticalMissing = $criticalEnv | Where-Object { -not $envActual.ContainsKey($_) }                    
                                                                                                        
  # 5) Port conflicts                                                                                   
  $portChecks = @()                                                                                     
  foreach ($p in $compose.ports) {                                                                      
    $inUse = Test-Port -Port $p.host                                                                    
    $portChecks += [pscustomobject]@{                                                                   
      service=$p.service; host=$p.host; container=$p.container; in_use=$inUse                           
    }                                                                                                   
  }                                                                                                     
                                                                                                        
  # 6) Summary                                                                                          
  $recommendations = @()                                                                                
  if (-not $cmdStatus['docker'].present) { $recommendations += "Install Docker Desktop." }              
  elseif (-not $composeOK) { $recommendations += "Install Compose plugin (docker compose) or docker-    
  compose." }                                                                                           
  if (-not $cmdStatus['python'].present -and -not $cmdStatus['python3'].present) { $recommendations +=  
  "Install Python 3.10+ for local services." }                                                          
  if (-not (Test-Path '.env')) { $recommendations += "Create .env (start from docs/LOCAL_DEV.md or your 
  template)." }                                                                                         
  if ($missingEnv.Count -gt 0) { $recommendations += "Add missing env keys: {0}" -f ($missingEnv -join  
  ', ') }                                                                                               
  if ($criticalMissing.Count -gt 0) { $recommendations += "Critical: set PMOVES_CONTRACTS_DIR (schema   
  resolution)." }                                                                                       
  $blocked = $portChecks | Where-Object { $_.in_use } | Select-Object -First 1                          
  if ($blocked) { $recommendations += "Free occupied ports before launch (e.g., {0})." -f ($portChecks  
  | Where-Object in_use | ForEach-Object { "$($_.host)->$($_.service)" } | Select-Object -First 3 -join 
  ', ') }                                                                                               
                                                                                                        
  $result = [pscustomobject]@{                                                                          
    info=$info                                                                                          
    commands=$cmdStatus                                                                                 
    compose=@{                                                                                          
      exists=$compose.exists                                                                            
      services=$compose.services                                                                        
      profiles=$compose.profiles                                                                        
      ports=$compose.ports                                                                              
      config_ok=$composeConfigOK                                                                        
    }                                                                                                   
    repo_shape=$shape                                                                                   
    env=@{                                                                                              
      has_env=(Test-Path '.env')                                                                        
      required=$requiredEnv                                                                             
      present=($envActual.Keys | Sort-Object)                                                           
      missing=$missingEnv                                                                               
      critical_missing=$criticalMissing                                                                 
    }                                                                                                   
    ports=$portChecks                                                                                   
    recommendations=($recommendations | Select-Object -Unique)                                          
    ready=($compose.exists -and $composeConfigOK -ne $false -and ($portChecks | Where-Object in_use |   
  Measure-Object).Count -eq 0 -and $criticalMissing.Count -eq 0)                                        
  }                                                                                                     
                                                                                                        
  if ($Json) {                                                                                          
    $result | ConvertTo-Json -Depth 8                                                                   
  } else {                                                                                              
    Write-Host "`n== PMOVES Flight Check ==" -ForegroundColor Cyan                                      
    "{0,-12} {1}" -f "CWD:", $info.cwd                                                                  
    "{0,-12} {1}" -f "OS:",  $info.os                                                                   
    "{0,-12} {1}" -f "PS:",  $info.ps                                                                   
    ""                                                                                                  
    Write-Host "Prereqs:" -ForegroundColor Cyan                                                         
    foreach ($k in @('docker','docker-compose','make','rg','python','python3','git')) {                 
      $r = $cmdStatus[$k]; $mark = if ($r.present) { "[OK]" } else { "[--]" }                           
      "{0} {1,-14} {2}" -f $mark, $k, ($r.version -replace '\s+',' ' | Select-Object -First 1)          
    }                                                                                                   
    if ($composeOK) { "[OK] {0,-14} {1}" -f "compose", "available" | Write-Host }                       
    ""                                                                                                  
    Write-Host "Compose:" -ForegroundColor Cyan                                                         
    "{0,-14} {1}" -f "file:", ($(if($compose.exists){"found"}else{"missing"}))                          
    "{0,-14} {1}" -f "services:", ($(if($compose.services){ ($compose.services -join ', ') }            
  else{"none"}))                                                                                        
    "{0,-14} {1}" -f "config:", ($(if($composeConfigOK -eq $true){"valid"}elseif($composeConfigOK -eq   
  $false){"INVALID"}else{"skipped"}))                                                                   
    ""                                                                                                  
    Write-Host "Env:" -ForegroundColor Cyan                                                             
    "{0,-14} {1}" -f ".env:", ($(if(Test-Path '.env'){"present"}else{"missing"}))                       
    if ($missingEnv.Count -gt 0) { "missing: {0}" -f ($missingEnv -join ', ') | Write-Host }            
    if ($criticalMissing.Count -gt 0) { "critical missing: {0}" -f ($criticalMissing -join ', ') |      
  Write-Host }                                                                                          
    ""                                                                                                  
    Write-Host "Ports:" -ForegroundColor Cyan                                                           
    foreach ($pc in $portChecks | Sort-Object host) {                                                   
      "{0,-6} -> {1,-14} {2}" -f $pc.host, $pc.service, ($(if($pc.in_use){"IN-USE"}else{"free"}))       
    }                                                                                                   
    ""                                                                                                  
    Write-Host "Repo shape:" -ForegroundColor Cyan                                                      
    $shape.GetEnumerator() | Sort-Object Name | ForEach-Object { "{0,-14} {1}" -f ($_.Name+':'),        
  $_.Value }                                                                                            
    ""                                                                                                  
    Write-Host "Recommendations:" -ForegroundColor Cyan                                                 
    ($result.recommendations | Where-Object { $_ }) | ForEach-Object { "- $_" }                         
    ""                                                                                                  
    "{0} Ready for launch" -f ($(if($result.ready){"[OK]"}else{"[--]"})) | Write-Host                   
  }                                                                                                     
  What it checks                                                                                        
                                                                                                        
  - Docker + Compose present; basic toolchain (make, ripgrep, python, git).                             
  - docker-compose.yml parses for services, profiles, ports, and referenced env variables.              
  - docker compose config -q validates your compose file.                                               
  - .env coverage vs env vars referenced in compose (flags critical PMOVES_CONTRACTS_DIR).              
  - Port conflicts on host for all published ports in compose.                                          
  - Repo shape sanity: services, contracts, schemas, supabase, neo4j, n8n, comfyui, datasets, docs.     
                                                                                                        
  Known ports in your compose right now                                                                 
                                                                                                        
  - 5432, 3000, 6333, 7700, 7474, 7687, 9000, 9001                                                      
  - 8086 (legacy hi-rag), 8087->8086 (hi-rag-v2 host), 8088->8080 (presign), 8078 (ffmpeg-whisper), 8079
  (media-video), 8082 (media-audio), 8077 (pmoves-yt)                                                   
  - 8090 (retrieval-eval), 4222 (nats), 8080 (agent-zero), 8091 (archon)                                
                                                                                                        
  How to run                                                                                            
                                                                                                        
  - Save the script to scripts/pmoves_flight_check.ps1.                                                 
  - Run: pwsh -File scripts/pmoves_flight_check.ps1                                                     
  - Optional: add -Json to integrate into CI or a preflight step.                                       
                                                                                                        
  Want a Bash version too or for me to wire this into a Makefile target like make flight-check?   