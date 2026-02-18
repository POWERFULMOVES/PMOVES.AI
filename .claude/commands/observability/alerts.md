# Observability Alerts

Check active Prometheus alerts and alerting rules.

## Instructions

Query Prometheus for active alerts and alerting rules:

```bash
# Active alerts
curl -s http://localhost:9090/api/v1/alerts | python -c "
import sys, json
d = json.load(sys.stdin)
alerts = d.get('data', {}).get('alerts', [])
if not alerts:
    print('No active alerts')
else:
    for a in alerts:
        print(f'[{a.get(\"state\",\"?\")}] {a.get(\"labels\",{}).get(\"alertname\",\"?\")} - {a.get(\"annotations\",{}).get(\"summary\",\"no summary\")}')
"
```

```bash
# Alerting rules
curl -s http://localhost:9090/api/v1/rules | python -c "
import sys, json
d = json.load(sys.stdin)
groups = d.get('data', {}).get('groups', [])
for g in groups:
    print(f'Group: {g.get(\"name\",\"?\")}')
    for r in g.get('rules', []):
        state = r.get('state', '?')
        name = r.get('name', '?')
        print(f'  [{state}] {name}')
"
```

Report:
- Active firing alerts with severity
- Pending alerts approaching threshold
- Alert rule health (active vs inactive groups)
