PMOVES Provisioning Bundle — Application Guide
==============================================

The PMOVES mini CLI stages this bundle into `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/`
whenever you run:

```
python3 -m pmoves.tools.mini_cli bootstrap [--output /path/to/bundle]
```

The staged directory mirrors the canonical assets tracked in this repository so you
can hand them off to remote environments or downstream forks without hunting for
individual files.

Included assets
---------------

- `docker-compose.gpu.yml` – production-grade compose profile with GPU runtime and
  external-mode toggles.
- `scripts/install/wizard.sh` and `scripts/install/wizard.ps1` – cross-platform
  interactive installer that chains env bootstrap, dependency checks, and smoke
  prompts.
- `scripts/proxmox/pmoves-bootstrap.sh` – unattended bootstrap helper for Proxmox
  nodes.
- This README – quick reference for applying the bundle.

Bundled directories
-------------------

When you target a custom `--output` path, the CLI also mirrors the curated
subdirectories maintained under `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/` so
the portable bundle ships with the same Docker stacks and bootstrap helpers
tracked in this repository:

- `backup/`
- `docker-stacks/`
- `docs/`
- `inventory/`
- `jetson/`
- `linux/`
- `proxmox/`
- `tailscale/`
- `ventoy/`
- `windows/`

The `README.md` from the provisioning bundle is copied alongside these
directories to preserve the high-level orientation guide for remote recipients.

Applying the bundle in another repository
-----------------------------------------

1. Create a feature branch in the target repository.
2. Copy each file into its matching path (respect executable bits on the shell
   scripts):
   - `docker-compose.gpu.yml`
   - `scripts/install/wizard.sh`
   - `scripts/install/wizard.ps1`
   - `scripts/proxmox/pmoves-bootstrap.sh`
3. Review the latest PMOVES documentation for complementary updates:
   - `pmoves/docs/LOCAL_DEV.md`
   - `pmoves/docs/LOCAL_TOOLING_REFERENCE.md`
   - `pmoves/docs/SMOKETESTS.md`
   - `CRUSH.md`
   These documents already include the provisioning wizard, GPU compose profile,
   and bootstrap guidance. Replicate the relevant sections or link back to them as
   needed in the downstream project.
4. Run any required smoke checks (`make smoke`, `python3 -m pmoves.tools.mini_cli
   status`, etc.) before submitting the PR to validate the installation workflow.

Notes
-----

- Because these files are copied directly from the PMOVES repository you can use
  `git log --stat --` or `git show` on each path to audit recent changes when
  preparing downstream updates.
- If a downstream project diverges significantly, generate targeted patches with
  `git format-patch` against the desired base commit instead of relying solely on
  this curated bundle.
- Keep the bundle directory under version control when syncing multiple machines;
  it doubles as a manifest of which provisioning assets have been distributed.
