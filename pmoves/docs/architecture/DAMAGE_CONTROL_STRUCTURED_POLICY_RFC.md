# RFC — Structured Policy for the Damage-Control Guard

**Status:** Draft for review
**Lane:** not yet claimed — claim before implementation
**Author:** 4090-claude (canonical per `pmoves/config/identity_vocabulary.yaml:108`)
**Intended path:** `pmoves/docs/architecture/DAMAGE_CONTROL_STRUCTURED_POLICY_RFC.md`
**Supersedes:** nothing. Extends the guard rewritten in #3034.

---

## 1. Problem

`.claude/hooks/damage-control/bash-tool-damage-control.py` decides security policy
by running regular expressions over raw shell command **text**. The surface is
368 `patterns.yaml` entries plus 10 direct `re.*` call sites.

Shell is not a regular language, so every match is an approximation of a parse
that never happens. This is not a theoretical objection. In a single working
session (2026-09-16 → 09-18), on this one file:

| # | Failure | Class |
|---|---|---|
| 1 | Zero-access pattern matched a protected path inside an **inert commit message**, blocking a commit that only *described* the file | false positive on text vs. operation |
| 2 | A guard written as `grep '^\t@'` searched for a literal `t` — GNU grep BRE does not expand `\t` | regex-dialect drift |
| 3 | Heredoc terminator accepted indentation for `<<`, which only `<<-` permits | shell-semantics mismatch |
| 4 | **ReDoS** — ambiguous alternation, 80,473× blowup at N=22, in a hook that runs before *every* Bash call | catastrophic backtracking |
| 5 | The first ReDoS repro used bare `--` and measured 0.0000s — it could never have failed | untestable by construction |

The file's own comments already concede the ceiling:

> *"RESIDUAL GAP, stated not papered over: indirection is still out of reach …
> Closing them needs interpretation, not pattern matching."*

A sixth instance appeared outside the guard and is the clearest statement of the
problem. `pmoves/scripts/mint_cipher_token.py` accepts `--agent` as a free-form
string and INSERTs it into a fleet-shared Supabase table. `identity_vocabulary.yaml`
defines canonical agent identities and their aliases. Nothing connects the two.
This author minted `claude-4090` — not canonical, not an alias, one word-order
away from the real `claude_4090` — and it was accepted silently. **Free-form
strings crossing a trust boundary with a vocabulary file sitting unused beside
them is the same defect as regex-matching a shell command.**

### 1.1 The same failure, outside the guard, while writing this

The defect is not "the guard is badly written". It is that **unvalidated values
crossing boundaries fail this way for everyone**. Six instances occurred in
sequence while landing the fix and drafting this document, all by its author:

| assumed | actual |
|---|---|
| `# codeql[py/redos]` suppresses the alert | it does not; code scanning ignored it |
| `awk '{print $2}'` yields a check status | the check name contains a space |
| alerts live on the branch ref | they live on `refs/pull/N/merge` — the query returned `0 open` while two were blocking |
| `dismissed_reason=used-in-tests` | the API wants `used in tests`, with spaces |
| dismissal comments are unbounded | 280 characters |
| a 288-character comment is fine | it is not; the length was printed and not compared |

The third is the dangerous one: a wrongly-scoped query produced a confident
"no alerts" that was false.

Only two steps in that sequence did not fail, and both for the same reason —
something declared the valid set up front. The API answered
`["false positive", "won't fix", "used in tests", "mitigated"]`, and the final
attempt compared a length against its limit before sending. **That is what a
schema does automatically, at every boundary, without the author having to
remember.** It is the entire argument of this RFC, demonstrated at its own
expense.

## 2. Non-goals

- Not a rewrite of *what* is protected. `patterns.yaml`'s 368 entries are policy
  and stay policy; this changes how they are **expressed and evaluated**.
- Not removing the local hook. Fast local feedback is valuable.
- Not blocking on a perfect shell parser. Partial structure beats no structure,
  provided the partiality is declared rather than hidden.

