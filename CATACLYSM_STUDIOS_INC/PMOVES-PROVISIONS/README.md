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
2. **Windows**: pick your Win11 ISO in Ventoy. If prompted, select the **Autounattend** template. First login runs `windows/win-postinstall.ps1` from the USB automatically. If `tailscale/tailscale_up.ps1` is present, the post-install will also join the host to your Tailnet right away.
3. **Ubuntu**: pick the Ubuntu Server ISO. The autoinstall will use `linux/ubuntu-autoinstall/user-data`, set up Docker + Tailscale, copy `tailscale/tailscale_up.sh` into `/usr/local/bin`, and run it so the host joins your Tailnet right away (using the same flags as the manual helper script).
4. **Proxmox VE 9**: Install from ISO normally, then run `proxmox/pve9_postinstall.sh` to finish. Alternatively, install Debian 13 (autoinstall), then run `proxmox/pve_on_debian13.sh` to convert to PVE 9.
5. **Jetson**: Flash JetPack as usual. Then run `jetson/jetson-postinstall.sh` on first boot. Use `jetson/ngc_login.sh` to authenticate to NGC, and `jetson/pull_and_save.sh` to pre-pull/save containers.
6. **Stacks**: On your main host/VM, `docker compose -f docker-stacks/portainer.yml up -d`, then deploy the rest from Portainer.

## Secrets
- Replace placeholders like `YOUR_TUNNEL_TOKEN_HERE` and fill both `tailscale/tailscale_up.sh` (Linux) and `tailscale/tailscale_up.ps1` (Windows) with your Tailnet preferences.
- Store the Tailnet auth key in `tailscale/tailscale_authkey.txt` (not committed) or set a `TAILSCALE_AUTHKEY` environment variable before running the helpers. Both the Windows (`tailscale_up.ps1`) and Linux (`tailscale_up.sh`) scripts read from those sources so the unattended Ubuntu install and the Windows post-install stay in sync on tags/flags.
- For unattended runs, leave the auth key file on the Ventoy USB only as long as needed. The Ubuntu autoinstall reads the first line, exports it for the one-time `tailscale up`, and does not persist the secret on disk. Remove the key from the USB (or rotate it) once provisioning is complete.
- For NVIDIA NGC, run `jetson/ngc_login.sh` (or do `docker login nvcr.io`) with your API key.

## Notes
- Ventoy mapping lives in `ventoy/ventoy.json`—edit the `"image"` paths to match your ISO filenames.
- If Windows doesn't auto-run the post-install script, open the USB and run `windows/win-postinstall.ps1` as admin.
- On staged builds, confirm the machine appears in the Tailnet admin console with the expected tags right after post-install.
