# Hotfix Development Guide

When working on a hotfix branch for PMOVES.AI skills, follow this focused approach to resolve critical issues quickly and safely.

## Mindset

You are fixing a critical issue in production. Your priorities are:

1. **Fix the bug** - Resolve the immediate issue
2. **Minimize risk** - Don't introduce new problems
3. **Verify thoroughly** - Test the fix extensively
4. **Document clearly** - Explain what was changed and why

## Hotfix Workflow

### 1. Diagnosis Phase

**Understand the Issue**:
- What is the exact error or unexpected behavior?
- When does it occur? (timing, conditions, inputs)
- What is the impact? (severity, affected users, data loss risk)
- What was the last working state?

**Reproduce the Bug**:
- Create a minimal reproduction case
- Document exact steps to reproduce
- Capture error messages, logs, stack traces
- Identify the root cause (not just symptoms)

**Questions to Answer**:
- Is this a regression? (Did it work before?)
- Is it configuration-related or code-related?
- Is it environment-specific? (dev/staging/prod)
- Are there workarounds? (temporary fixes)

### 2. Fix Design Phase

**Fix Strategy**:
- **Minimal change**: Fix only what's broken
- **No refactoring**: Save improvements for feature branches
- **Backward compatible**: Don't break existing integrations
- **Rollback safe**: Easy to revert if needed

**Risk Assessment**:
- What could go wrong with this fix?
- Are there side effects?
- Does it affect other services or integrations?
- Can it be rolled back safely?

**Design Questions**:
- Can this be fixed with a small change?
- Does the fix address the root cause?
- Are there edge cases to consider?
- What tests are needed to verify the fix?

### 3. Implementation Phase

**Hotfix Principles**:

✅ **DO**:
- Make minimal, targeted changes
- Add tests for the bug fix
- Update documentation if behavior changes
- Add comments explaining the fix
- Log the fix for observability

❌ **DON'T**:
- Refactor surrounding code
- Add new features
- Change APIs or interfaces
- Update dependencies (unless security-related)
- Make architectural changes

**Hotfix Pattern**:
```python
# Before: Bug
def process_data(data: dict) -> dict:
    # Bug: Doesn't handle missing 'key' field
    value = data['key']  # KeyError if 'key' missing
    return {"result": value}

# After: Fix
def process_data(data: dict) -> dict:
    # Fix: Handle missing 'key' gracefully
    value = data.get('key')
    if value is None:
        logger.warning("Missing 'key' in data, using default")
        value = ""  # or raise ValueError with clear message
    return {"result": value}
```

**Error Handling**:
```python
# Before: Silent failure
def fetch_data(id: str) -> dict:
    data = api_call(id)
    return data  # Returns None if API fails

# After: Explicit error
def fetch_data(id: str) -> dict:
    try:
        data = api_call(id)
        if not data:
            raise ValueError(f"No data found for ID: {id}")
        return data
    except Exception as e:
        logger.error(f"Failed to fetch data for ID {id}: {e}")
        raise  # Re-raise for caller to handle
```

**Validation Fixes**:
```python
# Before: No validation
def connect_to_service(url: str) -> Connection:
    return Connection(url)

# After: Add validation
def connect_to_service(url: str) -> Connection:
    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL: {url}")
    logger.info(f"Connecting to service: {url}")
    return Connection(url)
```

### 4. Testing Phase

**Regression Tests** (CRITICAL):
```python
def test_bug_is_fixed():
    """Test that the specific bug is fixed."""
    # This was failing before the fix
    result = process_data({"other_key": "value"})
    assert result is not None  # Should handle missing key
    assert 'error' not in result

def test_edge_cases():
    """Test edge cases that could reintroduce the bug."""
    # Empty input
    result = process_data({})
    assert result is not None

    # None input
    result = process_data(None)
    assert result is not None

    # Malformed input
    result = process_data({"key": None})
    assert result is not None
```

**Integration Tests**:
```python
def test_hotfix_integration():
    """Test that fix doesn't break integrations."""
    # Test with real service
    result = fetch_data("test_id")
    assert result is not None

    # Test NATS events still work
    event = publish_and_wait("test.subject", {"test": "data"})
    assert event['status'] == 'processed'
```

