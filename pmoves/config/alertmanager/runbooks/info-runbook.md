# Info Alert Runbook Template

## Severity Definition

**INFO** — Awareness only. No action required. Informational events for audit trails,
access patterns, or system behavior documentation. Review during regular checks.

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

## Review Steps

### Regular Review (during daily check)

- [ ] Review the alert in Alertmanager or Discord #alerts-info channel
- [ ] Confirm expected behavior (e.g., known access patterns)
- [ ] Check if frequency has changed significantly
- [ ] Log any notable observations for trend analysis

### Context Analysis

- [ ] Check if this correlates with other alerts (warning/critical)
- [ ] Review historical trends for this alert type
- [ ] Determine if threshold adjustment is warranted
- [ ] Consider if alert should be promoted to warning level

---

## Action Guidelines

### When to Take Action

1. **Frequency increase**: If info alerts spike 3x above baseline, investigate
2. **Pattern change**: New info alerts after deployments may indicate issues
3. **Correlation**: Multiple info alerts from same service may indicate underlying problem
4. **Threshold review**: If alert fires constantly, consider adjusting or suppressing

### No Action Needed

- Expected access patterns (e.g., authorized bucket access denials)
- Known system behavior during maintenance windows
- Baseline noise that has been reviewed and accepted

---

## Escalation Path

| Level | Contact          | Response Time | Trigger                          |
|-------|------------------|---------------|----------------------------------|
| L1    | On-call engineer | Next shift    | Info alert spike (3x baseline)   |
| L2    | Service owner    | Weekly review | Persistent pattern over 1 week   |

### When to Escalate

- Info alert frequency spikes 3x above normal baseline
- Pattern suggests security reconnaissance
- Correlates with warning/critical alerts in same service
- Persistent firing over 1 week without review

---

## Trend Analysis

- Track alert frequency weekly using Grafana dashboards
- Compare against baseline established over last 30 days
- Use for capacity planning and access pattern documentation
- Feed into quarterly security review

---

## Prevention

- [ ] Tune alert threshold if firing too frequently without value
- [ ] Add suppression rules for known benign patterns
- [ ] Consider promoting to warning if pattern becomes actionable
- [ ] Document accepted baseline in this runbook

---

*Last updated: 2026-04-10 | PMOVES.AI Observability (P3)*
