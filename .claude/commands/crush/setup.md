# PMOVES-Crush Setup

Set up PMOVES-Crush CLI for the current project.

## Instructions

1. **Check if crush is installed**:
   ```bash
   command -v crush || command -v pmoves-crush
   ```

2. **Generate PMOVES-opinionated crush.json**:
   ```bash
   python3 pmoves/tools/crush_configurator.py --output ./crush.json
   ```

3. **Configure for current project**:
   - Set project-specific context paths
   - Configure LLM provider priority (TensorZero → OpenAI → Anthropic)
   - Enable attribution: `generated_with: true`

4. **Verify configuration**:
   ```bash
   cat crush.json | jq '.options.attribution'
   ```

5. **Test crush invocation**:
   ```bash
   crush --version
   ```

## PMOVES-BoTZ Integration

After setup, the crush CLI becomes a PMOVES-BoTZ instance capable of:
- Claiming work items from the registry
- Executing TAC commands
- Coordinating with Agent Zero/Archon via MCP

## Files Created/Modified

- `./crush.json` - PMOVES-opinionated Crush configuration
- Context paths configured for PMOVES.AI structure

## Next Steps

- Run `/workitems:list` to see available work items
- Run `/crush:status` to check BoTZ registration
