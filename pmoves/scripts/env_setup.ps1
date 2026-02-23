param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ForwardArgs
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($null -ne $python) {
  & py -3 tools/env_setup_unified.py @ForwardArgs
  exit $LASTEXITCODE
}

$python = (Get-Command python -ErrorAction SilentlyContinue)
if ($null -eq $python) {
  Write-Error "python is required to run env setup"
  exit 1
}

& python tools/env_setup_unified.py @ForwardArgs
exit $LASTEXITCODE
