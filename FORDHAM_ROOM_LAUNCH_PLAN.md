# Fordham Hill Community Room — Launch Plan

> **Governance Pattern:** Three-Body  
> **Stage:** Rehearsal → Live Transition  
> **Branch:** `feat/ws4-fordham-catalog`  
> **Last Updated:** 2026-07-09

---

## Owner Decisions Log

| Decision | Status | Description |
|----------|--------|-------------|
| **Decision A** | ✅ APPROVED | DARKXSIDE approved using signing card `00000000-0000-4000-8000-000000000001` as interim `creator_id` for CHIT validation. |
| **Decision B** | ✅ APPROVED | Create `fordham-steward` agent with signing card `00000000-0000-4000-8000-000000000038`. Community steward for Fordham Hill room lifecycle, vote governance, and member onboarding. |

---

## CHIT Activation Checklist

> Each item must be RESOLVED before the room can transition from rehearsal to live.  
> Resolved items are marked with ✅ and include the resolution details.  
> Items in progress are marked with 🔄. Pending items are marked with ⬜.

| # | Item | Status | Resolution / Notes |
|---|------|--------|-------------------|
| 1 | **card_id** — Valid signing identity card bound to room creator | ✅ RESOLVED | Interim: DARKXSIDE card `00000000-0000-4000-8000-000000000001` configured as `creator_id: "darkxside"` with `interim: true`, `transition_to: "fordham-steward"`. Owner Decision A approved. |
| 2 | **creator_id** — Non-null creator identity in manifest meta.chit | ✅ RESOLVED | Set to `"darkxside"` (interim). Will transition to `"fordham-steward"` when steward card is issued. |
| 3 | **interim flag** — Explicitly mark interim vs permanent creator | ✅ RESOLVED | `"interim": true` set in `meta.chit`. Clear transition path documented. |
| 4 | **transition_to** — Document successor identity for handoff | ✅ RESOLVED | `"transition_to": "fordham-steward"` set. Handoff will occur when steward agent card is created. |
| 5 | **Signing card validation** — Card exists in `signing_identity_cards.yaml` | ✅ VERIFIED | Card `00000000-0000-4000-8000-000000000001` confirmed present, `active: true`, SSH fingerprint loaded. |
| 6 | **Steward card creation** — Issue permanent `fordham-steward` signing card | ✅ RESOLVED | Card `00000000-0000-4000-8000-000000000038` created in `signing_identity_cards.yaml`. Agent signature added to `agent_signatures.yaml`. SSH fingerprint pending operator action (advisory, not blocking). Transition date: 2026-07-16. Owner Decision B approved. |
| 7 | **Signing card creation** — Create signing identity card for fordham-steward | ✅ RESOLVED | Signing card `00000000-0000-4000-8000-000000000038` added to registry with `active: true`, `role: community_steward`, `governance_scope: fordham.room.community`. H-half synced with agent_signatures.yaml. ML half (SSH) pending operator ssh-keygen. |
| 8 | **Interim→permanent handoff** — Remove `interim: true` after steward card lands | ⬜ PENDING | Blocked: awaiting #7 completion and transition_date (2026-07-16). |
| 9 | **Legal review** — DRAFT markings removed after legal sign-off | ⬜ PENDING | Room description, ballot-receipt, dues-ledger, and enrollment-roll carry `draft-legal-review` tags. |
| 10 | **Rehearsal→live transition** — Flip stage, enable ballot-receipt, emit activation CHIT | ⬜ PENDING | Final step. All above items must be RESOLVED. |

---

## Activation Sequence

```
Step 1: Configure interim creator_id                    ✅ COMPLETE
Step 2: Create fordham-steward agent signature           ✅ COMPLETE
Step 3: Create fordham-steward signing identity card     ✅ COMPLETE
Step 4: Update manifest meta.chit transition plan        ✅ COMPLETE
Step 5: Mark checklist items RESOLVED                    ✅ COMPLETE
Step 6: Interim → permanent handoff on transition_date   → PENDING (2026-07-16)
Step 7: Legal review sign-off                            → PENDING
Step 8: Transition rehearsal → live                      → PENDING
```

---

## Related Files

| File | Purpose |
|------|---------|
| `pmoves/config/rooms/fordham.room.community.json` | **Room manifest** — contains `meta.chit` block |
| `pmoves/config/rooms/catalog.json` | Room catalog entry |
| `pmoves/config/signing_identity_cards.yaml` | Signing identity registry — DARKXSIDE card verified, fordham-steward card added |
| `pmoves/config/agent_signatures.yaml` | Agent signature registry — fordham-steward signature added |
| `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` | CHIT schema (pending land) |

---

## Change Log

| Date | Change | Commit |
|------|--------|--------|
| 2026-07-09 | Add `meta.chit` with interim DARKXSIDE creator_id | `dc04dfbf` |
| 2026-07-09 | Create launch plan + activation checklist | (this file) |
| 2026-07-09 | Add fordham-steward agent signature + signing card, update transition plan, resolve checklist items 6-7 | (this update) |