## 3. Design

### 3.1 Layer 1 — Parse, don't match

Replace "regex over raw text" with "inspect parsed structure". Three tiers,
degrading explicitly rather than silently:

1. `shlex` (stdlib, available today) — argv splitting. Handles quoting properly,
   which alone removes failures #1 and #3.
2. A real shell AST (`bashlex` or `tree-sitter-bash`) — **neither is installed**
   (verified). Adding one is a dependency decision for this lane, §7.
3. Declared-unreachable — variable indirection (`p=$X; rm "$p"`) cannot be
   resolved statically. Today this is a comment; it becomes a **typed outcome**
   the caller can act on.

The third tier is the important one. A guard that cannot say *"I could not
determine this"* has to pretend it decided.

### 3.2 Layer 2 — Pydantic models, applied asymmetrically

The contract is **not** "validate everything". It is:

> **Ingress is permissive. Egress carries provenance.**

- **Ingress — open.** Accept what is within the phase. Do not reject a creator's
  input because the vocabulary has not caught up. A system meant to be available
  to as many as possible cannot be usable only by whoever already knows the
  schema.
- **Egress — provenance-mandatory.** The moment a value **pipes, links, or
  displays** — agent cards, signatures, trails, shared tables, rendered output —
  it must carry where it came from. That boundary is where the models live.

This is the correction that matters most, and it came from re-reading the
`claude-4090` incident. That was not an ingress failure: accepting a new name at
the CLI is fine. The failure was that it **piped into a fleet-shared table and
became citable** with no provenance and no vocabulary check. Validate the egress
and the ingress can stay open.

The citation property then falls out rather than being bolted on. If everything
downstream carries provenance, work cites itself by construction — a trail, not
a bibliography someone has to maintain.

Pydantic is already the house pattern, in two CI-enforced gates:

| gate | workflow |
|---|---|
| `pmoves/tools/chit_security_validator.py` | `.github/workflows/integration-gate.yml` |
| `pmoves/scripts/validate_agent_registry.py` | `.github/workflows/validate-agents-config.yml` |

So this is applying an existing road, not inventing one. Sketch:

- `ProtectedPath` — path, class (`zero_access` / `read_only` / `no_delete`),
  provenance (§4), and the sanctioned route to cite when it blocks.
- `Operation` — verb, targets, confidence (`parsed` / `heuristic` / `undetermined`).
- `Decision` — `allow` / `ask` / `block` / `undetermined`, reason, matched rule id.
- `AgentIdentity` — **validated at the write to shared state**, against
  `identity_vocabulary.yaml`. Not at argument parse: the CLI may accept a name
  the vocabulary has not learned yet; what it may not do is write that name into
  a table other agents will cite.
- `IdentityLifecycle` — mint **and revoke** as one validated surface. Today
  minting is a Known Road and retiring is freehand REST (§7 D3); a registry you
  can only append to is not a registry.

`patterns.yaml` is validated against the schema **at load**, fail-closed, which
the loader already does for parse errors but not for shape.

### 3.3 Layer 3 — Decisions are records

Every `block` / `ask` emits a structured record: rule id, provenance, confidence
tier, and the sanctioned route. This is what makes §5 and §6 possible.

## 4. Provenance contract

Every rule declares where its authority comes from, and that source is tracked
for freshness exactly like a living doc.

- Each `ProtectedPath` / rule carries `provenance: <doc path>#<anchor>`.
- Those docs are registered in `pmoves/configs/living_docs_registry.yaml`
  (`path`, `freshness_days`, `severity`, `description`).
- `pmoves/tools/docs_reconcile.py --check` already fails CI on stale **P1**.
- A new check asserts **every rule's provenance target exists and is registered**.
  A rule whose justification has gone stale is a finding, not silence.

**This RFC registers itself** under that contract — `freshness_days: 180`,
`severity: P2` — so the proposal is subject to the rule it proposes.

