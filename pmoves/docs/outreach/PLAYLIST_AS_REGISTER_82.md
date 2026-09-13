# The 82 — Playlist as Register (staged 2026-09-12)

> Operator directive: remix the PMOVES.AI playlist — track + lyric selection mapped to
> screenshots, code, git commits, PRs. Shine light on the agents, their contributions,
> the changes over time. Show how weird the science really is. Aligned for positive
> impact vs competitors in each field: *here's my solution — how does it stack against
> yours, or where does it stack up?*
>
> DAMN order preserved (see OUTREACH_DAMN_ORDER.md): consequence first, justification
> in rewind.

## The instrument

Each track IS a chit. 82 tracks → 82 signed entries in the register. The playlist is
not promotion ABOUT the work — it IS the work, sequenced.

```
track 01 ── signed chit ── commit fdcf3d8 ── screenshot ── PR #3039
   │             │
   └─ lyric line └─ what the agent did (measured, not claimed)
```

- **Payload stays under 607B measured.** The chit signs: track id, lyric fragment
  (≤120 chars, fair-witness quoted), artifact refs (commit/PR/shot), agent name,
  measured change-over-time delta.
- **Public anchor:** playlist description carries the register root hash; each
  video/track's pinned comment carries its single chit. Anyone can verify in 30s.
- **Comparison discipline (operator's rule):** "here my solution how does it stack
  against urs" → every track maps to ONE competitor-adjacent field with a measured
  delta, never a trash claim. Stack, don't block. *Don't block — it's a better block
  for pennies.*

## Track → artifact mapping (scaffold — operator fills beat/lyric picks)

| # | Track (DAMN order) | Fleet artifact it signs | Agent spotlight | Change-over-time |
|---|---|---|---|---|
| 01 | BLOOD. | First signed trail on disk (607B) | graph-linker signer | unsigned → signed |
| 02 | DNA. | chit_signer.py + gate tests (86 green) | graph-linker | dead verify code → live consumer edge |
| 03 | ELEMENT. | init_streams.sh — 9 streams verified vs live read | nats lane | promised → measured |
| 04 | YAH. | token.work.attested.v1 + recorder service | token-stub | contract → deployable |
| 05 | FEEL. | cast-tts-gateway voice trails | cast-tts | voice without receipts → signed voice |
| 06 | LOYALTY. | mesh.gpu.* Spark/5090/ROCm | SparkClaw, NemotronClaw | idle GPUs → mesh |
| 07 | PRIDE. | validate_streams.py + CI gate | nats lane | silent discard → guarded |
| 08 | XXX. | THIRD_ANCHOR_DOCTRINE | darkxside | trust → checkable |
| 09 | FEAR. | CHIT throughput artifact (retention crossover) | kilo/main | doom ladder → honest crossover |
| 10 | GOD. | PMOVES.YT anchor + chit-tour-data | chit-tour | docs → live projection |
| 11 | DUCKWORTH. | Mick/Aragon collab branch (pending) | outreach lane | DM → co-publish |
| … | (fill: 82 total) | operator picks beats → maps to PR log | — | — |

## Filling procedure

1. Operator: pick track + lyric line (30–60s clip max, fair use short).
2. Agent (me): map to strongest artifact for that theme from git log / PR list /
   screenshot bank; emit chit; pin to track comment + register.
3. Weekly burn-down: 82 tracks = 82 weeks max; ship in DAMN order until the catalog
   is the register.

## Status

- [x] Doctrine: playlist = register, DAMN order, stack-don't-block
- [x] Chit format verified (468B roundtrip, 2026-09-12)
- [ ] Operator track/lyric picks (blocked on operator session)
- [ ] Screenshot bank ingest (Discord DMs → media store)
- [ ] Campaign signing key from vault
