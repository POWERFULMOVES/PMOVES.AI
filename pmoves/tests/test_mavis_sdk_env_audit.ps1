# Behavioural check for the PowerShell twin's audit-log append.
#
# Invoked by pmoves/tests/test_mavis_sdk_env.py under whichever PowerShell is on
# PATH (Windows PowerShell 5.1 and/or pwsh 7). The caller sets
# PMOVES_MAVIS_SDK_LOG_PATH to a file inside a directory that does NOT exist
# yet. The helper must create the parent and append exactly one JSONL line.
#
# Exit 0 only when the file exists afterwards and holds a line. Stream 3
# (Write-Warning) is left visible on purpose: the helper's best-effort catch
# reports there, and that is the first thing to read when this fails.
$ErrorActionPreference = 'Continue'
if (-not $env:PMOVES_MAVIS_SDK_LOG_PATH) {
    Write-Output 'PMOVES_MAVIS_SDK_LOG_PATH must be set by the caller'
    exit 2
}
. ./pmoves/scripts/mavis_sdk_env.ps1
# Seed one strip candidate so the call has something to strip and log.
$env:ANTHROPIC_MODEL = 'twin-audit-test'
Strip-MavisSdkEnvFor -CliName twin-audit-test
$p = $env:PMOVES_MAVIS_SDK_LOG_PATH
if (-not (Test-Path $p)) {
    Write-Output ("AUDIT LOG MISSING (PS {0}): {1}" -f $PSVersionTable.PSVersion, $p)
    exit 1
}
$lines = @(Get-Content $p)
if ($lines.Count -lt 1) {
    Write-Output ("AUDIT LOG EMPTY (PS {0})" -f $PSVersionTable.PSVersion)
    exit 1
}
Write-Output $lines[-1]
exit 0
