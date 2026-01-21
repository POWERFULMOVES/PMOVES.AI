# =============================================================================
# PMOVES.AI Universal Credential Bootstrap v3 (PowerShell)
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials.
#
# Full Documentation: pmoves/docs/SECRETS.md
#
# MODES:
#   DOCKED MODE:   ONLY loads from parent PMOVES.AI (detected via env vars)
#   STANDALONE:    Loads from CHIT -> git-crypt -> Docker Secrets -> Parent
#
# Usage: .\scripts\bootstrap_credentials.ps1
#
# Platforms: Windows PowerShell, PowerShell Core, pwsh
#
# Credential Sources (tried in order):
#   1. CHIT Geometry Packet (env.cgp.json) - Encoded secrets in git
#   2. git-crypt (.env.enc) - GPG-encrypted files in git
#   3. Docker Secrets (/run/secrets/) - Container-standard secrets
#   4. Parent PMOVES.AI - Fallback to parent env.shared
# =============================================================================

#Requires -Version 5.1

# =============================================================================
# Logging Functions
# =============================================================================

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Info { Write-ColorOutput "ℹ $args" -Color "Cyan" }
function Write-Success { Write-ColorOutput "✓ $args" -Color "Green" }
function Write-Warning { Write-ColorOutput "⚠ $args" -Color "Yellow" }
function Write-Error { Write-ColorOutput "✗ $args" -Color "Red" }
function Write-Mode { Write-ColorOutput "▶ $args" -Color "DarkCyan" }

# =============================================================================
# Detect Mode: Docked vs Standalone
# =============================================================================

function Test-DockedMode {
    # Check explicit environment variable
    if ($env:DOCKED_MODE -eq "true") { return $true }

    # Check if running in Docker container
    if (Test-Path "/.dockerenv" -ErrorAction SilentlyContinue) {
        # Only consider docked if we can reach parent services
        if ($env:NATS_URL -or $env:TENSORZERO_URL) { return $true }
    }

    return $false
}

# =============================================================================
# Find Parent PMOVES.AI Repository
# =============================================================================

function Find-ParentPmoves {
    $currentDir = Get-Location

    # Check if we're in a submodule
    $gitFile = Join-Path $currentDir ".git"
    if (Test-Path $gitFile -PathType Leaf) {
        $content = Get-Content $gitFile -Raw
        if ($content -match "gitdir:.*modules") {
            # We're in a submodule - find the parent
            $gitRoot = git rev-parse --show-toplevel 2>$null
            if ($gitRoot) {
                $parentDir = Split-Path $gitRoot -Parent
            } else {
                $parentDir = Split-Path $currentDir -Parent
            }
        } else {
            $parentDir = Split-Path $currentDir -Parent
        }
    } else {
        $parentDir = Split-Path $currentDir -Parent
    }

    # Check if parent looks like PMOVES.AI
    $envShared = Join-Path $parentDir "pmoves\env.shared"
    $envFile = Join-Path $parentDir "pmoves\.env"

    if (Test-Path $envShared -PathType Leaf -ErrorAction SilentlyContinue) {
        return $parentDir
    }

    # Try grandparent
    $grandParent = Split-Path $parentDir -Parent
    $envSharedGP = Join-Path $grandParent "pmoves\env.shared"
    if (Test-Path $envSharedGP -PathType Leaf -ErrorAction SilentlyContinue) {
        return $grandParent
    }

    return $null
}

# =============================================================================
# Load Credentials from Parent PMOVES.AI
# =============================================================================

