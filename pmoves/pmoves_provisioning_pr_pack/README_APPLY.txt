PMOVES Provisioning Upgrades — PR Pack
======================================

This bundle contains:
- Diffs for modified files
- New files to add directly
- A short guide on how to apply

Recommended workflow
--------------------
1) Create a new branch in your repo, e.g.:
   git checkout -b feat/provisioning-upgrades-proxmox-sync

2) Apply the diffs manually or with 'git apply':
   git apply patches/Makefile.diff
   git apply patches/env.example.diff
   git apply patches/docker-compose.yml.diff
   # If any chunk fails, open the diff and patch manually.

3) Add NEW files:
   - docker-compose.gpu.yml
   - scripts/install/wizard.sh
   - scripts/install/wizard.ps1
   - scripts/proxmox/pmoves-bootstrap.sh

   Example:
   git add docker-compose.gpu.yml scripts/install/wizard.sh scripts/install/wizard.ps1 scripts/proxmox/pmoves-bootstrap.sh

4) Update docs using diffs (or copy sections manually if conflicts):
   git apply patches/docs_LOCAL_DEV.md.diff
   git apply patches/docs_MAKE_TARGETS.md.diff
   git apply patches/docs_SMOKETESTS.md.diff

5) Commit & push:
   git commit -m "Provisioning upgrades: update/backup/restore, external-mode, GPU profile, wizards, Proxmox bootstrap"
   git push origin feat/provisioning-upgrades-proxmox-sync

Notes
-----
- If your repo paths differ, open the diffs and adjust target paths.
- The diffs are unified format and assume LF line endings.
- All NEW files are included in full; make them executable where noted.

