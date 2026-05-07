Wire `bpm_encoder.py` to publish CGP v0.2 packets directly to NATS on `tokenism.prosodic.bpm.v1`.

## Lane

W6-P2 · KiloCode/5090 · branch `feat/w6-tokenism-nats-5090`

## Arguments

- `$ARGUMENTS` — optional: prosodic input (text or JSON profile) to publish

## Status (verified 2026-05-06)

- ✅ `pmoves/tools/bpm_encoder.py:399-444` — `wrap_as_cgp_packet()` already returns dict ready for NATS publish on `tokenism.prosodic.bpm.v1`
- ✅ `pmoves/tools/beats_to_voice.py:127` — `_nats_publish_cgp()` already implements the publish helper for the same subject
- ❌ Branch `feat/w6-tokenism-nats-5090` does not yet exist on origin
- ❌ This brief was just authored; no PR yet

## Scope (one PR)

1. **Hoist the publish helper** out of `beats_to_voice.py` so `bpm_encoder.py` (and any future caller) can reuse it without an indirect import. Candidate destinations:
   - `pmoves/services/common/nats_cgp.py` (preferred — matches `services/common/` convention)
   - or extend `pmoves/tools/bpm_encoder.py` to expose a `publish_to_nats()` method directly
2. **Add CLI runner** to `bpm_encoder.py`:
   ```bash
   python -m pmoves.tools.bpm_encoder --bpm 90 --persona kokoro --publish
   ```
   Default subject: `tokenism.prosodic.bpm.v1`. Override via `--subject` or env `BPM_NATS_SUBJECT`.
3. **Regression test** modeled on `pmoves/tests/services/test_pr1279_fixes.py` — validate packet structure + subject match.
4. **No app/code changes outside the encoder + a thin runner** — Village Rule: one scope, one PR.

## Pre-flight

```bash
make -C pmoves up-nats               # ensure bus is up
curl -s http://localhost:4222/varz   # confirm broker reachable
git fetch origin && git checkout -b feat/w6-tokenism-nats-5090 origin/main
```

## Verification

- `nats sub tokenism.prosodic.bpm.v1` shows live JSON packet when CLI runs
- `python -m pmoves.tools.bpm_encoder --bpm 90 --persona kokoro --publish` exits 0
- `pytest pmoves/tests/tools/test_bpm_encoder_nats.py` (new file) — packet schema + subject assert
- CI green on PR (merge-gate, hardening, python-tests, CodeRabbit)

## Related

- `/chit-encode` — sibling encode-to-CGP command
- AGNOTE4482.BEATS.md — BPM math reference
- AGNOTE4482PHI.t1.md L671-686 — submodule Lane A/B specs (parallel work, not this lane)
- Memory `feedback_pipeline_bypass_self_catch.md` — never raw `docker compose`
- Memory `feedback_use_make_targets_for_builds.md` — always Make targets

## Notes

- **Reuse, don't reimplement.** The `_nats_publish_cgp` in `beats_to_voice.py` is the canonical publish helper — verified 2026-05-06 to publish on the correct subject with correct format. Hoist it.
- Pairs with §9.4 hardening signoff (`branch.{branch_name}.trail.v1` NATS pattern). Once this lane lands, §9.4 unblocks because the pattern is proven.
- DARKXSIDE co-creation attribution required in trail entry on close.
