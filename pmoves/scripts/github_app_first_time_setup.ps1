# =============================================================================
# GitHub App First-Time Setup Script (Windows PowerShell)
# =============================================================================
#
# This script automates the first-time setup of GitHub App credentials
# on Windows systems using PowerShell.
#
# PREREQUISITES:
#   - GitHub CLI installed (https://cli.github.com/)
#   - GitHub CLI authenticated (gh auth login)
#   - Python 3.8+ installed
#
# USAGE:
#   .\pmoves\scripts\github_app_first_time_setup.ps1
#
# =============================================================================

#Requires -Version 5.1

[CmdletBinding()]
param()

# Helper functions
function Write-Header {
    param([string]$Text)
    $padding = " " * ((70 - $Text.Length) / 2)
    Write-Host ""
    Write-Host "==========================================================================" -ForegroundColor Blue
    Write-Host ("${padding}${Text}") -ForegroundColor Blue -NoNewline
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Blue
    Write-Host ""
}

function Write-Step {
    param(
        [int]$Step,
        [string]$Text
    )
    Write-Host "[Step $Step] " -ForegroundColor Green -NoNewline
    Write-Host $Text
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Error-Host {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Warning-Host {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PmovesDir = Join-Path $RepoRoot "pmoves"

# Check prerequisites
function Test-Prerequisites {
    Write-Step 1 "Checking prerequisites..."

    $allGood = $true

    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python installed: $pythonVersion"
        } else {
            Write-Error-Host "Python 3 not found"
            Write-Host "  Install Python 3.8+ from https://www.python.org/"
            $allGood = $false
        }
    } catch {
        Write-Error-Host "Python 3 not found"
        Write-Host "  Install Python 3.8+ from https://www.python.org/"
        $allGood = $false
    }

    # Check GitHub CLI
    try {
        $ghVersion = gh --version 2>&1 | Select-Object -First 1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "GitHub CLI installed: $ghVersion"
        } else {
            Write-Error-Host "GitHub CLI not found"
            Write-Host "  Install from https://cli.github.com/"
            $allGood = $false
        }
    } catch {
        Write-Error-Host "GitHub CLI not found"
        Write-Host "  Install from https://cli.github.com/"
        $allGood = $false
    }

    # Check GitHub CLI authentication
    try {
        $null = gh auth status 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "GitHub CLI authenticated"
        } else {
            Write-Error-Host "GitHub CLI not authenticated"
            Write-Host "  Run: gh auth login"
            $allGood = $false
        }
    } catch {
        Write-Error-Host "GitHub CLI not authenticated"
        Write-Host "  Run: gh auth login"
        $allGood = $false
    }

    if (-not $allGood) {
        Write-Host ""
        Write-Error-Host "Prerequisites not met. Please install missing dependencies."
        exit 1
    }

    Write-Host ""
}

# Verify GitHub Secrets
function Test-GitHubSecrets {
    Write-Step 2 "Verifying GitHub App credentials in GitHub Secrets..."

    $ghAppKeys = @('GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID')
    $foundCount = 0

    Write-Host "  Checking GitHub Secrets for POWERFULMOVES/PMOVES.AI:"
    foreach ($key in $ghAppKeys) {
        $result = gh secret list --repo POWERFULMOVES/PMOVES.AI | Select-String "^${key}"
        if ($result) {
            Write-Success "  ${key}: Found"
            $foundCount++
        } else {
            Write-Warning-Host "  ${key}: Not found"
        }
    }

    if ($foundCount -lt 4) {
        Write-Host ""
        Write-Error-Host "Only ${foundCount}/4 credentials found in GitHub Secrets"
        Write-Host ""
        Write-Host "  Missing credentials must be added to GitHub Secrets first:"
        Write-Host "  https://github.com/organizations/POWERFULMOVES/PMOVES.AI/settings/secrets/actions"
        Write-Host ""
        exit 1
    }

    Write-Host ""
}

# Run automated setup
function Invoke-AutomatedSetup {
    Write-Step 3 "Running automated GitHub App setup..."

    Push-Location $PmovesDir
    try {
        $result = python tools/github_app_auto_setup.py
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Automated setup completed"
        } else {
            Write-Error-Host "Automated setup failed"
            Write-Host ""
            Write-Host "  Try running manually:"
            Write-Host "  1. Edit pmoves\env.shared and uncomment GH_APP_* lines"
            Write-Host "  2. Run: cd pmoves; make secrets-funnel"
            Write-Host ""
            exit 1
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
}

# Verify setup
function Test-Setup {
    Write-Step 4 "Verifying GitHub App setup..."

    Push-Location $PmovesDir
    try {
        $result = python tools/verify_github_app_setup.py
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Setup verification passed"
        } else {
            Write-Warning-Host "Setup verification failed (this is OK on first run)"
            Write-Host "  You may need to restart services to pick up new credentials"
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
}

# Show next steps
function Show-NextSteps {
    Write-Header "Setup Complete! 🎉"

    Write-Host "GitHub App credentials are now configured."
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Start services:"
    Write-Host "     cd $PmovesDir"
    Write-Host "     docker compose up -d archon botz-gateway"
    Write-Host ""
    Write-Host "  2. Verify services are healthy:"
    Write-Host "     curl http://localhost:8091/healthz  # Archon"
    Write-Host "     curl http://localhost:8054/healthz  # BoTZ Gateway"
    Write-Host ""
    Write-Host "  3. Test token minting:"
    Write-Host "     cd $RepoRoot\PMOVES-BoTZ"
    Write-Host "     python features\github\mint_and_exec.py"
    Write-Host ""
    Write-Host "For troubleshooting, see:"
    Write-Host "  • Quick Start: pmoves\docs\GITHUB_APP_QUICK_START.md"
    Write-Host "  • Agent Docs: pmoves\docs\AGENTS\GITHUB_APP_CREDENTIALS.md"
    Write-Host ""
}

# Main execution
function Main {
    Write-Header "GitHub App First-Time Setup"

    Test-Prerequisites
    Test-GitHubSecrets
    Invoke-AutomatedSetup
    Test-Setup
    Show-NextSteps
}

# Run main function
Main
