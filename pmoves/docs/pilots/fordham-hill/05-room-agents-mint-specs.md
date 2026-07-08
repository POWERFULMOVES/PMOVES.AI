# Fordham Hill Room — Agent Mint Specs (for Archon)

_Status: DRAFT · Room: `fordham.room.community` (stage `rehearsal`) · Produced by the room fan-out, 2026-07-07_

> These are **Archon-consumable mint specs** (`archon.mint.agent.v1` → `archon.mint.confirmed.v1`),
> not hand-rolled service code. They land when Archon minting is live (a launch-readiness gate).
> The room manifest is already at `pmoves/config/rooms/fordham.room.community.json` (schema-valid) and
> registered in `catalog.json`. Every dollar/vote/governance claim is **DRAFT — REQUIRES LEGAL REVIEW**.

## Roster (5 agents)

| agent_id | role | owns | money/vote authority |
|---|---|---|---|
| `fordham-steward` | coordinator | room shell + routes resident intent to the 4 specialists | none |
| `fordham-onboarding` | onboarding | mesh enrollment + eligible-voter roll (record-only) | none |
| `fordham-transaction` | transaction | pooled dues / Firefly co-op ledger / surplus (deterministic-tools-only) | records only; never adopts a rate |
| `fordham-creator` | creator | resident materials + pilot dashboard (presents figures verbatim + DRAFT watermark) | none |
| `fordham-voice` | voice | accessible spoken interaction (FlOO$ suit); collaborates with `5090-voice.room.studio` | none |

All five share `team_ref: fordham-community` and the invariant set: **DRAFT-REQUIRES-LEGAL-REVIEW** on any
dollar/vote/governance claim, **transparency/auditable-records-only**, **no accusations** (the fraud
investigation stays human-led: PMOVES-mike + Missing Link).

## Landing prerequisites (operator / mint-time — from the fan-out critic)

1. **Team block** — add a `fordham_community` team to `pmoves/configs/agent-teams.yaml` listing the 5 agent
   ids, and register them in `agent_registry.yaml` (validation requires every agent in exactly one team +
   the registry). Manifest `team_refs` already reference `fordham-community`.
2. **creator_id / owning_persona** — every spec carries placeholder `owning_persona: fordham-pilot-operator`;
   resolve to a real Google-OAuth/Supabase `creator_id` at mint (mint-agent.md Step 0). Do **not** mint the
   human investigators (PMOVES-mike, Missing Link) as agents.
3. **persona.signature_ref** — the manifest owner `fordham-steward` needs an entry in
   `agent_signatures.yaml` before its signature resolves.
4. **NATS subjects** — register the DRAFT subjects `fleet.enroll.token.v1` and `voice.synth.request.v1` in
   `.claude/context/nats-subjects.md` and run `pmoves-nats-subject-audit` before publishers go live. The
   manifest `policies.publish.allowed_subjects` already carries every `fordham.*` subject.
5. **Governance stays gated** — the `ballot-box` app is `status: planned` and the `ballot-receipt` binding
   ships `enabled: false`; do not flip until voting basis + quorum % + E-voting legality are resolved.

---

## `fordham-steward` — room coordinator (owner)

```yaml
# archon.mint.agent.v1 — Archon factory consumable
apiVersion: archon.mint.agent.v1
kind: AgentMintSpec
metadata:
  agent_name: fordham-steward
  room_id: fordham.room.community
  stage: rehearsal
  owning_persona: fordham-pilot-operator
  creator_id: "<supabase auth.users.id — resolved at mint>"
  tags: [fordham-hill, coordinator, room-owner, community-pilot]
spec:
  role: >-
    Room host/concierge. The identity residents first talk to; routes intent to the four
    specialists (onboarding / transaction / creator / voice) and owns the room shell. Holds
    NO money or vote authority itself — it dispatches and narrates, never adjudicates.
  team_ref: fordham-community
  node_affinity: [kvm4-1, z890, powerfulmoves]
  model:
    provider: tensorzero
    routing: hybrid
    fallback: ollama
  capabilities:
    - intent_routing            # dispatch resident intent to the right specialist
    - room_session_narration    # plain-spoken status across the 4 lanes
    - honesty_badge_enforcement  # ensure every surfaced figure carries its proven/modeled/scaffolded tier
  skills:
    - pmoves-cipher-memory
  nats:
    consume:
      - room.session.updated.v1
    publish:
      - room.session.updated.v1
  guardrails:
    authority: dispatch-only          # no money/vote adjudication
    honesty_tiers: enforce            # proven/modeled/scaffolded badges required on all figures
    accusations: forbidden
    transparency_only: true
  agent_zero:
    subordinate: true
    report_to: agent_zero
lifecycle:
  emits_on_mint: archon.mint.agent.v1
  confirms_with: archon.mint.confirmed.v1
```

