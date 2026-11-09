# Release Notes — Deployment-Class Registry (2026-08-27)

**PR:** #2800 · **Suit concern:** profiles/* + new pmoves/config/deployment_classes.yaml (§6.4)

## What changed
- New registry `pmoves/config/deployment_classes.yaml`: the four customer types
  (`private-mesh`, `community`, `school`, `enterprise`) with per-class
  `hosted_path` and `requires_ack_components` posture, mirroring the
  creator_models `requires_ack` gate one level up (per-deployment instead of
  per-model/per-engine).
- Profiles gain an optional top-level `deployment_class:` field. All ten known
  fleet profiles declare `private-mesh` explicitly; unset stays unset —
  loaders must not guess (declare-never-infer).
- Six coupling tests (`pmoves/tests/test_deployment_class_registry.py`):
  classes resolve, the four exist, hosted-path posture is consistent with the
  gate, fleet fully tagged, no guessed defaults.
- Ratchet baseline: 3 stale CHIT-signing entries dropped (fixed by #2799).

## Why it matters
The fleet could express license class per model and per TTS engine but not
per deployment — so "which customer type is this node?" was unanswerable and
every licensing rule (requires_ack enforcement beyond models, submodule
licensing such as jcodemunch) had no axis to key on. This is that axis.
