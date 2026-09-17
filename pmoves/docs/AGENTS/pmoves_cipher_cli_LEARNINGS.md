# pmoves_cipher_cli_LEARNINGS.md

**Lane:** pmoves-cipher CLI dispatcher (`pmoves/tools/cipher_cli.py`)
**Author:** 5090-CLAUDE · **Operator:** DARKXSIDE
**Active:** 2026-09-16/17 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` 2026-09-17T01:20:00Z
**PR:** #3093 (`feat/pmoves-cipher-cli-and-mcp` off `origin/main@3ebd2b79ed`)

---

## Operator direction (verbatim)

> "you need your cipher all PMOVES agents get cipher there should be one on this node as well as local and cli"

The directive names **three surfaces**, and this lane ships the **third (CLI)**:

1. **cipher API container** (`pmoves-cipher-api-1` on `127.0.0.1:8105`) — already wired, healthy uptime 559769s.
2. **cipher MCP SSE** (`.claude/mcp.json::pmoves-cipher`, bearer auth via `CIPHER_API_TOKEN`) — already wired.
3. **cipher CLI** (`pmoves/tools/cipher_cli.py`) — NEW surface, this PR.

Cross-node cipher availability (Spark, 4090, b850, z890) is a **follow-up** that uses NATS subjects (`pmoves.cipher.*`), not the CLI. The CLI is local-node only; every node still needs its own cipher API container, then the CLI on top.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **contract-correctness** | The lane ledger (`pmoves/data/chit/lanes.jsonl`) MUST append BEFORE the subprocess runs — the audit trail exists even if the chit tool fails. The test `test_failed_subprocess_does_not_append` pins this contract by deliberately failing the subprocess and asserting the ledger still got the entry. | `pmoves/tools/cipher_cli.py:133` (`cmd_register`) calls `_append_lane(...)` before `_run_chit(...)`. The test name is a NEGATIVE assertion that pins a POSITIVE behavior; documented in the test docstring so a future maintainer doesn't "fix" the name. | Any audit-ledger-write pattern where the underlying action can fail independently of the audit. |
| 2 | **contract-correctness** | 4 narrowly-defined exit codes (0 ok, 2 usage, 3 wrapped tool failed, 4 health endpoint down), NOT the generic Unix 1. Callers branch without false positives — a chit tool that prints stderr warnings but returns 0 stays a 0 here. Exit 3 (lane failed) and exit 4 (cipher API down) carry different operator alerts: exit 3 = "the agent's task failed", exit 4 = "the agent is deaf to incoming CHIT messages". | `pmoves/tools/cipher_cli.py:33-43` (docstring contract) + lines 128, 152, 162, 174, 187, 205 (each exit site). | Any CLI that wraps subprocess tools and needs to be monitorable. |
| 3 | **defense-in-depth** | The CLI wraps chit_* tools as **subprocesses**, not as imports. Each chit_* tool is invoked via `subprocess.run([sys.executable, str(path), *argv])`. This preserves each chit_* tool's independence (no shared module-level state) and lets the wrapper catch non-zero exits cleanly. Cost: process startup; benefit: each chit_* tool can be deprecated or replaced independently. | `pmoves/tools/cipher_cli.py:113` (`cmd = [sys.executable, str(path), *argv]`); tests assert exact argv at `ms.run.call_args[0][0]`. | Any "thin wrapper over a tool family" pattern. |
| 4 | **reasoning-gap** | The CLI builds `cmd` with `sys.executable` (the same interpreter that runs cipher_cli), not `python3` or a hardcoded path. This ensures the chit_* tools use the same dependency environment as the CLI itself, and matches the AGENTS.md python-ladder convention. A chit_* tool imported via subprocess gets the same `sys.path`, the same `venv`, the same package versions as the CLI that called it. | `pmoves/tools/cipher_cli.py:113`; this works because `python -m pmoves.tools.cipher_cli` and `python pmoves/tools/chit_X.py` resolve to the same interpreter. | Any wrapper that subprocess-invokes helper scripts in the same package. |
| 5 | **semantic-naming drift** | The CLI has `bundle <lane>` AND `register <lane> <summary>`. `bundle` reads its lane info from the ledger it just wrote; `register` takes lane+summary as args. Both append to the same ledger. Test `test_bundle_invokes_chit_sync_with_lane_arg` asserts `len(argv) == 2` for bundle (python + script, no positional args). This split keeps the lane metadata in OUR format (operator-friendly) and the chit call clean (one input format per tool). | `pmoves/tools/cipher_cli.py:193-207` (`cmd_bundle`); `pmoves/tools/cipher_cli.py:122-153` (`cmd_register`). | Any "audit-trail + tool-call" pattern where the tool's input format doesn't match the audit's input format. |
| 6 | **defense-in-depth** | Smoke test on this node surfaced a chit bug: `chit_sync_workflow_bundle.py:28` does `from pmoves.chit import decode_secret_map` which fails with `ModuleNotFoundError`. The CLI correctly surfaces this as exit 1 (chit wrapped-tool exit). The bug was NOT in cipher_cli — it was in the wrapped chit tool, hidden by the CLI's "always exits with chit's rc" contract. **Without the smoke test, this bug would have hidden until the next operator ran `pmoves-cipher bundle` and got a confusing traceback.** | Smoke run: `python pmoves/tools/cipher_cli.py bundle feat/test-cipher-pr` → exit 1, ModuleNotFoundError on `pmoves.chit`. | Any wrapper where the wrapped-tool failures get masked by the wrapper's own success behavior. |
| 7 | **contract-correctness** | The lane ledger lives at `pmoves/data/chit/lanes.jsonl` which IS gitignored (pmoves/.gitignore:17 — `data/chit/` directory). The cipher_cli.py docstring (lines 75-77) CLAIMS the ledger "SHOULD be in git so future agents can see what lanes have been registered" — but the gitignore rule excludes it. The lane history belongs in cipher MCP / lane-aware AGNOTE rows (like this one), NOT in committed JSONL files. **This is a docstring/gitignore mismatch — fix the docstring, not the gitignore.** | `pmoves/.gitignore:17` (`data/chit/`); `pmoves/tools/cipher_cli.py:75-77`. | Any module docstring that asserts a git-trackability claim — verify it against `.gitignore` before claiming. |
| 8 | **defense-in-depth** | `health` is the ONLY subcommand that does NOT spawn a chit_* tool. It hits the cipher API's `/health` directly (loopback), preferring system `curl` over stdlib `urllib.request` because the operator's mental model is `curl -sf http://127.0.0.1:8105/health`. The curl-failure distinction (exit 22 = HTTP error, exit 7 = can't connect, exit 28 = timeout) is preserved end-to-end so the failure class is observable in the CLI's own exit code. | `pmoves/tools/cipher_cli.py:210-262` (`cmd_health`). | Any "is the upstream service up" check that needs to be parseable from a single exit code. |
| 9 | **contract-correctness** | The CLI does NOT use `CIPHER_API_TOKEN`. Only the MCP SSE binding uses it (against `http://localhost:8105/mcp/sse`). The CLI hits the cipher API's unauthenticated `/health` endpoint only. This split keeps the token's blast radius narrow (MCP SSE only) and means a node without `CIPHER_API_TOKEN` set still has `pmoves-cipher health` working. | `pmoves/tools/cipher_cli.py:68-69` (no auth in health check); `pmoves/env.shared.example` CIPHER_API_TOKEN comment explicitly says "the pmoves-cipher CLI does NOT use this token". | Any "two surfaces share a backend" pattern where one surface needs auth and the other doesn't. |
| 10 | **reasoning-gap** | The CLI's argparse subparsers use `set_defaults(func=cmd_X)` — one function per subcommand. `main()` is a 3-liner (`parse_args`, `args.func(args)`, return rc). This makes each subcommand independently testable (just call `cmd_register(mock_args)` directly) AND makes the test file's `with mock.patch.object(cc, "subprocess") as ms:` pattern work — the test calls the cmd function directly, not through `main()`, so there's no sys.argv leakage. | `pmoves/tools/cipher_cli.py:271-308` (`build_parser`); `pmoves/tools/cipher_cli.py:311-314` (`main`, 4 lines). | Any CLI that needs to be exercised by tests without touching sys.argv. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 2 lessons (#4, #10) — interpreter-resolve and argparse-func-attribute patterns are subtle, easy to skip.
- **(2) semantic-naming drift** — 1 lesson (#5) — bundle/register split is a deliberate semantic choice, easy to merge.
- **(3) contract-correctness** — 4 lessons (#1, #2, #7, #9) — the bulk of the work is making the contracts precise (exit codes, ledger-before-subprocess, docstring vs gitignore, token scope).
- **(4) defense-in-depth** — 3 lessons (#3, #6, #8) — subprocess-wrapping, smoke-test surfacing, curl-failure classification.

Pattern: **defense-in-depth + contract-correctness dominate** — 7 of 10 lessons. This lane ships a thin wrapper, so the contracts (exit codes, ledger timing, docstring truth, token scope) ARE the value; the wrapper's body is mostly forwarding.

---

## Test design notes

22 tests across 6 classes:

| Class | Tests | What it pins |
|---|---|---|
| `TestArgparse` | 7 | Each subcommand parses with the expected args; missing subcommand errors; subcommand order is byte-stable. |
| `TestSubprocessDispatch` | 6 | Each cmd_X forwards the exact argv to the wrapped script; missing file → exit 2; bundle passes no positional args. |
| `TestLaneLedgerAppend` | 3 | register/bundle append JSON-Lines records with `action` key (NOT `label`); failed subprocess STILL appends. |
| `TestExitCodes` | 3 | 0 on success; 3 when wrapped tool exits 3; 4 when health endpoint is down. |
| `TestHealthEndpoint` | 1 | Live loopback `/health` is reachable (or 4 if cipher API is down — xfail-tolerant). |
| `TestByteStability` | 2 | Parser is idempotent (same subcommand order on re-build); register's lane+summary are both required. |

**Test bug found + fixed:** `TestExitCodes.test_three_when_wrapped_tool_exits_three` used `self.tmp_path` but had no `setUp`. Fix: added `setUp` + `tearDown` to `TestExitCodes` (same pattern as `TestSubprocessDispatch`).

---

## SDK provenance

- **CLI**: `pmoves/tools/cipher_cli.py` (318 lines)
- **Tests**: `pmoves/tools/tests/test_cipher_cli.py` (291 lines, **22/22 green**)
- **Launchers**: `deploy/provision/pmoves-cipher.{sh,ps1,cmd}` (157+131+6 lines)
- **Installers**: `deploy/provision/install-pmoves-cipher-command.{sh,ps1}` (88+94 lines)
- **Env example**: `pmoves/env.shared.example` (CIPHER_API_TOKEN= field added with full comment)

---

## Hand-written exclusions (DO NOT regenerate)

The registry-driven launcher generator (`pmoves/tools/pmoves_launcher_generator.py`, PR #3092) emits `<cli>-pmoves.{sh,ps1,cmd}` for each CLI in `pmoves/configs/cli_tools.yaml`. The `claude-pmoves.{sh,ps1,cmd}` and `crush-pmoves.{sh,ps1,cmd}` are marked `managed="hand"` and are NOT regenerated — they carry SDK-fixed FAIL-CLOSED MCP roster logic per PR #2847 + python ladder per PR #2809.

The cipher CLI launchers ARE emitted by the launcher generator IF a `pmoves-cipher` wrapper is added to `cli_tools.yaml`. As of this PR, the cipher launchers are emitted by hand into `deploy/provision/`, not via the registry. A follow-up could register `pmoves-cipher` in the registry if the operator wants drift-pinning on the cipher launchers; out of scope for this slice.
