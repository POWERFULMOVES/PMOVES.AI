# PMOVES Environment Loader (PowerShell 7+)
# Windows equivalent of with-env.sh for 6-tier architecture
# Loads, in order: tier env files → env.shared.generated → env.shared → .env.generated → .env.local
#
# Usage:
#   .\scripts\with-env.ps1
#   .\scripts\with-env.ps1 { docker compose up -d }

$ErrorActionPreference = "Continue"
$ScriptRoot = $PSScriptRoot
if (-not $ScriptRoot) { $ScriptRoot = "." }
$RootDir = (Split-Path -Parent $ScriptRoot)

# Function to load environment variables from a file
function Load-EnvFile {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    Write-Verbose "Loading env from: $Path"

    Get-Content -Path $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()

        # Skip comments and empty lines
        if ([string]::IsNullOrEmpty($line) -or $line.StartsWith('#')) {
            continue
        }

        # Parse KEY=VALUE format
        if ($line -match '^[A-Za-z_][A-Za-z0-9_]*\s*=.+$') {
            $eqIdx = $line.IndexOf('=')
            $key = $line.Substring(0, $eqIdx).Trim()
            $value = $line.Substring($eqIdx + 1).Trim()

            # Set the environment variable in the current process
            Set-Item -Path "env:$key" -Value $value -Force
        }
    }
}

# Hardened 6-tier architecture: load tier env files first
# Note: ROOT_DIR is the pmoves folder (script is at pmoves/scripts/with-env.ps1)
# All env files are in the pmoves folder

Load-EnvFile "$RootDir\env.tier-data"
Load-EnvFile "$RootDir\env.tier-api"
Load-EnvFile "$RootDir\env.tier-llm"
Load-EnvFile "$RootDir\env.tier-media"
Load-EnvFile "$RootDir\env.tier-agent"
Load-EnvFile "$RootDir\env.tier-worker"

# Legacy env files (loaded after tiers for backward compatibility)
# These are also in the pmoves folder
Load-EnvFile "$RootDir\env.shared.generated"
Load-EnvFile "$RootDir\env.shared"
Load-EnvFile "$RootDir\.env.generated"
Load-EnvFile "$RootDir\.env.local"

# Back-compat: some docs/manifests use MINIO_USER/MINIO_PASSWORD. Services use MINIO_ACCESS_KEY/MINIO_SECRET_KEY.
if (-not $env:MINIO_ACCESS_KEY -and $env:MINIO_USER) {
    $env:MINIO_ACCESS_KEY = $env:MINIO_USER
}
if (-not $env:MINIO_SECRET_KEY -and $env:MINIO_PASSWORD) {
    $env:MINIO_SECRET_KEY = $env:MINIO_PASSWORD
}

# Local MinIO defaults:
# If only the unified S3 creds (MINIO_ACCESS_KEY/MINIO_SECRET_KEY) are configured,
# mirror them into MINIO_ROOT_USER/MINIO_ROOT_PASSWORD so the optional local MinIO service can boot.
if (-not $env:MINIO_ROOT_USER -and $env:MINIO_ACCESS_KEY) {
    $env:MINIO_ROOT_USER = $env:MINIO_ACCESS_KEY
}
if (-not $env:MINIO_ROOT_PASSWORD -and $env:MINIO_SECRET_KEY) {
    $env:MINIO_ROOT_PASSWORD = $env:MINIO_SECRET_KEY
}

$env:PMOVES_ENV_LOADER = "1"

# Export environment variables to child processes (PowerShell 7+)
# This allows subsequent commands in the same session to access the variables
Get-ChildItem -Path Env: | ForEach-Object {
    $key = $_.Name
    $value = $_.Value
    # Use Set-Content to write to a temp file that can be sourced
    # This is primarily for documentation; actual env vars are already set above
}
