# Pub-Gate Bridge (PR B)

`geometry.publish.gate.v1` -> egress floor (fail-closed) -> `content.publish.approved.v1`.

## Enable
Set `PUBLISH_GATE_BRIDGE=1` (truthy: `1`/`true`/`yes`/`on`) on hi-rag-gateway-v2.
Configure the operator denylist via `EGRESS_PROTECTED_TERMS` (comma/newline list)
or `EGRESS_PROTECTED_TERMS_FILE` (a gitignored path). Unset denylist => every
publish is HELD (fail-closed) — the worker never starts without
`PUBLISH_GATE_BRIDGE` set.

## Demo (needs NATS)
    export NATS_URL=nats://nats:pmoves@localhost:4222 PUBLISH_GATE_BRIDGE=1 EGRESS_PROTECTED_TERMS=""
    make -C pmoves gate-emit ARTIFACT=s3://pmoves/reports/r1.md TITLE="Report 1"

A clean item publishes content.publish.approved.v1 (publisher then releases it);
a dirty item (LAN IP / protected term) is held with a log line and no approval.
