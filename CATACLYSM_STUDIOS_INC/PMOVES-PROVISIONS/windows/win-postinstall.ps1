param(
  [string]$Mode
)

if (-not $Mode -or [string]::IsNullOrWhiteSpace($Mode)) {
  $Mode = $env:MODE
}
if (-not $Mode -or [string]::IsNullOrWhiteSpace($Mode)) {
  $Mode = 'full'
}
$Mode = $Mode.Trim().ToLowerInvariant()

$validModes = @('standalone', 'web', 'full')
if ($validModes -notcontains $Mode) {
  Write-Error "Invalid mode '$Mode'. Valid options: standalone, web, full."
  exit 1
}

Write-Host "Starting Windows Post-Install ($Mode mode)..." -ForegroundColor Cyan

$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath
$bundleRoot = Split-Path -Parent $scriptDir
$repoUrl = "https://github.com/CataclysmStudiosInc/PMOVES.AI.git"

function Set-SystemDefaults {
  Write-Host "Configuring Explorer defaults..." -ForegroundColor Cyan
  reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f | Out-Null
  reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideFileExt /t REG_DWORD /d 0 /f | Out-Null
}

function Invoke-WingetInstall {
  param([string]$Id)
  try {
    winget install -e --id $Id --silent --accept-package-agreements --accept-source-agreements
  }
  catch {
    Write-Warning "winget install failed for $Id: $($_.Exception.Message)"
  }
}

function Get-WingetAppsForMode {
  param([string]$CurrentMode)
  switch ($CurrentMode) {
    'standalone' { return @('Tailscale.Tailscale', 'RustDesk.RustDesk') }
    'web' { return @('Microsoft.VisualStudioCode', 'Git.Git', 'OpenJS.NodeJS.LTS', 'Docker.DockerDesktop', 'Tailscale.Tailscale', 'RustDesk.RustDesk', '7zip.7zip') }
    default { return @('Microsoft.VisualStudioCode', 'Git.Git', 'Python.Python.3.12', 'OpenJS.NodeJS.LTS', 'Docker.DockerDesktop', 'Tailscale.Tailscale', 'RustDesk.RustDesk', '7zip.7zip') }
  }
}

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    Write-Host "Creating $Path" -ForegroundColor Yellow
    [System.IO.Directory]::CreateDirectory($Path) | Out-Null
  }
}

function Add-ToPath {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  if (-not (Test-Path $Path)) { return }

  $segments = $env:PATH -split ';'
  $alreadyPresent = $segments | Where-Object { $_.Trim().ToLowerInvariant() -eq $Path.Trim().ToLowerInvariant() }
  if (-not $alreadyPresent) {
    $env:PATH = "$Path;$env:PATH"
  }
}

function Refresh-PathForWingetInstalls {
  Write-Host "Refreshing PATH for newly installed tools..." -ForegroundColor Cyan

  $gitRoot = Join-Path $env:ProgramFiles 'Git'
  if (Test-Path $gitRoot) {
    Add-ToPath -Path (Join-Path $gitRoot 'cmd')
    Add-ToPath -Path (Join-Path $gitRoot 'bin')
  }

  $pythonRoots = @(
    Join-Path $env:LOCALAPPDATA 'Programs\Python',
    Join-Path $env:ProgramFiles 'Python'
  )
  foreach ($root in $pythonRoots) {
    if (-not (Test-Path $root)) { continue }
    $latestPython = Get-ChildItem -Path $root -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestPython) {
      Add-ToPath -Path $latestPython.FullName
      Add-ToPath -Path (Join-Path $latestPython.FullName 'Scripts')
      break
    }
  }

  $nodeDir = Join-Path $env:ProgramFiles 'nodejs'
  if (Test-Path $nodeDir) {
    Add-ToPath -Path $nodeDir
  }
}

