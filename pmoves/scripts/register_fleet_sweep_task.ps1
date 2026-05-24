# Registers the PMOVES Weekly Fleet Sweep as a Windows Scheduled Task.
# Run once, elevated. Bakes $Env:DISCORD_WEBHOOK_URL into a per-task wrapper
# outside the repo tree so the task is independent of the registering shell's env after the fact.

Param(
  [string]$TaskName = "PMOVES Weekly Fleet Sweep",
  [string]$RunAt    = "09:30",   # local time, weekly on Monday
  [string]$RepoRoot = "D:\PMOVES.AI\PMOVES.AI",
  [int]$StaleDays   = 60,
  [string]$TaskRoot = "$Env:ProgramData\PMOVES\tasks"
)

$ErrorActionPreference = 'Stop'

if (-not $Env:DISCORD_WEBHOOK_URL) {
  Write-Error "Set `$Env:DISCORD_WEBHOOK_URL in this shell before running register_fleet_sweep_task.ps1"
  exit 1
}

$wrapperDir  = $TaskRoot
$wrapperPath = Join-Path $wrapperDir "fleet_stale_node_sweep_wrapper.ps1"
$sweepPath   = Join-Path $RepoRoot "pmoves\scripts\fleet_stale_node_sweep.ps1"

New-Item -ItemType Directory -Force -Path $wrapperDir | Out-Null

@"
`$Env:DISCORD_WEBHOOK_URL = '$Env:DISCORD_WEBHOOK_URL'
& '$sweepPath' -StaleDays $StaleDays
"@ | Set-Content -Path $wrapperPath -Encoding UTF8

$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $RunAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $Env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Host "Registered '$TaskName' -- runs every Monday at $RunAt (stale-threshold $StaleDays days)."
Write-Host "Wrapper: $wrapperPath"
Write-Host "Test now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Dry run: powershell -File `"$sweepPath`" -DryRun"
