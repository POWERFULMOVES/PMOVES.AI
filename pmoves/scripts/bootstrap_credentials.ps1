# =============================================================================
# PMOVES.AI Universal Credential Bootstrap v2 (PowerShell)
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials.
#
# MODES:
#   DOCKED MODE:   ONLY loads from parent PMOVES.AI (detected via env vars)
#   STANDALONE:    Loads from CHIT -> GitHub Secrets -> Docker Secrets
#
# Usage: .\scripts\bootstrap_credentials.ps1
#
# Platforms: Windows PowerShell, PowerShell Core, pwsh
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
    if ($env:DOCKED_MODE -eq "true") {
        return $true
    }

    # Check if running in Docker container (WSL2 indicators)
    if (Test-Path "/.dockerenv" -ErrorAction SilentlyContinue) {
        # Only consider docked if we can reach parent services
        if ($env:NATS_URL -or $env:TENSORZERO_URL) {
            return $true
        }
    }

    # Check WSL2 indicators
    if ($env:WSL_DISTRO_NAME) {
        # Check for parent services
        if ($env:NATS_URL -or $env:TENSORZERO_URL) {
            return $true
        }
    }

    return $false
}

# =============================================================================
# Find Parent PMOVES.AI Repository
# =============================================================================

function Find-ParentPmoves {
    $currentDir = Get-Location
    $parentDir = ""

    # Check if we're in a submodule (look for .git file with gitdir reference)
    $gitFile = Join-Path $currentDir ".git"
    if (Test-Path $gitFile -PathType Leaf) {
        $gitContent = Get-Content $gitFile -Raw
        if ($gitContent -match "gitdir:.*modules") {
            # We're in a submodule
            $gitRoot = (git rev-parse --show-toplevel 2>$null) ?? $currentDir
            $parentDir = Split-Path $gitRoot -Parent
        }
    }

    # If not found, try going up one level
    if ([string]::IsNullOrEmpty($parentDir)) {
        $parentDir = Split-Path $currentDir -Parent
    }

    # Check if parent looks like PMOVES.AI
    $envShared = Join-Path $parentDir "pmoves\env.shared"
    $parentEnv = Join-Path $parentDir "pmoves\.env"

    if (Test-Path $envShared) -or (Test-Path $parentEnv) {
        return Resolve-Path $parentDir
    }

    # Try grandparent level (for nested structures)
    $grandparent = Split-Path $parentDir -Parent
    $envShared = Join-Path $grandparent "pmoves\env.shared"
    $parentEnv = Join-Path $grandparent "pmoves\.env"

    if (Test-Path $envShared) -or (Test-Path $parentEnv) {
        return Resolve-Path $grandparent
    }

    return $null
}

# =============================================================================
# Load Credentials from Parent PMOVES.AI (DOCKED MODE ONLY)
# =============================================================================