function Update-PmovesRepository {
  param(
    [string]$RepoPath,
    [string]$Url
  )

  if (-not (Test-Path $RepoPath)) {
    Write-Host "Cloning PMOVES into $RepoPath" -ForegroundColor Cyan
    git clone $Url $RepoPath
  }
  else {
    Write-Host "Updating PMOVES repo in $RepoPath" -ForegroundColor Cyan
    Push-Location $RepoPath
    try {
      git fetch --all
      git pull --ff-only
    }
    finally {
      Pop-Location
    }
  }
}

function Seed-PmovesEnvFiles {
  param([string]$RepoPath)

  $envExample = Join-Path $RepoPath 'pmoves/.env.example'
  $envFile = Join-Path $RepoPath 'pmoves/.env'
  if ((Test-Path $envExample) -and -not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Seeded pmoves/.env from .env.example" -ForegroundColor Green
  }

  $envLocalExample = Join-Path $RepoPath 'pmoves/.env.local.example'
  $envLocal = Join-Path $RepoPath 'pmoves/.env.local'
  if ((Test-Path $envLocalExample) -and -not (Test-Path $envLocal)) {
    Copy-Item $envLocalExample $envLocal
    Write-Host "Seeded pmoves/.env.local from template" -ForegroundColor Green
  }
}

function Install-PmovesDependencies {
  param([string]$RepoPath)

  $installScript = Join-Path $RepoPath 'pmoves/scripts/install_all_requirements.ps1'
  if (-not (Test-Path $installScript)) {
    Write-Warning "Could not locate pmoves/scripts/install_all_requirements.ps1"
    return
  }

  Write-Host "Installing PMOVES dependencies..." -ForegroundColor Cyan
  try {
    $currentPolicy = Get-ExecutionPolicy -Scope Process
    if ($currentPolicy -ne 'Bypass') {
      try { Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force } catch {}
    }
    Push-Location $RepoPath
    try {
      & $installScript
    }
    finally {
      Pop-Location
    }
  }
  catch {
    Write-Warning "Dependency installation failed: $($_.Exception.Message)"
  }
}

function Prompt-YesNo {
  param(
    [string]$Message,
    [switch]$DefaultYes
  )

  $suffix = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
  $answer = Read-Host "$Message $suffix"
  if ([string]::IsNullOrWhiteSpace($answer)) {
    return [bool]$DefaultYes
  }
  return $answer.Trim().ToLowerInvariant().StartsWith('y')
}

function Install-WslUbuntu {
  Write-Host "Checking for existing WSL distributions..." -ForegroundColor Cyan
  $hasUbuntu = $false
  try {
    $list = wsl.exe -l -q 2>$null
    if ($LASTEXITCODE -eq 0 -and $list) {
      $hasUbuntu = (($list -split "`n") | Where-Object { $_.Trim().ToLowerInvariant() -eq 'ubuntu' }).Count -gt 0
    }
  } catch {}

  if ($hasUbuntu) {
    Write-Host "Ubuntu distribution already registered with WSL." -ForegroundColor Green
    return
  }

  Write-Host "Installing WSL with Ubuntu (this may request a reboot)..." -ForegroundColor Yellow
  try {
    wsl.exe --install -d Ubuntu
  }
  catch {
    Write-Warning "WSL installation failed: $($_.Exception.Message)"
  }
}

function Configure-DockerDesktopSettings {
  $settings = "$env:APPDATA\Docker\settings.json"
  if (Test-Path $settings) {
    $json = Get-Content $settings | ConvertFrom-Json
    $json.autoStart = $true
    $json.wslEngineEnabled = $true
    $json | ConvertTo-Json -Depth 10 | Set-Content $settings -Encoding UTF8
  }
}

function Apply-RustDeskBundle {
  $rustdeskConfig = Join-Path $bundleRoot 'windows/rustdesk/server.conf'
  if (Test-Path $rustdeskConfig) {
    $rustdeskTarget = Join-Path $env:APPDATA 'RustDesk/config/RustDesk2/RustDesk/config'
    Ensure-Directory -Path $rustdeskTarget
    Copy-Item $rustdeskConfig (Join-Path $rustdeskTarget 'server.conf') -Force
    Write-Host "RustDesk server.conf copied into AppData." -ForegroundColor Green
  }
}

