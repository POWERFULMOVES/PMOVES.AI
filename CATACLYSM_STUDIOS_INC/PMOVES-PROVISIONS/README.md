
# Cataclysm Provisioning Bundle

This bundle lets you mass-deploy your homelab and workstations **in parallel** with Ventoy USB sticks:
- Unattended Windows 11 installs (with auto post-install script)
- Ubuntu autoinstall (cloud-init) for server/VMs
- Proxmox VE 9 post-install script (for hosts installed via ISO or Debian 13)
- Jetson Orin Nano bootstrap (Docker/NVIDIA runtime + jetson-containers)
- Ready-to-run Docker Compose stacks (Portainer, NPM, Cloudflared, Netdata, Ollama)

> Put this entire folder onto the **2nd partition** on your Ventoy USB (exFAT is fine).  
> Your ISOs go under `isos/`. The `ventoy/ventoy.json` already maps common ISOs to the right templates.

## Quick Start
1. **Ventoy USBs**: create multiple sticks. Copy this bundle to each one. Copy your ISO files into `isos/`.
2. **Windows**: pick your Win11 ISO in Ventoy. If prompted, select the **Autounattend** template. First login runs `windows/win-postinstall.ps1` from the USB automatically.
3. **Ubuntu**: pick the Ubuntu Server ISO. The autoinstall will use `linux/ubuntu-autoinstall/user-data` and set up Docker + Tailscale.
4. **Proxmox VE 9**: Install from ISO normally, then run `proxmox/pve9_postinstall.sh` to finish. Alternatively, install Debian 13 (autoinstall), then run `proxmox/pve_on_debian13.sh` to convert to PVE 9.
5. **Jetson**: Flash JetPack as usual. Then run `jetson/jetson-postinstall.sh` on first boot. Use `jetson/ngc_login.sh` to authenticate to NGC, and `jetson/pull_and_save.sh` to pre-pull/save containers.
6. **Stacks**: On your main host/VM, `docker compose -f docker-stacks/portainer.yml up -d`, then deploy the rest from Portainer.

## Secrets
- Replace placeholders like `YOUR_TUNNEL_TOKEN_HERE` and fill `tailscale/tailscale_up.sh` with your Tailnet preferences.
- For NVIDIA NGC, run `jetson/ngc_login.sh` (or do `docker login nvcr.io`) with your API key.

## Notes
- Ventoy mapping lives in `ventoy/ventoy.json`—edit the `"image"` paths to match your ISO filenames.
- If Windows doesn't auto-run the post-install script, open the USB and run `windows/win-postinstall.ps1` as admin.

# Cataclysm Provisioning Bundle

This bundle lets you mass-deploy your homelab and workstations **in parallel** with Ventoy USB sticks:
- Unattended Windows 11 installs (with auto post-install script)
- Ubuntu autoinstall (cloud-init) for server/VMs
- Proxmox VE 9 post-install script (for hosts installed via ISO or Debian 13)
- Jetson Orin Nano bootstrap (Docker/NVIDIA runtime + jetson-containers)
- Ready-to-run Docker Compose stacks (Portainer, NPM, Cloudflared, Netdata, Ollama)

> Put this entire folder onto the **2nd partition** on your Ventoy USB (exFAT is fine).  
> Your ISOs go under `isos/`. The `ventoy/ventoy.json` already maps common ISOs to the right templates.

## Quick Start

1. **Ventoy USBs**: create multiple sticks. Copy this bundle to each one. Copy your ISO files into `isos/`.
2. **Windows**: pick your Win11 ISO in Ventoy. If prompted, select the **Autounattend** template. First login runs `windows/win-postinstall.ps1` from the USB automatically. The script now:
   - Prompts for a workspace (defaults to `%USERPROFILE%\workspace`) and clones/updates `PMOVES.AI` there.
   - Installs PMOVES dependencies via `pmoves/scripts/install_all_requirements.ps1`, seeds `.env` files, and optionally starts Docker Desktop.
   - Offers to enable WSL with Ubuntu if it is missing (expect Windows to request a reboot and the Ubuntu username/password prompts on first launch).
   - Applies Tailnet + RustDesk settings from the provisioning media when present so the host can connect to remote control channels immediately.

1. **Ventoy USBs**: create multiple sticks. Copy this bundle to each one. Copy your ISO files into `isos/`.

2. **Windows**: pick your Win11 ISO in Ventoy. If prompted, select the **Autounattend** template. First login runs `windows/win-postinstall.ps1` from the USB automatically. When the Tailnet helper or config is present under `tailscale/`, the script executes it after Winget finishes so the machine joins your Tailnet right away.
3. **Ubuntu**: pick the Ubuntu Server ISO. The autoinstall will use `linux/ubuntu-autoinstall/user-data` and set up Docker + Tailscale.

2. **Windows**: pick your Win11 ISO in Ventoy. If prompted, select the **Autounattend** template. First login runs `windows/win-postinstall.ps1` from the USB automatically. If `tailscale/tailscale_up.ps1` is present, the post-install will also join the host to your Tailnet right away.

