# pmoves_voice_router

Voice routing scaffold for the PMOVES voice layer: one entrypoint that selects
between the three engine families (OmniVoice, Flute, UTTS) and builds provider
requests. Scaffold phase per CLAIM 2026-10-11T09:25:00Z (register:
`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`).

- Config is env-only (`*_API_KEY` never logged, never in errors — redaction
  guard on every payload, same house pattern as `pmoves-titanmail-mcp`).
- Clients expose pure request-builders that are unit-testable without network.
- Live HTTP wiring is DEFERRED to the 5090 voice-layer lane (voice-layer-5090
  skill owns engine bring-up; this package owns routing policy).

## Env vars (names only, never values in repo)

| Var | Purpose |
| --- | --- |
| `default` param on `build_route()` | fallback engine when no hint/keyword matches (code param, not env var) |
| `OMNIVOICE_BASE_URL` / `OMNIVOICE_API_KEY` | OmniVoice endpoint + key |
| `FLUTE_BASE_URL` / `FLUTE_API_KEY` | Flute relay endpoint + key |
| `UTTS_BASE_URL` / `UTTS_API_KEY` | Ultimate TTS Studio endpoint + key |

## Tests

```bash
python -m pytest pmoves_voice_router/tests -q  # from repo root; conftest bootstraps sys.path
```