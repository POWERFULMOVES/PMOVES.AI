Wire `bpm_encoder.py` to publish CGP v0.2 packets directly to NATS on `tokenism.prosodic.bpm.v1`.

## Lane

W6-P2 · KiloCode/5090 · branch `feat/w6-tokenism-nats-5090`

## Arguments

- `$ARGUMENTS` — optional: prosodic input (text or JSON profile) to publish

## Status (closed 2026-05-08)

- ✅ `pmoves/tools/bpm_encoder.py:399-444` — `wrap_as_cgp_packet()` already returns dict ready for NATS publish on `tokenism.prosodic.bpm.v1`
- ✅ `pmoves/tools/beats_to_voice.py:127` — `_nats_publish_cgp()` already implements the publish helper for the same subject
- ✅ Branch `feat/w6-tokenism-nats-5090` shipped via PR #1425
- ✅ `bpm_encoder.py` now exposes `encode --publish`, `--subject`, and `--persona`; tests live in `pmoves/tests/tools/test_bpm_encoder_nats.py`

## Delivered Scope

1. **Hoist the publish helper** out of `beats_to_voice.py` so `bpm_encoder.py` (and any future caller) can reuse it without an indirect import. Candidate destinations:
   - Delivered in `pmoves/services/common/nats_client.py`
2. **Add CLI runner** to `bpm_encoder.py`:
   ```bash
   python -m pmoves.tools.bpm_encoder encode --bpm 90 --persona kokoro --publish
   ```
   Default subject: `tokenism.prosodic.bpm.v1`. Override via `--subject` or env `BPM_NATS_SUBJECT`.
3. **Regression test** in `pmoves/tests/tools/test_bpm_encoder_nats.py` — validate helper import, packet structure, CLI flags, and subject handling.
4. **No app/code changes outside the encoder + thin shared helper** — Village Rule preserved.

## Pre-flight

Historical brief only. Do not create a new `feat/w6-tokenism-nats-5090` branch for this lane.

## Verification

- `nats sub tokenism.prosodic.bpm.v1` shows live JSON packet when CLI runs
- `python -m pmoves.tools.bpm_encoder encode --bpm 90 --persona kokoro --publish` exits 0
- `pytest pmoves/tests/tools/test_bpm_encoder_nats.py` — packet schema + subject assert
- CI green on PR #1425

## Related

- `/chit-encode` — sibling encode-to-CGP command
- AGNOTE4482.BEATS.md — BPM math reference
- AGNOTE4482PHI.t1.md L671-686 — submodule Lane A/B specs (parallel work, not this lane)
- Memory `feedback_pipeline_bypass_self_catch.md` — never raw `docker compose`
- Memory `feedback_use_make_targets_for_builds.md` — always Make targets

## Notes

- **Reuse, don't reimplement.** The reusable publish helper now lives in `pmoves/services/common/nats_client.py`.
- Pairs with §9.4 hardening signoff (`branch.{branch_name}.trail.v1` NATS pattern). This lane proves the publish pattern; CHIT trail wiring remains its own implementation path.
- DARKXSIDE co-creation attribution carried in PR #1425 trail.
