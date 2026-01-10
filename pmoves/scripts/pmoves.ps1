Param(
  [Parameter(Position=0)][string]$Cmd = "help",
  [string]$File,
  [string]$Namespace = "pmoves",
  [string]$Out,
  [int]$K = 10,
  [int]$Limit = 1000
)

function Compose {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
  docker compose @Args
}

switch ($Cmd) {
  "up" {
    Compose --profile data up -d qdrant neo4j minio meilisearch postgres postgrest presign
    Compose --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker
  }
  "up-fullsupabase" {
    if (Get-Command supabase -ErrorAction SilentlyContinue) {
      Write-Host "Detected Supabase CLI. Starting full Supabase via CLI..."
      try { supabase status | Out-Null } catch {}
      $running = $LASTEXITCODE -eq 0
      if (-not $running) { supabase start }
      # Point PMOVES to CLI endpoints reachable from inside containers via host.docker.internal
      $hostBase = "http://host.docker.internal:54321"
      if (-not $Env:SUPA_REST_URL) { $Env:SUPA_REST_URL = "$hostBase/rest/v1" }
      if (-not $Env:SUPABASE_STORAGE_URL) { $Env:SUPABASE_STORAGE_URL = "$hostBase/storage/v1" }
      if (-not $Env:SUPABASE_PUBLIC_STORAGE_BASE) { $Env:SUPABASE_PUBLIC_STORAGE_BASE = "$hostBase/storage/v1" }
      # Start PMOVES services without local Postgres/PostgREST to avoid conflicts
      Compose --profile data up -d qdrant neo4j minio meilisearch presign
      Compose --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker
    } else {
      Write-Host "Supabase CLI not found. Falling back to compose-based full Supabase."
      Compose -f docker-compose.yml -f docker-compose.supabase.yml --profile data --profile workers up -d
    }
  }
  "down" { Compose down }
  "down-fullsupabase" { Compose -f docker-compose.yml -f docker-compose.supabase.yml down }
  "clean" { Compose down -v }
  "clean-fullsupabase" { Compose -f docker-compose.yml -f docker-compose.supabase.yml down -v }
  "up-legacy" {
    Compose --profile data up -d qdrant neo4j minio meilisearch presign
    Compose --profile workers up -d hi-rag-gateway retrieval-eval render-webhook
  }
  "seed-data" {
    Compose build hi-rag-gateway-v2
    Compose run --rm --entrypoint python hi-rag-gateway-v2 /app/scripts/seed_local.py
  }
  "load-jsonl" {
    if (-not $File) { Write-Error "Usage: pmoves.ps1 load-jsonl -File C:\path\data.jsonl [-Namespace pmoves]"; exit 1 }
    Compose build hi-rag-gateway-v2
    Compose run --rm --entrypoint python --volume "$File`:/data/input.jsonl:ro" hi-rag-gateway-v2 /app/scripts/load_jsonl.py /data/input.jsonl $Namespace
  }
  "load-csv" {
    if (-not $File) { Write-Error "Usage: pmoves.ps1 load-csv -File C:\path\data.csv [-Namespace pmoves]"; exit 1 }
    Compose build hi-rag-gateway-v2
    Compose run --rm --entrypoint python --volume "$File`:/data/input.csv:ro" hi-rag-gateway-v2 /app/scripts/load_csv.py /data/input.csv $Namespace
  }
  "export-jsonl" {
    if (-not $Out) { Write-Error "Usage: pmoves.ps1 export-jsonl -Out C:\path\output.jsonl [-Namespace pmoves] [-Limit 1000]"; exit 1 }
    Compose build hi-rag-gateway-v2
    Compose run --rm --entrypoint python --volume "$Out`:/data/output.jsonl" hi-rag-gateway-v2 /app/scripts/export_jsonl.py /data/output.jsonl $Namespace $Limit
  }
  "eval-jsonl" {
    if (-not $File) { Write-Error "Usage: pmoves.ps1 eval-jsonl -File C:\path\queries.jsonl [-K 10]"; exit 1 }
    Compose build retrieval-eval
    Compose run --rm --entrypoint python --volume "$File`:/data/queries.jsonl:ro" retrieval-eval /app/evaluate.py /data/queries.jsonl $K
  }
  "init-avatars" {
    Write-Host "Creating 'avatars' bucket via storage-api..."
    Compose build extract-worker
    # Mount the init script and run it inside the networked container so it can reach 'storage'
    $scriptPath = Join-Path $PSScriptRoot 'init_avatars.py'
    Compose run --rm --entrypoint python --volume "$scriptPath`:/app/init_avatars.py:ro" extract-worker /app/init_avatars.py
  }
  default {
    Write-Host "PMOVES helper (Windows)"
    Write-Host "Usage: .\scripts\pmoves.ps1 <command> [options]"
    Write-Host "Commands: up, down, clean, up-legacy, seed-data, load-jsonl, load-csv, export-jsonl, eval-jsonl"
  }
}