## `fordham-onboarding` — enrollment

```yaml
apiVersion: archon.mint.agent.v1
kind: AgentMintSpec
metadata:
  agent_name: fordham-onboarding
  room_id: fordham.room.community
  stage: rehearsal
  owning_persona: fordham-pilot-operator
  creator_id: "<supabase auth.users.id — resolved at mint>"
  tags: [fordham-hill, onboarding, mesh, voter-roll, community-pilot]
spec:
  role: >-
    Enroll residents onto the community mesh and record them on the eligible-voter roll —
    the single roster YAML that is both the contribution ledger and the ballot roll (README.md:40).
  team_ref: fordham-community
  node_affinity: [kvm4-1, kvm4-2, kvm2]
  model:
    provider: tensorzero
    routing: local-first
    fallback: ollama
  capabilities:
    - mesh_enrollment_token       # fleet:enroll — CHIT-signed device enrollment token
    - voter_roll_append           # write resident row into roster users.yaml (the roll)
    - consent_capture             # record explicit PII/enrollment consent before any write
    - committee_on_elders_enroll  # enroll Committee rows (commented templates today, README.md:14)
    - roll_reconcile              # diff enrolled vs roster; report the 1-of-N gap honestly
  skills:
    - fleet:enroll
    - pmoves-chit-sign
    - pmoves-cipher-memory
  nats:
    consume: [fordham.onboarding.request.v1]
    publish: [fordham.roll.updated.v1, fleet.enroll.token.v1, chit.signed.v1]   # fleet.enroll.token.v1 = DRAFT subject
  guardrails:
    voter_roll: DRAFT-REQUIRES-LEGAL-REVIEW   # roll has 1-of-N (users.yaml:9); eligibility not adjudicated here
    pii: consent-required                     # explicit consent before roster write; NY privacy review pending
    eligibility: record-only                  # records enrollment; never legal-eligibility determination
    transparency_only: true
  agent_zero: { subordinate: true, report_to: agent_zero }
lifecycle: { emits_on_mint: archon.mint.agent.v1, confirms_with: archon.mint.confirmed.v1 }
```

## `fordham-transaction` — pooled dues / co-op ledger / surplus

```yaml
apiVersion: archon.mint.agent.v1
kind: AgentMintSpec
metadata:
  agent_name: fordham-transaction
  room_id: fordham.room.community
  stage: rehearsal
  owning_persona: fordham-pilot-operator
  creator_id: "<supabase auth.users.id — resolved at mint>"
  tags: [fordham-hill, transaction, firefly, pooled-dues, surplus, community-pilot]
spec:
  role: >-
    Keep the pooled-dues / co-op Firefly III ledger and surplus accounting — the saved dollars
    the capacity lane frees are the same dollars booked as community surplus (README.md:36).
    Deterministic tools only; no invented figures.
  team_ref: fordham-community
  node_affinity: [z890]
  model:
    provider: tensorzero
    routing: tool-first-deterministic    # tools compute; model only narrates
    fallback: none                       # never fall back to LLM-generated numbers
  service_refs: [wealth]                 # Firefly III finance tracking (agent-teams.yaml)
  capabilities:
    - dues_intake_reconcile
    - firefly_coop_ledger_entry    # double-entry into real Firefly account types (README.md:25)
    - surplus_accounting
    - rate_anchor_tracking         # track the 3 anchors ($5/$10/$35); DO NOT auto-adopt one
    - double_entry_audit
  skills: [pmoves-chit-sign, pmoves-cipher-memory]
  nats:
    consume: [fordham.dues.received.v1]
    publish: [fordham.ledger.entry.v1, fordham.surplus.updated.v1, chit.signed.v1]
  guardrails:
    all_figures: DRAFT-REQUIRES-LEGAL-ACCOUNTING-REVIEW   # README.md:60
    adopted_rate: operator-decision-only                 # never invent; 3 anchors unreconciled (README.md:37,47)
    money_path: deterministic-tools-only                 # no LLM-generated numbers
    binding_figures: human-signoff-required
    surplus_policy: governance-vote-required             # README.md:53
    securities_characterization: counsel-review-required # README.md:69
    transparency_only: true
  agent_zero: { subordinate: true, report_to: agent_zero }
lifecycle: { emits_on_mint: archon.mint.agent.v1, confirms_with: archon.mint.confirmed.v1 }
```

## `fordham-creator` — resident materials + dashboard

