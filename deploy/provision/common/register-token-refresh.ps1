<#
.SYNOPSIS
  Register a host-side scheduled task that keeps env.shared GITHUB_PAT fresh (Windows / Z890).
.DESCRIPTION
  Runs `make -C pmoves gha-token-refresh` every N hours in the CURRENT USER
  context, so it inherits the gh CLI keyring. The make target is idempotent — it
  only rewrites env.shared when the stored GITHUB_PAT is actually stale (missing,
  drifted from the keyring, or failing a behavioral actions/runners check).

  This is the durable fix for the stale-env-token poison: without a periodic
  re-snapshot, the one-shot GITHUB_PAT in env.shared drifts from the keyring over
  time, and `gh` inside make recipes prefers the stale env value (which broke
  runner bootstrap for hours). See pmoves/tools/inject_github_pat_from_gh_cli.py.
.NOTES
  The gh keyring lives in the host USER profile, NOT the dockerized ai-lab runner
  — so this MUST run on the host, not as a GitHub Actions job on the container.
.EXAMPLE
  pwsh -File deploy/provision/common/register-token-refresh.ps1
  pwsh -File deploy/provision/common/register-token-refresh.ps1 -IntervalHours 4
#>
param(
  [string]$RepoDir = (Resolve-Path "$PSScriptRoot\..\..\..").Path,
  [int]$IntervalHours = 6,
  [string]$TaskName = "PMOVES-GHA-Token-Refresh"
)
$ErrorActionPreference = "Stop"

# Need a bash that can run the project Makefile (Git for Windows ships one).
$bash = (Get-Command bash -ErrorAction SilentlyContinue)
if (-not $bash) {
  throw "bash not found on PATH (install Git for Windows). Needed to run the project Makefile."
}

# Convert the Windows repo path to a bash path: D:\PMOVES.AI -> /d/PMOVES.AI
$drive   = $RepoDir.Substring(0,1).ToLower()
$rest    = $RepoDir.Substring(2) -replace '\\','/'
$bashRepo = "/$drive$rest"

$cmd = "cd '$bashRepo' && make -C pmoves gha-token-refresh >> .git/token-refresh.log 2>&1"
$action  = New-ScheduledTaskAction -Execute $bash.Source -Argument "-lc `"$cmd`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
            -RepetitionInterval (New-TimeSpan -Hours $IntervalHours)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Force -RunLevel Limited | Out-Null

Write-Host "OK Registered '$TaskName' - runs every $IntervalHours h as $env:USERNAME."
Write-Host "   Log:     $RepoDir\.git\token-refresh.log"
Write-Host "   Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "   Remove:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
