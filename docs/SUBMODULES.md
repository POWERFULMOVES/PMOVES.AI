Submodules Plan: Hardening Integrations as First‑Class Repos

Goals
- Separate upstream integrations from PMOVES.AI overlays.
- Publish hardened images to GHCR with SBOMs, signatures, and vulnerability scans.
- Keep monorepo compose dev‑friendly via image‑first overrides and dev‑local builds.

Priority Order
1) PMOVES.YT
2) Archon
3) Agent Zero
4) Channel Monitor

Process (example for PMOVES.YT)
1. Create the destination repo in GitHub (e.g., POWERFULMOVES/PMOVES.YT).
2. Run the extraction helper:
   `bash pmoves/tools/submodules/extract_to_submodule.sh services/pmoves-yt POWERFULMOVES/PMOVES.YT pmoves/integrations/pmoves-yt`
3. Update compose to prefer published image (`pmoves/docker-compose.integrations.images.yml`) and keep dev‑local build behind profiles or alternative targets.
   - For Archon specifically, you can build directly from the submodule via an override:
     `docker compose -p pmoves -f pmoves/docker-compose.yml -f pmoves/docker-compose.archon.submodule.yml up -d archon`
4. Enable integrations GHCR workflow for the repo (see .github/workflows/integrations-ghcr.yml) and confirm SBOM/Trivy/Cosign outputs.
5. Document service‑specific env/health in `pmoves/docs/services/<service>/README.md`.

Archon submodule (this repo)
- Source list: see docs/githuborgan.md (POWERFULMOVES/PMOVES-Archon).
- Add as submodule (already linked here):
  `git submodule add https://github.com/POWERFULMOVES/PMOVES-Archon.git pmoves/integrations/archon`
- Build from submodule instead of clone‑at‑build:
  `make -C pmoves up-archon-submodule`

Make Targets
- `make up-yt-published` — run PMOVES.YT from GHCR.
- `make up-yt-hardened` — run with hardened compose overrides.
- `make up-agents-hardened` — agents stack with hardened overrides.

Security Baseline
- Non‑root user, read‑only FS + tmpfs /tmp, drop all caps, no‑new‑privileges.
- SBOM (CycloneDX/SPDX), Trivy scan (block HIGH/CRITICAL), Cosign signing.