> Rationale, in the operator's words: *stale living docs is also a pattern tools
> should follow*. A tool enforcing policy from an unciteable or rotted source is
> the same failure as a doc nobody reconciles — it looks authoritative and isn't.

## 5. DangerRoom validation

A security-hook rewrite must not be proven by unit tests alone: unit tests only
check the cases their author imagined, and §1 #5 shows the author can write a
test that cannot fail.

Plan, using the existing sandbox surface (`pmoves/config/rooms/danger-room.*`,
`agent-sandbox` skill):

1. **Corpus replay** — replay a captured corpus of real Bash commands through old
   and new guards; any decision divergence is a finding requiring written
   justification. Catches silent policy drift the test suite cannot.
2. **Adversarial room** — an agent is tasked, in the sandbox, with reaching a
   protected path. Every success is a gap; every block is checked for whether it
   names a *usable* route.
3. **Performance floor** — the adversarial corpus runs against the perf budget
   already established (`5KB < 1.0s`, currently 0.001s). The ReDoS assertions
   from #3105 fold in here.
4. **Fail-closed drill** — corrupt `patterns.yaml`, confirm the guard blocks
   rather than opens. Proving a gate can say NO is the point.

## 6. Cipher-backed decision memory

Cipher is live and auth-enforced on 4090 (`no-header → 401`, real token → 200)
with per-agent tokens in `cipher_agent_tokens`. Guard decisions become
retrievable across agents:

- A block writes its record (§3.3) to cipher memory.
- Agents query *"has this class blocked before, and what was the route?"*
  instead of rediscovering it per session.
- Repeated blocks on the same class become evidence that a **road is missing**,
  not that the agent is misbehaving — turning the guard into a signal source
  rather than only a wall.

Aligns with the standing principle: governance by **flow and memory**, not walls.

## 7. Dependency decisions — needed before implementation

**D1 — pydantic is undeclared.** Imported by both CI gates above; present in no
`requirements*.txt` or `pyproject.toml`. It resolves on this node only from
global miniconda site-packages. Two CI gates stand on an undeclared dependency,
and per-user site-packages is exactly the trap that hides this. *Declare it, in
its own commit, before anything new depends on it.*

**D3 — no revoke road.** `cipher-mint-token` exists; nothing retires an identity.
There is no `cipher-revoke` target and `mint_cipher_token.py` has no revoke path.
Retiring the two bad `claude-4090` rows on 2026-09-18 required a direct REST
PATCH — a write to fleet-shared state with no road, by an agent, unreviewed.
Minting is governed and retiring is freehand, which is backwards: revocation is
the security-relevant half. Folded into `IdentityLifecycle` (§3.2).

**D2 — shell AST parser.** `bashlex` and `tree-sitter-bash` are both absent.
Options: (a) `shlex` only — no new dep, no compound/redirect structure;
(b) `bashlex` — pure Python, real AST, unmaintained upstream; (c)
`tree-sitter-bash` — maintained, native build, heavier for a PreToolUse hook
where startup cost is paid on every call. **Recommendation: ship Phase 1 on
`shlex`, decide (b)/(c) with Phase-2 measurements in hand** — a hook that runs
before every command cannot absorb an unmeasured import.

## 8. Implementation round-trip

Each phase is independently revertible and ends in evidence, not assertion.

| Phase | Deliverable | Gate |
|---|---|---|
| 0 | Declare pydantic (D1) | CI green; gates now honest about deps |
| 1 | Pydantic models + `patterns.yaml` schema validation at load; behaviour unchanged | Existing suites pass unchanged; fail-closed drill on corrupt config |
| 2 | `shlex` argv layer for path checks; regex retained as fallback, divergences logged not acted on | DangerRoom corpus replay: **zero unjustified divergences** |
| 3 | Promote argv layer to authoritative; regex demoted to `undetermined` signal | Adversarial room; perf floor |
| 4 | Provenance contract + reconcile check (§4) | Every rule cites a registered, fresh doc |
| 5 | Cipher decision records (§6) | Records queryable; repeated-block report exists |
| 6 | CI/App enforcement parity — the App enforces server-side, local hook advisory | Divergence between local and CI decisions is itself a CI failure |

