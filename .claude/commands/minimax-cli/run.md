# MiniMax CLI — Run

Execute a `mmx` CLI subcommand against the MiniMax model surface.

## Arguments

- `$ARGUMENTS` - the subcommand and flags to run (see the 14-command surface in `pmoves/docs/services/MMX_CLI_SURFACE.md`)

## Instructions

1. Confirm `mmx` resolves on PATH (installed via the `Pmoves-minimax-cli` submodule path). If missing, say so — do not hand-roll a replacement for an installed CLI.
2. Load credentials from the tier env files: the Token Plan key (`MINIMAX_TOKEN_PLAN_API_KEY`) with `MINIMAX_API_KEY` fallback, host `MINIMAX_API_HOST` (default `https://api.minimax.io`, OpenAI-compatible `/v1/chat/completions`; the old `chatcompletion_v2` path and `api.minimax.chat` host are retired).
3. Run the subcommand exactly as given; surface stderr verbatim.
4. On quota/auth failures, point at the Token Plan tier docs rather than retrying.

## Notes

- Boundary (MMX_CLI_SURFACE.md): the CLI is the operator surface; the MCP server (`uvx minimax-mcp`) is the programmatic one. Do not drive the MCP from here.
