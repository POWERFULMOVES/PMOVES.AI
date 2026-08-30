# Agent Zero In-App Self-Updater — Footgun & Mitigation

**Status:** Active mitigation (env-pinned). **Owner:** PMOVES infra.
**Affected component:** PMOVES-Agent-Zero submodule, `docker/run/fs/exe/self_update_manager.py`.

## (a) The footgun

PMOVES-Agent-Zero ships an **in-app self-updater** reachable from the Agent Zero
webUI ("Update" button). It is implemented in
`docker/run/fs/exe/self_update_manager.py`, which:

- Hardcodes the upstream remote:
  `OFFICIAL_REPO_URL = https://github.com/agent0ai/agent-zero.git`
- Is overridable **only** via the environment variable
  `A0_SELF_UPDATE_REMOTE_URL` (not set anywhere in stock PMOVES config).
- After fetching the remote, runs a hard reset / `git clean -ffd` of the
  working tree.

Consequences if an operator clicks **Update** with the default (unset) config:

1. The updater fetches **upstream `agent0ai/agent-zero`**, not the PMOVES fork.
2. `git clean -ffd` then **deletes all untracked PMOVES custom code** — including
   `chit/`, `pmoves_announcer/`, and the PMOVES `health` / `registry` / `common`
   modules — because they do not exist in upstream.
3. The updater **defaults to `branch=main` and resolves only vX.Y release tags
   reachable from that branch** (`tag --merged`); the PMOVES
   `PMOVES.AI-Edition-Hardened` branch is neither the default nor carries
   upstream-style release tags, so the button cannot target (or stay on) the
   hardened fork even if pointed at the fork remote.

Net effect: a single UI click can wipe the PMOVES customizations that make this
an orchestrator-grade Agent Zero, and silently revert to vanilla upstream.

## (b) The env fix

Pin the updater's remote at the PMOVES fork via the sanctioned env-pipeline path.
This is declared in `pmoves/env.shared.example` (do **not** edit `env.shared`
directly — let the secrets pipeline regenerate it):

```
A0_SELF_UPDATE_REMOTE_URL=https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
```

With this set, any in-app update fetches the **PMOVES fork** rather than upstream,
so the custom modules exist in the fetched tree and survive the post-fetch clean.

This is a defense-in-depth guard, **not** a green light to use the in-app
updater — see below.

## (c) Operational rule: never use the in-app "Update" button

Because the updater **defaults to `branch=main` and resolves vX.Y release tags
reachable from it** — and `PMOVES.AI-Edition-Hardened` is neither the default nor
carries those tags — the in-app updater cannot advance the fork on its canonical
hardened branch even with the remote pinned. The env fix only limits blast
radius; it does not make the button safe for advancing the fork.

**Operators must advance the fork via a worktree merge-forward**, e.g.:

```
git worktree add ../az-merge PMOVES.AI-Edition-Hardened
cd ../az-merge
git fetch upstream
git merge --no-ff upstream/main      # resolve, keep PMOVES custom modules
git push origin PMOVES.AI-Edition-Hardened
```

Then bump the submodule gitlink in PMOVES.AI through the normal PR flow.

**Do not** click the Agent Zero webUI "Update" button to update the fork.

## Reference

- `PMOVES-Agent-Zero/docker/run/fs/exe/self_update_manager.py`
  (`OFFICIAL_REPO_URL`, `A0_SELF_UPDATE_REMOTE_URL`, post-fetch `git clean -ffd`,
  `branch=main` default + vX.Y release-tag resolution).
- `pmoves/env.shared.example` — `A0_SELF_UPDATE_REMOTE_URL` declaration.
