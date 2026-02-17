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

## AI Graphiti Verification

After generating crush.json, verify Graphiti integration:

6. **Verify Graphiti context paths are injected**:
   ```bash
   python3 -c "
   from pmoves.tools.crush_configurator import build_config
   config, _ = build_config()
   paths = config['options']['context_paths']
   graphiti = [p for p in paths if 'AGENT_TRAIL' in p or 'GRAPHITI' in p or 'agent_signatures' in p]
   print(f'Graphiti context paths: {len(graphiti)}')
   for p in graphiti: print(f'  - {p}')
   assert len(graphiti) >= 2, 'Missing Graphiti context paths'
   print('OK')
   "
   ```

7. **Verify Crush identity in signatures**:
   ```bash
   python3 -c "
   import yaml
   sig = yaml.safe_load(open('pmoves/config/agent_signatures.yaml', encoding='utf-8'))
   crush = sig['signatures']['crush']
   assert crush['glyph'] == '\u25c7', f'Wrong glyph: {crush[\"glyph\"]}'
   assert crush['voice'] == 'companion'
   print(f'Crush identity: {crush[\"glyph\"]} {crush[\"display_name\"]} ({crush[\"color\"]})')
   print('OK')
   "
   ```

8. **Verify Crush is registered in agent registry**:
   ```bash
   python3 -c "
   import yaml
   reg = yaml.safe_load(open('pmoves/config/agent_registry.yaml', encoding='utf-8'))
   assert 'crush' in reg['external_contributors']
   assert 'crush' in reg['agents']
   print('Crush registered in agent registry: OK')
   "
   ```

## Files Created/Modified

- `./crush.json` - PMOVES-opinionated Crush configuration
- Context paths configured for PMOVES.AI structure
- Graphiti context paths: `docs/AGENT_TRAIL.md`, `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md`, `pmoves/config/agent_signatures.yaml`

## Next Steps

- Run `/workitems:list` to see available work items
- Run `/crush:status` to check BoTZ registration
- Read `pmoves/docs/AGENTS/CRUSH_OPERATOR_HOME.md` for the full operator runbook
