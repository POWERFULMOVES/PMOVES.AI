# Fordham Hill Community Room — Launch Plan

## Rehearsal → Live Transition

**Room:** `fordham.room.community`  
**Agent ID:** `fordham-steward`  
**Current Stage:** `rehearsal`  
**Target Stage:** `live`  
**Planned Launch Date:** 2026-07-14 (7-day window from plan approval)  
**Owner Decision Required By:** 2026-07-10  
**Related Known Road:** KR-012  

---

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Author | 4090-CLAUDE |
| Reviewer | AGENT-ZERO-0 (CHIT audit) |
| Created | 2026-07-09 |
| Branch | `research/comprehensive-analysis-2026-07-09` |
| GRAPHITI_MARK | `PHI-4482::FORDHAM-LAUNCH-PLAN::2026-07-09` |

---

## 1. Pre-flight Checklist — 7 Activation Items

The checklist below is derived from `pmoves/docs/AGENTS/AGNOTE4482.md` (2026-06-30 CHIT signing-card schema carveout) and applies the 7-item room activation gate to the Fordham room's current state.

### Item-by-Item Status

| # | Checklist Item | Status | Evidence / Notes | Gate |
|---|---------------|--------|-----------------|------|
| 1 | **Valid `card_id`**: Room manifest has a valid `card_id` in `meta.chit.card_id` or the room skill has an active signing card row in `signing_identity_cards.yaml` | **FAIL** | No `creator_id` field in manifest. No `fordham-steward` entry in `signing_identity_cards.yaml`. No `meta.chit.card_id` block. | **HARD** |
| 2 | **Schema validation**: `signing-card.v1.schema.json` validates the referenced card (`card_id` UUID, `ml.primary_method` in `[ssh,gpg,github-app]`, `h.agent_id` matches registry, `active=true`) | **PASS** | Manifest validated against `room.manifest.v1.schema.json` via `Draft202012Validator`: **0 errors** (confirmed 2026-07-07, PR #1993). Note: room schema has legitimate extension fields (`p7`, app `config`, `sandbox_policy`, `multi_user`) that strict schema rejects — Owner Decision required to extend schema or conform data. | SOFT |
| 3 | **Signing card entry**: `pmoves/config/signing_identity_cards.yaml` has an entry for the room's operating agent with matching `ssh_fingerprint` / `github_app_installation_id` / `gpg_key_id` | **FAIL** | `fordham-steward` has **no card** in `signing_identity_cards.yaml`. 17 cards exist (001–037); none for `fordham-steward`. | **HARD** |
| 4 | **Sign-trail status**: `make sign-trail AGENT=<agent_id>` returns `status: signed` or `unsigned-local` advisories are explicitly accepted for the transition | **BLOCKED** | Cannot run `make sign-trail AGENT=fordham-steward` — agent has no signing card. DARKXSIDE (card `...001`) returns signed trails. Interim: DARKXSIDE can sign on behalf of steward lane. | **HARD** |
| 5 | **MCP/A2A servers**: Room's `mcp_servers` and `a2a_servers` (if any) are present in `pmoves/config/agent_registry.yaml` and reachable in the target topology mode | **PASS** | 8 service refs in manifest (`nats`, `supabase`, `agent-zero`, `archon`, `cipher-memory`, `tokenism-simulator`, `flute-gateway`, `firefly-iii`) — all registered in topology. Archon confirmed **up/healthy on 4090**. NATS subjects `fordham.*` family registered. | SOFT |
| 6 | **PGRST schema paths**: `PGRST_DB_EXTRA_SEARCH_PATH` includes the schemas the room touches; PostgREST returns HTTP 200 on a representative schema-qualified endpoint | **PASS / ADVISORY** | `pmoves` schema confirmed. `pmoves_kb` schema live (unblocked 2026-07-03 B850 standup). Representative endpoint: `GET /agent_registry` returns 200. No Fordham-specific schema required — uses shared `pmoves` schema. | SOFT |
| 7 | **CHIT toggle documentation**: `CHIT_REQUIRE_SIGNATURE` / `CHIT_DECRYPT_ANCHORS` toggles are documented in `sidecar.env` for the target topology gradient (`standalone` → `docked` → `fleet`) | **PASS** | Toggles documented in `pmoves/docs/operations/SIGNING_IDENTITY_CARDS.md` and `AGNOTE4482.md` §2026-06-30. `CHIT_REQUIRE_SIGNATURE` defaults to `advisory` (Owner-Decision D: warn, don't block). `CHIT_DECRYPT_ANCHORS` documented per topology mode. | SOFT |

### Summary: 7 Items

| Category | Count | Items |
|----------|-------|-------|
| **PASS** | 4 | #2 Schema validation, #5 MCP/A2A servers, #6 PGRST paths, #7 CHIT toggles |
| **FAIL (HARD gate)** | 3 | #1 Valid card_id, #3 Signing card entry, #4 Sign-trail status |
| **Overall** | **3/7 HARD gates blocked** | Launch blocked until Items #1, #3, #4 resolved |

---

## 2. Key Decisions Required

### Decision A: `creator_id` — Interim vs. Long-term

| Option | Approach | Pros | Cons | Recommendation |
|--------|----------|------|------|----------------|
| **A1** | **Use DARKXSIDE as interim `creator_id`** (reuse existing card `...001`) | Immediate — DARKXSIDE has active SSH card, operator-level trust, existing signature in `agent_signatures.yaml`. Unblocks launch in 24h. | Not role-segregated. DARKXSIDE is operator, not community steward. Long-term conflation of operator + room identity. | **Short-term: SELECT THIS** |
| **A2** | Create new `fordham-steward` agent + card from scratch | Clean role separation. Room has its own identity. Aligned with "shared" `owner_mode`. | Requires: new signature entry, new signing card, key generation, card validation, sign-trail test. **+2–3 days minimum**. | **Long-term: SELECT THIS** |
| **A3** | Promote existing agent (e.g., `4090-claude`) to `creator_id` | No new card needed. Immediate availability. | Wrong semantic — 4090-claude is a compute node, not a community steward. Breaks identity model. | **REJECT** |

**Recommended Decision:** Hybrid A1→A2:
1. **Now (Day 0)**: Set `creator_id: "darkxside"` in manifest as interim. Document as "interim creator — pending fordham-steward card."
2. **Day 2–3**: Create `fordham-steward` signature + card (parallel track).
3. **Day 5–7**: Transition `creator_id` from `darkxside` → `fordham-steward` post-card validation.

### Decision B: `fordham-steward` Signature — New Agent or Reuse?

| Option | Approach | Recommendation |
|--------|----------|----------------|
| **B1** | **New agent** `fordham-steward` in `agent_signatures.yaml` + new card in `signing_identity_cards.yaml` | **SELECT THIS**. The room manifest declares `agent_id: "fordham-steward"`. This agent ID must exist in the registry. Create full signature entry + card. |
| **B2** | Reuse DARKXSIDE as `fordham-steward` alias | Reject — aliases are for alters (same entity, different mode). DARKXSIDE and fordham-steward are different roles/entities. |

**`fordham-steward` proposed signature entry (to add to `agent_signatures.yaml`):**

```yaml
  fordham-steward:
    agent_id: "fordham-steward"
    display_name: "Fordham Hill Steward"
    glyph: "\u2302"              # ⌂ House — community/blueprint
    color: "#0E7490"             # Cyan-700 (matches room accent)
    accent: "#22D3EE"
    voice: companion              # warm, interactive, community-first
    co_author: "Fordham Hill Steward <fordham-steward@pmoves.ai>"
    resonance:
      - cost-pooling
      - community-mesh
      - self-governance
      - accessible-voice
      - resident-empowerment
    description: "Community steward for Fordham Hill — cost-pooling, self-governance, accessible voice. Warm companion register with plain-spoken governance protocols."
```

**`fordham-steward` proposed signing card (to add to `signing_identity_cards.yaml`):**

```yaml
  - card_id: "00000000-0000-4000-8000-000000000038"
    issued_at: "2026-07-09T00:00:00Z"
    active: true
    ml:
      primary_method: github-app
      github_app_installation_id: null   # populated from GH_APP_INSTALLATION_ID secret at runtime
    h:
      agent_id: "fordham-steward"
      display_name: "Fordham Hill Steward"
      glyph: "\u2302"        # ⌂
      color: "#0E7490"
      voice: companion
      role: community-steward
    notes: |
      Fordham Hill Community Room operating agent. Card seeded h-only;
      ML half (github_app_installation_id) populated at runtime.
      Interim: DARKXSIDE (card ...001) signs as creator_id proxy.
```

### Decision C: Vote Path — Gating Requirements

The `ballot-receipt` skill binding is `enabled: false`. This is **correct and required** for rehearsal stage. Before enabling:

| Gating Requirement | Status | Action |
|-------------------|--------|--------|
| Legal review of governance scaffold | **PENDING** | Manifest notes "DRAFT - REQUIRES LEGAL REVIEW." Blocked until `pmoves/docs/pilots/fordham-hill/04-governance-bylaws-scaffold.md` reviewed. |
| Enrollment roll has ≥1 resident | **PENDING** | `voter-roll` app is `planned` stage. Requires `enroll-roll-receipt` skill to be exercised with real consent. |
| Committee-on-elders formation | **PENDING** | Governance scaffold defines committee structure. Not yet instantiated. |
| `require_approval: true` on ballot-receipt | **PASS** | Guardrail already requires explicit approval. Even when enabled, votes require manual approval. |

**Recommendation:** Keep `ballot-receipt.enabled: false` for initial live transition. Enable only after:
1. Legal review completes (target: 2026-07-21)
2. ≥3 residents enrolled on roll
3. Committee-on-elders formed (min 2 members)
4. Separate "Vote Enable" PR approved by operator

---

## 3. Launch Steps — Rehearsal → Live Transition

### Phase 1: Pre-launch (Days 0–2)

| Step | Action | Owner | ETA | Verification |
|------|--------|-------|-----|--------------|
| 1.1 | **Owner Decision A**: Approve interim `creator_id: darkxside` | DARKXSIDE / Operator | Day 0 | ACK in this document |
| 1.2 | **Owner Decision B**: Approve `fordham-steward` agent creation | DARKXSIDE / Operator | Day 0 | ACK in this document |
| 1.3 | Add `creator_id: "darkxside"` field to `fordham.room.community.json` manifest | 4090-CLAUDE | Day 0 | `git diff` shows `creator_id` added |
| 1.4 | Add `fordham-steward` signature to `agent_signatures.yaml` | 4090-CLAUDE | Day 0 | Signature entry present, glyph unique |
| 1.5 | Add `fordham-steward` signing card (`...038`) to `signing_identity_cards.yaml` | 4090-CLAUDE | Day 0 | Card validates against schema |
| 1.6 | Add `meta.chit.card_id` block referencing `...038` to manifest | 4090-CLAUDE | Day 0 | `card_id: "00000000-0000-4000-8000-000000000038"` in manifest |
| 1.7 | Run schema validation: `python -m jsonschema -i fordham.room.community.json room.manifest.v1.schema.json` | CI / z890-claude | Day 0 | Exit code 0 |
| 1.8 | Run naming drift audit: `make naming-drift-check` | CI / z890-claude | Day 0 | No new drift |
| 1.9 | Run `make sign-trail AGENT=fordham-steward` (expect unsigned-local advisory) | 4090-CLAUDE | Day 0 | Advisory accepted, documented |
| 1.10 | Open PR with all Phase 1 changes | 4090-CLAUDE | Day 0 | PR opened, CI green |

### Phase 2: Validation (Days 2–4)

| Step | Action | Owner | ETA | Verification |
|------|--------|-------|-----|--------------|
| 2.1 | **Owner Decision C**: Approve vote-path stay-disabled | DARKXSIDE / Operator | Day 2 | ACK in this document |
| 2.2 | Code review: Three-body pattern (delivery/control/memory) | claude-opus / z890-claude | Day 2 | Review ACK in PR |
| 2.3 | Merge Phase 1 PR to `main` | Operator | Day 3 | PR merged, gitlink advanced |
| 2.4 | Deploy to 4090 staging: `make -C pmoves room-deploy ROOM=fordham.room.community` | 4090-CLAUDE | Day 3 | Container healthy, logs clean |
| 2.5 | Verify CHIT trail: `make sign-trail AGENT=fordham-steward` returns signed | 4090-CLAUDE | Day 3 | `status: signed` in output |
| 2.6 | Verify NATS subjects: `nats sub fordham.>` receives test events | 4090-CLAUDE | Day 3 | Events received, no errors |
| 2.7 | Verify Archon health: `curl http://archon:8080/health` returns 200 | 4090-CLAUDE | Day 3 | `{"status":"ok"}` |
| 2.8 | Verify PGRST endpoint: `curl /agent_registry?agent_id=eq.fordham-steward` returns 200 | 4090-CLAUDE | Day 3 | Row present, data correct |
| 2.9 | Run full smoke test suite: `make -C pmoves smoke-test-room ROOM=fordham.room.community` | 4090-CLAUDE | Day 4 | All tests pass |

### Phase 3: Live Transition (Days 5–7)

| Step | Action | Owner | ETA | Verification |
|------|--------|-------|-----|--------------|
| 3.1 | Update manifest: `stage: "live"` (replace `rehearsal` in description) | 4090-CLAUDE | Day 5 | `grep -i rehearsal` returns 0 matches |
| 3.2 | Update `catalog.json`: room summary removes "Stage: rehearsal. DRAFT" | 4090-CLAUDE | Day 5 | Summary updated |
| 3.3 | Open "Go Live" PR | 4090-CLAUDE | Day 5 | PR opened, tagged `launch/fordham` |
| 3.4 | Final review + merge | Operator | Day 6 | PR merged |
| 3.5 | Deploy to production fleet | z890-claude / P7 | Day 6 | `make -C pmoves fleet-deploy` succeeds |
| 3.6 | Verify live: `curl /api/health` on room endpoint returns 200 | 4090-CLAUDE | Day 6 | `{"status":"ok","room":"fordham.room.community","stage":"live"}` |
| 3.7 | **Post-live**: DARKXSIDE signs launch attestation trail | DARKXSIDE | Day 7 | CHIT trail entry with `signing_card_id: ...001` |
| 3.8 | **Post-live**: Announce in AGNOTE4482PHI.t1.md | 4090-CLAUDE | Day 7 | Trail entry appended |

### Phase 4: Vote-Path Enable (Future — Post Day 7)

| Step | Action | Owner | ETA | Verification |
|------|--------|-------|-----|--------------|
| 4.1 | Legal review of `04-governance-bylaws-scaffold.md` | Legal / Operator | 2026-07-21 | Document signed off |
| 4.2 | Enroll ≥3 residents via `enroll-roll-receipt` skill | fordham-steward | 2026-07-21 | Roll has 3+ entries |
| 4.3 | Form Committee-on-Elders (min 2 members) | Community / Operator | 2026-07-21 | Committee registered |
| 4.4 | Change `ballot-receipt.enabled: false → true` | 4090-CLAUDE | 2026-07-21 | `git diff` shows enabled:true |
| 4.5 | Open "Enable Voting" PR | 4090-CLAUDE | 2026-07-21 | Tagged `governance/vote-enable` |
| 4.6 | Merge after operator approval | Operator | 2026-07-28 | Vote path live |

---

## 4. Rollback Plan

### Trigger Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| CHIT signing failures in production | **P0** | Immediately revert `creator_id` to `null`, stage back to `rehearsal` |
| NATS subject flood / malformed events | **P0** | Disable `allow_nats_emit` in policies, restart room container |
| Schema validation errors post-merge | **P1** | Revert PR, re-stage to `rehearsal`, investigate in staging |
| Sign-trail advisory escalates to error | **P1** | Switch `CHIT_REQUIRE_SIGNATURE` to `false` (advisory mode), warn don't block |
| Vote path accidentally enabled | **P1** | Immediately set `ballot-receipt.enabled: false`, redeploy |

### Rollback Steps (Any P0)

```bash
# 1. Emergency stage revert (30 seconds)
sed -i 's/"live"/"rehearsal"/g' pmoves/config/rooms/fordham.room.community.json
git commit -am "rollback(fordham): emergency revert to rehearsal — P0 <ticket>"

# 2. Redeploy (2 minutes)
make -C pmoves room-deploy ROOM=fordham.room.community

# 3. Verify rollback
curl /api/health | jq '.stage'  # should return "rehearsal"

# 4. Notify (immediate)
# Post to AGNOTE4482PHI.t1.md with rollback reason + recovery plan
```

### Rollback Verification Checklist

- [ ] `stage: "rehearsal"` in manifest
- [ ] `/api/health` returns `stage: rehearsal`
- [ ] NATS `fordham.*` subjects still receiving events (no data loss)
- [ ] Notebook writeback still functioning
- [ ] CHIT trail still recording (advisory mode)
- [ ] No resident-facing errors in dashboard

---

## 5. Verification Steps — Confirm Room is Live

### Automated Verification (CI/CD)

| # | Check | Command / Endpoint | Expected Result |
|---|-------|-------------------|-----------------|
| 5.1 | Manifest stage | `jq '.stage' fordham.room.community.json` | `"live"` or field absent (default live) |
| 5.2 | Catalog entry | `jq '.rooms[] | select(.room_id=="fordham.room.community") | .summary' catalog.json` | No "rehearsal" or "DRAFT" in text |
| 5.3 | Schema validation | `make validate-room-manifest ROOM=fordham.room.community` | Exit 0 |
| 5.4 | Agent registry | `curl "/agent_registry?agent_id=eq.fordham-steward"` | HTTP 200, row present |
| 5.5 | Signing card | `python pmoves/scripts/audit_naming_drift.py --card fordham-steward` | Card found, active=true |
| 5.6 | Health endpoint | `curl http://<room-host>/api/health` | `{"status":"ok","stage":"live"}` |
| 5.7 | NATS subjects | `nats sub fordham.dashboard.request.v1 --count=1` | Receives test event within 5s |
| 5.8 | CHIT trail | `make sign-trail AGENT=fordham-steward` | `status: signed` |
| 5.9 | Archon health | `curl http://archon:8080/health` | `{"status":"ok"}` |
| 5.10 | PGRST schema | `curl "/agent_registry?select=agent_id&limit=1"` | HTTP 200 |

### Manual Verification (Operator)

| # | Check | How | Expected Result |
|---|-------|-----|-----------------|
| 5.11 | Dashboard loads | Open `/dashboard/fordham` in browser | 200 OK, no errors |
| 5.12 | Notebook accessible | Click into pilot-notebook panel | Content loads, threads visible |
| 5.13 | Voice console | Navigate to `/dashboard/voice` | TTS controls present |
| 5.14 | Skill binding trigger | Say "run the capacity A/B" in chat | `capacity-ab-probe` workflow activates |
| 5.15 | CHIT trail visible | Check `pages/honesty-ledger` in notebook | Trail entries present, signed |

---

## 6. Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `pmoves/config/rooms/fordham.room.community.json` | **EDIT** | Add `creator_id`, `meta.chit.card_id`, update `stage` → `live` |
| `pmoves/config/rooms/catalog.json` | **EDIT** | Update summary to remove "rehearsal" / "DRAFT" |
| `pmoves/config/agent_signatures.yaml` | **EDIT** | Add `fordham-steward` signature entry |
| `pmoves/config/signing_identity_cards.yaml` | **EDIT** | Add card `...038` for `fordham-steward` |
| `pmoves/docs/AGENTS/AGNOTE4482.md` | **EDIT** | Add launch record entry (this plan execution) |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | **EDIT** | CLAIM / RELEASE block for launch lane |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `fordham-steward` card creation delayed | Medium | Launch slips 2–3 days | Use DARKXSIDE interim creator_id; parallel card creation |
| Legal review blocks vote-path enable | High | Voting stays disabled | Acceptable — room is live without voting; governance activates later |
| Schema extension field rejection | Low | Manifest validation fails | Owner Decision already documented; conform data or extend schema |
| NATS subject conflict with existing fleet | Low | Event routing collision | `fordham.*` subjects are namespaced; no collision detected |
| CHIT signing failures in production | Low | Trail entries unsigned | Advisory mode (Owner-Decision D); warn, don't block |

---

## 8. Agent ACK

This plan requires ACK from three bodies (Three-Body pattern):

| Role | Agent | Signature | Status |
|------|-------|-----------|--------|
| **Delivery** | 4090-CLAUDE | `ACK::4090-CLAUDE::FORDHAM-LAUNCH-PLAN` | ✅ Draft complete |
| **Control** | AGENT-ZERO-0 | `ACK::AGENT-ZERO-0::FORDHAM-LAUNCH-REVIEW` | ⏳ Pending review |
| **Memory** | DARKXSIDE | `ACK::DARKXSIDE::FORDHAM-LAUNCH-OWNER-DECISION` | ⏳ Pending Decisions A, B, C |

---

## 9. Appendices

### Appendix A: Room Manifest Summary (Current State)

```json
{
  "room_id": "fordham.room.community",
  "version": "1.0.0",
  "display_name": "Fordham Hill Community Room",
  "agent_id": "fordham-steward",
  "alter": "fordham-community",
  "room_type": "hybrid",
  "owner_mode": "shared",
  "stage": "rehearsal",
  "apps": 5,
  "skill_bindings": 8,
  "vote_path_enabled": false,
  "schema_validation_errors": 0,
  "creator_id": null,
  "card_id": null,
  "archon_status": "up/healthy (4090)"
}
```

### Appendix B: Known Road KR-012 Reference

> "Manifest validates but stage=`rehearsal`; needs creator_id, steward signature, vote enable"

| Sub-item | Resolution Path |
|----------|----------------|
| `creator_id` | Decision A: interim DARKXSIDE → long-term fordham-steward |
| `steward signature` | Decision B: new `fordham-steward` agent + card `...038` |
| `vote enable` | Decision C: stay disabled until legal review + enrollment |

### Appendix C: Related Documents

| Document | Purpose |
|----------|---------|
| `pmoves/docs/AGENTS/AGNOTE4482.md` | Canonical AGNOTE — CHIT/room activation checklist source |
| `pmoves/docs/ROOMS_ON_A_STAGE.md` | Room lifecycle framework |
| `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` | Room manifest contract spec |
| `pmoves/config/rooms/fordham.room.community.json` | **This room's manifest** |
| `pmoves/config/agent_signatures.yaml` | Agent signature registry |
| `pmoves/config/signing_identity_cards.yaml` | Signing identity cards (5×5 trail) |
| `pmoves/docs/pilots/fordham-hill/README.md` | Fordham Hill pilot program overview |
| `pmoves/docs/pilots/fordham-hill/04-governance-bylaws-scaffold.md` | Governance bylaws (legal review pending) |

---

*GRAPHITI_MARK: 4090-CLAUDE::FORDHAM-LAUNCH-PLAN::2026-07-09*
