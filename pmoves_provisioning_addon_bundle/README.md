# PMOVES.AI Provisioning Addon (Self‑Contained)

This addon drops into the root of your **PMOVES.AI** repo to enable:
- One‑line bootstrap (Proxmox or generic Linux)
- First‑run onboarding wizard (Bash/PowerShell)
- GPU compose overlay
- External integrations bring‑up (Wger, Firefly‑III, Jellyfin)
- Default credential summary command
- Flight check & smoke helpers
- Patch files for Makefile, env, compose, docs

## Quickstart
1) **Extract** this zip at the root of your PMOVES.AI clone.
2) (Optional) Apply patches:
   ```sh
   git checkout -b feat/provisioning-addon
   git apply addons/patches/Makefile.diff || true
   git apply addons/patches/env.example.diff || true
   git apply addons/patches/docker-compose.yml.diff || true
   git apply addons/patches/docs_LOCAL_DEV.md.diff || true
   git apply addons/patches/docs_MAKE_TARGETS.md.diff || true
   git apply addons/patches/docs_SMOKETESTS.md.diff || true
   ```
3) **Onboard**:
   ```sh
   bash pmoves/scripts/install/wizard.sh
   # or on Windows
   pwsh -File pmoves/scripts/install/wizard.ps1
   ```
4) **Launch**: `make up` (or `make up-gpu`), then `make smoke`

## Default creds summary (after first run)
```sh
bash pmoves/scripts/credentials/print_credentials.sh
# or
pwsh -File pmoves/scripts/credentials/print_credentials.ps1
```

Outputs service URLs and default/safe login info based on your `.env` and `env.shared`.

---

If you prefer Proxmox‑first, create a VM and run:
```sh
curl -fsSL https://raw.githubusercontent.com/POWERFULMOVES/PMOVES.AI/main/pmoves/scripts/proxmox/pmoves-bootstrap.sh -o pmoves-bootstrap.sh
sudo bash pmoves-bootstrap.sh
```
(You can also run the included `pmoves/scripts/proxmox/pmoves-bootstrap.sh` directly inside the guest.)
