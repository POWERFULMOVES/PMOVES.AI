@echo off
:: One-click wrapper: install OpenSSH Server and inject the PMOVES agent key.
:: Double-click this file. Click "Yes" on the popup. Wait for the "Done" message.
:: Output saved to %TEMP%\pmoves-enable-ssh-windows.log
@call "%~dp0_elevate.cmd" enable-ssh-windows.ps1 %*
