# PMOVES Integrations PR Pack

This pack includes:
- compose profiles for **wger** and **firefly**
- n8n **auto-import** script
- **CI** workflow to smoke test profiles
- optional **flows watcher** sidecar
- README badge snippet

## How to apply

1) Unzip at the root of your **PMOVES.AI** repository:
```bash
unzip pmoves-integrations-pr-pack.zip -d .
```

2) Commit on a feature branch and push:
```bash
git checkout -b feat/integrations-wger-firefly
git add .
git commit -m "feat(integrations): add wger+firefly compose profiles, n8n auto-import, CI, watcher"
git push origin feat/integrations-wger-firefly
```

3) Open a Pull Request and verify the **PMOVES Integrations CI** checks pass.

> Reminder: replace `OWNER/REPO` in `.github/README-badge-snippet.md` when adding the badge to your README.