**Round-trip property:** phases 2–3 run old and new **side by side** with
divergence logging before the new path is authoritative. That is what makes this
a migration rather than a rewrite-and-pray. No phase both changes behaviour and
removes the old path in one step.

## 9. Delegation map

Authorized to delegate across the ecosystem. **Village rule is dual** — work is
held by a pair on a node, not assigned downward. On 4090 that pair is
`4090-claude` + `PMOVES-CRUSH-4090`. Sibling nodes carry their own pairs and
their own AGInTZ; they are **peers, not workers**, and a lane goes to whichever
pair holds the relevant context:

| Work | Pair / lane | Why |
|---|---|---|
| D1 pydantic declaration | any pair | Mechanical, isolated, unblocks Phase 1 |
| D3 revoke road + `IdentityLifecycle` | 4090 pair | Caused the incident; owns the evidence |
| Phase 1 models + schema | 4090 pair | Holds the failure context |
| Phase 2/3 parser layer | 5090 / Z890 pair | Well-specified once models exist |
| DangerRoom corpus + adversarial room | agent-sandbox lane | Sandbox is its surface |
| Provenance reconcile check | any pair | Extends existing `docs_reconcile.py` |
| CI/App enforcement | VPS/App lane | Owns the App credential path |

**Cap the fan-out explicitly.** A workflow that picks its own scale will pick a
large one. State a ceiling in the prompt (e.g. *use at most 5 agents*) or set it
once via Dynamic workflow size. Six phases across peer pairs is coordination,
not parallelism — the register is the coordination surface, not agent count.

Coordination via the register (TTL'd claims). Note the register currently shows
**13 of 32 open claims with no TTL** — they can never expire. Worth its own lane;
a claim that cannot expire is not a claim.

## 10. Open decisions

1. **D2 parser choice** — deferred to Phase-2 measurement (§7).
2. **Divergence tolerance in Phase 2** — is any unjustified divergence a hard
   stop, or is a documented allowlist acceptable? Recommend hard stop.
3. **Identity vocabulary as the enum source** — `identity_vocabulary.yaml` becomes
   load-bearing for `AgentIdentity`. It must then itself be schema-validated and
   registered for freshness, or the fix inherits the defect it closes.
4. **Forward-looking identity.** The operator indicates a promotion beyond the
   current canonical `4090-claude` (level-11 / HyPeRAGInT / Spynel framing).
   **Not cited here as existing** — zero hits in `pmoves/config/`, `pmoves/docs/`,
   `PMOVES-registry/`. When that lands in the registry, `AgentIdentity` picks it up
   from the vocabulary with no code change, which is the point of §3.2.

## 11. Risks

- **Scope.** Six phases is a lot. Mitigation: each independently revertible; §8
  never couples a behaviour change to a removal.
- **Parser gaps become new false negatives.** Mitigation: the `undetermined`
  outcome is explicit and fails **closed**.
- **Startup cost in a PreToolUse hook.** Mitigation: the perf floor is an
  existing, passing gate, not a new aspiration.
- **This RFC rotting.** Mitigation: registered as a living doc (§4) — if it goes
  stale it shows up as a finding, like anything else.

## 12. Verification of claims in this RFC

Every measurement cited was taken on 4090 during 2026-09-16→18 and is
reproducible:

- ReDoS scaling table — `test_commit_message_heredoc.py`, `[ReDoS]` section
- Perf floor — `test_interpreter_writes.py`, `5KB in 0.001s`
- pydantic gates + workflows — `grep -rln 'from pydantic' pmoves/tools pmoves/scripts`
- pydantic undeclared — absent from all `requirements*.txt` / `pyproject.toml`
- Parsers absent — `python -c "import bashlex"` → ImportError
- Canonical identity — `identity_vocabulary.yaml:108`
- Cipher posture — `no-header 401`, real token `200`, container token len 32
