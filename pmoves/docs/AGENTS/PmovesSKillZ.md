# PMOVES SkillZ (Codex + Agent Tooling)
_Last updated: 2026-02-15_

This file tracks PMOVES-specific skill intent so Codex/agents can operate
consistently across submodules and production-audit workflows.

## Skill bundles

1. `bringup-audit`
- Purpose: tiered bring-up, smoke validation, and evidence capture.
- Inputs: Make targets, service health endpoints, CI failure logs.
- Output: pass/fail matrix + remediation queue.

2. `secrets-chit-funnel`
- Purpose: map secrets stores into CHIT manifests without cleartext commits.
- Inputs: GitHub secrets, vault labels, supabase runtime values.
- Output: synced manifest + verification report.

3. `submodule-parity`
- Purpose: ensure PMOVES overlays align with upstream submodule capabilities.
- Inputs: `.gitmodules`, integration contracts, overlay docs.
- Output: parity audit + missing mapping report.

4. `persona-grounding`
- Purpose: transform source materials into grounded persona anchors.
- Inputs: `pmoves/docs/context` artifacts + approved ingest sources.
- Output: anchor mappings + persona policy metadata.

5. `multimodal-verifier`
- Purpose: verify tool execution using text + audio + VLM checks.
- Inputs: logs, metrics, screenshots/video frames, service outputs.
- Output: verification evidence bound to task/run id.

## Operator expectations

- Prefer `open-chat+scout` while requirements are uncertain.
- Switch to `focus` for implementation and validation.
- Never finalize without concrete command evidence.

For runtime behavior details, see:
- `pmoves/docs/AGENTS/CODEX_RUNTIME_PROTOCOL.md`
- `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`

