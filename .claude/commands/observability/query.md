# Observability Query

Query Prometheus metrics or Loki logs for service observability.

## Instructions

The user should specify what to query:
1. **Prometheus metrics** — PromQL query against port 9090
2. **Loki logs** — LogQL query against port 3100

### Prometheus examples:

```bash
# Service uptime
curl -s 'http://localhost:9090/api/v1/query?query=up' | python -c "
import sys, json
d = json.load(sys.stdin)
for r in d.get('data',{}).get('result',[]):
    job = r['metric'].get('job','?')
    val = r['value'][1]
    print(f'{job}: {\"UP\" if val==\"1\" else \"DOWN\"}')
"
```

```bash
# Request rate (last 5 min)
curl -s 'http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])' | python -c "
import sys, json
d = json.load(sys.stdin)
for r in d.get('data',{}).get('result',[]):
    print(f'{r[\"metric\"]}: {float(r[\"value\"][1]):.2f} req/s')
"
```

### Loki examples:

```bash
# Recent error logs
curl -s 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={level="error"}' \
  --data-urlencode 'limit=10' \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000"
```

Report the query results in a readable format.
