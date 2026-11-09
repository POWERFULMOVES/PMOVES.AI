# Archon: coding-plan-first auth and the `claude-pmoves` harness

**Status:** finding verified 2026-08-24 on the 4090. Core fix shipped as
POWERFULMOVES/PMOVES-Archon#25; compose stopgap in this PR; harness scoped below.
**Owner:** 4090-claude (CLAUDE-OPUS-5)

## The finding

`pmoves-archon-1` is healthy and Claude Code **2.1.209** is already inside it
(`/app/node_modules/@anthropic-ai/claude-agent-sdk-linux-x64/claude`, 260 MB, resolved by
absolute path in `docker-entrypoint.sh` — it is deliberately NOT on `$PATH`, so
`command -v claude` returning nothing proves nothing).

Archon is one working credential away from running. The blocker is auth **precedence**,
verified in-container rather than inferred:

| env | CLI result |
|---|---|
| dead `ANTHROPIC_API_KEY` only | `Credit balance is too low` |
| dead key **+** OAuth token | `Credit balance is too low` — **key wins** |
| OAuth token only | `401 Invalid bearer token` — token is used |
| `ANTHROPIC_API_KEY=""` + OAuth token | `401` — **empty string == absent** |

The `ANTHROPIC_API_KEY` archon inherits is a **live key with zero credit** (HTTP 400
`credit balance is too low`, confirmed against the API directly). It authenticates as
*present*, so it wins precedence, and then fails every call.

**Consequence:** delivering a valid `CLAUDE_CODE_OAUTH_TOKEN` to this node does **not**
fix archon on its own. It still reports "Credit balance is too low", which reads as a bad
token and sends you debugging the wrong half.

## Root cause — an upstream gap, not our misconfiguration

`packages/providers/src/claude/provider.ts` already knows about this trap. The comment
above the mirror guard says the CLI "prefers ANTHROPIC_API_KEY over the OAuth token, so
injecting the install key alongside it would silently rebill the run", and guards
accordingly:

```ts
if (env.CLAUDE_API_KEY && !env.ANTHROPIC_API_KEY && !env.CLAUDE_CODE_OAUTH_TOKEN) { ... }
```

That guard covers an **injected** key. It did not cover an **inherited** one:
`buildSubprocessEnv()` spreads the host process environment, so a key already present
flows through and wins. Same hazard, different door.

Fixed in **POWERFULMOVES/PMOVES-Archon#25** — drops the key only when it was inherited
*and* an OAuth token is present, leaving Archon-managed per-user credentials
authoritative. Upstreamable as-is; nothing in it is PMOVES-specific.

## Track 1 — compose stopgap (this PR)

The core fix ships with the next archon image rebuild. Until then the running container
still inherits the dead key, so neutralise it at the compose layer:

```yaml
# archon service environment:
- ANTHROPIC_API_KEY=
```

Empty assignment is sufficient (row 4 of the table) — no vector-style entrypoint `unset`
wrapper needed. Scoped to archon; every other service keeps what the shared env provides.

Worth keeping after the rebuild as defence in depth: it costs nothing and makes the
posture legible at the deployment layer.

Still requires the token value on this node. Sanctioned no-paste route (manifest slot
registered in #2700):

```
export PMOVES_ROTATE_VALUE=<token from `claude setup-token`>
make -C pmoves secrets-rotate KEY=CLAUDE_CODE_OAUTH_TOKEN
```

## Track 2 — the `claude-pmoves` harness

Archon has a first-class provider registry (`packages/providers/src/registry.ts`:
`registerProvider({ id, displayName, factory, capabilities, builtIn, credentials })`) with
community providers (`copilot`, `opencode`, `pi`) as precedent — each a small
`registration.ts` + `capabilities.ts` + `provider.ts` under `community/`. Archon builds
locally (`build.context: ../PMOVES-Archon`), so a new provider ships with a normal image
rebuild rather than an upstream release.

**Deliberately NOT built as part of this fix.** The auth bug belongs in core, where it
fixes the stock `claude` provider for everyone — wrapping it in a PMOVES harness would
have shipped a provider whose only feature was a workaround for a bug we could simply fix.
Archon's own engineering constitution rules that out: *"Do not introduce speculative
abstractions without at least one current caller."*

`claude-pmoves` earns its registration when it carries posture core should not have:

1. **Model/provider routing across harnesses** — the customization named in the original
   directive. Concretely: PMOVES tier/alias resolution against the fleet's own model
   catalog rather than a hand-maintained `config.yaml`.
2. **CHIT integration** — signing/attestation on run boundaries, the seam PMOVES adds that
   upstream would plausibly want back.
3. **Fleet-aware execution** — routing a node to the capability-matched machine (SPARK
   arm64, 5090, 4090) instead of assuming local execution.

Register `builtIn: false`, mirroring `pi`, whose registration documents that flag as
load-bearing: community providers must not be conflated with core until explicitly
promoted.

**Prerequisite worth naming now:** `buildRequestSubprocessEnv` is a module-level function
called directly at `provider.ts:1267`, not a method — so a subclass cannot override the env
seam today. A `claude-pmoves` extending `ClaudeProvider` will first need that call routed
through a `protected` method. Small, and independently upstreamable.

## Probe hygiene note

`docker exec` does **not** inherit the entrypoint's `export`s. Probing auth vars that way
reports empty for variables the real PID-1 process has set, and `/proc/1/environ` is not
readable as the non-root `appuser`. Test the binary directly instead.
