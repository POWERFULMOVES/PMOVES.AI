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
   # Glancer (optional profile + env keys)
   bash addons/install_glancer.sh
   # or
   pwsh -File addons/install_glancer.ps1
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

---

## Glancer option
- **Patch + fetch/build:** run `bash addons/install_glancer.sh` (or `pwsh -File addons/install_glancer.ps1`) from the repository root to inject the Glancer compose profile, append env defaults, clone the source (`GLANCER_REPO_URL` / `GLANCER_REF` overrideable), and build the image (`GLANCER_IMAGE`, defaults to `pmoves-glancer:local`).
- **Env keys added:** `GLANCER_IMAGE`, `GLANCER_PORT`, `GLANCER_PUBLIC_BASE_URL`, `GLANCER_BASIC_AUTH_USER`, `GLANCER_BASIC_AUTH_PASSWORD`, `GLANCER_HEALTH_PATH` (all appended to `.env.example` / `env.shared.example`).
- **Bring-up:** `docker compose -f pmoves/docker-compose.yml --profile glancer up -d glancer` after the patch runs.
- **Health / smoke:** expect HTTP 200 on `${GLANCER_PUBLIC_BASE_URL:-http://localhost:9105}${GLANCER_HEALTH_PATH:-/healthz}`. Quick check: `curl -fsSL http://localhost:9105/healthz` (or adjust port/path to match your overrides). The compose healthcheck mirrors the same probe.
