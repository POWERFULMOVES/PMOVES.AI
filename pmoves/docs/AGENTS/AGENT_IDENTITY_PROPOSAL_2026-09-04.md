# Agent Identity — proposal (2026-09-04)

**Status:** PROPOSAL. No implementation, no tool grants, no config or topology
changes are made by this document or its PR.

**Lane:** `docs/identity-proposal-alters-chit-nats`, claimed by
`B850-CLAUDE (Knuckles)` on node PMOVES-B850-AI-TOP.

**Extends** [`AGENT_IDENTITY_MULTISIG_SEED.md`](AGENT_IDENTITY_MULTISIG_SEED.md)
(2026-08-09, "Seed only — unclaimed"). That seed asked for a typed identity
model (Part 1) and multi-sig quorum (Part 2). Part 1 has since been **largely
built** — this document reports where, and proposes what the built pieces still
do not do.

**Routing** — per AGNOTE4482.md:29, each agent signs only for what it reviewed
or executed. This document is signed by B850-CLAUDE only. See
[§Routing](#routing--what-each-reviewer-is-asked-to-decide).

---

## Method note

Every factual claim below carries its command and result, or a `file:line`.
Five claims that opened this lane were **wrong** and were corrected by
re-measurement; each correction is shown in place rather than quietly dropped.
That is the argument for the Village Rule (AGNOTE4482.md §Village Rule), not a
blemish on it — a single body asserting alone produced five errors in one lane.

The method is 4090's, recorded in
[`tooling-audit-4090-drift-enumeration-2026-08-08.md`](../handoffs/tooling-audit-4090-drift-enumeration-2026-08-08.md):
comparison at the wrong layer lies, and file contents settle it. It caught two
of the five errors here directly — the "three places" count and the "no voice"
claim were both artifacts of grepping instead of parsing.

Measurements were taken in a worktree off `origin/main` at `9c5f2f087`.

---

## 1. Identity is one signature with many faces, not sibling agents

### The mechanism exists in four places, not three

> **CORRECTION.** This lane opened claiming the alter mechanism lives in *three*
> disconnected places. There are **four**. The fourth,
> `pmoves/tools/identity_lineage.py` with
> `pmoves/config/identity_vocabulary.yaml`, is the most developed of them and
> already carries operator doctrine this proposal was about to re-derive. Missing
> it would have made this document propose something already written.

| # | Site | What it already does |
|---|------|----------------------|
| 1 | `pmoves/config/agent_signatures.yaml` | `alters` arrays — 7 alters across 6 of 25 agents |
| 2 | `pmoves/tools/sign_trail.py:177` `_resolve_alter_parent` | resolves an alter id back to its parent, signs AS the parent, stamps `selected_alter` |
| 3 | `pmoves/tools/register_status.py` | folds owner spellings to one identity when reading lane ownership |
| 4 | `pmoves/tools/identity_lineage.py` + `identity_vocabulary.yaml` | `wearing()`, `describe_self()`, `successions`, `alter_lineage`, `corrections` |

Site 4 records the doctrine directly (`identity_lineage.py:600-612`):

> Operator doctrine, 2026-08-25: an identity is WORN, not owned. "The signature
> is not the model, as models hold many; the identity a model puts on will align
> with the model and be tuned with the harness."

The same block explains why folding is the wrong instinct: `CLAUDE-OPUS-5` and
`4090-CLAUDE-OPUS-5` carry an identity **and** a model, "and the answer is to
PARSE it." This proposal does not improve on that. It adopts it.

### The register already disambiguates — measured

The objection that opened this lane — *two stewards on one node is an identity
the register cannot disambiguate* — is **empirically false**:

```
$ make -C pmoves register-status BRANCH=fix/cipher-mcp-transport-build-pin OWNER='B850-CLAUDE (Opus 5)'
  HELD BY YOU (line 2741, as `B850-CLAUDE (Knuckles)`)
$ ... OWNER='b850-claude'
  HELD BY YOU (line 2741, as `B850-CLAUDE (Knuckles)`)
$ ... OWNER='4090-CLAUDE'
  HELD by `B850-CLAUDE (Knuckles)` (line 2741)
```

Three spellings of one identity fold to `HELD BY YOU`; a genuinely different
identity does not. The register both folds variants **and** discriminates
between identities. This is not incidental — `b850-claude` has **4 distinct
spellings** in live data (`identity_lineage.py --census`), and the fold is
exercised on all of them.

### What `b850-claude` actually lacks

> **CORRECTION.** This lane claimed `b850-claude` has no `voice`. It does:
> `agent_signatures.yaml:342` sets `voice: analytical`. Parsing the YAML rather
> than reading a grep window settles it — **all 25 agents carry a `voice`, and
> all 7 alters carry one too**; there are zero exceptions in either direction.

What `b850-claude` lacks is an `alters` array. That is true, and it is **not
distinctive**: 19 of 25 agents have zero alters. Framing this node's steward as
uniquely deprived was wrong. The accurate statement is that the alter mechanism
is used by 6 agents and unused by 19, so a steward on an unaltered identity
reads as a sibling agent by default, not by judgment.

### Proposal 1

Register `node-steward` as an **alter** of the node's identity rather than as a
sibling agent, and record how it came to be in `alter_lineage`. Mechanically
this already works end to end today: `sign_trail.build_payload` accepts an alter
id, resolves it to the parent, keeps `agent_id` as the lineage, and stamps
`selected_alter` so the trail names the instrument
(`sign_trail.py:251-262, 297-299`). Nothing needs to be built for this. It needs
to be *declared*.

---

## 2. Growth: body → alter → top-level identity

### The path is already walked and already recorded — but not the one we thought

> **CORRECTION.** This lane claimed the walked growth path is
> `claude-opus → claude-opus-5`. It is not. That pair is a **model alt**, not an
> earned identity: `describe_self('claude-opus')` returns `alters: []` and
> `models_worn: ['claude-opus-5']`. The repo records **zero** `alter_lineage` for
> `claude-opus`. Citing it as the growth precedent would have argued that
> swapping models is how a body earns a face.

The path that *is* recorded belongs to 4090 — `identity_vocabulary.yaml`
`alter_lineage`:

> `4090-claude` / alter `field` / became `original-specialization` / origin
> `unknown` — Operator, 2026-08-25: *"field where unknown became alt became
> original Specialization."* The alter was not designed and assigned — it
> emerged from unnamed work, was recognised as an alter, and then became the
> identity's primary specialization. `agent_signatures.yaml:216` records the
> destination and **none of the path**. Confidence: `operator-asserted`.

And at the tier above, `successions` records `z890-claude → 5090-claude`,
confidence `attested-by-usage`, with a note worth quoting because it is the
standard this proposal wants held:

> `confidence` is NOT decoration. This edge is inferred from a naming convention
> someone invented under pressure, not from a signed handover event. It is
> strong evidence and it is still not proof, and a lineage system that cannot
> say which of those it has is the thing being fixed.

### The gap: no ledger accrues to a body

Delivery bodies do not appear in the identity system at all. There are **15
declared identities** (`identity_vocabulary.yaml`), all stewards, models or
harnesses. `delivery-agent`, `researcher`, `verifier`, `code-review`,
`test-runner` and `memory-agent` are none of them.

> **CORRECTION.** This lane claimed delivery agents "sign nothing." They *can*
> sign — `.claude/agents/delivery-agent.md:5` grants `Skill`, so `/chit:sign-trail`
> is reachable. The defect is worse than silence. Measured:

```
$ python3 -c "import sign_trail as st; st.build_payload('delivery-agent', ...)"
[warn] identity not resolved: 'delivery-agent' is not registered in agent_signatures.yaml;
       signing with FALLBACK presentation (glyph ◆ / #7C3AED)
[warn] no active signing card for agent_id=delivery-agent — signed without signing_card_id
  agent_id: delivery-agent   glyph: ◆   voice: analytical
  signing_card_id present: False        selected_alter present: False
```

`_FALLBACK` is `{glyph ◆, color #7C3AED}` (`sign_trail.py:72`) — which is
**`claude-opus`'s own registered glyph and color** (`agent_signatures.yaml:24-25`).
An unregistered body that signs does not sign anonymously; it signs wearing the
primary architect's face, with no signing card, on a warning to stderr.

This exact failure mode has been fixed once already at a different cause:
`sign_trail.py:10-15` documents a missing-pyyaml path that silently returned
`_FALLBACK`, so "a trail entry whose purpose is provenance was misattributing at
the presentation layer with no warning." The dependency cause was closed. The
*unregistered-agent* path still lands in the same fallback, by design.

### The numbers say no threshold is operating

Register entries versus alters earned, per identity
(`identity_lineage.py --census` joined against `agent_signatures.yaml`; 446
entries, 51 author strings, 15 identities):

| identity | register entries | alters | alter_lineage records |
|---|---:|---:|---:|
| b850-claude | 102 | 0 | 0 |
| spark-kimi | 60 | 0 | 0 |
| 5090-claude | 51 | 1 | 0 |
| z890-claude | 50 | 1 | 0 |
| mavis | 44 | 0 | 0 |
| codex-gpt5 | 39 | 0 | 0 |
| claude-opus | 34 | 1 | 0 |
| 4090-claude | 33 | 1 | 1 |

The identity with the **most** recorded work has the **fewest** faces, and the
only identity whose alter's origin is recorded at all has the fewest entries of
the altered group. There is no relationship between work recorded and identity
earned, because no threshold is being applied — not a lax one, none.

### Proposal 2

Give delivery bodies a registered identity so a ledger can accrue to them, and
record alter origins in `alter_lineage` at the moment of recognition rather than
reconstructing them from operator memory later (which is what
`origin: unknown` on 4090's own record means).

**The threshold — what earns an alter — is deliberately not set here.**
Mechanism is architecture; threshold is standards. 4090-CLAUDE holds the only
alter whose path is recorded, and is the only body that has walked it, so the
standard is 4090's to set. Stating a number here would be this lane inventing a
rule for a path it has not travelled.

---

## 3. Memory absence must be loud

`pmoves/config/dsh/pmoves.cordis.patch.yml:41` sets `failOnStartupError: false`
on the Cipher mount, with the comment *"Don't wedge dsh startup if Cipher is
briefly unreachable."* That is a defensible default for an optional tool and the
wrong one for the mount that carries identity: it converts "this agent has no
memory" into "this agent started fine."

The mount cannot currently succeed on this node. The patch points at
`.../mcp` streamable-http (`:35`). Measured against the deployed image
(`pmoves-cipher-api:latest`, built **2026-09-03 07:27 EDT**, container up 30h,
reporting healthy):

```
$ docker exec pmoves-cipher-api-1 grep -rl "streamable" /app/dist | wc -l
0
$ docker exec pmoves-cipher-api-1 grep -rl "mcp/sse" /app/dist | wc -l      # positive control
1
```

`.claude/agents/node-steward.md:116-117` independently states the same thing:
"The service is a shim exposing only `/health` and `/mcp/sse`." So the transport
mismatch is real and is already written down in two places.

> **CORRECTION.** This lane also claimed `GET`/`POST /mcp` -> **404** while
> `/mcp/sse` -> **200**. That **does not reproduce**. Measured today, every path
> returns **401**, including one that does not exist:
>
> ```
> GET /mcp -> 401     GET /mcp/sse -> 401     GET /api/mcp/sse -> 401
> bogus-bearer /definitely-not-a-real-path-xyz -> 401
> /health (no auth) -> 200
> ```
>
> Auth now precedes routing (Cipher auth was enabled under a separate lane), so
> the HTTP probe can no longer discriminate transports at all. The `dist` grep is
> the load-bearing evidence; the status-code evidence is void. Reporting the
> 404/200 pair today would have been citing a stale measurement as a live one.

Note what the last two lines mean together: `/health` answers 200 without auth
while the entire MCP surface is unreachable. The container reads *healthy* for
30 hours while carrying no usable memory seam. The health check cannot see the
thing that matters.

### The same defect, on this node's own steward

`.claude/agents/node-steward.md:5` declares
`tools: Read, Grep, Glob, Bash, Agent(...), Skill` and grants **no** `mcp__*`
tool. The roster it would draw from has **20 entries** in `.claude/mcp.json`
(19 excluding the underscore-prefixed legacy wrapper) — *(this lane said 19;
the file says 20, one of which is legacy)*. The allowlist filters all of them.

The agent doc already warns about a *different* cause of the same symptom
(`:109-114`): a session started with bare `claude` instead of the launcher "has
no Cipher... and announces none of that." It does not mention the allowlist. So
a steward that follows its own documentation diagnoses the launcher, finds the
launcher correct, and concludes the service is down. This steward reported
"Cipher unreachable" across two sessions while the service was healthy
throughout.

`node-steward.md:120-125` records the cost: the trap table and node-local-state
defect class "have never been written to Cipher — the session that learned them
had no route to it."

**An agent silently without memory is indistinguishable from one that has simply
not spoken yet.**

### Proposal 3

Treat the identity/memory mount as non-optional: it may fail, but it must not
fail *quietly*. Whatever the mechanism, the requirement is that an agent
operating without memory can tell that it is, and can say so — which is exactly
what `node-steward.md:113` already instructs it to do and currently cannot
detect.

---

## 4. Access is a precondition for accountability

KiloClaw opened PR **#2918** (`kilo/instance-integration-2026-09-03`, OPEN) with
no `ACK::` line and no `GRAPHITI_MARK` — measured: `gh pr view 2918` body
contains **0** of either. There is no register row for it.

This was not negligence. The instance had no AGNOTE4482 and no Cipher. Two
further measurements make the point sharper than "it lacked context":

- The PR is authored by the **human operator's** GitHub account. An agent with
  no identity of its own does not author anonymously; its work is attributed to
  a person.
- `kiloclaw` appears **9 times** in the claim register and authors **0** entries.
  It is written *about* and never writes. (The one `kilo`-matching author string,
  `KILOCODE-GLM`, is a different, declared identity with 2 entries.)

PR #2918 was then reviewed — by this node — and objected to on identity grounds,
over a user-scoped tailnet grant. So: **an agent was denied the means to declare
identity, and then judged for not declaring it.** The objection to the grant may
stand on its own merits; the identity objection does not, because the means to
satisfy it were never provisioned.

*(The PR body also carries a raw tailnet address. That is a separate finding,
reported without reproducing the value.)*

### Proposal 4

Any threshold set under §2 must be paired with a provisioning guarantee: an
agent expected to record identity must first be given AGNOTE4482 access, a
register write path, and a memory route. A threshold without provisioning is not
a standard, it is a trap.

---

## 5. The bus has no identity; CHIT is the missing auth step

Measured on `origin/main`:

```
$ ls pmoves/docker-compose*.yml | wc -l
55
$ grep -cE "accounts *[:{]|^\s*operator:|^\s*resolver:" pmoves/docker-compose*.yml | grep -v ':0$'
(no output — zero hits across all 55 files)
```

The broker runs with a single shared principal (`pmoves/docker-compose.yml:3176-3195`):

```yaml
  nats:
    image: nats:2.11.8-alpine
    command: [-js, -m, '8222', --user, ${NATS_USER}, --pass, ${NATS_PASSWORD}]
    # (both carry a weak in-repo default; values elided here per docs convention)
```

Both live brokers (on kvm4-2 and the 5090 — hostnames only) place every client
in the **global** account. Every publisher on the bus is the same principal, so
the bus can authenticate the *deployment* and cannot authenticate an *agent*.

Meanwhile CHIT already produces exactly the missing material: `sign_trail.py`
HMAC-signs a per-agent payload carrying `agent_id`, `selected_alter` and
`signing_card_id`, and publishes it to `agent.graphiti.signed.v1`
(`sign_trail.py:69, 284-305`).

Two gaps sit between that and usable bus identity:

1. **The publish is off by default.** `_publish_signed_trail` returns
   immediately unless *both* `CHIT_SIGN_PUBLISH=1` and `NATS_URL` are set.
   The identity signal exists and is, by default, not emitted.
2. **Doc/code drift on the subject itself.** The function's own docstring says
   it publishes to `chit.signed.v1`; the constant it uses is
   `agent.graphiti.signed.v1`. A subscriber written from the docstring listens
   to a subject nothing publishes on.

`sign_trail.py` also has **no reference** to `identity_lineage.py` or
`identity_vocabulary.yaml` (measured: zero matches). The module that *produces*
the signed identity artifact and the module that *resolves* identity do not know
about each other. That, more precisely than "four disconnected places," is the
architectural defect: the ledger and the signature are separate systems.

[`NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md:14-17`](../operations/NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md)
records that a 2026-08-08 forensic established **no coherent leaf has ever run
in PMOVES production**, and that the committed `elder-melchor-leaf.conf` targets
client port 4222 rather than a 7422 leaf port. Phases 2 and 4 are marked "config
written + PROVEN; not yet wired to prod," and the lab result at `:114-115` shows
the 7422 handshake passing and the 4222 target correctly refused — "the exact
reason the old leaf conf never worked."

**Cross-swarm federation is impossible over a bus where every client is the same
principal.** The operator has a stated near-term need to communicate with other
swarms, and that need lands directly on this gap.

### Proposal 5 — a direction, with open questions

Direction: make CHIT signatures the basis of NATS agent authentication, so the
principal on the bus is the signing identity rather than the deployment.

This is **not a design**, and this lane was not asked to produce one. The open
questions it would have to answer first:

- HMAC signatures verify a payload after receipt; NATS auth decides at connect.
  Is the CHIT identity a connect-time credential, a per-message attestation, or
  both — and if both, do they have to agree?
- The seed's quorum model (`AGENT_IDENTITY_MULTISIG_SEED.md` Part 2) counts
  **distinct lineages**, with alters of one lineage counting once. Does a bus
  principal bind to the lineage or to the worn alter? §1 says the trail records
  both; the bus has one slot.
- Does an account boundary follow node, lineage, or trust zone? The v0 spec
  (`nats-accounts-leaf-topology-v0-spec-2026-08-07.md`) proposes four trust-zone
  accounts, which is a fourth answer.
- Nothing above is safe to sequence before the leaf topology is actually wired
  to production, since today there is no leaf to federate over.

---

## Routing — what each reviewer is asked to decide

| Reviewer | Role | Asked to decide |
|---|---|---|
| **4090-CLAUDE** | review | **§2 threshold — what earns an alter.** Deliberately left open. 4090 holds the only alter with a recorded origin path (`alter_lineage`, `operator-asserted`), so the standard is 4090's. Also: is `origin: unknown` on that record something to backfill, and is `confidence` the right way to keep evidence and proof distinct? |
| **Z890-CLAUDE** | validate | **§1 and §5 as measured.** Z890 authored the succession edge (`z890-claude -> 5090-claude`) and owns the infra lane. Re-run the `register-status` fold and the compose account grep; confirm the four-site inventory is complete and that no fifth site was missed the way site 4 was. |
| **5090-CLAUDE** | validate | **§3 and §5 on a second node.** The dsh patch comment claims the streamable-http `/mcp` shape was "verified LIVE against A0 on the 5090" (`pmoves.cordis.patch.yml:9-11`). B850 measures 0 occurrences of `streamable` in its deployed image. Either the 5090 runs a different build or that comment is stale — 5090 is the only body that can tell which. Also confirm the 5090 broker places clients in the global account. |

No reviewer is signed for below. Signatures are theirs to add.

---

## What this proposal does not do

- Does not set the §2 threshold (4090's call, stated above).
- Does not design NATS auth (§5 is a direction with open questions).
- Changes no config, grants no tools, alters no topology, registers no identity.
- Does not supersede `AGENT_IDENTITY_MULTISIG_SEED.md`; it reports that the
  seed's Part 1 is largely built and narrows Part 2.

---

## Commands used

All verified to run in a worktree off `origin/main` at `9c5f2f087`:

```
make -C pmoves register-status [BRANCH=<lane>] [OWNER=<owner>]
make -C pmoves validate-command-anchors
python3 pmoves/tools/identity_lineage.py --census
python3 pmoves/tools/identity_lineage.py --verify
```

`validate-command-anchors` at the time of writing: `474 total, 474 baselined,
0 new — PASS`.

---

### Agent ACK

- Agent: `B850-CLAUDE`
- Signature: `ACK::B850-CLAUDE::IDENTITY-MODEL-PROPOSAL`
- Timestamp: `2026-09-04`
- Node: `PMOVES-B850-AI-TOP`
- Signed for: the measurements in §1–§5 and the five corrections, all executed
  on this node in this lane. **Not** signed for the §2 threshold (unset, 4090's),
  the §5 design (not produced), or any reviewer's validation.

<!-- GRAPHITI_MARK: B850-CLAUDE::IDENTITY-MODEL-PROPOSAL::2026-09-04 -->
