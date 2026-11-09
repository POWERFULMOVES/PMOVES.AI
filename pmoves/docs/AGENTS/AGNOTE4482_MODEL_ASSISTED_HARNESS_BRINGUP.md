# Model-assisted harness bring-up — review and wiring (hf-agent + Archon + crush)

**Node:** SPARK · **Date:** 2026-09-14 · **Lane:** harness-minting loop, first concrete pass
**Trigger:** operator — "we have composio and vscode access to tailscale as well as mcp; make
review docs and/or hostinger tailscale; we can ask hf agent for model to assist in harness for
bring-up with archon or you."

This is the executable version of the positive-sum door's north star: **a model assists in
bringing up the harness that fits it** — with Archon minting, or with crush configuring itself.

## What is already running (measured)

| Surface | State |
|---|---|
| `pmoves-hf-agent` :8201 | **healthy, 515 models discovered**, polling; publishes `hf.model.discovered.v1` on NATS |
| `pmoves-hf-mcp-server` :8203 (loopback) | MCP surface for harness agents to query discovery |
| `pmoves-hf-research-agent` :8202 | deep-dive lane |
| Archon native :3090 | live (v0.6.0) — the minting/factory side |
| Composio key | funnel-registered (`composio_api_key` → env.tier-llm, on main) — external-app actions when needed |
| VS Code + Tailscale | operator-side reach to any node (the human lever for gates that need hands on hosts) |

## The loop (design; consumption side is the missing half)

```
hf.model.discovered.v1 (NATS, already flowing)
  → registry candidate (pmoves_core model registry — NEXT_STEPS "connect HF
    candidate discovery to registry candidates" has been open since the
    model-fitness lane; this is its trigger)
  → fitness evidence (TensorZero inference telemetry + evals; trusted only with
    signed Graphiti agreement — standing doctrine)
  → model-suit mint (pmoves/configs/model-suits/<model>.yaml — the per-model
    profile: context window, harness mappings, fallbacks)
  → harness bring-up, two doors:
      ARCHON door: mint the harness/agent definition (factory) + KB entry
      CRUSH door:  crush.json provider/model wiring on the node (self-config —
                   the model in the CLI tunes the harness around itself)
```

**Who asks the hf agent:** any harness agent via the hf-mcp-server (:8203) or a NATS request
on the discovery subject. The ask is not "give me a model" but "rank candidates against this
workload shape" — the patrol already holds the metadata (515 discovered).

## Review: Hostinger / Tailscale surface vs the current gates

The shared-DB doctrine's operator gates live on exactly this surface
(`FLEET_SHARED_DB_DOCTRINE.md`):

1. **Hub kong bind** (kvm4-2): a Hostinger VPS env change — reachable via the claw/SSH Known
   Roads (`make claw-verify SCOPE=kvm4-2` family) or VS Code Tailscale SSH.
2. **Tailscale ACL `:8000` hub-bound**: admin-console/API change — needs a LIVE
   `TAILSCALE_API_KEY` (current funnel key 401s — rotation still pending; measured
   2026-09-14).
3. **Funnel mint**: `fleet_reader` + `SUPA_REST_FLEET_URL` labels (CHIT pipeline, no host
   access needed).
4. `TAILSCALE_EXIT_NODE_RUNBOOK.md` (299 lines): still the operational reference for
   exit-node work; no conflicts with the doctrine, but it predates the shared-DB gates —
   when the ACL edit happens, add the hub-`:8000` rule alongside the exit-node rules there.

Composio's role: optional automation glue for external apps (e.g. Hostinger panel actions,
calendar/notify on gate completion). Not a dependency of the loop above; the key being
funnel-registered means any agent can adopt it when a concrete integration lands.

## Ordered next steps

1. **Registry candidate bridge**: subscribe `hf.model.discovered.v1` → upsert into the model
   registry (candidate status). Small service or extension of an existing worker.
2. **Fitness gate**: candidate → TensorZero variant → eval → scorecard (the standing
   model-fitness lane; `model.fitness.recorded.v1`).
3. **Suit-mint path**: scorecard above threshold → generate `model-suits/<model>.yaml` PR —
   Archon door (mint) or crush door (self-config), provenance signed.
4. **Bring-up recipe per node**: crush.json provider entry + TensorZero variant + (GB10)
   local weights lane for open-weight candidates.
5. Operator gates 1–3 above (the same gates the school queue waits on).

## Provenance

- hf-agent health/discovery: `http://localhost:8201/healthz` (measured)
- hf-agent source: `pmoves/services/hf-agent/main.py` (patrol + NATS publisher)
- Doctrine links: `AGNOTE4482.md` §Onboarding (positive-sum door),
  `FLEET_SHARED_DB_DOCTRINE.md` (gates), `MODEL_FABRIC_CONTRACT.md` (candidate → trusted
  flow), `pmoves/docs/AGENTS/AGNOTE4482_EVO_CONTROLLER_DEEP_DIVE.md` (north-star text)
