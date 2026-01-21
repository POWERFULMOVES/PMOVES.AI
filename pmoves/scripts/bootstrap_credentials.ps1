# =============================================================================
# PMOVES.AI Universal Credential Bootstrap (PowerShell)
# =============================================================================
# Run this script in ANY PMOVES.AI submodule to load credentials from:
# 1. Parent PMOVES.AI environment (preferred)
# 2. GitHub Secrets (fallback)
# 3. Local .env file (last resort)
#
# Usage: .\scripts\bootstrap_credentials.ps1
#
# Platforms: Windows PowerShell, PowerShell Core, pwsh
# =============================================================================

#Requires -Version 5.1

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
# Load Credentials from Parent PMOVES.AI
# =============================================================================

function Load-FromParent {
    param(
        [string]$ParentDir,
        [string]$OutputFile = ".env.bootstrap"
    )

    Write-Info "Found parent PMOVES.AI at: $ParentDir"

    $envShared = Join-Path $ParentDir "pmoves\env.shared"
    $parentEnv = Join-Path $ParentDir "pmoves\.env"

    # Load env.shared first (has structure)
    if (Test-Path $envShared) {
        Write-Info "Loading from env.shared..."
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
        Write-Info "Loading from parent .env..."
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
        Write-Warning "GitHub CLI (gh) not installed. Install from: https://cli.github.com/"
        return $false
    }

    # Check if authenticated
    $authStatus = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Not logged into GitHub. Run: gh auth login"
        return $false
    }

    Write-Info "Fetching secrets from $RepoName..."

    # Get list of secrets
    $secretList = gh secret list --repo $RepoName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not fetch secrets from $RepoName"
        return $false
    }

    # Filter for credential secrets
    $secrets = $secretList | Where-Object {
        $_ -match "(API_KEY|APIKEY|TOKEN|PASSWORD|SECRET|OPENAI|ANTHROPIC|GOOGLE|GEMINI)"
    } | ForEach-Object {
        $_.Split(' ')[0]
    }

    if ($secrets.Count -eq 0) {
        Write-Warning "No credential secrets found in repo"
        return $false
    }

    # Create bootstrap file with placeholders
    foreach ($secret in $secrets) {
        $envName = $secret
        "${envName}=`${GH_SECRET_${envName}}" | Add-Content $OutputFile
        Write-Info "  - Added placeholder for $envName"
    }

    Write-Warning "GitHub Secrets fetched - placeholders created. Use 'gh secret set' to populate values."
    return $true
}

# =============================================================================
# Main Bootstrap Flow
# =============================================================================

function Invoke-PmovesBootstrap {
    $outputFile = ".env.bootstrap"
    $sourceUsed = ""

    Write-Info "PMOVES.AI Credential Bootstrap"
    Write-Info "================================"

    # 1. Try to find and load from parent PMOVES.AI
    $parentDir = Find-ParentPmoves
    if ($parentDir) {
        if (Load-FromParent -ParentDir $parentDir -OutputFile $outputFile) {
            $sourceUsed = "parent PMOVES.AI"
        }
    } else {
        Write-Warning "Parent PMOVES.AI not found"
    }

    # 2. If parent failed, try GitHub Secrets
    if (-not (Test-Path $outputFile)) -or ((Get-Content $outputFile | Measure-Object -Line).Lines -lt 5) {
        if (Load-FromGitHubSecrets -OutputFile $outputFile) {
            $sourceUsed = "GitHub Secrets"
        }
    }

    # 3. Final check and output
    if ((Test-Path $outputFile) -and ((Get-Content $outputFile | Measure-Object -Line).Lines -gt 0)) {
        $varCount = (Get-Content $outputFile | Measure-Object -Line).Lines
        Write-Success "Bootstrapped $varCount variables from $sourceUsed"
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
        Write-Host "  1. Ensure parent PMOVES.AI repo exists with pmoves\.env populated"
        Write-Host "  2. OR authenticate with GitHub: gh auth login"
        Write-Host "  3. OR create .env file manually with required credentials"
        return $false
    }
}

# Run bootstrap if executed directly
if ($MyInvocation.InvocationName -eq $MyInvocation.MyCommand.Name) {
    Invoke-PmovesBootstrap
}

# Export functions if sourced
Export-ModuleMember -Function Find-ParentPmoves, Load-FromParent, Load-FromGitHubSecrets, Invoke-PmovesBootstrap