function Load-FromParent {
    param(
        [string]$ParentDir,
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Loading from parent PMOVES.AI at: $ParentDir"

    $envShared = Join-Path $ParentDir "pmoves\env.shared"
    $parentEnv = Join-Path $ParentDir "pmoves\.env"

    # Load env.shared first (has structure)
    if (Test-Path $envShared) {
        Write-Info "Loading env.shared structure..."
        Get-Content $envShared | Where-Object {
            $_ -match '^[A-Z_]+=' -or $_ -match '^export '
        } | ForEach-Object {
            $_ -replace '^export ', ''
        } | Set-Content $OutputFile
        $varCount = (Get-Content $OutputFile | Measure-Object -Line).Lines
        Write-Success "Loaded $varCount variables from env.shared"
    } else {
        Write-Warning "env.shared not found at: $envShared"
    }

    # Merge parent .env (has actual credential values)
    if (Test-Path $parentEnv) {
        Write-Info "Loading credential values from parent .env..."
        Get-Content $parentEnv | Where-Object {
            $_ -match '^[A-Z_]+='
        } | Add-Content $OutputFile
        Write-Success "Merged parent .env credentials"
    } else {
        Write-Warning "Parent .env not found at: $parentEnv"
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

    # Possible CGP file locations
    $cgpPaths = @(
        (Join-Path (Get-Location) "data\chit\env.cgp.json"),
        (Join-Path (Get-Location) "pmoves\data\chit\env.cgp.json"),
        (Join-Path $env:USERPROFILE ".config\pmoves\chit\env.cgp.json"),
        (Join-Path $env:USERPROFILE ".pmoves\chit\env.cgp.json"),
        (Join-Path (Split-Path (Get-Location)) "data\chit\env.cgp.json"),
        (Join-Path (Split-Path (Split-Path (Get-Location))) "data\chit\env.cgp.json")
    )

    # Find CGP file
    $cgpFile = $null
    foreach ($path in $cgpPaths) {
        if (Test-Path $path -PathType Leaf) {
            $cgpFile = $path
            break
        }
    }

    if (-not $cgpFile) {
        Write-Info "  No CGP file found (checked: data\chit\env.cgp.json, ~/.config/pmoves/chit/, etc.)"
        return $false
    }

    Write-Info "  Found CGP at: $cgpFile"

    # Try to decode using Python
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

        if ($decoded -and $decoded -match '^[A-Z_]+=') {
            $decoded | Where-Object { $_ -match '^[A-Z_]+=' } | Add-Content $OutputFile
            $count = ($decoded | Where-Object { $_ -match '^[A-Z_]+=' }).Count
            Write-Success "  Decoded $count secrets from CHIT Geometry Packet"
            return $true
        }
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        # Try with 'python' command
        $decoded = python -c @"
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

        if ($decoded -and $decoded -match '^[A-Z_]=') {
            $decoded | Where-Object { $_ -match '^[A-Z_]+=' } | Add-Content $OutputFile
            $count = ($decoded | Where-Object { $_ -match '^[A-Z_]+=' }).Count
            Write-Success "  Decoded $count secrets from CHIT Geometry Packet"
            return $true
        }
    }

    Write-Warning "  CHIT decode failed (Python CHIT module not available)"
    return $false
}

# =============================================================================
# Load Credentials from GitHub Secrets
# =============================================================================

function Load-FromGitHubSecrets {
    param(
        [string]$OutputFile = ".env.bootstrap",
        [string]$RepoName = "POWERFULMOVES/PMOVES.AI"
    )

    Write-Info "Attempting to load from GitHub Secrets..."

    # Check if gh CLI is available
    $ghCmd = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $ghCmd) {
        Write-Info "  GitHub CLI (gh) not installed."
        return $false
    }

    # Check if authenticated
    $authStatus = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Info "  Not logged into GitHub (run: gh auth login)"
        return $false
    }

    Write-Info "  Fetching secret names from $RepoName..."

    # Get list of secrets
    $secretList = gh secret list --repo $RepoName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Info "  Could not fetch secrets from $RepoName"
        return $false
    }

    # Filter for credential secrets
    $secrets = $secretList | Where-Object {
        $_ -match "(API_KEY|APIKEY|TOKEN|PASSWORD|SECRET|OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER)"
    } | ForEach-Object {
        $_.Split(' ')[0]
    }

    if ($secrets.Count -eq 0) {
        Write-Info "  No credential secrets found in repo"
        return $false
    }

    # NOTE: GitHub CLI cannot read secret values (security restriction)
    Write-Warning "  GitHub Secrets found but values cannot be fetched via CLI"
    Write-Info "  Creating reference placeholders..."

    foreach ($secret in $secrets) {
        $envName = $secret
        "# GitHub Secret: $secret" | Add-Content $OutputFile
        "${envName}=`${GH_SECRET_${envName}}" | Add-Content $OutputFile
    }

    Write-Warning "  GitHub Secrets placeholders created. Populate via: gh secret set"
    return $true
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

    Write-Info "PMOVES.AI Credential Bootstrap v2"
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
        Write-Mode "STANDALONE MODE detected - trying CHIT, GitHub, Docker secrets"
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

        # 2. Try GitHub Secrets
        $currentCount = (Get-Content $outputFile -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        if (-not (Test-Path $outputFile) -or $currentCount -lt 3) {
            if (Load-FromGitHubSecrets -OutputFile $outputFile) {
                if ($sourceUsed) { $sourceUsed += " + " }
                $sourceUsed += "GitHub Secrets"
                $sourcesTried.Add("GitHub: success (placeholders)")
            } else {
                $sourcesTried.Add("GitHub: failed")
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
    if ((Test-Path $outputFile) -and ((Get-Content $outputFile | Measure-Object -Line).Lines -gt 0)) {
        $varCount = (Get-Content $outputFile | Select-String '^[A-Z__=').Count
        Write-Success "Bootstrapped $varCount variables from: $sourceUsed"
        Write-Host ""
        Write-Info "To use these credentials:"
        Write-Host "  1. Review:   Get-Content $outputFile"
        Write-Host "  2. Append:   Add-Content $outputFile .env"
        Write-Host "  3. Export:   foreach ($line in Get-Content $outputFile) { if ($line -match '^(.+?)=(.*)') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }"
        Write-Host ""
        Write-Info "Preview of loaded credentials:"
        Get-Content $outputFile | Where-Object {
            $_ -match '^(OPENAI|ANTHROPIC|GOOGLE|GEMINI|OPENROUTER|SUPABASE)_'
        } | ForEach-Object {
            $_ -replace '=.*', '=***masked***'
        }
        return $true
    } else {
        Write-Error "Failed to bootstrap credentials from any source"
        Write-Host ""
        Write-Info "Manual setup required:"
        Write-Host "  1. Create CHIT Geometry Packet: pmoves/tools/chit_encode_secrets.py"
        Write-Host "  2. OR set keys in GitHub Secrets: gh secret set"
        Write-Host "  3. OR create Docker secrets for your stack"
        Write-Host "  4. OR create .env file manually with required credentials"
        return $false
    }
}

# Run bootstrap if executed directly
if ($MyInvocation.InvocationName -eq $MyInvocation.MyCommand.Name) {
    Invoke-PmovesBootstrap
}

# Export functions if sourced
Export-ModuleMember -Function Test-DockedMode, Find-ParentPmoves, Load-FromParent, Load-FromCHIT, Load-FromGitHubSecrets, Load-FromDockerSecrets, Invoke-PmovesBootstrap
