Sign a Graphiti trail entry for attribution and provenance.

## Arguments

- `$ARGUMENTS` - Summary of work completed

## Implementation

```bash
make -C pmoves sign-trail SUMMARY="$ARGUMENTS" AGENT=kilocode-glm PHASE="Phase K"
```

Trail entry format:
```text
▲ KiloCode GLM | #059669 | Phase K | <timestamp>
Summary: <summary>
Source: DARKXSIDE x POWERFULMOVES on 5090
Resonance: feature-impl, mcp-integration, ...
```

## Notes

- Signing is optional locally if CHIT_PASSPHRASE is not set
- Use after multi-file changes, task completion, or agent handoff
- Per AGNOTE4482PHI.t1 — sign trail on release
- KiloCode co-creation with DARKXSIDE: always include source attribution
