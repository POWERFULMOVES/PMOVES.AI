Quick health check of core PMOVES services. Completes in < 5 seconds.

## Implementation

Run fast parallel health checks on core services:

```bash
echo "PMOVES 5090 Node — Service Health"
echo "=================================="

declare -A SERVICES=(
  ["agent-zero"]="8080"
  ["archon"]="8091"
  ["hirag-v2-cpu"]="8086"
  ["tensorzero"]="3030"
  ["nats"]="4222"
  ["flute-gateway"]="8055"
  ["cipher-memory"]="8096"
)

for name in "${!SERVICES[@]}"; do
  port="${SERVICES[$name]}"
  if curl -sf "http://localhost:$port/healthz" -o /dev/null -m 2 2>/dev/null || \
     curl -sf "http://localhost:$port/health" -o /dev/null -m 2 2>/dev/null || \
     nc -z localhost "$port" 2>/dev/null; then
    echo "OK $name (:$port)"
  else
    echo "FAIL $name (:$port)"
  fi
done
```

## Remote Services (via Tailscale)

Check Z890 services if Tailscale is up:

```bash
if command -v tailscale &>/dev/null; then
  for svc in agent-zero:8080 archon:8091 tensorzero:3030 cipher:8096; do
    name="${svc%%:*}"; port="${svc##*:}"
    if curl -sf "http://100.64.0.1:$port/healthz" -o /dev/null -m 3 2>/dev/null; then
      echo "OK $name (remote :$port)"
    fi
  done
fi
```

## Notes

- Use `/smoke` for comprehensive smoke tests
- Use `/deploy:up` to start services
- GPU status: `nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader`
