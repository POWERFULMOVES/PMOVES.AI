param(
  [string]$Source = 'supa.md',
  [string]$Out = '.env.supa.remote'
)

if (!(Test-Path $Source)) {
  Write-Error "Source file '$Source' not found"
  exit 1
}

$raw = Get-Content -Raw -Path $Source

# Parse KEY=VALUE or KEY: VALUE; strip surrounding quotes
$map = @{}
foreach ($line in ($raw -split "`n")) {
  $t = $line.Trim()
  if ($t -eq '' -or $t.StartsWith('#')) { continue }
  if ($t -match '^\s*([A-Za-z0-9_]+)\s*[:=]\s*(.+)$') {
    $k = $matches[1]
    $v = $matches[2].Trim().Trim('"', "'")
    $map[$k] = $v
  }
}

$base = $map['SUPABASE_URL']
if (-not $base) { $base = $map['NEXT_PUBLIC_SUPABASE_URL'] }
if (-not $base) {
  Write-Error "Could not find SUPABASE_URL in $Source"
  exit 1
}

$anon = $map['SUPABASE_ANON_KEY']
if (-not $anon) { $anon = $map['NEXT_PUBLIC_SUPABASE_ANON_KEY'] }
$service = $map['SUPABASE_SERVICE_KEY']
if (-not $service) { $service = $map['SUPABASE_KEY'] }

$lines = @(
  "SUPA_REST_URL=$base/rest/v1",
  "GOTRUE_SITE_URL=$base",
  "SUPABASE_STORAGE_URL=$base/storage/v1",
  "SUPABASE_PUBLIC_STORAGE_BASE=$base/storage/v1",
  "# Fill keys locally; do not commit",
  "SUPABASE_ANON_KEY=$anon",
  "SUPABASE_SERVICE_ROLE_KEY=$service",
  "SUPABASE_JWT_SECRET="
)

Set-Content -Path $Out -Value ($lines -join "`r`n")
Write-Host "Wrote $Out from $Source"
