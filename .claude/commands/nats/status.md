# NATS Status

Check the status of the NATS JetStream message bus.

## Instructions

Check health of:
1. **NATS Server** (port 4222) - Core message broker
2. **JetStream** - Persistent streaming enabled
3. **Active streams** - List configured streams

```bash
# NATS server health
curl -s http://localhost:8222/varz | python -c "import sys,json; d=json.load(sys.stdin); print(f'NATS: {d.get(\"server_name\",\"?\")} uptime={d.get(\"uptime\",\"?\")} connections={d.get(\"connections\",0)}')"
```

```bash
# JetStream status
curl -s http://localhost:8222/jsz | python -c "import sys,json; d=json.load(sys.stdin); js=d.get('server',{}); print(f'JetStream: streams={js.get(\"total_streams\",0)} messages={js.get(\"total_messages\",0)} bytes={js.get(\"total_bytes\",0)}')"
```

```bash
# Container status
docker ps --filter "name=nats" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Server health (connected/disconnected)
- JetStream stream count and message totals
- Active connections
- Any errors in logs
