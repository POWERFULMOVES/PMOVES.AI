#!/usr/bin/env bash
# codex-pmoves — Bootstrap Codex CLI with PMOVES context
# Usage: codex-pmoves [codex-args...]
#
# Launches OpenAI Codex CLI with PMOVES project context.
# Codex is restricted to OpenAI models (GPT-5.4 / codex).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"
exec codex "$@"