**Smoke Tests**:
```python
def test_service_health_after_fix():
    """Verify service still healthy after hotfix."""
    response = requests.get("http://localhost:8080/healthz")
    assert response.status_code == 200

def test_metrics_still_work():
    """Verify metrics are still collected."""
    response = requests.get("http://localhost:8080/metrics")
    assert response.status_code == 200
    assert 'pmoves_skill_errors_total' in response.text
```

### 5. Documentation Phase

**Update SKILL.md** (if behavior changed):
```markdown
## Troubleshooting

### Issue: [Bug Description]
**Status**: Fixed in v1.0.1

**Problem**: Brief description of the bug

**Solution**: How it was fixed

**Migration**: Any steps needed for existing deployments
```

**Add Changelog Entry**:
```markdown
## [1.0.1] - 2025-01-30

### Fixed
- Fix KeyError when processing data without 'key' field
- Add validation for missing required fields
- Improve error messages for debugging

### Security
- Fix potential injection vulnerability in input validation
```

**Comment the Fix**:
```python
def process_data(data: dict) -> dict:
    """
    Process data dictionary.

    Hotfix (v1.0.1): Added handling for missing 'key' field to prevent
    KeyError when processing incomplete data. Returns default value instead
    of crashing.

    Args:
        data: Dictionary to process

    Returns:
        Dictionary with processed result

    Raises:
        ValueError: If data is None or not a dictionary
    """
    if not isinstance(data, dict):
        raise ValueError("data must be a dictionary")

    # Hotfix: Use .get() to handle missing key gracefully
    value = data.get('key', '')  # Default to empty string
    return {"result": value}
```

## Hotfix Checklist

Before submitting hotfix PR:

- [ ] Bug is reproduced and root cause identified
- [ ] Fix is minimal and targeted
- [ ] No refactoring or improvements included
- [ ] Tests added for the bug fix
- [ ] All existing tests still pass
- [ ] Integration tests pass
- [ ] Smoke tests pass
- [ ] Behavior changes documented in SKILL.md
- [ ] Changelog updated
- [ ] Code commented explaining the fix
- [ ] Error handling improved
- [ ] Logging added for observability
- [ ] Edge cases considered
- [ ] Rollback plan documented

## Common Hotfix Patterns

### Pattern 1: Null/None Handling
```python
# Bug: Crashes on None input
def process(item):
    return item.upper()  # AttributeError if item is None

# Fix: Handle None explicitly
def process(item):
    if item is None:
        logger.warning("Received None item, returning empty string")
        return ""
    return item.upper()
```

### Pattern 2: Missing Dictionary Keys
```python
# Bug: KeyError on missing key
def get_user_name(user: dict) -> str:
    return user['name']  # KeyError if 'name' missing

# Fix: Use .get() with default
def get_user_name(user: dict) -> str:
    name = user.get('name')
    if name is None:
        logger.warning(f"User missing 'name': {user.get('id')}")
        return "Unknown"
    return name
```

### Pattern 3: Type Validation
```python
# Bug: Fails silently with wrong type
def process_count(count: int) -> int:
    return count * 2  # Works with strings too ("2" * 2 = "22")

# Fix: Validate type explicitly
def process_count(count: int) -> int:
    if not isinstance(count, int):
        raise TypeError(f"count must be int, got {type(count).__name__}")
    return count * 2
```

### Pattern 4: API Error Handling
```python
# Bug: No error handling for API failures
def fetch_remote_data(url: str) -> dict:
    response = requests.get(url)
    return response.json()  # Crashes if status != 200

# Fix: Handle API errors explicitly
def fetch_remote_data(url: str) -> dict:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise for 4xx/5xx
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API request failed for {url}: {e}")
        raise ValueError(f"Failed to fetch data from {url}") from e
```

### Pattern 5: Race Conditions
```python
# Bug: Race condition in check-then-act
def increment_counter():
    if counter < 10:  # Check
        counter += 1  # Act (another thread could increment here)

# Fix: Use atomic operations
def increment_counter():
    with counter_lock:  # Thread-safe
        if counter < 10:
            counter += 1
```

