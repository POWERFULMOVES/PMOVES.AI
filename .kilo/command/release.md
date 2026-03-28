Release a workstream claim in AGNOTE4482PHI.t1 and sign the handoff trail.

## Arguments

- `$ARGUMENTS` - Summary of completed work

## Implementation

1. Append RELEASE entry to AGNOTE4482PHI.t1:

```text
`<ISO8601>` RELEASE `KILOCODE-GLM` scope: <matched claim scope>
```

2. Sign Graphiti trail:

```bash
make -C pmoves sign-trail SUMMARY="$ARGUMENTS" AGENT=kilocode-glm PHASE="Phase K"
```

3. Document handoff target (claude, codex, or next agent)

## Notes

- Always release before switching branches or ending session
- Per AGNOTE4482PHI.t1 — all cross-agent handoffs posted as CHIT payload references
- DARKXSIDE co-creation attribution included in all trail entries
