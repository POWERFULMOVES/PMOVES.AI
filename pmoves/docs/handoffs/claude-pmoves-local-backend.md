# Handoff: `claude-pmoves --backend=local` (operator-apply launcher patch)

PR #3404. The python source of truth (`pmoves/tools/claude_backend.py local`) and the
tests are in the PR. The two launcher twins (`deploy/provision/claude-pmoves.{sh,ps1}`)
are `readOnly` under the damage-control `launcher` domain. An agent cannot grant itself a
Known Road, so the launcher half ships as a patch for the operator to apply.

## Apply (operator)

```bash
# in the shell that launches Claude Code, or as an operator-written file grant:
#   echo 'launcher:pr:3404' > .claude/hooks/damage-control/.known-road-active
git apply pmoves/docs/handoffs/patches/claude-pmoves-local-backend.patch
python -m pytest pmoves/tools/tests/test_claude_backend.py pmoves/tools/tests/test_claude_pmoves_launch.py -q
```

Before the patch is applied, 4 launch tests and 1 parity test fail, as intended. After it
is applied, the bash launch suite passes 10/10 on SPARK, measured by running the suite
against a patched copy.

## What `--backend=local` does

| Env (input) | Default |
|---|---|
| `PMOVES_LOCAL_ANTHROPIC_URL` | `http://127.0.0.1:11434` |
| `PMOVES_LOCAL_CLAUDE_MODEL` | `qwen3:30b-a3b-gpu` |
| `PMOVES_LOCAL_CLAUDE_SMALL_MODEL` | `qwen3:8b-gpu` |

Sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN=ollama` (a placeholder), `ANTHROPIC_MODEL`,
`ANTHROPIC_DEFAULT_{OPUS,SONNET}_MODEL` (main model) and `ANTHROPIC_DEFAULT_HAIKU_MODEL`
(the small model). `ANTHROPIC_DEFAULT_HAIKU_MODEL` is the current name for the background
or small-fast model. `ANTHROPIC_SMALL_FAST_MODEL` is deprecated (code.claude.com/docs/en/model-config;
code.claude.com/docs/en/env-vars). It also unsets `ANTHROPIC_API_KEY` and passes the same
routing as `--settings=<json>`. A settings.json `env` block overwrites shell exports
(code.claude.com/docs/en/settings-reference), and the command-line level outranks
user and project settings (code.claude.com/docs/en/settings). The MCP roster wiring is unchanged.

The preflight refuses to launch when `GET /api/version` gets no answer or either model is
missing from `GET /api/tags`. It warns when `/api/show` has no `num_gpu` (measured ~1 tok/s
off-GPU) or has `num_ctx` < 32768 (measured: n_ctx 8192 cut a 14k-token prompt down to
one-token replies).

## Measured on SPARK 2026-10-21 (Ollama 0.30.0, Claude Code 2.1.304)

`claude-pmoves --backend=local -p "say ok" --output-format json`:

- The session completed (`subtype: success`) in 233 s over 7 turns. Every turn went to
  `qwen3:30b-a3b-gpu` (`modelUsage` shows no cloud model). The `costUSD` figure is
  Claude Code's list-price estimate, not a real charge.
- The prompts reaching the 32768 slot were `task.n_tokens` = 30005, 30801, 26707 and 26773,
  all with `n_keep = 4`. Claude Code reported 114,286 input tokens over all turns.
- The reply was off-task: the model followed the brainstorming skill instead of saying
  "ok". This run had no `env.shared`, because the worktree root has none, so some MCP
  servers ran degraded. The full roster's tool definitions would add to the prompt.

**Is 32768 enough?** Not reliably. The first request used 30,005 of 32,768 tokens, which
leaves about 2.7k for output and growth, and a fuller MCP roster adds more. It is also
unverified whether Ollama cut the request down before the runner saw it: `n_keep = 4` and
the off-task reply both point that way. Ollama's Claude Code page recommends a 64k+ context.
qwen3-30b-a3b is natively 40960 (`qwen3moe.context_length`), so going past that needs
RoPE/YaRN scaling. `qwen3-coder:30b` (installed) has a native 256k context and may suit
this better.

Operator-owned host: no Ollama model was created or modified. To make a 64k variant:

```bash
curl -s http://127.0.0.1:11434/api/create -d '{
  "model": "qwen3:30b-a3b-gpu-64k",
  "from": "qwen3:30b-a3b-gpu",
  "parameters": {"num_ctx": 65536, "num_gpu": 999}
}'
PMOVES_LOCAL_CLAUDE_MODEL=qwen3:30b-a3b-gpu-64k claude-pmoves --backend=local
```

## Unverified

- The ps1 twin has not been parsed or run: `pwsh` is blocked by worktree isolation on
  SPARK, and the Windows launch tests run only on Windows.
- Found, not fixed: in the bash twin, `claude_backend_apply` runs `(eval "$_apply_out")`
  inside a subshell, so the `apply` strip never reaches the parent shell. The env.shared
  sweep currently hides this.
