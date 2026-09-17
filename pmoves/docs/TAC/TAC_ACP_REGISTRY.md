# TAC Tree: ACP Registry (PMOVES-Registry)

> Technology-Architecture-Context tree for the Agent Client Protocol registry fork — the launcher catalog that lets any ACP client (Zed, JetBrains, gemini-cli, fleet harnesses) spawn fleet-relevant coding agents, and the bridge that maps those entries onto the PMOVES agent registry.

## Service Identity

| Field | Value |
|-------|-------|
| **Fork** | `POWERFULMOVES/PMOVES-registry` (upstream: `agentclientprotocol/registry`) |
| **Clone convention** | repo-root sibling (`../PMOVES-registry`) — enforced by `acp_registry_map.py:33`, `infra.mk:682` |
| **Fork registry entry** | `pmoves/config/fork_registry.json` → `PMOVES-registry` (`sync: true`, branch `main`) |
| **Entries at fork** | 42 agents (synced 2026-09-15) |
| **Published index** | `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json` |
| **Tier** | agent (cross-cutting launcher substrate) |
| **Class** | Utility |

## Upstream Surface (the base we work from)

| Asset | Location | What it does |
|-------|----------|--------------|
| Entry format spec | `FORMAT.md` | `agent.json` schema: `distribution` = `binary` / `npx` / `uvx`; platform keys (`windows-x86_64`, ...); archive formats incl. raw binaries; `sha256` integrity; preview channel rules |
| Auth requirements | `AUTHENTICATION.md` + `README.md` | Listing gate: ≥1 authMethod of type `agent`\|`terminal`, verified via CI handshake |
| Contribution flow | `CONTRIBUTING.md` | Entry requirements: `id`=dirname, semver `version`, `license_url`, 16x16 `currentColor` SVG icon, distribution |
| Handshake client | `.github/workflows/client.py` | Spawn agent → JSON-RPC `initialize` (protocolVersion 1, clientInfo, terminal+fs+`_meta` caps) → validate `result.authMethods` |
| Agent verifier | `.github/workflows/verify_agents.py` | CLI; per-platform verification; `prepare_npx_package` pre-installs (why their 120s handshake suffices); `verify_binary` skips platforms with no build |
| Protocol matrix | `.github/workflows/protocol_matrix.py` + `daily-protocol-matrix.yml` | Nightly matrix on **`ubuntu-latest`** |
| Version cron | `update-versions.yml` | Hourly version bumps from npm/PyPI/GitHub releases, committed to `main` |
| Build/validate | `build_registry.py` | Schema-validates all entries → `dist/`; run via `uv run --with jsonschema` (fork `AGENTS.md`) |

**Upstream constraint that shapes everything below:** the harness runs on Linux CI only. `client.py:132-134,159-165` waits on pipes with `select`, which on Windows only works on sockets — upstream's verifier cannot run on this fleet's Windows nodes (POWERFULMOVES, Z890, Knuckles) as-is.

## Fleet Assets (ours, reconciled against upstream)

| Asset | Location | Upstream relationship |
|-------|----------|----------------------|
| ACP↔PMOVES mapper | `pmoves/tools/acp_registry_map.py` → `pmoves/configs/acp_registry_map.json` | **No upstream equivalent.** Conservative matching (explicit bridges + exact repo basenames; substring search forbidden). Live: `kilo → kilocode_glm` |
| Launcher probe | `pmoves/tools/acp_launcher_probe.py` | **Port of upstream's client.py contract** (initialize shape verbatim, env allowlist from `AGENT_ENV_PASSTHROUGH`, authMethods parsing) with 3 documented divergences: thread reads (Windows pipes), continuously-drained stderr (npx cold-install deadlock), `taskkill /T` tree kill |
| Make targets | `infra.mk:682` `acp-registry-map` | — |
| Explicit bridges | `acp_registry_map.py:39` | `spynel → PMOVES-spynel` is **dead** — no `spynel/` entry exists in the registry (see Branch E) |

## Measured State — 2026-09-16, POWERFULMOVES (windows-x86_64)

