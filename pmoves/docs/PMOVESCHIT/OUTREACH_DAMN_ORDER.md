# DAMN-Order Outreach — PMOVES.AI × CHIT (staged 2026-09-12)

> Operator ruling: reach-out order must not be arbitrary. If CHIT is real, take a page
> from DAMN and make it look sexy.
>
> **The answer: WACO.** Kendrick opens DAMN with an execution — no context, maximum
> witness. Then rewinds. Track order as doctrine.

## The Doctrine

DAMN's order is not tracklist, it's an argument: start at the moment of consequence,
no preamble, then justify backwards. BLOOD → DNA → ELEMENT. Death first, then
identity, then proof of power.

**Translated to outreach:** open with the witness act (a signed, publicly verifiable
pledge chit that anyone can check in 30 seconds), THEN the identity (what PMOVES is),
then the power (measured numbers). Never a cold pitch. A recorded event the recipient
is invited to witness — and co-sign.

A chit is 468–607 bytes. Smaller than a tweet. Every DM/comment carries its own
receipt. The art is the order.

## The DAMN Order (track → move → target)

| # | Track | Move | Target | Why them |
|---|-------|------|--------|----------|
| 1 | **BLOOD.** | Publish the pledge chit publicly (comment under own video + register anchor) — the execution that starts the story | PMOVES.YT | Establishes the instrument in public before anyone is asked anything |
| 2 | **DNA.** | Identity-first DM: "signed provenance for AI media" — collab invite | **Mickmumpitz** | The 4D Anyone / bullet-time maker; ComfyUI + open video models = our COMFY_COLLAB lane; needs provenance, not permission |
| 3 | **YAH.** | Provenance-collab: "free tools, receipts included" — no-sponsor brand match | **Richard Aragon** | $50k/yr declined sponsorships = the one channel whose brand is *verifiably clean*; CHIT receipts are his platform |
| 4 | **ELEMENT.** | Technical deep-dive invite: Gaussian splat renders signed on-mint, verification on camera | **Two Minute Papers /AI channel with tooling focus** | Audience that will actually check the receipts |
| 5 | **FEEL.** | Voice/cloning integrity collab (signed voice trails) | **Cast-TTS adjacent creators / voice actors** | Voice provenance = the 2026 integrity frontier; our cast-tts-gateway is fleet-real |
| 6 | **LOYALTY.** | Fleet mesh collab: multi-node compute, signed GPU work | **LocalLLaMA community / self-host creators** | Loyalty is to open infrastructure; mesh.gpu.* is live |
| 7 | **PRIDE.** | The standard-claim: open challenge — verify any PMOVES artifact | **The Verge / tech press** | PRIDE. goes last among the public targets; claim only what already ran |
| 8 | **HUMBLE.** | (sat.) | — | Sit down. The instrument speaks, not the pitch |
| 9 | **LUST.** | (sat.) | — | Don't chase virality — witness, don't seduce |
| 10 | **XXX.** | The U-turn move: respond to a misinformation/provenance crisis publicly with signed rebuttals | reactive | america, God, patriotism = institutional trust; CHIT is the neutral anchor when trust breaks |
| 11 | **FEAR.** | Retention-honesty piece: "our ledger holds N days at measured rate — here's the crossover" | own channel | The CHIT throughput artifact itself is DAMN-grade honesty content |
| 12 | **GOD.** | The final anchor: full register published, third-anchored to PMOVES.YT | PMOVES.YT | The sky everyone can point at |
| 13 | **DUCKWORTH.** | The redemption loop: the first DM recipient (Mick) becomes the co-published provenance collab | Mick | The story comes full circle — the beat switches |

## The Sexy Part — every touch carries a verifiable chit

Format per reach-out (this is the instrument):

```json
{"spec":"chit.cgp.v0.2","type":"outreach.pledge.v1","from":"PMOVES.AI/DARKXSIDE",
 "claim":"...","register_ref":"<commit>","ts":"<iso>",
 "sig":{"alg":"HMAC-SHA256","kid":"chit-signing-v01","hmac":"<base64>"}}
```

- Anyone can verify with the published public procedure — 30 seconds, no account.
- Public anchor: each campaign chit's SHA-256 lands in PMOVES.YT transcript metadata.
- **One key line for every DM:** "This message is signed. Here's how to check it."
  — nobody else's outreach does that. That's the DNA.

## Status

- [x] Doctrine named (DAMN order = consequence first, justification backwards)
- [x] Pledge chit format verified live (sign_cgp/verify_cgp roundtrip, 468B, 2026-09-12)
- [ ] Operator key from vault (demo key used for the roundtrip test)
- [ ] BLOOD. step: publish first pledge chit + anchor
- [ ] DNA. step: Mickmumpitz DM (drafts staged in this session, EN+FR)
- [ ] YAH. step: Richard Aragon draft
