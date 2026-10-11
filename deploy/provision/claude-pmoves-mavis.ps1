# claude-pmoves-mavis.ps1 -- thin PowerShell twin of claude-pmoves-mavis.sh.
# See claude-pmoves-mavis.sh for the WHY (separate-run-name opt-in for the
# Mavis/MiniMax SDK overlay; default launcher stays clean Claude Code).
#
# Usage: powershell -ExecutionPolicy Bypass -File deploy\provision\claude-pmoves-mavis.ps1 [args]
#   (or double-click / run claude-pmoves-mavis.cmd, which calls this)

$ErrorActionPreference = 'Stop'
$SELF_DIR = Split-Path -Parent $PSCommandPath
$MAIN = Join-Path $SELF_DIR 'claude-pmoves.ps1'

if (-not (Test-Path $MAIN)) {
  Write-Host "[claude-pmoves-mavis] ERROR: main launcher not found: $MAIN" -ForegroundColor Red
  exit 1
}

# Pin the backend unless operator-set. (Inherited $env:PMOVES_CLAUDE_BACKEND wins.)
if (-not $env:PMOVES_CLAUDE_BACKEND) {
  $env:PMOVES_CLAUDE_BACKEND = 'minimax'
}

Write-Host "[claude-pmoves-mavis] launching with --backend=$($env:PMOVES_CLAUDE_BACKEND)" -ForegroundColor Cyan
& $MAIN --backend=$env:PMOVES_CLAUDE_BACKEND @args
exit $LASTEXITCODE