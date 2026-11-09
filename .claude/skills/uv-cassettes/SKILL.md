---
name: uv-cassettes
description: >
  Cut every Python agent/plugin/service as a reproducible, LOCKED "cassette" that plays
  identically in sandbox, on host, and deployed. Use when adding or editing a PMOVES service
  image, an MCP server, an A0/dsh plugin, or a standalone tool/script — anywhere Python deps
  are declared. Codifies uv + a committed requirements.lock (the botz-gateway pattern),
  uv run for tooling, lock regeneration, and the TypeScript (pnpm/bun lock) parallel.
  Use /uv-cassettes or just "add a python service/plugin" / "why did this rebuild break".
---

# uv-cassettes — reproducible locked packaging

**The principle (DARKXSIDE canon).** Each agent/plugin/service is a *cassette* the platform
(Soundwave / P7) ejects into any layer. A cassette must **play identically in sandbox
(E2B / agent-sandbox), on host, and deployed**. The mechanism is **reproducible locked
packaging**: uv + a committed lock. Lockless deps = a cassette that plays differently in each
deck. This is reliability substrate, not style. See memory `vision_agents_as_cassettes_uv_portability`.

**Proof it's load-bearing:** notebook-mcp shipped `mcp>=1.2.0` unpinned; a later rebuild pulled
**mcp 2.x** (FastMCP → MCPServer rename) → crash-loop. A lock would have caught it. **70 of 73
PMOVES service Dockerfiles are lockless `requirements.txt`** — the same break can recur in any.

## Service / MCP-server / plugin images — the botz-gateway pattern

Two files + a two-line install. `requirements.txt` = direct deps (with sane bounds);
`requirements.lock` = every version pinned (direct **and** transitive).

```dockerfile
# repo pattern: services/botz-gateway, services/ffmpeg-whisper, services/notebook-mcp
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --constraint requirements.lock -r requirements.txt
```

`requirements.txt` (direct, bounded — a bound alone is NOT reproducibility, the lock is):
```
mcp>=1.2.0,<2          # never bare >=; a floating major is how mcp 2.x crash-looped us
httpx>=0.27.0
nats-py>=2.6.0
```

`requirements.lock` (fully pinned — the actual cassette):
```
mcp==1.29.1
httpx==0.28.1
nats-py==2.15.0
# …every transitive, pinned…
```

**Editing a service Dockerfile / requirements is a Known Road** (`dockerfile:` domain) — see
`.claude/PATTERNS.md § Known Roads`. `requirements.txt`/`.lock` are build-context files (not the
Dockerfile domain) and edit freely; the Dockerfile itself needs `dockerfile:handoff:<brief>`.

## Regenerating the lock

After changing a direct dep, rebuild then freeze the built image (captures exact transitives):

```bash
make -C pmoves build-svc SVC=<service>            # build only
docker run --rm --entrypoint pip <image> freeze \
  | grep -viE '^-e |pkg-resources' | sort > pmoves/services/<service>/requirements.lock
make -C pmoves rebuild-svc SVC=<service>          # build + surgical recreate (env flows)
```
Or, offline, `uv pip compile requirements.txt -o requirements.lock`. Commit the lock in the
SAME change as the dep bump — an unlocked bump is an un-cut cassette.

## Local tooling & one-off scripts — `uv run`

Never `pip install` into the system for a script. `uv run` resolves ephemerally from the
script's own project (see `feedback_use_uv_for_python_packages`):

```bash
cd <tool-project> && uv run --quiet python verify.py …   # e.g. the MiniMax provider-verifier
uv run --with httpx python one_off.py                     # inline deps, no venv to manage
```

## Single-file agents — the self-contained cassette (PEP 723 / IndyDevDan)

The most portable cassette: ONE `.py` that carries its own deps inline. No venv, no separate
requirements files — `uv run` reads the header, builds an ephemeral **locked** env, runs it.
This is the IndyDevDan single-file-agent pattern; ideal for a tool an agent hands to a sandbox
(E2B / agent-sandbox) or a teammate copies to another node — the file travels, and plays the
same everywhere.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "mcp>=1.2,<2",       # bound the major — same rule as requirements.txt
#   "httpx>=0.27,<1",
# ]
# ///
"""The file IS the cassette. `uv run agent.py`, or chmod +x and run it directly."""
```

Lock it for true reproducibility: `uv lock --script agent.py` writes `agent.py.lock`; run with
`uv run --locked --script agent.py` so sandbox == host == deploy. For a frozen drop, pin exact
`==` versions in the block. Add a dep with `uv add --script agent.py <pkg>` (edits the header).

## The TypeScript parallel (same discipline, other deck)

TS agents (deepseek-harness = TS/pnpm) are cassettes too. The **pnpm/bun lockfile** is the
uv.lock equivalent: commit `pnpm-lock.yaml` / `bun.lock`, install with `--frozen-lockfile`
(CI) so sandbox/host/deploy resolve identically. `PMOVES-Creator`, dsh, and A2UI ride this.

## Deploy — never bypass the pipeline

Build + recreate through Make so env tiers load and the lock is honored:
- `make -C pmoves build-svc SVC=<name>` · `recreate-svc SVC=<name>` · `rebuild-svc` (both).
- Do **not** hand-run `docker compose --env-file …` (guard-blocked; deliberate) or `docker run`
  (skips the env pipeline → missing tokens/URLs). See `feedback_use_make_targets_for_builds`.

## Checklist when cutting a new cassette

- [ ] `requirements.txt` bounds every direct dep (`<major+1`), never a bare `>=`.
- [ ] `requirements.lock` committed, pinning direct + transitive.
- [ ] Dockerfile uses `uv pip install --system --constraint requirements.lock -r requirements.txt`.
- [ ] Built + recreated via `make … rebuild-svc SVC=<name>` (env pipeline honored).
- [ ] In-network service URLs are compose-DNS, not inherited `localhost` (host-only).
- [ ] Verified live (health + a real call), not just "it built".

## Reference cassette

`pmoves/services/notebook-mcp/` — the first app-plugin cut this way (PR #2909): uv+lock,
verified live (Open Notebook `/api/search` → 200). Pairs with
`project_apps_as_mcp_plugins_architecture` (build once, mount twice).

## References

- **IndyDevDan** (YouTube) — single-file uv agents + agentic uv workflows (the source the
  operator anchors this on).
- uv single-file scripts / PEP 723 — https://docs.astral.sh/uv/guides/scripts/ ;
  locking — https://docs.astral.sh/uv/concepts/projects/sync/ (`--locked`, `uv lock --script`).
- **Skills ecosystem / CLI** — `skills/PMOVES-skills` (fork of `vercel-labs/skills`) is how a
  `SKILL.md` packages + distributes across the open skills ecosystem. Keep this skill's
  frontmatter ecosystem-compatible so it propagates (the "resonate across layers" path).
- Memory: `vision_agents_as_cassettes_uv_portability`, `feedback_use_uv_for_python_packages`.