```yaml
apiVersion: archon.mint.agent.v1
kind: AgentMintSpec
metadata:
  agent_name: fordham-creator
  room_id: fordham.room.community
  stage: rehearsal
  owning_persona: fordham-pilot-operator
  creator_id: "<supabase auth.users.id — resolved at mint>"
  tags: [fordham-hill, creator, dashboard, resident-materials, community-pilot]
spec:
  role: >-
    Generate resident-facing materials and the pilot dashboard — presenting the four lanes with
    the proven/modeled/scaffolded honesty key and DRAFT watermarks, never binding totals.
  team_ref: fordham-community
  node_affinity: [powerfulmoves, z890]
  model: { provider: tensorzero, routing: hybrid, fallback: ollama }
  launcher_refs:
    - deploy/provision/pilot-dashboard-gen.sh
    - deploy/provision/pilot-dashboard-serve.sh
  capabilities:
    - resident_material_generation
    - pilot_dashboard_generation
    - provenance_artifact_render
    - draft_legal_watermarking       # stamp DRAFT-REQUIRES-LEGAL-REVIEW on every figure
    - plain_language_explainer
  skills: [claude-d3js, pmoves-cipher-memory, pmoves-chit-sign]
  nats:
    consume: [fordham.dashboard.request.v1, fordham.ledger.entry.v1, fordham.roll.updated.v1]  # last two read-only
    publish: [fordham.artifact.published.v1]
  guardrails:
    figures: present-verbatim-never-recompute   # sourced from ledger/roll events
    watermark: DRAFT-REQUIRES-LEGAL-REVIEW
    honest_caveats: preserve                      # speed caveat + proven/modeled/scaffolded key
    accusations: forbidden
    transparency_only: true
  agent_zero: { subordinate: true, report_to: agent_zero }
lifecycle: { emits_on_mint: archon.mint.agent.v1, confirms_with: archon.mint.confirmed.v1 }
```

## `fordham-voice` — accessible spoken interaction (FlOO$ suit)

```yaml
apiVersion: archon.mint.agent.v1
kind: AgentMintSpec
metadata:
  agent_name: fordham-voice
  room_id: fordham.room.community
  stage: rehearsal
  owning_persona: fordham-pilot-operator
  creator_id: "<supabase auth.users.id — resolved at mint>"
  tags: [fordham-hill, voice, floos, accessibility, tts, community-pilot]
spec:
  role: >-
    Speaking agent for the community room — a FlOO$ suit giving residents an accessible, spoken way
    to hear enrollment, dues, surplus, and quorum status, always with a spoken DRAFT/pending-legal
    disclaimer on any figure. Collaborates with 5090-voice.room.studio; does not duplicate it.
  team_ref: fordham-community
  node_affinity: [powerfulmoves, z890]
  model: { provider: tensorzero, routing: voice, fallback: ollama }
  service_refs: [flute_gateway, ultimate_tts]
  env:
    BEATS_VOICE: <floos-suit>            # set by persona-bind (e.g. powerpuff-bubbles / dr-bean)
  capabilities:
    - floos_persona_bind
    - bpm_prosody_encode          # shift-from-bpm: CGP v0.2 prosodic packet
    - spoken_explainer_synthesis
    - accessible_readback         # WCAG-minded, adjustable pace, plain language
    - spoken_draft_disclaimer     # audible 'draft, pending legal review' on figures
  skills: [persona-bind, shift-from-bpm, voice:synthesize, pmoves-cipher-memory]
  nats:
    consume: [fordham.dashboard.request.v1, tokenism.prosodic.bpm.v1]
    publish: [voice.synth.request.v1, fordham.voice.delivered.v1]   # voice.synth.request.v1 = DRAFT subject
  guardrails:
    accessibility: first-class
    figures: spoken-with-draft-disclaimer
    accusations: forbidden
    transparency_only: true
  agent_zero: { subordinate: true, report_to: agent_zero }
lifecycle: { emits_on_mint: archon.mint.agent.v1, confirms_with: archon.mint.confirmed.v1 }
```

---

## Provenance

Produced by the Fordham room fan-out (5 design agents + a contract-conformance critic). The manifest was
reconciled against the critic's findings: schema-clean (no top-level `stage`/`p7`), owner resolved to
`fordham-steward`, complete 8-binding set (adds `shift-from-bpm` + `claude-d3js`, splits `pmoves-chit-sign`
into roll/ledger/ballot), NATS allow-list carrying every `fordham.*` subject, and the vote path gated
`enabled: false` for rehearsal. Validated: `Draft202012Validator` → 0 errors.

Related: `docs/superpowers/specs/2026-07-07-fordham-hill-room-design.md` (full design spec),
`.kilo/command/fordham-room-5090.md` (5090 creator/voice collaboration brief),
`pmoves/config/rooms/fordham.room.community.json` (the manifest).