Probe: `make -C pmoves acp-launcher-probe` (scope with `ACP_PROBE_ENTRIES=`; PASS = starts + replies to `initialize` with `result`; authMethods reported, upstream gate behind `--auth-required`). Both npx paths verified: cold `npx` and the upstream-parity pre-install (`npm install --prefix` → `node_modules/.bin`, `[npx-installed]`) — the latter is the default, matching upstream `prepare_npx_package` semantics.

| Entry | Launcher | Result | authMethods |
|-------|----------|--------|-------------|
| glm-acp-agent v1.8.0 | npx | **PASS** | 2 |
| qwen-code v0.23.3 | npx | **PASS** | 2 |
| codex-acp v1.11.0 | npx | **PASS** | 2 |
| claude-acp v0.77.0 | npx | **PASS** | 2 |
| kilo v7.6.2 | npx **and** binary | **PASS** / **PASS** | 1 |
| minimax-code v0.2.7 | npx | **PASS under Node 24** (auth=1) — FAIL on system Node 22.17.1, root-caused | 1 |

Resolved measurement gaps (2026-09-17):
- **kilo binary path verified** — windows-x86_64 archive downloaded, sha256 verified, extracted, `kilo acp` answered initialize (`--distribution binary`). Both kilo distribution paths now pass.
- **minimax-code FAIL decomposed** — two stacked causes: (1) its installer hard-gates **Node ≥ 22.19** (this node runs 22.17.1: `"This Node.js release is outside the verified MCode compatibility range"`), so the upstream-parity pre-install cannot complete and cold `npx` hangs instead of erroring over ACP; (2) the node's DNS is flaky (`EAI_FAIL` across registry fetches, 70s stalls), which crashed npm mid-install with the "Exit handler never called" wrapper on the first attempt and muddied the signal. **RESOLVED 2026-09-17 as a managed dep:** fnm (winget-installed but dormant on this node) now manages Node — `fnm install 24` (v24.21.0, default alias), repo pin `.node-version` = `24`, `fnm env --use-on-cd` wired into PowerShell profiles + `~/.bashrc`. Verified: minimax-code **PASS auth=1** under 24.21.0. System MSI 22.17.1 stays as machine-wide fallback. Remaining fleet action: repeat `fnm install 24 && fnm default 24` + profile wiring on Z890/Knuckles.

## Reconciliation Doctrine — upstream-first

1. **Contract comes from upstream code, not inference.** Handshake shape, env sanitization, and the authMethods gate are mirrored verbatim from `client.py`; entry/launcher shapes from `FORMAT.md`. Where docs and CI code disagree (e.g., AUTHENTICATION.md describes authMethods on `AUTH_REQUIRED` errors while CI reads them from the `initialize` result), the CI code is the operational truth.
2. **Divergences are either contributed upstream or documented here.** The three Windows portability fixes are genuine upstream gaps (their CI is Linux-only) — they belong in an upstream PR to `agentclientprotocol/registry`, with our probe as the interim fleet carrier (Branch A).
3. **Fleet-only layers stay thin.** The mapper (`acp_registry_map.py`) has no upstream counterpart and is fleet-canonical. The probe should shrink, not grow: as upstream gains Windows support, the probe delegates more (Branch A/D).
4. **Never hand-edit generated artifacts** (`acp_registry_map.json`, `docker_matrix.yaml`-style) — regenerate.

## Branches

