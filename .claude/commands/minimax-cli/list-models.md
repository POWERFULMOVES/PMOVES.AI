# MiniMax CLI — List Models

Enumerate the model suits available through the mmx CLI / MiniMax surface.

## Arguments

- `$ARGUMENTS` - optional filters (e.g. `--text`, `--video`)

## Instructions

1. Run the CLI's model-list subcommand (`mmx models list` or the equivalent from `pmoves/docs/services/MMX_CLI_SURFACE.md`).
2. Cross-check the returned IDs against the fleet truth in `pmoves/config/agent_signatures.yaml` (minimax `model_suits`) and `pmoves/configs/agent-profiles/minimax_edition.yaml` — currently `MiniMax-M3` primary, `minimax-m2.7` (1M long-context), `minimax-m2.1` (100K efficient).
3. Report any drift in both directions: an API model the fleet profile lacks, or a profile entry the API does not serve. Model IDs are case-sensitive (`MiniMax-M3`, not `minimax-m3`).

## Notes

- If the API is unreachable, fall back to listing the fleet-side suits from the two config files and mark the output "fleet-config only, unverified against API".