3. **Ubuntu**: pick the Ubuntu Server ISO. The autoinstall will use `linux/ubuntu-autoinstall/user-data`, set up Docker + Tailscale, copy `tailscale/tailscale_up.sh` into `/usr/local/bin`, and run it so the host joins your Tailnet right away (using the same flags as the manual helper script).

4. **Proxmox VE 9**: Install from ISO normally, then run `proxmox/pve9_postinstall.sh` to finish. Alternatively, install Debian 13 (autoinstall), then run `proxmox/pve_on_debian13.sh` to convert to PVE 9.
5. **Jetson**: Flash JetPack as usual. Then run `jetson/jetson-postinstall.sh` on first boot. Use `jetson/ngc_login.sh` to authenticate to NGC, and `jetson/pull_and_save.sh` to pre-pull/save containers.
6. **Stacks**: On your main host/VM, `docker compose -f docker-stacks/portainer.yml up -d`, then deploy the rest from Portainer.


## Secrets
- Replace placeholders like `YOUR_TUNNEL_TOKEN_HERE` and fill both `tailscale/tailscale_up.sh` (Linux) and `tailscale/tailscale_up.ps1` (Windows) with your Tailnet preferences.
- Store the Windows Tailnet auth key in `tailscale/tailscale_authkey.txt` (never commit this file) or set a `TAILSCALE_AUTHKEY` environment variable before running `tailscale/tailscale_up.ps1`. The helper reads the environment variable first, then falls back to the adjacent secret file, and finally calls `tailscale.exe up --ssh --accept-routes --advertise-tags=tag:lab`.
- Keep the secret file on the Ventoy USB alongside the provisioning bundle so post-install can discover it automatically. To rotate the auth key, revoke the old key in the Tailscale admin console, generate a new reusable key, and update the `tailscale_authkey.txt` file (and any secure secret store) before imaging fresh machines.


## Windows Post-Install Workflow
`windows/win-postinstall.ps1` is the central bootstrapper once Windows finishes the unattended install:

1. **Workspace prompt** — Choose where to clone `PMOVES.AI` (default `%USERPROFILE%\workspace\PMOVES.AI`).
2. **Dependency install** — The script invokes `pmoves/scripts/install_all_requirements.ps1` so Python packages for every service are ready. It also copies `.env.example` → `.env` and `.env.local.example` → `.env.local` if they are missing.
3. **WSL offer** — You are prompted to enable WSL and install Ubuntu. Accepting runs `wsl --install -d Ubuntu`; Windows may request a restart and Ubuntu will prompt for a UNIX username/password on first launch.
4. **Docker Desktop launch** — Accepting the prompt starts Docker Desktop so it can finish the first-run setup (required before `docker compose` commands succeed).
5. **Tailnet/RustDesk hooks** — If you provided Tailnet or RustDesk secrets on the USB bundle (see below), the script applies them automatically and confirms success in the console output.

## Regular PMOVES Install (Pop!_OS / Ubuntu Desktop)

Run `linux/scripts/pop-postinstall.sh` on a fresh Pop!_OS/Ubuntu desktop to provision a ready-to-develop workstation:

1. **Prepare the bundle**: Copy this provisioning folder to your media (Ventoy USB, external disk, etc.). Drop a Tailnet auth key in `tailscale/tailscale_authkey.txt` (first line only) so the helper can run `tailscale up` without prompts.
2. **Execute the script**: From the copied bundle, run `sudo bash linux/scripts/pop-postinstall.sh` (defaults to `--mode full`). The script:
   - Upgrades the OS, installs Docker + NVIDIA container toolkit, and adds RustDesk via the upstream apt repository.
   - Installs Python tooling (`python3`, `pip`, `venv`) required for the PMOVES stack.
   - Sources `tailscale/tailscale_up.sh`, using the colocated auth key (or `$TAILSCALE_AUTHKEY`) to join the Tailnet non-interactively.
   - Clones or refreshes the `PMOVES.AI` repo into `/opt/pmoves` (override with `PMOVES_INSTALL_DIR=/some/path` or change the repo URL via `PMOVES_REPO_URL=`).
   - Copies `.env` templates (`.env.example`, `.env.local.example`, `.env.supa.*.example`) into live `.env` files if they do not exist yet.
   - Runs `pmoves/scripts/install_all_requirements.sh` so every service dependency is installed on first boot.
   - Symlinks the `docker-stacks/` bundle into the install directory for quick compose access.
3. **Post-install secrets**: Replace the placeholder values in `/opt/pmoves/pmoves/.env`, `.env.local`, and Supabase `.env` files with real credentials/API keys. The defaults mirror the compose stack but should be rotated for production use.
4. **RustDesk pairing**: Once the script completes, RustDesk is installed and ready to be paired using your preferred relay/ID server.


Use the `--mode` flag (or export `MODE=<standalone|web|full>` before running the script) to tailor what gets installed. The list above describes the default `full` mode.

