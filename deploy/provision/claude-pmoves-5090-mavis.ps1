# claude-pmoves-5090-mavis.ps1 -- 5090 identity pin + Mavis overlay (PowerShell).
# See claude-pmoves-5090-mavis.sh for the WHY.

$ErrorActionPreference = 'Stop'
$env:PMOVES_NODE_ID = '5090'
$wrapper = Join-Path (Split-Path -Parent $PSCommandPath) 'claude-pmoves-mavis.ps1'
& $wrapper @args
exit $LASTEXITCODE