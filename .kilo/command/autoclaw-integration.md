Scope and track the three autoclaw workstreams injected into AGENTS.md (2026-05-23).
Creates TAC stubs, service contracts, and branch scaffolding for autoclaw/hermes work.

## Arguments

- `--stream` — which workstream to scaffold: `browser`, `vision`, `hermes`, or `all` (default: all)
- `--node` — target node profile (default: `4090`)

## Implementation

Three workstreams, each needs a branch + TAC node + service contract:

### Stream 1: autoclaw-integration (skill-path standard)

```bash
# Verify managed skills dir exists
ls ~/.openclaw-autoclaw/skills/ 2>/dev/null || echo "DIR NOT FOUND — needs provisioning"

# Check Archon skill discovery config
grep -r "openclaw\|autoclaw" ~/.claude/ --include="*.json" -l 2>/dev/null
```

Branch: `feat/autoclaw-integration`
TAC node: `n4090.autoclaw.skill-path`
Work: standardize `~/.openclaw-autoclaw/skills/<name>/SKILL.md` format; wire auto-discovery
into Archon mint-skill flow; add `.openclaw-autoclaw/` to `.gitignore` if not present.

### Stream 2: autoglm-agents (browser + vision)

```bash
# Check if autoglm services are reachable (ports TBD — update once CATALOG.md entries land)
declare -A AUTOGLM_PORTS=([autoglm-browser-agent]=8200 [autoglm-image-recognition]=8201)
for svc in autoglm-browser-agent autoglm-image-recognition; do
  port="${AUTOGLM_PORTS[$svc]}"
  echo -n "$svc (:$port): "
  curl -sf "http://localhost:${port}/healthz" -o /dev/null -m 2 2>/dev/null \
    && echo "UP" || echo "NOT RUNNING"
done
```

Branch: `feat/autoglm-agents`
TAC node: `n4090.autoclaw.browser-agent`, `n4090.autoclaw.image-recognition`
Work: define service contracts (port, healthz, fallback chain); add to CATALOG.md;
add health checks to `/health:quick` skill; document Playwright/Puppeteer fallback.

### Stream 3: hermes-4090-evolution

```bash
# Check if hermes-agent is installed in Pinokio
ls ~/pinokio/apps/hermes-agent* 2>/dev/null || ls /D/pinokio/api/hermes-agent* 2>/dev/null \
  || echo "hermes-agent not installed in Pinokio"

# Check current AGENTS.md evolution intensity block
grep -A5 "hermes-evolution" AGENTS.md
```

Branch: `feat/hermes-4090-evolution`
TAC node: `n4090.autoclaw.hermes-evolution`
Work: review autoclaw-injected evolution intensity (100% aggressive) for 4090 suitability;
customize per-node; wire `hermes-agent.pinokio.git` to Pinokio launcher; add TAC Phase 7
subtree under `node-4090-laptop.tac.yaml`; commit AGENTS.md from that branch.

## Related

- `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml` — Phase 7 goes here
- `pmoves/configs/tac_trees/node-5090-powerfulmoves.tac.yaml:66` — hermes-agent listed
- `AGENTS.md` — holds the 4 injected autoclaw blocks (unstaged, awaiting `feat/hermes-4090-evolution`)
- `.claude/CATALOG.md` — autoglm service entries should land here

## Notes

- AGENTS.md must NOT be committed to main until hermes-evolution intensity is reviewed for 4090
- All three streams are independent PRs — do not bundle
- `~/.openclaw-autoclaw/` is machine-local; already gitignored; do not commit its contents
- Submodule bump for 17 pointer mismatches: separate `chore/submodule-bump-YYYY-MM-DD` PR, not here
