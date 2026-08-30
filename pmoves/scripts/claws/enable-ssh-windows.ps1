# enable-ssh-windows.ps1 — Enable OpenSSH Server + inject authorized key on Windows
# Usage: .\enable-ssh-windows.ps1 [-PubKey "ssh-ed25519 AAAA..."]
#
# Run as Administrator on the target Windows machine.
# This script:
#   1. Installs OpenSSH Server if not present
#   2. Starts and enables the sshd service
#   3. Injects the provided public key into administrators_authorized_keys
#   4. Sets correct ACLs (Administrators + SYSTEM only)
#   5. Fixes user .ssh permissions if broken

param(
    [string]$PubKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILwNwCmQKDS3c6LuRRLKf60yQHfLyUINnU1Z1eTytcrf pmoves-claw@pmoves.ai"
)

$ErrorActionPreference = "Stop"

Write-Host "=== PMOVES SSH Setup for Windows ===" -ForegroundColor Cyan

# 1. Check/install OpenSSH Server
$sshCap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCap.State -ne 'Installed') {
    Write-Host "[1/5] Installing OpenSSH Server..."
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
} else {
    Write-Host "[1/5] OpenSSH Server already installed"
}

# 2. Start and enable sshd + ssh-agent
# Both services must have StartupType flipped BEFORE Start-Service. sshd's
# post-install default is Manual (Start-Service accepts that), but ssh-agent
# ships Disabled — Start-Service on a Disabled service throws and aborts the
# script under $ErrorActionPreference='Stop'. Always Set-Service first.
Write-Host "[2/5] Starting sshd + ssh-agent services..."
Set-Service -Name sshd -StartupType 'Automatic'
Start-Service sshd
Set-Service -Name ssh-agent -StartupType 'Automatic'
Start-Service ssh-agent
Write-Host "  sshd: Running (Automatic)"
Write-Host "  ssh-agent: Running (Automatic)"

# 3. Set default shell to PowerShell
Write-Host "[3/5] Setting default shell to PowerShell..."
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
    -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -PropertyType String -Force | Out-Null

# 4. Inject authorized key
Write-Host "[4/5] Injecting authorized key..."
$authKeysPath = "$env:ProgramData\ssh\administrators_authorized_keys"
New-Item -Path "$env:ProgramData\ssh" -ItemType Directory -Force | Out-Null
$existing = if (Test-Path $authKeysPath) { Get-Content $authKeysPath -Raw } else { "" }
# Dedup on the base64 key body (middle field of "type body comment") so any agent
# pubkey can be re-applied idempotently — not just the default pmoves-claw key.
$keyBody = ($PubKey -split '\s+')[1]
if (-not $keyBody) {
    throw "Invalid -PubKey: expected 'type body [comment]', got: $PubKey"
}
if ($existing -notmatch [regex]::Escape($keyBody)) {
    Add-Content -Path $authKeysPath -Value $PubKey
    Write-Host "  Appended new key (body=$($keyBody.Substring(0, [Math]::Min(20, $keyBody.Length)))...)"
} else {
    Write-Host "  Key already present (no-op)"
}
icacls $authKeysPath /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
Write-Host "  Key written to: $authKeysPath"

# 5. Fix user .ssh permissions
Write-Host "[5/5] Fixing user .ssh permissions..."
$userSsh = "$env:USERPROFILE\.ssh"
if (Test-Path $userSsh) {
    icacls $userSsh /grant "${env:USERNAME}:F" /T | Out-Null
    Write-Host "  Fixed: $userSsh"
} else {
    New-Item -ItemType Directory -Path $userSsh -Force | Out-Null
    Write-Host "  Created: $userSsh"
}

Write-Host ""
Write-Host "=== SSH Setup Complete ===" -ForegroundColor Green
Write-Host "Test from Z890: ssh -i /tmp/hostinger_vps Administrator@$(tailscale ip -4)"
Write-Host ""
