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
| 6 | **CHIT schema compliance** — Manifest passes CHIT v1 schema validation | ⬜ PENDING | Schema `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` pending land. |
| 7 | **Steward card creation** — Issue permanent `fordham-steward` signing card | ⬜ PENDING | Blocked: awaiting steward agent bring-up and SSH/GPG key material. |
| 8 | **Interim→permanent handoff** — Remove `interim: true` after steward card lands | ⬜ PENDING | Blocked by #7. |
| 9 | **Legal review** — DRAFT markings removed after legal sign-off | ⬜ PENDING | Room description, ballot-receipt, dues-ledger, and enrollment-roll carry `draft-legal-review` tags. |
| 10 | **Rehearsal→live transition** — Flip stage, enable ballot-receipt, emit activation CHIT | ⬜ PENDING | Final step. All above items must be RESOLVED. |

---

## Activation Sequence

```
Step 1: Configure interim creator_id  ✅ COMPLETE
Step 2: Validate CHIT schema compliance  → PENDING
Step 3: Create fordham-steward signing card  → PENDING
Step 4: Handoff interim → permanent creator  → PENDING
Step 5: Legal review sign-off  → PENDING
Step 6: Transition rehearsal → live  → PENDING
```

---

## Related Files

| File | Purpose |
|------|---------|
| `pmoves/config/rooms/fordham.room.community.json` | **Room manifest** — contains `meta.chit` block |
| `pmoves/config/rooms/catalog.json` | Room catalog entry |
| `pmoves/config/signing_identity_cards.yaml` | Signing identity registry — DARKXSIDE card verified |
| `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` | CHIT schema (pending land) |

---

## Change Log

| Date | Change | Commit |
|------|--------|--------|
| 2026-07-09 | Add `meta.chit` with interim DARKXSIDE creator_id | `dc04dfbf` |
| 2026-07-09 | Create launch plan + activation checklist | (this file) |
