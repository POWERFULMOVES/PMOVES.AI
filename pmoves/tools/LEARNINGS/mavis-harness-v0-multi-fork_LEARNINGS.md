# Mavis harness v0 - multi-fork consumer follow-ups (LEARNINGS)

The companion LEARNINGS file to the AGNOTE follow-up row. Captures
the 5-class taxonomy (legit / already-fixed / owner / out-of-scope /
pre-existing) + the 4-bucket learning signal (missed-signal /
fix-pattern / wrong-suggestion / already-addressed) per the
pr-trim convention.

## Scope

Two new DRAFT PRs (companion to PMOVES.AI PR #2477):

- **POWERFULMOVES/PMOVES-hermes-agent PR #4** (DRAFT) - the agent
  subscriber. New `pmoves_bootstrap/` package (loader.py +
  tools_bridge.py + subscriber.py + 33/33 tests). No modifications
  to existing Hermes files.

- **POWERFULMOVES/PMOVES-pinokio PR #1** (DRAFT) - the app launcher.
  New `pmoves_loader/` + `pmoves_apps/example-pmoves-app/` (24/24
  tests). No modifications to existing Pinokio files. No new
  npm dependencies.

## 5-class taxonomy

(empty for this initial slice - the PRs are DRAFT, no review yet)

- legit: TBD on review
- already-fixed: TBD on review
- owner: TBD on review
- out-of-scope: TBD on review
- pre-existing: TBD on review

## 4-bucket learning signal

(empty for this initial slice)

- missed-signal: TBD on review
- fix-pattern: TBD on review
- wrong-suggestion: TBD on review
- already-addressed: TBD on review

## Self-review notes (operator can use as a starting point)

Things the next session should check on review:

1. **Cross-fork CGP schema drift.** The three PRs all reference
   `pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json` in
   the PMOVES.AI side. The 2 forks VENDORED a copy of the schema.
   If the PMOVES.AI schema changes, the forks will silently drift.
   Possible fixes: (a) a CI check that hashes the vendored copy
   against the canonical schema on every PR, (b) a shared
   `pmoves-schemas` repo that all 3 forks pull from, (c) a CHIT
   signed check at session init. (a) is the cheapest; (c) is the
   right long-term answer. Out of scope for this slice.

2. **No real NATS transport in v0.** The PMOVES.AI orchestrator
   uses `MockPublisher`; the Hermes subscriber is a stub. End-to-end
   task dispatch requires a real NATS server (`PMOVES-nats-server`
   fork) + a `pmoves-nats-mcp` MCP transport. Both are follow-up
   slices.

3. **No CGP re-emission in the Hermes side.** When Hermes picks up
   a task and processes it, the result goes out on
   `pmoves.agent.result.v1` but the CGP identity block is unchanged
   (still says `agent: minimax`). A future slice could have Hermes
   re-emit a CGP with `identity.agent: hermes` so downstream
   consumers know which agent did the work.

4. **The 6 constraints are honored by behavior, not by code.** No
   code path explicitly checks for `no-override-existing-config`
   or `preserve-existing-tools` - the loader's behavior is to
   never touch the fork's existing config, so the constraints are
   satisfied by design. A future slice could add a constraint
   validator that raises if a CGP is loaded that would violate a
   constraint (e.g. a "set Hermes's config to this" CGP would
   fail).

5. **The example app in PMOVES-pinokio is a no-op on purpose.**
   The install.js / start.js files log a summary and exit 0. A real
   Pinokio app would do its actual work (git clone, pip install,
   launch a service, etc.). The point of the example is to show
   the wiring, not to ship a working service.

## Acceptance criteria

- [x] PMOVES.AI side: load_bootstrap + orchestrator + bpm_cron + 56/56 tests (PR #2477, ready for review)
- [x] PMOVES-hermes-agent side: pmoves_bootstrap/ + 33/33 tests (PR #4, DRAFT)
- [x] PMOVES-pinokio side: pmoves_loader/ + example app + 24/24 tests (PR #1, DRAFT)
- [x] Cross-fork CGP schema alignment (all 3 read the same v1.schema.json)
- [x] Non-breaking test pair on each fork (no-CGP = exact pre-change, with-CGP = PMOVES tools added)
- [x] AGNOTE follow-up row added (this row)
- [x] CHIT trail unsigned-local (no CHIT_PASSPHRASE loaded)
- [ ] Real `pmoves-nats-mcp` NatsPublisher (follow-up)
- [ ] Real `nats-py` Hermes subscriber (follow-up, needs pyproject.toml deps change)
- [ ] Pinokio main.js wiring (follow-up)
- [ ] Pillar 4 cyber.png → pillar4-encoding.json render (needs ComfyUI host with H3)
- [ ] KVM control surface (RustDesk, not a harness concern yet)
- [ ] 3 clubs + lounges content (explicitly after Mavis lanes)

## Cross-fork plan

The 3 PRs of the harness v0 slice:

1. **PMOVES.AI PR #2477** (writer) - load_bootstrap + orchestrator + bpm_cron + 56/56 tests
2. **PMOVES-hermes-agent PR #4** (agent) - pmoves_bootstrap/ + 33/33 tests
3. **PMOVES-pinokio PR #1** (app launcher) - pmoves_loader/ + example app + 24/24 tests

All 3 read the same v1.schema.json. The schema is the contract.

## Three-body

delivery=Mavis (this, the 2 fork PRs + the AGNOTE row + this LEARNINGS),
control=DARKXSIDE (operator reviews the 3 PRs together, merges after
all 3 land), memory=this trail + the 2 PRs + the cross-fork LEARNINGS
files.

## CHIT trail unsigned-local

No CHIT_PASSPHRASE loaded in this Mavis session per the standing
operator convention.
