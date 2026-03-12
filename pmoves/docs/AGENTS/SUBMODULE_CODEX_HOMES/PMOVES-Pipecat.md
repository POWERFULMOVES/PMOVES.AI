# Codex Home Overlay: PMOVES-Pipecat

Scope:
- Pipecat and Flute voice runtime parity.

Use this when:
- the task needs voice session orchestration, narration, or prosodic synthesis
- Codex must bridge persona policy into voice output
- the user journey depends on audio, TTS, or voice interaction

PMOVES companions:
- `Flute-Gateway` for prosodic synthesis and voice sessions
- `PMOVES-Ultimate-TTS-Studio` for engine/voice inventory
- `pmoves/docs/AGENTS/PERSONAS.md`
- `.claude/context/voice-personas.md`

Core checks:
- `curl -fsS http://localhost:8055/healthz | jq .`
- `curl -fsS http://localhost:7861/gradio_api/info | jq .`
- `make -C pmoves verify-all`

Related parity tokens:
- `/pipecat:status`
- `/pipecat:connect`
- `/voice:synthesize`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`
- `.claude/context/voice-personas.md`