function Launch-DockerDesktopPrompt {
  if (-not (Prompt-YesNo -Message "Launch Docker Desktop now" -DefaultYes)) { return }
  $dockerExe = "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
  if (Test-Path $dockerExe) {
    Start-Process -FilePath $dockerExe
  } else {
    Write-Warning "Docker Desktop executable not found at $dockerExe"
  }
}

function Join-Tailnet {
  $tailscaleScript = Join-Path $bundleRoot 'tailscale/tailscale_up.ps1'
  $tailscaleAuthFile = Join-Path $bundleRoot 'tailscale/tailscale_authkey.txt'

  if (Test-Path $tailscaleScript) {
    Write-Host "Running Tailnet bootstrap script..." -ForegroundColor Cyan
    try {
      & $tailscaleScript
    }
    catch {
      Write-Warning "Tailnet bootstrap failed: $($_.Exception.Message)"
    }
    return
  }

  if (-not (Test-Path $tailscaleAuthFile)) {
    Write-Host "Tailnet helper not found; skipping automatic join." -ForegroundColor Yellow
    return
  }

  Write-Host "Joining Tailnet with default flags..." -ForegroundColor Cyan
  try {
    $authKey = (Get-Content $tailscaleAuthFile -ErrorAction Stop | Select-Object -First 1).Trim()
    if ([string]::IsNullOrWhiteSpace($authKey)) {
      Write-Warning 'tailscale_authkey.txt is present but empty. Skipping Tailnet join.'
      return
    }
    $tailscaleArgs = @('--ssh', '--accept-routes', '--advertise-tags=tag:lab', "--authkey=$authKey")
    tailscale.exe up @tailscaleArgs
    if ($LASTEXITCODE -ne 0) {
      throw "tailscale.exe exited with code $LASTEXITCODE"
    }
    Write-Host 'Tailnet join command completed.' -ForegroundColor Green
  }
  catch {
    Write-Warning "Tailnet bootstrap failed: $($_.Exception.Message)"
  }
}

Set-SystemDefaults

$apps = Get-WingetAppsForMode -CurrentMode $Mode
foreach ($app in $apps) {
  Invoke-WingetInstall -Id $app
}
if ($Mode -ne 'standalone') {
  Refresh-PathForWingetInstalls
}

if ($Mode -ne 'standalone') {
  Configure-DockerDesktopSettings
}

$repoPath = $null
if ($Mode -eq 'full' -or $Mode -eq 'web') {
  $defaultWorkspace = Join-Path $env:USERPROFILE 'workspace'
  if (-not (Test-Path $defaultWorkspace)) { $defaultWorkspace = $env:USERPROFILE }

  if ($Mode -eq 'full') {
    $chosen = Read-Host "Directory to store PMOVES.AI repo`n(leave blank for $defaultWorkspace)"
    $workspace = if ([string]::IsNullOrWhiteSpace($chosen)) { $defaultWorkspace } else { $chosen.Trim() }
  }
  else {
    $workspace = $defaultWorkspace
    Write-Host "Using default workspace path: $workspace" -ForegroundColor Cyan
  }

  Ensure-Directory -Path $workspace
  $repoPath = Join-Path $workspace 'PMOVES.AI'
  Update-PmovesRepository -RepoPath $repoPath -Url $repoUrl
  Seed-PmovesEnvFiles -RepoPath $repoPath

  if ($Mode -eq 'full') {
    Install-PmovesDependencies -RepoPath $repoPath
  }
}

if ($Mode -eq 'full') {
  if (Prompt-YesNo -Message "Enable WSL and install Ubuntu" -DefaultYes) {
    Install-WslUbuntu
  }
}

Apply-RustDeskBundle

if ($Mode -ne 'standalone') {
  Launch-DockerDesktopPrompt
}

Join-Tailnet

Write-Host "Windows Post-Install complete. Reboot recommended." -ForegroundColor Green
