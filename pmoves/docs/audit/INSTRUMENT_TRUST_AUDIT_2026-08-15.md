# Instrument-trust audit — seven checks that reported confidently and were wrong

**Date:** 2026-08-15
**Auditor:** B850-CLAUDE (Knuckles)
**Scope:** findings from a single B850 session (2026-08-13 → 08-15), landed as
[#2538](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2538),
[#2545](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2545),
[#2567](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2567),
[#2570](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2570)
**Companion audits:** #2525 (CI enforcement), #2527 (reproducibility), #2522 (ruleset exposure)

## What this audit does and does not establish

*(framing borrowed from #2527, which states its own limits before its findings)*

**Establishes:** seven specific checks on this node reported a confident result that did
not match reality, each verified by reading the underlying values rather than the
verdict. Each has a named mechanical cause, reproduced.

**Does not establish:** that these are the only such cases, or that the pattern
generalises beyond the surfaces examined. Six of the seven were found incidentally while
chasing unrelated bugs — the sampling is opportunistic, not systematic. **No claim is
made that the fleet has been swept.** Finding 7 in particular was found only because a
glyph looked wrong, which is not a method.

**Deliberately not restated here:** the verification discipline itself. It is already
written in `.claude/agents/verifier.md` — *"evidence before assertions … capture
verbatim … do not paraphrase '12 passed, 1 skipped' into 'tests pass' … state
UNVERIFIED (environment) rather than approximating."* That contract predates this
session and covers the general case better than a restatement would. **The gap this
audit documents is invocation, not documentation.**

## The seven

| # | Instrument | Reported | Actually | Mechanism |
|---|---|---|---|---|
| 1 | rocm-smi exporter `:9835` | `200 OK` | 0-byte body, weeks | systemd expanded `%d` and `${#body}` in an inline `ExecStart` |
| 2 | `claude-pmoves` launcher | launched normally | every cred-dependent MCP empty | `WARN`-then-`exec` on a root it failed to resolve |
| 3 | submodule branch audit | 53 mismatches | 3 real | measured branch *name*, not branch *membership* |
| 4 | `dmesg` | no PCIe errors | buffer evicted | a USB keyboard re-enumerating ~5,000×/day |
| 5 | `geometry_bus_health.py` | "Health: 0.0%" | never contacted NATS | `ParseResult` → `re.sub` raised; caught and relabelled "connection failed" |
| 6 | *this auditor* | "the venv lacks nats-py" | it has 2.14.0 | read an `AttributeError` as an `ImportError`, then wrote it into a Makefile comment as fact |
| 7 | `sign_trail.py` (CHIT trail) | valid signature | **default identity** | `import yaml` inside a `try` with `except Exception: pass`; under `uv run` (no pyyaml declared) it silently returned `_FALLBACK` |

Finding 7 was discovered while registering *this audit* in AGNOTE4482 — the signing
tool emitted a cryptographically valid HMAC carrying glyph `◆` / `#7C3AED` instead of
the agent's registered `⌬` / `#DC2626`. The `agent_id` survived only because it is
passed on the command line; every field sourced from the registry was substituted. Its
own comment states the intent — *"so the tool never hard-fails on missing YAML"* — and
the effect is a provenance tool that cannot report not knowing who you are. Fixed by
declaring `pyyaml` in an inline `# /// script` block; verified re-signing now yields the
registered identity. **Noticed only because the glyph looked wrong**; had the agent's
configured glyph happened to match the fallback, it would have passed unremarked, which
is a fair guess at why it went unnoticed until now.

Two shapes, and they need different remedies:

- **1, 2, 5, 7 are mechanizable.** Each is a surface returning success while the payload
  is absent, stale, or substituted. A check asserting *content* rather than status catches
  all four without knowing anything about any of them. Three of the four share one exact
  cause: **a soft-import or broad `except` that swallows the reason and returns a
  plausible default**, so the caller receives a complete-looking result built from
  nothing. *Mechanizable is not the same as grep-able* — see the sweep below, where
  that instinct over-reported by a factor of forty before it was narrowed.
- **3, 4, 6 are not.** They are a wrong question, unrelated noise destroying evidence, and
  a misread. No linter catches these; only the habit of reading raw values does.

`merge-gate` deserves a note: #2525 found it vacuous. By the time of this audit it had
been **repaired** (`pytest_ratchet.py` runs all 264 test files, previously `head -20` by
filesystem order; the dependency install lost its `|| fallback` and `2>/dev/null`; the
gate now `exit 1`s on any failure). Verified before relying on it for the merges above.
**The audit lane is driving fixes ahead of its own PRs merging.**

## The sweep — and what it says about the sweep

Finding 7's cause looked mechanizable, so it was swept for across `pmoves/tools/` and
`pmoves/services/` by AST rather than grep (a text grep cannot tell a handler's shape).
The funnel matters more than the endpoint:

| Filter | Hits |
|---|---|
| `try:` containing an import, with a broad or bare `except` | **157** |
| …of those, handlers that are **silent** (no log, no raise, no warn) | **60** |
| …of those, handlers that are fully `pass` | 6 |
| …of those, in a path that **reports outward** as authoritative | **4** |

**The first number is the finding.** 157 would have been a fleet-wide alarm, and it would
have been wrong: `torch`, `faiss`, `sentence_transformers`, `numpy`, `tqdm`, `rich`,
`psutil` guards are all *correct* — the feature genuinely degrades and the caller is told.
Had this audit stopped at the grep it would have become an eighth entry in the table
above: a confident count that did not match reality. **The antipattern is not "a broad
`except` on an import." It is a silent handler in a path that reports outward.**

Two sites show what correct looks like, and both survived every filter honestly:

- `services/hf-mcp-server/main.py:542` — live registry query falls back to the static
  catalog and stamps `"source": "catalog"` instead of `"source": "registry"`. The
  consumer can *see* which one it got.
- `tools/chit_security.py:13` — crypto import failure sets `_CRYPTO_OK = False`, an
  explicit degraded flag rather than a silent no-op.

The four that lied outward, all fixed in this PR (logging only — no behaviour or
contract change; best-effort delivery stays best-effort):

| Site | Was | Now |
|---|---|---|
| `tools/sign_trail.py:77` | substituted the whole agent identity in silence | warns to stderr naming the reason (pyyaml missing / file unreadable / agent unregistered) |
| `hi-rag-gateway-v2/routes/geometry.py:166` | dropped every live subscriber, returned `{"ok": true}` | `logger.exception` |
| `hi-rag-gateway-v2/routes/geometry.py:583` | same | `logger.exception` |
| `hf-mcp-server/main.py:853` | `hf.model.gguf.converted.v1` never published, returned `{"ok": true}` | `logger.exception` |

Two of these are self-evidencing. `sign_trail.py` already warned loudly that it could not
find a requested **alter** — twenty lines below the block that substituted the entire
**agent** without a word; it could report a missing persona but not a missing person.
And `geometry.py` persists with `logger.exception` + `raise HTTPException(500)`, then
eight lines later swallows the broadcast and returns `ok: true`. **Both files already
contained the correct discipline; it just had not been applied to the adjacent line.**
That is the more useful lesson than any lint rule: the fix was usually already in the
file.

## Mechanical traps (the genuinely new material)

Node-agnostic, reproduced, and in none of the existing surfaces:

| Trap | Consequence seen |
|---|---|
| `$(...)` strips **all** trailing newlines | `Content-Length` one byte short of the body; Prometheus exposition lost its required final newline. Bit **four separate times** — in the responder, in two tests of the responder, and in the installer verifying it. |
| nats-py `connect_timeout` does **not** bound DNS resolution | unresolvable host hung ~60 s while `connect_timeout=5` sat there looking authoritative. Wrap in `asyncio.wait_for`. |
| `%` and `${}` in a systemd `ExecStart` are expanded **by systemd** | `%d` → credentials dir, `%s` → user shell, `${#body}` → empty. Put shell code in a real script; escaping works but reintroduces itself on the next edit. |
| Submodule branch **name** ≠ branch **membership** | detached HEAD is normal; the real test is `merge-base --is-ancestor <sha> origin/<tracked>`. And the *recorded gitlink* is a different layer from the *working tree* — only the former affects clones. |
| Fleet `NATS_URL` is container-scoped (`nats:4222`) | any host-run tool hangs on it. Use the published address from the host. |
| A tool run in a bare `uv run` env has no venv packages | a soft-import fallback then renders a full report from nothing. Declare inline deps (`# /// script`). |

## Recommendations

1. **Invoke `.claude/agents/verifier.md` reflexively** — on one's own claims before
   asserting them, not only on others' PRs. It was invoked zero times during a session
   in which it would have caught finding #6 immediately.
2. **Healthchecks and status targets assert payload, not status code.**
   `pmoves-mesh-preflight` and `health:check-all` currently trust endpoint verdicts;
   either would have passed the 0-byte exporter every day it was broken.
3. **Land the audit lane** (#2522, #2525, #2527). Its findings are already changing the
   repo; merging them makes the reasoning citable rather than folkloric.
4. **Consider the #2527 package as a calibration fixture.** #2525 had to hand-roll "a
   deliberately failing test run through an equivalent path" to prove a check *could*
   fail. A frozen, network-isolated, hash-manifested package with six deterministic
   checks of known outcome is the standing form of that — a target whose answer is known,
   which is exactly what every instrument in the table above lacked.

## Provenance

Every row was verified by reading the underlying value, not the verdict:
`Content-Length` vs actual bytes; `LnkSta: Width x16` vs the expected `x8`;
`4.2%` vs `0.0%`; `merge-base --is-ancestor` vs branch name; `importlib.metadata
.version('nats-py')` vs a traceback's first line. Where a claim could not be checked on
this node it is marked as such above rather than approximated.
