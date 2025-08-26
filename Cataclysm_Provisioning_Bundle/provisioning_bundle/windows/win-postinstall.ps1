# windows/win-postinstall.ps1
# Run as Admin (FirstLogonCommands tries to auto-run this)
Write-Host "Starting Windows Post-Install..." -ForegroundColor Cyan

# Enable long paths & show file extensions
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideFileExt /t REG_DWORD /d 0 /f | Out-Null

# Install via winget
$apps = @(
  "Microsoft.VisualStudioCode",
  "Git.Git",
  "Python.Python.3.12",
  "OpenJS.NodeJS.LTS",
  "Docker.DockerDesktop",
  "Tailscale.Tailscale",
  "RustDesk.RustDesk",
  "7zip.7zip"
)
foreach ($app in $apps) {
  try { winget install -e --id $app --silent --accept-package-agreements --accept-source-agreements } catch {}
}

# Docker Desktop first-run tweaks
$settings = "$env:APPDATA\Docker\settings.json"
if (Test-Path $settings) {
  $json = Get-Content $settings | ConvertFrom-Json
  $json.autoStart = $true
  $json.wslEngineEnabled = $true
  $json | ConvertTo-Json -Depth 10 | Set-Content $settings -Encoding UTF8
}

Write-Host "Windows Post-Install complete. Reboot recommended." -ForegroundColor Green
