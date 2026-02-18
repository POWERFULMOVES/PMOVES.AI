# PMOVES.AI Scripts and Tests Guide

This document provides comprehensive documentation for the validation scripts and test suites used to ensure PMOVES.AI security hardening compliance.

---

## Table of Contents

1. [Task Tracker Script](#task-tracker-script)
2. [Docker Hardening Validation Script](#docker-hardening-validation-script)
3. [Docker Hardening Test Suite](#docker-hardening-test-suite)
4. [Usage Workflow](#usage-workflow)

---

## Task Tracker Script

**Location:** `pmoves/scripts/task_tracker.py`

### Purpose

The Task Tracker is an agent claim system for the distributed compute roadmap. It enables AI agents to claim, update, and query tasks from the roadmap file, providing coordination between multiple agents working on the PMOVES.AI codebase.

### Features

- **Task Claiming**: Agents can claim unassigned tasks
- **Dependency Validation**: Validates that task dependencies are met before claiming
- **Status Updates**: Update task status (BLOCKED, CLAIMED, COMPLETED, UNASSIGNED, SKIPPED)
- **Progress Tracking**: Shows overall progress by track with visual progress bars
- **Agent-Specific Views**: Show tasks ready for specific agent types (Opus, Sonnet, Haiku)
- **Dependency Chain Visualization**: View upstream and downstream task dependencies

### Usage

```bash
# Claim a task for an agent
python pmoves/scripts/task_tracker.py claim T1-2-002 --agent "Opus 4.5"

# Update task status
python pmoves/scripts/task_tracker.py update T1-2-002 --status "COMPLETED"

# List all tasks
python pmoves/scripts/task_tracker.py list

# List tasks for a specific agent
python pmoves/scripts/task_tracker.py list --agent "Opus 4.5"

# List tasks by status
python pmoves/scripts/task_tracker.py list --status "UNASSIGNED"

# Show tasks ready for a specific agent
python pmoves/scripts/task_tracker.py ready --for "Sonnet 3.5"

# Show overall progress
python pmoves/scripts/task_tracker.py progress

# Show task dependencies
python pmoves/scripts/task_tracker.py deps T1-2-002
```

### Task Statuses

| Status | Emoji | Description |
|--------|-------|-------------|
| `BLOCKED` | 🔵 | Task is blocked by unmet dependencies |
| `CLAIMED` | 🟡 | Task has been claimed by an agent |
| `COMPLETED` | 🟢 | Task has been completed |
| `UNASSIGNED` | ⚪ | Task is available for claiming |
| `BLOCKER` | 🔴 | Task is blocking other tasks |
| `SKIPPED` | ⏭️ | Task was intentionally skipped |

### Agent Type Filtering

The task tracker intelligently filters tasks based on agent capabilities:

- **Opus**: Excludes documentation tasks (T8-*)
- **Haiku**: Excludes complex tasks (T1-2, T2-2, T3-1, T5, T7)
- **Sonnet**: Can handle most tasks
- **All**: Shows all ready tasks across all agent types

### Roadmap File Format

The task tracker parses tasks from the roadmap markdown file:

```yaml
- id: T1-2-001
  name: Implement Node Registry Service
  status: COMPLETED
  agent: Opus 4.5
  depends_on: []
  effort: 4 hours
  files:
    - pmoves/services/node-registry/
    - pmoves/services/resource-detector/
  description: Core service for tracking distributed compute nodes
```

---

## Docker Hardening Validation Script

**Location:** `pmoves/scripts/validate-hardening.sh`

### Purpose

Bash script to validate Docker Compose services against PMOVES.AI security hardening requirements. Ensures all services follow security best practices for production deployment.

### Validation Checks

The script validates the following security controls:

| Check | Description | Weight |
|-------|-------------|--------|
| **Non-root User** | Service runs as UID 65532, not root | Critical |
| **Read-only Filesystem** | Root filesystem is read-only | Important |
| **Capabilities Dropped** | All Linux capabilities dropped via `cap_drop: ["ALL"]` | Important |
| **No New Privileges** | `no-new-privileges:true` security option set | Important |
| **Resource Limits** | Memory and CPU limits defined | Recommended |

### Usage

```bash
# Validate all services in hardened compose file
./pmoves/scripts/validate-hardening.sh

# Validate a specific service
./pmoves/scripts/validate-hardening.sh flute-gateway

# Make script executable
chmod +x pmoves/scripts/validate-hardening.sh
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed (or warnings only) |
| `1` | One or more checks failed |

### Output Format

```
PMOVES.AI Docker Hardening Validation
======================================
[INFO] Checking: pmoves/docker-compose.hardened.yml

[INFO] Validating: flute-gateway
[PASS] Non-root user: 65532:65532
[PASS] Read-only filesystem
[PASS] All capabilities dropped
[PASS] No-new-privileges enabled
[PASS] Resource limits defined

======================================
Summary: 5 passed, 0 warnings, 0 errors
```

### Security Requirements Reference

Services must meet these requirements in `docker-compose.hardened.yml`:

```yaml
services:
  example-service:
    # 1. Non-root user (UID 65532)
    user: "65532:65532"

    # 2. Read-only root filesystem
    read_only: true

    # 3. Drop all Linux capabilities
    cap_drop:
      - ALL

    # 4. Prevent privilege escalation
    security_opt:
      - no-new-privileges:true

    # 5. Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

    # 6. Tmpfs for writable directories (when using read_only)
    tmpfs:
      - /tmp:size=100M
      - /var/run:size=10M
```

---

## Docker Hardening Test Suite

**Location:** `pmoves/tests/hardening/test_docker_hardening.py`

### Purpose

Comprehensive pytest test suite for validating Docker security hardening. Provides programmatic validation of security controls with detailed reporting and CI/CD integration.

### Test Categories

#### 1. Service Existence Tests (`TestHardenedServicesExist`)

Validates that the hardened compose file exists and critical services are defined.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestHardenedServicesExist -v
```

#### 2. Non-Root User Tests (`TestNonRootUser`)

Ensures services run as non-root user (UID 65532).

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestNonRootUser -v
```

#### 3. Read-Only Filesystem Tests (`TestReadOnlyFilesystem`)

Validates that services have read-only root filesystem.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestReadOnlyFilesystem -v
```

#### 4. Capabilities Tests (`TestCapabilitiesDropped`)

Ensures all Linux capabilities are dropped.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestCapabilitiesDropped -v
```

#### 5. No New Privileges Tests (`TestNoNewPrivileges`)

Validates the no-new-privileges security option.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestNoNewPrivileges -v
```

#### 6. Resource Limits Tests (`TestResourceLimits`)

Checks for memory and CPU resource limits.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestResourceLimits -v
```

#### 7. Dockerfile Security Tests (`TestDockerfileSecurity`)

Validates Dockerfile security best practices.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestDockerfileSecurity -v
```

#### 8. Secrets Management Tests (`TestSecretsManagement`)

Ensures proper use of Docker secrets for sensitive data.

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestSecretsManagement -v
```

#### 9. Security Score Tests (`TestSecurityScore`)

Calculates and validates security scores for services (0-100 scale).

```bash
pytest pmoves/tests/hardening/test_docker_hardening.py::TestSecurityScore -v
```

### Usage

```bash
# Run all hardening tests
pytest pmoves/tests/hardening/test_docker_hardening.py -v

# Run tests for a specific service
pytest pmoves/tests/hardening/test_docker_hardening.py -k "flute-gateway" -v

# Run specific test class
pytest pmoves/tests/hardening/test_docker_hardening.py::TestNonRootUser -v

# Run with coverage
pytest pmoves/tests/hardening/test_docker_hardening.py --cov=pmoves.tests.hardening -v

# Skip slow/container tests
pytest pmoves/tests/hardening/test_docker_hardening.py -v -m "not slow"
```

### Security Score Calculation

The test suite calculates a security score (0-100) for each service:

| Control | Points |
|---------|--------|
| Non-root user (UID 65532) | 30 |
| Read-only filesystem | 20 |
| Capabilities dropped (ALL) | 20 |
| No new privileges | 10 |
| Resource limits | 20 |
| **Total** | **100** |

### Hardened Services List

The following 29 services are validated by the test suite:

```
hi-rag-gateway-v2, extract-worker, langextract, presign, render-webhook,
retrieval-eval, pdf-ingest, jellyfin-bridge, invidious-companion-proxy,
ffmpeg-whisper, media-video, media-audio, hi-rag-gateway-v2-gpu,
hi-rag-gateway-gpu, deepresearch, supaserch, publisher-discord,
mesh-agent, nats-echo-req, nats-echo-res, publisher, analysis-echo,
graph-linker, comfy-watcher, grayjay-plugin-host, agent-zero, archon,
channel-monitor, pmoves-yt, notebook-sync, flute-gateway,
tokenism-simulator, botz-gateway, gateway-agent, github-runner-ctl,
tokenism-ui
```

### Third-Party Services (Exempt)

The following third-party services are excluded from hardening validation:

```
qdrant, meilisearch, neo4j, minio, nats, postgres, clickhouse,
prometheus, grafana, loki, cadvisor, ollama, tensorzero-gateway,
tensorzero-clickhouse, tensorzero-ui
```

### Requirements

```txt
pytest>=7.0.0
pyyaml>=6.0
```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Hardening Validation

on: [push, pull_request]

jobs:
  hardening:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run validation script
        run: ./pmoves/scripts/validate-hardening.sh
      - name: Run pytest tests
        run: pytest pmoves/tests/hardening/test_docker_hardening.py -v
```

---

## Usage Workflow

### Before Committing Changes

1. **Run the validation script** for quick validation:
   ```bash
   ./pmoves/scripts/validate-hardening.sh
   ```

2. **Run the full test suite** for detailed validation:
   ```bash
   pytest pmoves/tests/hardening/test_docker_hardening.py -v
   ```

3. **Check specific service** if you modified one service:
   ```bash
   ./pmoves/scripts/validate-hardening.sh your-service-name
   pytest pmoves/tests/hardening/test_docker_hardening.py -k "your-service-name" -v
   ```

### For Agent Coordination

1. **Claim a task** before starting work:
   ```bash
   python pmoves/scripts/task_tracker.py claim T1-2-002 --agent "Opus 4.5"
   ```

2. **Update status** when work is complete:
   ```bash
   python pmoves/scripts/task_tracker.py update T1-2-002 --status "COMPLETED"
   ```

3. **Check progress** to see overall status:
   ```bash
   python pmoves/scripts/task_tracker.py progress
   ```

---

## Related Documentation

- [Docker Compose Hardening Configuration](../docker-compose.hardened.yml)
- [Security Hardening Summary](../../docs/Security-Hardening-Summary-2025-01-29.md)
- [Hardened Services Catalog](../../docs/hardening/services-catalog.md)
- [PMOVES.AI Developer Context](../../.claude/CLAUDE.md)
