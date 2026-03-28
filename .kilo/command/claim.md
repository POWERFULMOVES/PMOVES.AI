Claim a workstream in AGNOTE4482PHI.t1 to prevent agent collision.

## Arguments

- `$ARGUMENTS` - Scope description (e.g., "W1 agent theming CLI bridge")

## Implementation

1. Read current AGNOTE4482PHI.t1 claims
2. Verify no conflicting active claims on same scope
3. Append CLAIM entry:

```
`<ISO8601>` CLAIM `KILOCODE-GLM` scope: $ARGUMENTS
```

4. Reference per AGNOTE4482 collision-avoidance protocol:
   - One owner per branch at a time
   - Update progress in PR comments and this note
   - Handoff: publish CHIT payload reference and sign ACK block

## Multi-Agent Note

On 5090, KiloCode shares the node with Claude and Codex.
Before claiming, check that neither claude-opus nor codex has an active claim on the same scope.

## Related

- `/release` — Release claim and sign trail
- `/sitrep` — Check current state
