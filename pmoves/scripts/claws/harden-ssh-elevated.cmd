@echo off
:: One-click wrapper: harden sshd_config (disable password auth, etc.).
:: ONLY run this after enable-ssh-elevated.cmd has been used to install at
:: least one SSH key. Hardening removes the password fallback — if no keys
:: are present, the harden script's own pre-flight will refuse.
::
:: Double-click this file. Click "Yes" on the popup. Wait for the "Done" message.
:: Output saved to %TEMP%\pmoves-harden-ssh-windows.log
@call "%~dp0_elevate.cmd" harden-ssh-windows.ps1 %*