### Mode matrix

| Platform | Mode | Command | Key installs/actions | Tailnet join behavior |
| --- | --- | --- | --- | --- |
| Pop!_OS / Ubuntu | `standalone` | `MODE=standalone sudo bash linux/scripts/pop-postinstall.sh` | System updates, Git/cURL basics, Tailscale CLI, RustDesk desktop client | Sources `tailscale/tailscale_up.sh` when present (or logs instructions) |
| Pop!_OS / Ubuntu | `web` | `sudo bash linux/scripts/pop-postinstall.sh --mode web` | Adds Docker Engine + NVIDIA toolkit, clones PMOVES repo, seeds `.env` templates, links `docker-stacks/` (no Python dependency install) | Same helper-driven `tailscale up` flow |
| Pop!_OS / Ubuntu | `full` | `sudo bash linux/scripts/pop-postinstall.sh --mode full` | Everything in web mode plus RustDesk install and `pmoves/scripts/install_all_requirements.sh` for Python services | Same helper-driven `tailscale up` flow |
| Windows 11 | `standalone` | `powershell -ExecutionPolicy Bypass -File windows\win-postinstall.ps1 -Mode standalone` | Winget installs Tailscale + RustDesk, explorer defaults | Runs `tailscale/tailscale_up.ps1` when available or uses the bundled auth key fallback |
| Windows 11 | `web` | `powershell -ExecutionPolicy Bypass -File windows\win-postinstall.ps1 -Mode web` | Installs VS Code, Git, Node.js LTS, Docker Desktop, Tailscale, RustDesk; clones PMOVES into `%USERPROFILE%\workspace\PMOVES.AI` and seeds `.env` files | Same helper script / auth key flow |
| Windows 11 | `full` | `powershell -ExecutionPolicy Bypass -File windows\win-postinstall.ps1 -Mode full` | Web mode installs plus Python 3.12, prompts for workspace, runs `pmoves/scripts/install_all_requirements.ps1`, optional WSL Ubuntu enablement | Same helper script / auth key flow |
| Jetson (JetPack) | `standalone` | `MODE=standalone sudo bash jetson/jetson-postinstall.sh` | System updates, Git/cURL basics, Tailscale CLI, RustDesk | Uses `tailscale/tailscale_up.sh` helper when present |
| Jetson (JetPack) | `web` | `sudo bash jetson/jetson-postinstall.sh --mode web` | Installs Docker + NVIDIA runtime config, clones PMOVES repo, seeds `.env`, links `docker-stacks/` | Same helper-driven `tailscale up` flow |
| Jetson (JetPack) | `full` | `sudo bash jetson/jetson-postinstall.sh --mode full` | Web mode tasks plus RustDesk install, Python dependency bootstrap, and `jetson-containers` checkout/install | Same helper-driven `tailscale up` flow |


## Secrets
- Replace placeholders like `YOUR_TUNNEL_TOKEN_HERE` and fill both `tailscale/tailscale_up.sh` (Linux) and `tailscale/tailscale_up.ps1` (Windows) with your Tailnet preferences. Keep them on the Ventoy USB only for as long as necessary.
- Tailnet auth options:
  - Store the auth key in `tailscale/tailscale_authkey.txt` (ignored by Git) and the scripts will read the first line.
  - Or set `TAILSCALE_AUTHKEY` in the environment before invoking the helper scripts.
- RustDesk relay/ID configuration:
  - Export `server.conf` from an existing RustDesk install **or** craft one manually, then place it beside this bundle at `windows/rustdesk/server.conf`.
  - During post-install the script copies it into `%AppData%\RustDesk\config\RustDesk2\RustDesk\config\server.conf` for the signed-in user.
  - Remove `server.conf` from the USB after imaging so the secrets do not persist on portable media.
  - See [docs/rustdesk-self-hosted.md](docs/rustdesk-self-hosted.md) for self-hosted server setup, key rotation, and exporting `server.conf` for provisioning.
- For unattended runs, leave the auth key file on the Ventoy USB only as long as needed. The Ubuntu autoinstall reads the first line, exports it for the one-time `tailscale up`, and does not persist the secret on disk. Remove the key from the USB (or rotate it) once provisioning is complete.

- For NVIDIA NGC, run `jetson/ngc_login.sh` (or do `docker login nvcr.io`) with your API key.

## Notes
- Ventoy mapping lives in `ventoy/ventoy.json`—edit the `"image"` paths to match your ISO filenames.

- If Windows doesn't auto-run the post-install script, open the USB and run `windows/win-postinstall.ps1` as admin.
- On staged builds, confirm the machine appears in the Tailnet admin console with the expected tags right after post-install. The Windows helper surfaces errors in the console if joining fails so you can rerun it after fixing the key or network access.

- If Windows doesn't auto-run the post-install script, open the USB and run `windows/win-postinstall.ps1` as admin.
- On staged builds, confirm the machine appears in the Tailnet admin console with the expected tags right after post-install.


