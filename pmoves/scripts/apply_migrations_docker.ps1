Param(
  [string]$ComposeService = 'postgres'
)

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$migs = Join-Path $repo 'supabase/migrations'
if (-not (Test-Path $migs)) { throw "No supabase/migrations directory at $migs" }

Write-Host "Applying migrations from $migs ..."

$cmd = @(
  'docker','compose','run','--rm',
  '-v',"$migs:/migs:ro",
  '--entrypoint','bash', $ComposeService, '-lc',
  'set -euo pipefail; echo Using POSTGRES_USER=$POSTGRES_USER POSTGRES_DB=$POSTGRES_DB; for f in /migs/*.sql; do echo --- applying $f; psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f"; done; echo All migrations applied.'
)

& $cmd

