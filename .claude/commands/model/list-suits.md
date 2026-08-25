# Model — List Suits

Enumerate the fleet's model suits with role, provider, and fallback chain.

## Arguments

- `$ARGUMENTS` - optional filter (`--family minimax`, `--role primary`, `--local`)

## Instructions

1. Read every `pmoves/configs/model-suits/*.yaml`; print a table: suit id | provider | role | context window | multimodal | fallback chain.
2. Mark the primary per family (e.g. `MiniMax-M3` primary, `minimax-m2.7` long-context fallback, `minimax-m2.1` efficient).
3. For `--local`, additionally read the node's hardware profile (`pmoves/config/profiles/`) and list its `model_bundles`.
4. Flag drift on sight: a suit id in the profiles/signatures that has no suit file (or the reverse) is a registry error — report it, do not paper over it.

## Notes

- The authoritative cross-checks: `pmoves/config/agent_signatures.yaml` (`model_suits` blocks) and `pmoves/configs/agent-profiles/*.yaml` (`model:` stanzas). All three should agree on ids.