| Branch | Phase | Status | Owner | Scope |
|--------|-------|--------|-------|-------|
| A | upstream-portability | planned | crush | PR to `agentclientprotocol/registry`: replace `select` pipe waits with Windows-safe reads, drain stderr during handshake, kill process tree on Windows. Unblocks running upstream's own verifier on fleet Windows nodes. |
| B | probe-hardening | **done** | crush | `--distribution` flag added (kilo binary path verified PASS); upstream-parity npx pre-install adopted (`prepare_npx_package` semantics); minimax-code root-caused (Node ≥ 22.19 engine gate + node DNS flakiness) and **fixed as a managed dep** (fnm 24.21.0 + `.node-version` pin + profile wiring) — now PASS. |
| C | mapping-bridges | in_progress | crush | `kilo` live. Remove or realize dead `spynel` bridge. Candidate: `glm-acp-agent → zai` lane bridge (needs explicit operator decision, matching stays conservative). |
| D | fleet-bringup-docs | planned | crush | Sibling-clone convention per node; Linux nodes (KVM4-1/2, KVM2, SPARK) should run upstream `verify_agents.py` natively instead of the port. |
| E | spynel-entry | planned | operator | Publish `PMOVES-Spynel` as a registry entry per CONTRIBUTING.md (id/version/license_url/icon/distribution). Publishing fleet tooling publicly is an operator call. |
| F | fork-sync-posture | planned | crush | `fork_registry.json` says `sync: true`; upstream's hourly version cron means constant drift. Verify `fleet-fork-sync` covers this fork; confirm the nightly matrix cross-check lands in the fleet sync report. |

## Related Lanes (checked against remote 2026-09-17)

| PR | Lane | Relationship |
|----|------|--------------|
| #3095 | test ratchets: kilo binary-path chain + minimax/Mavis 240s timeout | **Same subject, complementary angle.** Their ratchets assert the npm→shim→binary dispatch chain exists and `--version` answers; our probe proves the registry archive speaks the full ACP handshake. Their open question (platform vs upstream) is answered by our root cause: Node ≥ 22.19 engine gate (host: 22.17.1) + DNS EAI_FAIL — posted on the PR. |
| #3092 | registry-driven launcher generator (`deploy/provision/` trio per node) | Fleet launcher-fabric side; zero file overlap with this lane. Future consumer candidate for `acp_registry_map.json` — generator input manifest is PMOVES-side today. |
| #3094 | launcher dispatch parity (`pmoves/scripts/*-pmoves*` + damage-control hooks) | Adjacent (spawn wrappers), no overlap. |
| #3089 | topology docker-matrix relative paths | Shares the "no machine-local state in tracked artifacts" doctrine; the probe/map artifacts follow the same portability rule. |


```bash
# sibling clone (once per node)
git clone https://github.com/POWERFULMOVES/PMOVES-registry ../PMOVES-registry

# managed Node (once per node; repo .node-version pins the major)
fnm install 24 && fnm default 24   # then reload shell (fnm env is profile-wired)

# regenerate the ACP<->PMOVES mapping artifact
make -C pmoves acp-registry-map

# verify fleet-relevant launchers on this node
python pmoves/tools/acp_launcher_probe.py
python pmoves/tools/acp_launcher_probe.py --entries kilo --auth-required --json

# upstream's own harness (Linux nodes)
cd ../PMOVES-registry/.github/workflows && uv run --with pytest --with jsonschema pytest tests/ -v
```

<!-- graphiti:tac lane:acp-registry branch:bringup phase:root status:in_progress owner:crush reviewer:operator ts:2026-09-16T23:48:00Z -->

## TAC bringup: registry fork standing on POWERFULMOVES

**Lane:** `acp-registry`
**Status:** `in_progress`
**Owner:** `crush`
**Reviewer:** `operator`
**Dependencies:** none
**PR:** pending
**Verification:** probe run 2026-09-16 (5 PASS / 1 FAIL table above); `acp-registry-map` regenerated (42 entries, kilo linked)

### Done
- Sibling clone stood up; mapper run against live fork; launcher probe built as a documented port of upstream client.py; 6 fleet-relevant launchers measured on windows-x86_64

### Left Behind
- Branches A, C–F as tabled above; Node ≥ 22.19 bump needed on Windows fleet nodes before minimax-code can pass; spynel bridge still dead pending Branch E decision

### For Next Agent
- Read upstream `verify_agents.py` before extending the probe — pre-install semantics (`prepare_npx_package`) are the missing half of our minimax result
- Do not soften the conservative matcher in `acp_registry_map.py` to manufacture links

<!-- /graphiti:tac -->
