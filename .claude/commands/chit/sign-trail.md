# CHIT Sign Trail

Sign a Graphiti trail entry with CHIT HMAC for agent attribution and provenance.

## Arguments

- `$ARGUMENTS` - Summary of the work being signed (text string)

## Instructions

1. Parse `$ARGUMENTS` as the summary text.  If empty, use "Trail entry signed" as default.
2. Try signing via Make target (preferred — uses env-bootstrap):
   ```bash
   make -C pmoves sign-trail SUMMARY="<summary>" AGENT="${AGENT:-claude-opus}" PHASE="${PHASE:-Phase H}"
   ```
3. If Make is unavailable, fall back to direct Python invocation:
   ```bash
   python pmoves/tools/sign_trail.py --agent-id "${AGENT:-claude-opus}" --summary "<summary>" --phase "${PHASE:-Phase H}"
   ```
4. Report to the user:
   - Signed payload summary (agent, glyph, phase, timestamp)
   - HMAC kid (first 16 hex chars of SHA-256 of passphrase) — or "unsigned" if `CHIT_PASSPHRASE` not set
   - Whether `graphiti_signed_latest.json` was written
   - NATS publish status (if `nats` CLI available)

## Example

```bash
# Sign a trail entry for completed security audit
/chit:sign-trail "Completed Phase C security audit for Agent Zero"

# Sign with custom agent and phase
AGENT=codex PHASE="Phase G" /chit:sign-trail "Merged 12 PRs"

# Pipe JSON payload
echo '{"agent_id":"gemini","summary":"Research complete"}' | python pmoves/tools/sign_trail.py --stdin
```

## Related

- `/chit:encode` - Encode data as CGP v2 packet
- `/chit:floos` - FlOO$ linked skill pipelines
- `/chit:bus` - Publish to GEOMETRY BUS
- `pmoves/config/agent_signatures.yaml` - Agent glyph/color registry
- `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` - Payload schema
