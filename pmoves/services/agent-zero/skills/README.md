# Agent Zero Skills

This directory contains skills for PMOVES.AI Agent Zero.

## Structure

```
skills/
├── .template/           # SKILL.md template and patterns
│   ├── SKILL.md        # Template for new skills
│   ├── tools/          # Example tool implementation
│   ├── cookbook/       # Example cookbook
│   └── prompts/        # Prompt templates
├── validate_skills.py  # Validation script for SKILL.md files
└── README.md           # This file
```

## Creating a New Skill

1. Copy the `.template/` directory to a new skill directory:

```bash
cp -r .template/my-skill
cd my-skill
```

2. Edit `SKILL.md` to match your skill:

```bash
# Replace placeholders in SKILL.md
# - [Skill Name] → Your skill name
# - [Category/Subcategory] → Skill category
# - Fill in Overview, Capabilities, etc.
```

3. Implement tools in the `tools/` directory:

```bash
# Edit tools/example.py or create new tool files
# Follow the patterns shown in example.py
```

4. Add cookbook examples:

```bash
# Edit cookbook/examples.md
# Include practical usage examples
```

5. Validate your skill:

```bash
# Validate single skill
python ../validate_skills.py SKILL.md

# Validate all skills
python ../validate_skills.py --dir ..
```

## SKILL.md Pattern

All skills must follow the SKILL.md pattern defined in the Aligned Implementation Roadmap.

### Required Frontmatter

```yaml
---
name: Skill Name
description: One-line description
keywords: keyword1, keyword2, keyword3
version: 1.0.0
category: Category/Subcategory
---
```

### Required Sections

1. **Overview** - Brief description (2-3 sentences)
2. **Capabilities** - Key capabilities with emoji markers
3. **Skill Structure** - Directory structure diagram
4. **Trigger Phrases** - Natural language to action mapping
5. **Tools** - Tool documentation with parameters
6. **Configuration** - Environment variables or settings
7. **Cookbook** - Usage examples (can reference `cookbook/examples.md`)
8. **Quick Reference** - Command reference table
9. **Integration Points** - NATS subjects, APIs, etc.
10. **Troubleshooting** - Common issues and solutions
11. **See Also** - Related skills and documentation

## Tool Implementation Pattern

Tools should follow the example in `.template/tools/example.py`:

- **Docstrings**: Google-style docstrings for all classes and functions
- **Type hints**: All parameters and return types
- **Error handling**: Specific exceptions with clear messages
- **Logging**: Appropriate log levels (INFO, WARNING, ERROR)
- **CLI interface**: argparse with help documentation
- **Exit codes**: 0 (success), 1 (execution error), 2 (configuration error)

Example:

```python
class MyTool:
    """Brief description of the tool."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the tool."""

    def execute(self, param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute the primary operation.

        Returns:
            Dictionary with success, result, metadata
        """
```

## Validation

Run the validation script before committing:

```bash
# Validate all skills
python validate_skills.py --dir .

# Validate specific skill
python validate_skills.py my-skill/SKILL.md

# Strict mode (warnings = errors)
python validate_skills.py --strict --dir .
```

The validator checks for:
- Required frontmatter fields
- Required markdown sections
- Directory structure (tools/, cookbook/, prompts/)
- Tool docstring coverage
- Proper YAML formatting

## Integration with Agent Zero

Skills are discovered and loaded by Agent Zero's skill loader.

### Skill Loading

```python
from pmoves.services.agent_zero.skills import load_skill

skill = load_skill("my-skill")
tools = skill.get_tools()
capabilities = skill.get_capabilities()
```

### Trigger Phrases

Agent Zero uses the "Trigger Phrases" section to map natural language to tool calls.

Example:

```python
# From SKILL.md trigger phrases table
# "list files" → list_files_tool
# "show status" → status_tool
```

## Related Documentation

- [Aligned Implementation Roadmap](../../../docs/AGENTS/ALIGNED_IMPLEMENTATION_ROADMAP.md)
- [AGENTS Documentation](../../../docs/AGENTS/)
- [PMOVES.AI Main README](../../../../README.md)