### Pattern 6: Resource Leaks
```python
# Bug: File handle not closed
def read_config(path: str) -> dict:
    f = open(path, 'r')  # Never closed
    return json.load(f)

# Fix: Use context manager
def read_config(path: str) -> dict:
    with open(path, 'r') as f:  # Automatically closed
        return json.load(f)
```

## Testing Hotfixes

**Unit Test Template**:
```python
import pytest
from pmoves.services.agent_zero.skills.my_feature import process_data

class TestHotfix:
    """Tests for hotfix v1.0.1"""

    def test_bug_reproduction(self):
        """Test that the original bug is fixed."""
        # This was failing before the hotfix
        result = process_data({"other_field": "value"})
        assert result is not None
        assert 'error' not in result

    def test_normal_operation_still_works(self):
        """Test that normal operation isn't broken."""
        result = process_data({"key": "value"})
        assert result['result'] == "value"

    def test_edge_cases(self):
        """Test edge cases."""
        assert process_data({}) is not None
        assert process_data(None) is not None  # If applicable
```

**Integration Test Template**:
```python
@pytest.mark.integration
def test_hotfix_with_real_services():
    """Test hotfix with real service dependencies."""
    # Test with actual NATS
    result = publish_to_nats_and_wait("test.subject", {"test": "data"})
    assert result['success'] is True

    # Test with actual API
    response = requests.post("http://localhost:8080/api/test", json={"test": "data"})
    assert response.status_code == 200
```

## Verifying the Fix

**Pre-Merge Checklist**:
1. ✅ Bug is fixed (verified by reproduction test)
2. ✅ All tests pass (unit + integration)
3. ✅ No regressions (existing tests pass)
4. ✅ Documentation updated
5. ✅ Code reviewed by teammate
6. ✅ Tested in staging environment
7. ✅ Rollback plan documented

**Post-Merge Verification**:
1. ✅ Deployed to production
2. ✅ Health checks passing
3. ✅ Error rates decreased
4. ✅ Monitoring shows fix working
5. ✅ No new errors introduced

## Example Hotfix

**Bug Report**:
```
Error: KeyError when processing data without 'id' field
Impact: Service crashes, 50% of requests failing
Severity: High (production outage)
```

**Root Cause**:
```python
# Bug code
def process_event(event: dict) -> str:
    event_id = event['id']  # KeyError if 'id' missing
    return f"Processed {event_id}"
```

**Hotfix**:
```python
# Fixed code
def process_event(event: dict) -> str:
    # Hotfix (v1.2.1): Handle missing 'id' field
    if 'id' not in event:
        logger.error(f"Event missing 'id' field: {event}")
        raise ValueError("Event must contain 'id' field")

    event_id = event['id']
    return f"Processed {event_id}"
```

**Test**:
```python
def test_hotfix_missing_id():
    """Test that missing ID raises clear error."""
    with pytest.raises(ValueError, match="must contain 'id' field"):
        process_event({"data": "value"})

def test_normal_operation():
    """Test normal operation still works."""
    result = process_event({"id": "123", "data": "value"})
    assert result == "Processed 123"
```

## Rollback Plan

If the hotfix causes issues:

1. **Immediate**: Revert the commit
2. **Verify**: Run smoke tests
3. **Monitor**: Check error rates
4. **Communicate**: Notify team of rollback

**Rollback Command**:
```bash
# Revert the hotfix commit
git revert <hotfix-commit-hash>

# Or hard reset (if not pushed)
git reset --hard HEAD~1
git push --force
```

## Resources

- Git Workflow: `docs/PMOVES_Git_Organization.md`
- Testing Strategy: `.claude/context/testing-strategy.md`
- NATS Subjects: `.claude/context/nats-subjects.md`
- Services Health: `/health:check-all` skill

## Success Criteria

A hotfix is complete when:

1. ✅ Bug is fixed and verified
2. ✅ No regressions introduced
3. ✅ Tests added and passing
4. ✅ Documentation updated
5. ✅ Code reviewed and approved
6. ✅ Deployed to production
7. ✅ Monitoring confirms fix
8. ✅ Rollback plan documented

Remember: Hotfixes are about safety and speed. Fix the bug, don't refactor.
