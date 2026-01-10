# Kubernetes Logs

Stream or search logs from PMOVES services in Kubernetes.

## Usage

```
/k8s:logs <service> [options]
```

## Arguments

- `service`: Service name or pod name (required)
- `options`: `--tail`, `--since`, `--previous`, `--container`

## What This Command Does

1. **Stream Live Logs:**
   ```bash
   # Follow logs from deployment
   kubectl logs -f deployment/<service> -n pmoves

   # From specific pod
   kubectl logs -f <pod-name> -n pmoves
   ```

2. **Historical Logs:**
   ```bash
   # Last 100 lines
   kubectl logs deployment/<service> -n pmoves --tail=100

   # Since timestamp
   kubectl logs deployment/<service> -n pmoves --since=1h
   ```

3. **Previous Container Logs:**
   ```bash
   # Logs from crashed container
   kubectl logs <pod-name> -n pmoves --previous
   ```

4. **Multi-Container Pods:**
   ```bash
   # Specific container
   kubectl logs <pod-name> -c <container-name> -n pmoves

   # All containers
   kubectl logs <pod-name> -n pmoves --all-containers
   ```

## Log Aggregation (Loki)

PMOVES uses Loki for centralized log aggregation:

```bash
# Query via LogCLI
logcli query '{namespace="pmoves",app="agent-zero"}' --limit=100

# Via Grafana Explore
# URL: http://localhost:3000/explore
# Query: {namespace="pmoves"} |= "error"
```

### Common LogQL Queries

```logql
# All errors in namespace
{namespace="pmoves"} |= "error" | json

# Specific service logs
{namespace="pmoves", app="agent-zero"} | json | level="error"

# Request tracing
{namespace="pmoves"} |= "request_id" | json | request_id="abc123"

# Slow requests (>1s)
{namespace="pmoves", app="hi-rag"} | json | latency_ms > 1000
```

## Output Format

```markdown
## Logs: agent-zero

### Source
- **Deployment:** agent-zero
- **Namespace:** pmoves
- **Pods:** 3 replicas
- **Time Range:** Last 1 hour

### Log Stream
```
2025-06-07T12:00:01Z [INFO] Server started on :8080
2025-06-07T12:00:02Z [INFO] Connected to NATS at nats://nats:4222
2025-06-07T12:00:05Z [INFO] MCP endpoint ready at /mcp
2025-06-07T12:01:15Z [INFO] Received task: research_query
2025-06-07T12:01:16Z [DEBUG] Delegating to hi-rag service
2025-06-07T12:01:45Z [INFO] Task completed: research_query (29.5s)
```

### Statistics
- **Total Lines:** 1,247
- **Errors:** 3
- **Warnings:** 12
- **Info:** 1,232
```

## Example

```bash
# Stream live logs
/k8s:logs agent-zero

# Last 50 lines
/k8s:logs agent-zero --tail=50

# Logs from last hour
/k8s:logs agent-zero --since=1h

# Previous crashed container
/k8s:logs agent-zero --previous

# Specific container in multi-container pod
/k8s:logs tensorzero --container=gateway

# All pods matching label
/k8s:logs -l app=hi-rag
```

## Log Levels

PMOVES services use structured logging:

| Level | When Used |
|-------|-----------|
| DEBUG | Detailed debugging (disabled in prod) |
| INFO | Normal operation events |
| WARN | Recoverable issues |
| ERROR | Operation failures |
| FATAL | Unrecoverable errors (triggers restart) |

## Filtering Patterns

### By Log Level
```bash
# Errors only
kubectl logs deployment/agent-zero -n pmoves | grep -E '\[ERROR\]|\\"level\\":\\"error\\"'

# Warnings and above
kubectl logs deployment/agent-zero -n pmoves | grep -E '\[(ERROR|WARN)\]'
```

### By Request ID
```bash
# Trace specific request
kubectl logs deployment/agent-zero -n pmoves | grep "req_abc123"
```

### By Time Window
```bash
# Last 30 minutes
kubectl logs deployment/agent-zero -n pmoves --since=30m

# Since specific time
kubectl logs deployment/agent-zero -n pmoves --since-time="2025-06-07T12:00:00Z"
```

## Multi-Service Log Correlation

For tracing requests across services:

```bash
# Install stern for multi-pod logging
stern "agent-zero|hi-rag|archon" -n pmoves --since=5m

# Or use Loki correlation
# Query: {namespace="pmoves"} |= "correlation_id=xyz"
```

## Log Storage

| Location | Retention | Use Case |
|----------|-----------|----------|
| Pod logs | Until pod restart | Quick debugging |
| Loki | 7 days | Historical analysis |
| S3 archive | 90 days | Compliance, audit |

## Troubleshooting

### No Logs Appearing
```bash
# Check pod exists and is running
kubectl get pods -n pmoves -l app=<service>

# Check container status
kubectl describe pod <pod-name> -n pmoves

# Check if logging to stdout
kubectl exec -it <pod-name> -n pmoves -- cat /proc/1/fd/1
```

### Log Truncation
```bash
# Increase buffer size
kubectl logs deployment/<service> -n pmoves --limit-bytes=10485760

# Stream to file
kubectl logs deployment/<service> -n pmoves > service.log
```

### Promtail Not Collecting
```bash
# Check promtail status
kubectl get pods -n monitoring -l app=promtail

# Verify log path configuration
kubectl describe configmap promtail-config -n monitoring
```

## Notes

- Use Loki/Grafana for production log analysis
- Pod logs are ephemeral - use persistent storage for important logs
- Enable debug logging temporarily via ConfigMap
- Log volume affects storage costs - monitor usage
