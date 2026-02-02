---
name: Test Skill
description: A test skill for validating the SKILL.md template
keywords: test, example, validation
version: 1.0.0
category: Examples/Test
---

# Test Skill

**Category**: Examples/Test
**Version**: 1.0.0
**Status**: Stable

## Overview

This is a test skill to validate the SKILL.md template implementation. It demonstrates all required sections and proper formatting for PMOVES.AI skills.

## Capabilities

- ✨ Validate template structure
- 🔍 Test validation scripts
- 🛠️ Provide example for skill creators

## Skill Structure

```
.claude/skills/test-skill/
├── SKILL.md              # This file
├── tools/                # Implementation tools
│   └── test_tool.py
├── prompts/              # Prompt templates
└── cookbook/             # Usage examples
    └── examples.md
```

## Trigger Phrases

| Natural Language Phrase | Action | Tool |
|-------------------------|--------|------|
| "test validation" | Run validation test | test_tool.py |
| "show template" | Display template info | SKILL.md |

## Tools

### test_tool.py

**Purpose**: Simple test tool to demonstrate proper structure

**Usage**:
```bash
python tools/test_tool.py --test
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| test | boolean | Yes | Run test mode |

**Output**: Test result message

## Configuration

No configuration required for this test skill.

## Cookbook

For detailed examples, see `cookbook/examples.md`.

### Quick Examples

**Example 1: Run Test**
```python
result = tool.execute(test=True)
print(result)
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| Validate SKILL.md | Check structure compliance |

## Integration Points

- **Validation Script**: `validate_skills.py`
- **Template**: `.template/SKILL.md`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Validation fails | Check all required sections exist |
| Missing frontmatter | Ensure YAML delimiters present |

## See Also

- [Template SKILL.md](../../.template/SKILL.md)
- [Validation Script](../../validate_skills.py)
- [Skills README](../../README.md)
