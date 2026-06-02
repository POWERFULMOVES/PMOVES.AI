# Circuit-Breaker Principle: "Three Times the Charm = Stop"

## Core Ideal
> One clean failure beats three escalating ones.
> The damage from persistence is not linear — it's multiplicative.

## When This Applies
- **Service retry logic**: After N failures on a dependency, OPEN the circuit. Stop hitting it.
- **Agent tool calls**: If a tool fails, don't blindly retry. Reflect on WHY before trying again.
- **Human-AI interaction**: If the user signals frustration or confusion, STOP executing and reflect.
- **Pipeline processing**: If a downstream dependency is unreachable, fail-fast or fail-open — don't queue work that will timeout.

## The Multiplier Effect
Under concurrency, blocked workers accumulate:
- 1 failed request × 10s timeout = 10s waste
- 50 concurrent requests × 10s timeout = worker pool starvation
- Worker pool starvation = ALL requests fail, including health checks
- Health check failure = orchestrator restarts the service
- Restart doesn't fix the dependency = infinite restart loop

**The third attempt doesn't fail gracefully — it fails catastrophically by taking down the observer.**

## Implementation Rules
1. **Fail fast**: Don't wait for timeout if you can detect unreachability early (TCP connect vs HTTP response)
2. **Fail open**: When an optional dependency fails, degrade gracefully (return partial results, not errors)
3. **Fail observable**: When degrading, LOG it and REPORT it in health endpoints. Never mask degradation.
4. **Stop and reflect**: After the first clear failure signal, pause. Ask: is retrying going to help, or am I making it worse?
5. **Preserve context**: The state of the system at failure is valuable data. Spiraling destroys that state.

## Anti-Patterns (What NOT to Do)
- ❌ Retry without circuit breaker (unbounded damage under concurrency)
- ❌ Healthcheck that returns healthy when dependencies are degraded
- ❌ Silent fail-open that doesn't log or report the degradation
- ❌ Hardcoded feature flags (USE_MEILI=true) with no escape hatch
- ❌ Phantom defaults that mask configuration errors ("master_key" as default auth)
- ❌ Agent retry loops that burn context window on failing tool calls

## Carried Forward
This principle is a central ideal — not a lofty goal, but a practical constraint.
Every system built here should have a circuit breaker. Every agent interaction
should recognize when persistence causes more harm than the original failure.
Stop. Reflect. Preserve context for both yourself and everyone who follows.
