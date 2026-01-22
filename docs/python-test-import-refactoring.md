# Python Test Import Refactoring Guide

**Date**: 2025-12-06
**Status**: Analysis Complete - Ready for Implementation
**Effort**: 1.5-2 hours
**Risk**: Low

## Executive Summary

GitHub Actions Python Tests workflow is failing due to inconsistent import patterns between service code and test code. This document provides the analysis and recommended solution.

## Problem Statement

**Current Failure:**
```
ModuleNotFoundError: No module named 'pmoves.services'
```

**Root Cause:**
- Service code uses: `from services.common.telemetry import...`
- Test code uses: `from pmoves.services.common.telemetry import...`
- CI sets: `PYTHONPATH=pmoves`

When `PYTHONPATH=pmoves`, the string "pmoves" becomes both a directory and module name, causing Python's import system to fail on `pmoves.services.*` imports.

## Import Pattern Analysis

### Service Code (Production)
- **Pattern**: `from services.X import...` (relative to services/)
- **Files**: 25+ service files
- **Works with**: `PYTHONPATH=pmoves`

### Test Code (CI)
- **Pattern**: `from pmoves.services.X import...` (absolute path)
- **Files**: 7 test files with ~10-15 import statements
- **Conflicts with**: `PYTHONPATH=pmoves`

### Module Aliasing System

The codebase uses dynamic module aliasing in `pmoves/services/__init__.py`:
- Registers `services` as an alias to `pmoves.services`
- Dynamically loads modules via `__getattr__`
- Handles legacy `services.*` imports for service code
- Maps kebab-case directories to underscore module names

## Refactoring Options

### Option 1: Standardize Tests to `services.X` Pattern ✅ RECOMMENDED

**Description**: Update test imports to match service code pattern

**Changes**: 7 test files, 10-15 import statements

**Files to Update**:
1. `pmoves/services/publisher/tests/test_publisher.py`
2. `pmoves/services/publisher-discord/tests/test_formatting.py`
3. `pmoves/services/deepresearch/tests/test_parsing.py`
4. `pmoves/services/deepresearch/tests/test_worker.py`
5. `pmoves/services/gateway/tests/test_workflow_utils.py`
6. `pmoves/services/gateway/tests/test_mindmap_endpoint.py`
7. `pmoves/services/gateway/tests/test_geometry_endpoints.py`

**Example Change**:
```python
# BEFORE:
from pmoves.services.common.telemetry import PublisherMetrics
from pmoves.services.publisher import publisher

# AFTER:
from services.common.telemetry import PublisherMetrics
from services.publisher import publisher
```

**Pros**:
- ✅ Minimal effort (1.5-2 hours)
- ✅ Low risk (import changes only)
- ✅ Uses existing module aliasing
- ✅ No Docker/service code changes
- ✅ Works with current `PYTHONPATH=pmoves`

**Cons**:
- ⚠ Tests use different style than absolute imports convention
- ⚠ Module aliasing can be confusing for new developers

**Effort**: 1.5-2 hours
**Risk**: Low

### Option 2: Standardize All to `pmoves.services.X` Pattern

**Description**: Update all service code and tests to use absolute imports

**Changes**: 25+ service files + 7 test files

**Pros**:
- ✅ Explicit and unambiguous
- ✅ More Pythonic (PEP 8)
- ✅ Better IDE support

**Cons**:
- ❌ Requires updating 25+ service files
- ❌ Breaks Docker images
- ❌ High risk of merge conflicts in submodules
- ❌ Breaking change for deployment

**Effort**: 3-5 days
**Risk**: High

### Option 3: Dual-Import Support Via Shims

**Description**: Support both `services.*` and `pmoves.services.*` patterns

**Pros**:
- ✅ Backwards compatible
- ✅ Gradual migration possible

**Cons**:
- ❌ Adds complexity and "magic"
- ❌ Harder to debug
- ❌ IDE tooling struggles

**Effort**: 2-3 days
**Risk**: Medium

### Option 4: Restructure Package Hierarchy

**Description**: Reorganize to standard Python package structure with `__init__.py` everywhere

**Pros**:
- ✅ Clean, standard structure
- ✅ Future-proof

**Cons**:
- ❌ Extensive restructuring
- ❌ Breaks Dockerfiles and submodules
- ❌ Longest development time

**Effort**: 5-7 days
**Risk**: High

## Recommendation

**Implement Option 1: Standardize Tests to `services.X` Pattern**

This is a pragmatic quick-win that:
- Fixes CI failures immediately (1.5-2 hours)
- Minimal risk and disruption
- Leverages existing aliasing infrastructure
- Allows planning longer-term refactoring separately

