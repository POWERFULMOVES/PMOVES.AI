# Critical Alert Runbook Template

## Severity Definition

**CRITICAL** — Immediate action required. Service is down, data loss is possible, or
security breach is in progress. On-call engineer must respond within **5 minutes**.

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

### 1. Verify the Alert (2 minutes)

- [ ] Check Prometheus alert page: `http://prometheus:9093/alerts`
- [ ] Confirm the alert is still firing (not a flake)
- [ ] Check the affected service health endpoint
- [ ] Review recent deployments that may have caused the issue

### 2. Assess Impact (3 minutes)

- [ ] Determine which users/services are affected
- [ ] Check if this is a single-service or cascading failure
- [ ] Review related alerts for correlated failures
- [ ] Check Grafana dashboards for anomalous metrics

### 3. Gather Context

- [ ] Review service logs: `docker logs pmoves-<service> --tail 200`
- [ ] Check container status: `docker ps -f name=pmoves-<service>`
- [ ] Review resource usage: `docker stats pmoves-<service>`
- [ ] Check network connectivity between affected services

---

## Resolution Steps

### Quick Fix (Attempt First)

1. Restart the affected service:
   ```bash
   docker compose restart <service>
   ```
2. Monitor for 2 minutes — if alert resolves, document and close
3. If restart fails, proceed to deep investigation

### Deep Investigation

1. Check for configuration drift:
   ```bash
   git diff HEAD -- pmoves/config/<service>/
   ```
2. Review recent commits to affected service
3. Check upstream dependency health (databases, APIs, external services)
4. Examine resource limits — may need increase

### Rollback Procedure

If a recent deployment caused the issue:
```bash
# Identify last working version
git log --oneline -10 -- pmoves/services/<service>/

# Rollback to previous version
docker compose down <service>
git checkout <known-good-sha> -- pmoves/services/<service>/
docker compose up -d <service>
```

---

## Escalation Path

| Level | Contact              | Response Time | Trigger                    |
|-------|----------------------|---------------|----------------------------|
| L1    | On-call engineer     | 5 minutes     | Alert fires                |
| L2    | Service owner        | 15 minutes    | Not resolved in 15 min     |
| L3    | Platform lead        | 30 minutes    | Not resolved in 30 min     |
| L4    | Incident commander   | 45 minutes    | Multiple critical alerts   |

### Escalation Actions

1. **Post in #incidents Discord channel** with alert details
2. **Tag the service owner** from the service registry
3. **Open an incident ticket** if not resolved in 15 minutes
4. **Activate incident response** if multiple services affected

---

## Post-Incident

- [ ] Document root cause in incident ticket
- [ ] Update this runbook with lessons learned
- [ ] Add monitoring/alerting improvements as follow-up tasks
- [ ] Schedule blameless post-mortem within 48 hours

---

*Last updated: 2026-04-10 | PMOVES.AI Observability (P3)*
