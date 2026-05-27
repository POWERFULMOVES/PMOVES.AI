# Registers the PMOVES Daily Digest as a Windows Scheduled Task.
# Run once, elevated. Reads DISCORD_WEBHOOK_URL from the current shell env at registration time
# and bakes it into a per-task wrapper outside the repo tree, so the task survives reboots.

Param(
  [string]$TaskName = "PMOVES Daily Digest",
  [string]$RunAt    = "08:15",   # local time, daily
  [string]$RepoRoot = "D:\PMOVES.AI\PMOVES.AI",
  [string]$TaskRoot = "$Env:ProgramData\PMOVES\tasks"
)

$ErrorActionPreference = 'Stop'

if (-not $Env:DISCORD_WEBHOOK_URL) {
  Write-Error "Set `$Env:DISCORD_WEBHOOK_URL in this shell before running register_daily_digest_task.ps1"
  exit 1
}

$wrapperDir  = $TaskRoot
$wrapperPath = Join-Path $wrapperDir "daily_pmoves_digest_wrapper.ps1"
$digestPath  = Join-Path $RepoRoot "pmoves\scripts\daily_pmoves_digest.ps1"

New-Item -ItemType Directory -Force -Path $wrapperDir | Out-Null

# Wrapper bakes the webhook outside the working tree so Task Scheduler doesn't need env inheritance.
@"
`$Env:DISCORD_WEBHOOK_URL = '$Env:DISCORD_WEBHOOK_URL'
& '$digestPath'
"@ | Set-Content -Path $wrapperPath -Encoding UTF8

# Restrict wrapper to current user only — it contains a plaintext webhook secret.
$acl = Get-Acl $wrapperPath
$acl.SetAccessRuleProtection($true, $false)
$rule = [System.Security.AccessControl.FileSystemAccessRule]::new($Env:USERNAME, "FullControl", "Allow")
$acl.SetAccessRule($rule)
Set-Acl -Path $wrapperPath -AclObject $acl

$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $Env:USERNAME -LogonType Interactive -RunLevel Limited

# Unregister-then-register so re-runs of this script update cleanly.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Write-Host "Registered '$TaskName' — runs daily at $RunAt."
Write-Host "Wrapper: $wrapperPath"
Write-Host "Test now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Dry run: powershell -File `"$digestPath`" -DryRun"