## Implementation Plan

### Step 1: Update Test Imports (30 minutes)

Use find/replace to change imports in 7 test files:
```bash
# Pattern to find:
from pmoves.services.

# Replace with:
from services.
```

### Step 2: Verify Module Aliasing (15 minutes)

Confirm aliasing works locally:
```bash
cd /home/pmoves/PMOVES.AI
export PYTHONPATH=pmoves

python3 -c "from services import publisher; print(publisher)"
python3 -c "from services.common.telemetry import PublisherMetrics; print(PublisherMetrics)"
python3 -c "from services import publisher_discord; print(publisher_discord)"
```

### Step 3: Run Full CI Test Suite (15 minutes)

Run the same tests as CI workflow:
```bash
export PYTHONPATH=pmoves
pytest -q pmoves/services/publisher/tests \
       pmoves/services/pmoves-yt/tests \
       pmoves/services/publisher-discord/tests
```

### Step 4: Spot-Check Docker Builds (10 minutes)

Verify services that use `services.*` imports still build:
```bash
docker build -f pmoves/services/publisher/Dockerfile .
docker build -f pmoves/services/deepresearch/Dockerfile .
```

### Step 5: Commit and Push (5 minutes)

```bash
git add pmoves/services/*/tests/
git commit -m "fix(tests): standardize imports to services.* pattern

Resolves ModuleNotFoundError in CI by aligning test imports with
service code pattern. Tests now use 'from services.X import...'
instead of 'from pmoves.services.X import...'.

This leverages existing module aliasing in services/__init__.py
and works with PYTHONPATH=pmoves set in CI workflow.

Files updated:
- publisher/tests/test_publisher.py
- publisher-discord/tests/test_formatting.py
- deepresearch/tests/test_parsing.py
- deepresearch/tests/test_worker.py
- gateway/tests/test_workflow_utils.py
- gateway/tests/test_mindmap_endpoint.py
- gateway/tests/test_geometry_endpoints.py

Related: CI Python Tests workflow (#4126dba)"

git push origin PMOVES.AI-Edition-Hardened
```

## Testing Strategy

### Unit Test Validation

Run each affected test suite:
```bash
pytest -xvs pmoves/services/publisher/tests/test_publisher.py
pytest -xvs pmoves/services/publisher-discord/tests/test_formatting.py
pytest -xvs pmoves/services/deepresearch/tests/
pytest -xvs pmoves/services/gateway/tests/
```

### Import Smoke Tests

Verify all import patterns work:
```python
from services.common.telemetry import PublisherMetrics
from services.publisher import publisher
from services import publisher_discord
from services.deepresearch.worker import _extract_message_content
from services.gateway.gateway.api import workflow
```

### Rollback Plan

If issues arise:
1. Revert test file changes (service code unchanged)
2. PYTHONPATH stays at `pmoves` (backward compatible)
3. Import changes are isolated to test files only

## Critical Files

### Configuration
- `.github/workflows/python-tests.yml` - Already has `PYTHONPATH: pmoves`

### Module Registry
- `pmoves/services/__init__.py` - Handles dynamic module aliasing

### Common Utilities
- `pmoves/services/common/__init__.py`
- `pmoves/services/common/telemetry.py`

### Test Files (7 total)
- `pmoves/services/publisher/tests/test_publisher.py`
- `pmoves/services/publisher-discord/tests/test_formatting.py`
- `pmoves/services/deepresearch/tests/test_parsing.py`
- `pmoves/services/deepresearch/tests/test_worker.py`
- `pmoves/services/gateway/tests/test_workflow_utils.py`
- `pmoves/services/gateway/tests/test_mindmap_endpoint.py`
- `pmoves/services/gateway/tests/test_geometry_endpoints.py`

## Timeline

| Task | Duration | Status |
|------|----------|--------|
| Analysis (TAC Explore) | 15 min | ✅ Complete |
| Documentation | 10 min | ✅ Complete |
| Implementation | 1.5-2 hours | ⏳ Pending |

## Future Work

Once Option 1 is implemented and tests are stable, consider planning:
- **Phase 2**: Evaluate Option 4 (package restructuring) for long-term maintainability
- **Benefit**: Clean Python package structure, better IDE support, PEP 8 compliance
- **Timeline**: Schedule as separate epic (5-7 days)

## References

- TAC Analysis: Agent eb364a13 (2025-12-06)
- Related Commit: 4126dba (PYTHONPATH change + test_docs_catalog.py fix)
- GitHub Actions Run: https://github.com/POWERFULMOVES/PMOVES.AI/actions/runs/19985304670