function Load-FromParent {
    param(
        [string]$ParentDir,
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Loading from parent PMOVES.AI at: $ParentDir"

    $envShared = Join-Path $ParentDir "pmoves\env.shared"
    $parentEnv = Join-Path $ParentDir "pmoves\.env"

    if (Test-Path $envShared -PathType Leaf -ErrorAction SilentlyContinue) {
        Write-Info "Loading env.shared structure..."
        Get-Content $envShared -ErrorAction SilentlyContinue |
            Where-Object { $_ -match '^[A-Z_]+=' -or $_ -match '^export ' } |
            ForEach-Object { $_ -replace '^export ', '' } |
            Set-Content $OutputFile
        $count = (Get-Content $OutputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        Write-Success "Loaded $count variables from env.shared"
    }

    if (Test-Path $parentEnv -PathType Leaf -ErrorAction SilentlyContinue) {
        Write-Info "Loading credential values from parent .env..."
        Get-Content $parentEnv -ErrorAction SilentlyContinue |
            Where-Object { $_ -match '^[A-Z_]+=' } |
            Add-Content $OutputFile
        Write-Success "Merged parent .env credentials"
    }

    return $true
}

# =============================================================================
# Load Credentials from CHIT Geometry Packet
# =============================================================================

function Load-FromCHIT {
    param(
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Attempting to load from CHIT Geometry Packet..."

    $cgpPaths = @(
        # Current submodule data directory
        "$(Join-Path (Get-Location) 'data\chit\env.cgp.json')",
        "$(Join-Path (Get-Location) 'pmoves\data\chit\env.cgp.json')",
        # Parent data directory (if in submodule)
        "$(Join-Path (Split-Path (Get-Location) -Parent) 'pmoves\data\chit\env.cgp.json')",
        "$(Join-Path (Split-Path (Split-Path (Get-Location) -Parent) -Parent) 'pmoves\data\chit\env.cgp.json')"
    )

    $cgpFile = $null
    foreach ($path in $cgpPaths) {
        if (Test-Path $path -PathType Leaf -ErrorAction SilentlyContinue) {
            $cgpFile = $path
            break
        }
    }

    if (-not $cgpFile) {
        Write-Info "  No CGP file found (checked: data/chit/env.cgp.json, pmoves/data/chit/, etc.)"
        return $false
    }

    Write-Info "  Found CGP at: $cgpFile"

    # Try to decode using Python CHIT module
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        $decoded = python3 -c @"
import sys
import json
from pathlib import Path

# Try to import CHIT module from parent PMOVES.AI
repo_root = Path('$OutputFile').resolve().parent
for parent in [repo_root] + list(repo_root.parents):
    chit_path = parent / 'pmoves' / 'chit'
    if chit_path.exists():
        sys.path.insert(0, str(parent))
        break

try:
    from pmoves.chit import load_cgp, decode_secret_map
    cgp = load_cgp('$cgpFile')
    secrets = decode_secret_map(cgp)
    for k, v in sorted(secrets.items()):
        print(f'{k}={v}')
except ImportError:
    # Fallback: simple JSON parsing for cleartext values
    with open('$cgpFile') as f:
        cgp = json.load(f)
    for point in cgp.get('points', []):
        label = point['label']
        value = point.get('value', '')
        encoding = point.get('encoding', 'cleartext')
        if encoding == 'cleartext':
            print(f'{label}={value}')
        else:
            print(f'{label}=***CHIT_HEX_ENCODED***')
"@ 2>&1

        if ($LASTEXITCODE -eq 0 -and $decoded) {
            $decoded | Add-Content $OutputFile
            $count = ($decoded | Measure-Object -Line).Lines
            Write-Success "  Decoded $count secrets from CHIT Geometry Packet"
            return $true
        }
    }

    Write-Warning "  CHIT decode failed (Python CHIT module not available)"
    return $false
}

# =============================================================================
# Load Credentials from git-crypt Encrypted File
# =============================================================================

function Load-FromGitCrypt {
    param(
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Attempting to load from git-crypt..."

    $encPaths = @(
        # Current repository
        "$(Join-Path (Get-Location) 'pmoves\.env.enc')",
        "$(Join-Path (Get-Location) '.env.enc')",
        # Parent directories
        "$(Join-Path (Split-Path (Get-Location) -Parent) 'pmoves\.env.enc')",
        "$(Join-Path (Split-Path (Split-Path (Get-Location) -Parent) -Parent) 'pmoves\.env.enc')"
    )

    $encFile = $null
    foreach ($path in $encPaths) {
        if (Test-Path $path -PathType Leaf -ErrorAction SilentlyContinue) {
            $encFile = $path
            break
        }
    }

    if (-not $encFile) {
        Write-Info "  No git-crypt file found (checked: pmoves/.env.enc, .env.enc, etc.)"
        return $false
    }

    Write-Info "  Found git-crypt file at: $encFile"

    # Check if file is decrypted (content is readable)
    $firstLine = Get-Content $encFile -TotalCount 1 -ErrorAction SilentlyContinue

    # git-crypt encrypted files start with specific bytes
    # If we can read a normal-looking line, it's decrypted
    if ($firstLine -match '#|PMOVES|[A-Z]_') {
        # File is decrypted, load it
        Get-Content $encFile -ErrorAction SilentlyContinue |
            Where-Object { $_ -match '^[A-Z_]+=' } |
            Add-Content $OutputFile

        $count = (Get-Content $OutputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        Write-Success "  Loaded $count credentials from git-crypt (decrypted)"
        return $true
    } else {
        Write-Warning "  git-crypt file is encrypted. Run: git-crypt unlock"
        Write-Info "  Then re-run bootstrap to load credentials."
        return $false
    }
}

# =============================================================================
# Load Credentials from Docker Secrets
# =============================================================================

function Load-FromDockerSecrets {
    param(
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Attempting to load from Docker Secrets..."

    # On Windows/WSL2, check WSL mount point
    $secretsDirs = @(
        "/run/secrets",           # WSL2
        "\\wsl$\docker-desktop-data\run\secrets"  # Docker Desktop on Windows
    )

    $secretsDir = $null
    foreach ($dir in $secretsDirs) {
        if (Test-Path $dir -PathType Container -ErrorAction SilentlyContinue) {
            $secretsDir = $dir
            break
        }
    }

    if (-not $secretsDir) {
        Write-Info "  Docker secrets directory not found"
        return $false
    }

    $found = 0
    foreach ($pattern @("pmoves_*", "*_api_key", "*_token")) {
        $files = Get-ChildItem -Path $secretsDir -Filter $pattern -ErrorAction SilentlyContinue
        foreach ($file in $files) {
            if ($file.PSIsContainer) { continue }

            $basename = $file.Name
            # Convert docker secret name to env var format
            $envName = $basename -replace '^pmoves_', '' -replace '_', ' ' |
                        ForEach-Object { $_.ToUpper() } -join '_' -replace ' API KEY', '_API_KEY' -replace ' TOKEN', '_TOKEN'

            $value = Get-Content $file.FullName -ErrorAction SilentlyContinue
            if ($value) {
                "${envName}=${value}" | Add-Content $OutputFile
                Write-Info "  Loaded $envName from Docker secret"
                $found++
            }
        }
    }

    if ($found -gt 0) {
        Write-Success "  Loaded $found credentials from Docker secrets"
        return $true
    } else {
        Write-Info "  No PMOVES Docker secrets found"
        return $false
    }
}

# =============================================================================
# Main Bootstrap Flow
# =============================================================================

function Invoke-PmovesBootstrap {
    $outputFile = ".env.bootstrap"
    $sourceUsed = ""

    Write-Info "PMOVES.AI Credential Bootstrap v3"
    Write-Info "====================================="

    # Detect mode
    if (Test-DockedMode) {
        Write-Mode "DOCKED MODE detected - loading from parent only"
        Write-Host ""

        # DOCKED MODE: Only load from parent
        $parentDir = Find-ParentPmoves
        if ($parentDir) {
            Load-FromParent -ParentDir $parentDir -OutputFile $outputFile
            $sourceUsed = "parent PMOVES.AI (docked)"
        } else {
            Write-Error "DOCKED MODE: Parent PMOVES.AI not found!"
            Write-Info "In docked mode, credentials MUST come from parent repo."
            return $false
        }
    } else {
        Write-Mode "STANDALONE MODE detected - trying CHIT, git-crypt, Docker secrets"
        Write-Host ""

        # STANDALONE MODE: Try multiple sources
        $sourcesTried = [System.Collections.Generic.List[string]]::new()

        # 1. Try CHIT decode first
        if (Load-FromCHIT -OutputFile $outputFile) {
            $sourceUsed = "CHIT Geometry Packet"
            $sourcesTried.Add("CHIT: success")
        } else {
            $sourcesTried.Add("CHIT: failed")
        }

        # 2. Try git-crypt
        $currentCount = (Get-Content $outputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        if (-not (Test-Path $outputFile) -or $currentCount -lt 3) {
            if (Load-FromGitCrypt -OutputFile $outputFile) {
                if ($sourceUsed) { $sourceUsed += " + " }
                $sourceUsed += "git-crypt"
                $sourcesTried.Add("git-crypt: success")
            } else {
                $sourcesTried.Add("git-crypt: failed")
            }
        }

        # 3. Try Docker Secrets
        $currentCount = (Get-Content $outputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        if (-not (Test-Path $outputFile) -or $currentCount -lt 3) {
            if (Load-FromDockerSecrets -OutputFile $outputFile) {
                if ($sourceUsed) { $sourceUsed += " + " }
                $sourceUsed += "Docker Secrets"
                $sourcesTried.Add("Docker: success")
            } else {
                $sourcesTried.Add("Docker: failed")
            }
        }

        # 4. Fallback: Try parent (last resort in standalone)
        $currentCount = (Get-Content $outputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        if (-not (Test-Path $outputFile) -or $currentCount -lt 3) {
            $parentDir = Find-ParentPmoves
            if ($parentDir) {
                Write-Info "Fallback: loading from parent PMOVES.AI..."
                Load-FromParent -ParentDir $parentDir -OutputFile $outputFile
                if ($sourceUsed) { $sourceUsed += " + " }
                $sourceUsed += "parent PMOVES.AI"
                $sourcesTried.Add("Parent: success")
            } else {
                $sourcesTried.Add("Parent: not found")
            }
        }

        Write-Host ""
        Write-Info "Sources tried: $($sourcesTried -join ', ')"
    }

    # Final check and output
    if (Test-Path $outputFile -PathType Leaf) {
        $varCount = (Get-Content $outputFile -ErrorAction SilentlyContinue |
                     Where-Object { $_ -match '^[A-Z_]+=' } |
                     Measure-Object -Line).Lines
        if ($varCount -gt 0) {
            Write-Success "Bootstrapped $varCount variables from: $sourceUsed"
            Write-Host ""
            Write-Info "To use these credentials:"
            Write-Host "  .\$outputFile                    # PowerShell (dot-source)"
            Write-Host "  OR"
            Write-Host "  cat \$outputFile >> .env         # Append to .env"
            Write-Host ""
            Write-Info "Preview of loaded credentials:"
            Get-Content $outputFile | Where-Object {
                $_ -match '^(OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER|SUPABASE)_'
            } | ForEach-Object {
                $_ -replace '=.*', '=***masked***'
            }
            return $true
        }
    }

    Write-Error "Failed to bootstrap credentials from any source"
    Write-Host ""
    Write-Info "Manual setup required:"
    Write-Host "  1. Create CHIT Geometry Packet: python3 -m pmoves.tools.chit_encode_secrets"
    Write-Host "  2. OR setup git-crypt: git-crypt init && git-crypt add-gpg-user you@email.com"
    Write-Host "  3. OR create Docker secrets for your stack"
    Write-Host "  4. OR create .env file manually with required credentials"
    Write-Host ""
    Write-Info "Full documentation: pmoves/docs/SECRETS.md"
    return $false
}

# Run bootstrap if executed directly
if ($MyInvocation.InvocationName -eq $MyInvocation.MyCommand.Name) {
    Invoke-PmovesBootstrap
}
