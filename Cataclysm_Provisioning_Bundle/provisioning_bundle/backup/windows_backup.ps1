# backup/windows_backup.ps1
# Requires restic (winget install restic.restic). Adjust repo/password.
$env:RESTIC_REPOSITORY="D:\restic-repo"
$env:RESTIC_PASSWORD="ChangeThisPassword"
restic init --repo $env:RESTIC_REPOSITORY
restic backup --verbose C:\Users\%USERNAME%\Documents C:\Users\%USERNAME%\Pictures C:\Projects
restic snapshots
