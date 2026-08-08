# pmoves-nats-mcp — usage examples (v0.2, §7b)

Two-layer trust: the **NATS account** (via a CORE `.creds` file) gates transport;
the **CHIT signature** (via the canonical signer) gates payload provenance. The
MCP never fakes a signature — it signs only when the real signer succeeds, else
marks the message `X-CHIT-Signed: false`.

## `.claude/mcp.json` wiring (CORE-bound + canonical signer)

```json
"pmoves-nats-fleet": {
  "command": "uv",
  "args": ["--directory", "./pmoves-nats-mcp", "run", "python", "-m", "nats_mcp.server"],
  "env": {
    "NATS_URL": "nats://<Z890_TS_HOST>:4222",
    "NATS_CREDS": "${CHIT_VAULT}/nats/core-service.creds",
    "PYTHONPATH": "${PMOVES_ROOT}"
  }
}
```

- `NATS_CREDS` → binds to the **CORE account** (replaces the legacy `nats:pmoves`
  plaintext in `NATS_URL`). When unset, falls back to the URL creds (back-compat).
- `PYTHONPATH=<repo root>` → lets the MCP import the **canonical** signer
  `pmoves.tools.chit_security.sign_cgp`. Without it, CHIT-aware publishes go out
  `X-CHIT-Signed: false` (honest unsigned-local), never fake-signed.

## Raw publish (non-CHIT subject)

```
nats_publish(subject="archon.mint.agent.v1", payload="{\"agent\":\"demo\"}")
→ {"published": true, "chit_signed": false, "account": "CORE"}
```

## CHIT-signed publish (auto on CHIT-aware subject)

```
nats_publish(subject="tokenism.prosodic.bpm.v1", payload="{\"bpm\":90,\"anchors\":[...]}")
→ {"published": true, "chit_signed": true, "account": "CORE"}     # signer + key present
→ {"published": true, "chit_signed": false, "account": "CORE",
   "chit_note": "canonical sign_cgp failed (no passphrase?): ..."}  # unsigned-local, honest
```

## Force-sign a non-CHIT subject

```
nats_publish(subject="mesh.report.v1", payload="{...CGP...}", sign=true)
```

## Subscribe (shows the trust header)

```
nats_subscribe(subject="tokenism.prosodic.>", timeout_seconds=10)
→ messages[].chit_signed == "true" | "false"   # verify the two-layer gate at the consumer
```

## Acceptance (spec §10)

- Signed publish yields a CHIT-verifiable CGP (`verify_cgp` at the consumer).
- An unsigned CHIT-aware message crosses transport (account allowed it) but fails
  CHIT verification — proving the two layers are independent.
