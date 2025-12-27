Quick health check of core services (completes in < 5 seconds).

## Implementation

Run fast parallel health checks on core services:

```bash
echo "PMOVES Core Services Status"
echo "==========================="

# Core services to check
declare -A SERVICES=(
  ["agent-zero"]="8080"
  ["archon"]="8091"
  ["hirag-v2"]="8086"
  ["tensorzero"]="3030"
  ["nats"]="4222"
  ["flute-gateway"]="8055"
)

for name in "${!SERVICES[@]}"; do
  port="${SERVICES[$name]}"
  if curl -sf "http://localhost:$port/healthz" -o /dev/null -m 2 2>/dev/null || \
     curl -sf "http://localhost:$port/health" -o /dev/null -m 2 2>/dev/null || \
     nc -z localhost "$port" 2>/dev/null; then
    echo "✅ $name (:$port)"
  else
    echo "❌ $name (:$port)"
  fi
done
```

## Notes
- Use `/health:check-all` for comprehensive checks with `make verify-all`
- Use `/health:metrics` for Prometheus metrics data
- This command is for rapid status verification only
