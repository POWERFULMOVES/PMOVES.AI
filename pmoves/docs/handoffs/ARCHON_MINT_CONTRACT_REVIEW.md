# Archon Mint Contract — Review

_Status: REVIEW · Produced 2026-08-01 on 4090 · Baseline: `origin/main` @ `a84787dfb`_

> Scope: what the `archon.mint.*` contract actually specifies, what is built, what breaks against
> Archon 0.6.0, and the recommended landing shape. Written because minting is a launch gate for the
> Fordham Hill pilot and the PMOVES agent factory — not a nice-to-have.

## 1. The contract as specified

Minting is a **7-step ritual** (`.claude/commands/archon/mint-agent.md`) across **four NATS subjects**:

| Subject | Role | Registered in `nats-subjects.md`? |
|---|---|---|
| `archon.mint.agent.v1` | Proposed `AgentMintSpec` | **NO** |
| `archon.qa.result.v1` | Blocking QA verdict | **NO** |
| `archon.mint.confirmed.v1` | Confirmation after QA pass | **NO** |
| `archon.mint.skill.v1` / `archon.mint.creator.v1` | Sibling rituals (skill, creator onboarding) | **NO** |

**None of the mint family is registered.** The catalog carries exactly three `archon.*` subjects —
`archon.crawl.request.v1`, `archon.crawl.result.v1`, `archon.work_order.github.v1`. See §4.1.

Flow: `collect manifest → Archon factory → QA gate → scaffold persona doc + agent def → publish mint event → confirm`.

The **payload schema is real and good**. `pmoves/docs/pilots/fordham-hill/05-room-agents-mint-specs.md`
carries five complete `AgentMintSpec` manifests (`apiVersion: archon.mint.agent.v1`, `kind: AgentMintSpec`)
with `metadata` (agent_name, room_id, stage, owning_persona, creator_id, tags) and `spec` (role, team_ref,
node_affinity, model routing, capabilities, skills, nats consume/publish, guardrails). This is a declarative
agent manifest, not a loose event — the right shape for a factory.

The **QA gate is also real** (`.claude/agents/archon-qa-agent.md`): 7 checks — schema, NATS subject
registration + branded namespace, CHIT tier declaration, name collision, branded-defaults/no-SaaS,
OAuth/Supabase identity, env tier. It publishes `archon.qa.result.v1` and blocks `mint.confirmed`.

**Assessment: the contract is well-designed. The problem is entirely on the implementation side.**

## 2. Implementation status: zero

```
$ grep -rln "archon\.mint" --include=*.py --include=*.ts pmoves/
(no matches)
```

No publisher, no subscriber, no handler anywhere in the tree. ~40 documentation references, 0 lines of
code. `mint-agent.md` is honest about this in its own Notes:

- **W1.10** — Supabase `archon_minted_artifacts` table — not built
- **W2.1** — live `archon.mint.*` subjects on the bus — not built
- **W2.2** — `archon:create-agent` MCP tool — not built

## 3. What Archon 0.6.0 changed

Step 2 of the ritual calls the Archon factory:

```bash
curl -sf -X POST http://localhost:8091/api/agents -d @/tmp/agent-manifest.json
```

On `main`, port 8091 still answers — `docker-compose.yml:3062` maps it to Archon 0.6.0's 3090 for
backward compatibility. **But every path 404s.** 0.6.0 replaced the Python agent/skill/form factory with a
TypeScript remote-coding-agent. Its surface is:

| 0.6.0 has | The mint ritual expects |
|---|---|
| `/api/workflows`, `/api/workflows/{name}/run` | `/api/agents` |
| `/api/conversations`, `/api/codebases` | `/api/forms`, `/api/skills`, `/api/prompts` |
| `/api/workflows/runs/{id}/approve\|reject\|resume` | — |
| `/api/health` | `/healthz` |

The fork also has **no NATS code at all** — no `nats` dependency, no `NATS_URL` read in any `.ts`. The
`NATS_URL` injected at `docker-compose.yml:3035` is inert. A bridge is genuinely required.

### 3.1 The key insight

Do not read this as "0.6.0 has no home for mint". **Minting an agent is a code-scaffolding operation**:
write a persona doc, write an agent definition, add a registry entry, add a team entry, open a PR.
**Archon 0.6.0 is a code-scaffolding agent** — it runs coding workflows against registered codebases with
human-in-the-loop approve/reject gates.

So the mapping is natural, not invented:

| Mint step | 0.6.0 primitive |
|---|---|
| Step 2 — factory call | `POST /api/workflows/mint-agent/run` against the PMOVES.AI codebase |
| Step 3 — QA gate | `POST /api/workflows/runs/{id}/approve` \| `/reject`, driven by `archon-qa-agent` |
| Steps 4–5 — scaffold persona doc + agent def | what the workflow actually writes |
| Step 6–7 — mint/confirmed events | bridge emits from run lifecycle |

0.6.0's HITL approve/reject is a *better* home for the QA gate than the original design — the gate becomes
a hard runtime block, not a convention.

## 4. Gaps found

