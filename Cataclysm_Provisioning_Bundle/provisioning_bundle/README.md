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
