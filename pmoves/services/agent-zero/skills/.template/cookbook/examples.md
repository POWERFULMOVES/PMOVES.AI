# Cookbook: [Skill Name] Examples

This cookbook provides practical examples and workflows for using the [Skill Name] skill.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Common Workflows](#common-workflows)
3. [Advanced Usage](#advanced-usage)
4. [Troubleshooting Examples](#troubleshooting-examples)

---

## Quick Start

### Basic Usage

The simplest way to use this skill:

```python
from pmoves.services.agent_zero.skills import ExampleTool

# Initialize tool
tool = ExampleTool()

# Execute basic operation
result = tool.execute(param1="value")
print(result)
```

### With Configuration

```python
# Initialize with configuration
tool = ExampleTool(config_path="config.yaml")

# Validate configuration
tool.validate()

# Execute
result = tool.execute(param1="value", param2=42)
```

---

## Common Workflows

### Workflow 1: [Use Case Name]

**Scenario**: You need to [describe scenario]

**Steps**:

1. Initialize the tool with appropriate configuration
2. Execute the operation with required parameters
3. Handle the result

**Example**:

```python
from pmoves.services.agent_zero.skills import ExampleTool

# Step 1: Initialize
tool = ExampleTool(
    config_path="/path/to/config.yaml",
    dry_run=False  # Set to True for testing
)

# Step 2: Execute
result = tool.execute(
    param1="example_value",
    param2=100,
    verbose=True
)

# Step 3: Handle result
if result['success']:
    print(f"Success: {result['result']}")
    # Access metadata
    print(f"Metadata: {result['metadata']}")
else:
    print(f"Error: {result.get('error')}")
```

**Expected Output**:

```
Success: Processed example_value with value 100
Metadata: {'dry_run': False, 'config_path': '/path/to/config.yaml'}
```

### Workflow 2: [Another Use Case]

**Scenario**: [Describe another common scenario]

**Example**:

```python
# Batch processing example
tool = ExampleTool(dry_run=True)

items = ["item1", "item2", "item3"]
results = []

for item in items:
    result = tool.execute(param1=item, param2=len(item))
    results.append(result)

# Summarize results
success_count = sum(1 for r in results if r['success'])
print(f"Processed {success_count}/{len(items)} items successfully")
```

---

## Advanced Usage

### Custom Configuration

You can customize tool behavior by providing a configuration file:

**config.yaml**:

```yaml
# Example tool configuration
setting1: value1
setting2: 42
advanced:
  option1: true
  option2: false
```

**Usage**:

```python
tool = ExampleTool(config_path="config.yaml")
print(tool.config)
```

### Error Handling

Proper error handling patterns:

```python
from pmoves.services.agent_zero.skills import ExampleTool

try:
    tool = ExampleTool()
    tool.validate()  # Check configuration

    result = tool.execute(param1="value")

except FileNotFoundError as e:
    print(f"Config file missing: {e}")

except ValueError as e:
    print(f"Invalid parameter: {e}")

except RuntimeError as e:
    print(f"Execution failed: {e}")
```

### Dry Run Mode

Test operations without making actual changes:

```python
tool = ExampleTool(dry_run=True)

result = tool.execute(param1="test")
print(result['metadata']['dry_run'])  # True
print(result['result'])  # "Would process: test"
```

---

## Integration Examples

### Integration with NATS

```python
import asyncio
from nats.aio.client import Client as NATS
from pmoves.services.agent_zero.skills import ExampleTool

async def publish_result(subject: str, result: dict):
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    await nc.publish(subject, json.dumps(result).encode())
    await nc.close()

# Use in event handler
tool = ExampleTool()
result = tool.execute(param1="value")
await publish_result("pmoves.skill.result.v1", result)
```

### Integration with MCP

```python
from mcp.server import Server
from pmoves.services.agent_zero.skills import ExampleTool

app = Server("example-skill-server")
tool = ExampleTool()

@app.call_tool()
async def handle_example_tool(params: dict):
    result = tool.execute(**params)
    return result
```

---

## Troubleshooting Examples

### Issue: Configuration File Not Found

**Problem**: Tool fails to initialize with config file

**Solution**:

```python
from pathlib import Path

config_path = Path("config.yaml")

if not config_path.exists():
    print(f"Config file not found: {config_path.absolute()}")
    print("Creating default config...")
    # Create default config
else:
    tool = ExampleTool(config_path=str(config_path))
```

### Issue: Invalid Parameters

**Problem**: Tool raises ValueError for invalid inputs

**Solution**:

```python
def safe_execute(tool: ExampleTool, params: dict):
    """Execute with parameter validation."""
    try:
        # Validate before execution
        if 'param1' not in params or not params['param1']:
            raise ValueError("param1 is required and must be non-empty")

        if params.get('param2', 0) < 0:
            raise ValueError("param2 must be non-negative")

        return tool.execute(**params)

    except ValueError as e:
        print(f"Validation error: {e}")
        return {"success": False, "error": str(e)}
```

### Issue: Dry Run Shows Expected Output but Real Run Fails

**Problem**: Dry run succeeds but actual execution fails

**Solution**:

```python
# Test in dry run first
tool = ExampleTool(dry_run=True)
result = tool.execute(param1="test")
print(f"Dry run: {result}")

# Check for environment-specific issues
import os
required_env = ["API_KEY", "SERVICE_URL"]
missing = [e for e in required_env if not os.environ.get(e)]

if missing:
    print(f"Missing environment variables: {missing}")
    print("Set them before running without dry-run")
else:
    tool = ExampleTool(dry_run=False)
    result = tool.execute(param1="test")
```

---

## Performance Tips

### Batch Operations

When processing multiple items, consider these optimizations:

```python
from concurrent.futures import ThreadPoolExecutor

def process_item(item):
    tool = ExampleTool()  # Create per thread
    return tool.execute(param1=item)

# Parallel processing
items = ["item1", "item2", "item3", "item4", "item5"]

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_item, items))

print(f"Processed {len(results)} items in parallel")
```

### Caching Results

```python
from functools import lru_cache

class CachedExampleTool(ExampleTool):
    @lru_cache(maxsize=128)
    def execute(self, param1: str, param2: Optional[int] = None):
        return super().execute(param1, param2)

tool = CachedExampleTool()

# First call computes result
result1 = tool.execute(param1="test")

# Second call returns cached result (faster)
result2 = tool.execute(param1="test")
```

---

## Testing Examples

### Unit Testing

```python
import pytest
from pmoves.services.agent_zero.skills import ExampleTool

def test_basic_execution():
    tool = ExampleTool()
    result = tool.execute(param1="test")
    assert result['success'] is True
    assert "Processed test" in result['result']

def test_invalid_param():
    tool = ExampleTool()
    with pytest.raises(ValueError):
        tool.execute(param1="")  # Empty string

def test_dry_run():
    tool = ExampleTool(dry_run=True)
    result = tool.execute(param1="test")
    assert result['metadata']['dry_run'] is True
    assert "Would process" in result['result']
```

### Integration Testing

```python
import pytest
from pathlib import Path

@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file."""
    config = tmp_path / "test_config.yaml"
    config.write_text("setting1: value1")
    return str(config)

def test_with_config(config_file):
    tool = ExampleTool(config_path=config_file)
    assert tool.config['setting1'] == 'value1'
    tool.validate()  # Should not raise
```

---

## See Also

- [Main SKILL.md](../SKILL.md) - Skill overview and API reference
- [Tool Implementation](../tools/example.py) - Tool source code
- [PMOVES.AI Documentation](../../../../docs/) - Platform documentation
