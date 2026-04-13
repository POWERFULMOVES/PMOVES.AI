# Warning Alert Runbook Template

## Severity Definition

**WARNING** — Attention needed soon. Service degradation, elevated error rates, or
resource pressure detected. On-call engineer should investigate within **30 minutes**.

---

## Alert Information

| Field          | Value                          |
|----------------|--------------------------------|
| Alert Name     | `{{ .AlertName }}`             |
| Service        | `{{ .Labels.service }}`        |
| Job            | `{{ .Labels.job }}`            |
| Started At     | `{{ .StartsAt }}`              |
| Dashboard Link | [Grafana](http://grafana:3000) |

---

## Summary

{{ .Annotations.summary }}

## Description

{{ .Annotations.description }}

---

## Investigation Steps

### 1. Triage (5 minutes)

- [ ] Check Prometheus alert page: `http://prometheus:9093/alerts`
- [ ] Confirm the alert is genuinely firing (not transient)
- [ ] Check if a related critical alert is already being handled
- [ ] Review the affected service Grafana dashboard

### 2. Assess Impact (5 minutes)

- [ ] Determine user-facing impact (degraded performance vs invisible)
- [ ] Check if error rates are trending up or stable
- [ ] Review resource usage trends over the last hour
- [ ] Identify if recent deployment correlates with the alert

### 3. Gather Context

- [ ] Review service logs: `docker logs pmoves-<service> --tail 100`
- [ ] Check container metrics: `docker stats pmoves-<service> --no-stream`
- [ ] Review related metrics in Grafana
- [ ] Check upstream/downstream service health

---

## Resolution Steps

### Standard Resolution

1. **If resource-related** (CPU, memory, disk):
   - Check if usage is trending or a spike
   - Consider increasing resource limits if consistently hitting thresholds
   - Restart service if memory leak suspected

2. **If error-rate-related**:
   - Check recent deployments: `git log --oneline -5 -- pmoves/services/<service>/`
   - Review error logs for specific failure patterns
   - Consider rollback if a recent change caused the issue

3. **If latency-related**:
   - Check upstream dependency response times
   - Review database query performance
   - Check for network issues between services

### Monitoring

- Watch the alert for 10 minutes after taking action
- Confirm alert resolves in Alertmanager UI
- If alert escalates to critical, switch to critical runbook

---

## Escalation Path

| Level | Contact              | Response Time | Trigger                     |
|-------|----------------------|---------------|-----------------------------|
| L1    | On-call engineer     | 30 minutes    | Alert fires                 |
| L2    | Service owner        | 2 hours       | Not resolved in 1 hour      |
| L3    | Platform lead        | 4 hours       | Repeated warnings (3+ same) |

### When to Escalate

- Warning persists for more than 1 hour
- Same warning fires 3+ times in 24 hours
- Warning correlates with other active alerts
- Warning shows clear upward trend in severity

---

## Prevention

- [ ] Add capacity planning alerts if resource-related
- [ ] Review SLO/SLI thresholds — may need adjustment
- [ ] Document root cause pattern for future reference
- [ ] Consider adding pre-warning alert with lower threshold

---

*Last updated: 2026-04-10 | PMOVES.AI Observability (P3)*