### 4.1 The entire mint subject family is unregistered — BLOCKING

`.claude/context/nats-subjects.md` carries only three `archon.*` subjects: `archon.crawl.request.v1`,
`archon.crawl.result.v1`, `archon.work_order.github.v1`. Absent: `archon.mint.agent.v1`,
`archon.mint.confirmed.v1`, `archon.mint.skill.v1`, `archon.mint.creator.v1`, `archon.qa.result.v1`.

This matters twice over. `pmoves-nats-subject-audit` will flag every one as an orphan the moment a
publisher goes live. And `archon-qa-agent` check 3 requires that *every* subject an agent publishes or
consumes already appear in the catalog — so the QA gate would reject a mint manifest for using the mint
contract's own subjects. Register all five before any mint code lands.

### 4.2 The ritual produces artifacts that fail the repo's own validation gate

`make -C pmoves` runs `scripts/validate_agent_registry.py`, which requires **every agent to appear in both
`pmoves/config/agent_registry.yaml` and exactly one team in `pmoves/configs/agent-teams.yaml`**. Verified
live: `registry agents: 97 | team agents: 97`.

Mint steps 4–5 scaffold only the persona doc and the coding-agent definition. **Nothing writes the registry
or team entry.** The Fordham spec had to call this out as manual operator prerequisite #1 — which means the
ritual as documented cannot produce a valid agent without an undocumented human step.

Fix: the mint workflow must write all four artifacts (persona doc, agent def, registry entry, team entry)
in one commit, and the QA gate must run `validate_agent_registry.py` as a check.

### 4.3 Naming convention is enforced but not stated in the mint spec

The validator enforces **snake_case registry keys, kebab-case room/agent ids**. Live output shows two
pre-existing violations:

```
WARN room creator-studio.room.collab.json: owner 'creator-steward' resolves to neither
     a registry agent ('creator_steward') nor an external contributor
WARN room pmoves.room.helpdesk.json: owner 'pmoves-helpdesk-steward' → 'pmoves_helpdesk_steward'
```

`AgentMintSpec` does not state which case applies to which field. Mint will reproduce this drift at scale.

### 4.4 QA gate requires a field the schema doesn't have

`archon-qa-agent` check 4 requires the manifest to declare a **CHIT tier (Full / Partial / None)**. The
`AgentMintSpec` schema in the Fordham specs has no CHIT field — `metadata` and `spec` carry role, team_ref,
node_affinity, model, capabilities, skills, nats, guardrails, and nothing else. Every manifest written to
the current schema fails QA check 4. Either add `spec.chit_tier` to the schema or drop the check.

### 4.5 Step 0 reads a zero-access path

Step 0 instructs reading `pmoves/configs/env/.env` for `SUPABASE_URL`. That is a damage-control
zero-access path — no agent can read it. The creator-auth step needs a different source (launch env or a
declared `env.shared.example` key).

## 5. Recommended landing shape

Four increments, each independently reviewable:

1. **Register `archon.qa.result.v1`** in `nats-subjects.md`; add `spec.chit_tier` to `AgentMintSpec`;
   state the case convention per field. Docs/schema only — unblocks everything else. *(no runtime risk)*
2. **`archon-nats-bridge`** service (pattern: `pmoves/services/a2ui-nats-bridge/`, 728 LOC precedent).
   - Archon → NATS: subscribe SSE `GET /api/stream/__dashboard__`, emit `archon.task.update.v1` on run
     lifecycle and `archon.mint.confirmed.v1` when a mint-workflow run completes approved.
   - NATS → Archon: consume `archon.mint.agent.v1` → `POST /api/workflows/mint-agent/run`;
     consume `archon.qa.result.v1` → `approve`/`reject` on the pending run.
3. **`mint-agent` workflow** authored in Archon, writing all four artifacts and running
   `validate_agent_registry.py` before requesting approval.
4. **Rewrite `archon:*` skills** onto the 0.6.0 surface (`/api/health`, workflows, runs), replacing the
   dead `/api/{agents,forms,skills,prompts}` calls.

Fordham Hill's five agents (`fordham-steward`, `-onboarding`, `-transaction`, `-creator`, `-voice`) are the
first real consumer and the acceptance test for the whole chain.

## 6. What is NOT recommended

Retiring `archon.mint.*`. The contract is sound, it is the PMOVES agent-factory surface, and 0.6.0 can serve
it faithfully through workflows. The earlier read that mint "has no home in 0.6.0" was wrong — it has no
*REST resource*, which is not the same thing.

---

## Appendix — verification commands

```bash
# contract has no implementation
grep -rln "archon\.mint" --include=*.py --include=*.ts pmoves/

# qa.result unregistered
grep -n "archon.qa.result" .claude/context/nats-subjects.md

# registry/teams gate
python pmoves/scripts/validate_agent_registry.py

# 0.6.0 surface
grep -ohE "path: '/api[^']+'" PMOVES-Archon/packages/server/src/routes/api.ts | sort -u

# fork has no NATS
grep -rln "NATS_URL" --include=*.ts PMOVES-Archon/packages/
```
