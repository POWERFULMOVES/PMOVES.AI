# Pipecat fork family — provenance audit (2026-10-30)

**Operator question (verbatim):** *"where is doc provenance i forked multiple pipecat repos cluding a context one"*
**Author:** 5090-CLAUDE · **Operator:** DARKXSIDE
**Scope:** the four `POWERFULMOVES/pipecat-*` forks — where their provenance is recorded, and what the automation actually does with them.

---

## The short answer

**The doc provenance EXISTS and is in three places.** But it is *prose* provenance, not *machine* provenance — and the machine layer has a hole that lets the family drift untracked.

| Fork | Prose provenance | In `fork_registry.json`? | In `fork-sync.yml` FORKS? | In GH App token scope? | Drift vs upstream |
|---|---|---|---|---|---|
| `pmoves-pipecat` (the submodule) | `PIPECAT_FLEET_REVIEW.md`, `pipecat-schooling-mapping-2026-09-15.md` | **YES** (`sync: false`) | no (correct — `sync: false`) | no (correct) | **8015** behind on `main`; **3523** behind / 9 ahead on `PMOVES.AI-Edition-Hardened` |
| `Pmoves-pipecat-context-hub` | `PIPECAT_FLEET_REVIEW.md`, `pipecat-schooling-mapping-2026-09-15.md`, `AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md` | **YES** (`sync: true`) | **NO** ← gap 1 | **NO** ← gap 1 | **456** behind, 0 ahead |
| `Pmoves-pipecat-client-web-transports` | `PIPECAT_FLEET_REVIEW.md`, `pipecat-schooling-mapping-2026-09-15.md` | **NO** ← gap 2 | no (follows gap 2) | no | **117** behind, 0 ahead |
| `Pmoves-pipecat-mcp-server` | `PIPECAT_FLEET_REVIEW.md` only | **NO** ← gap 2 | no (follows gap 2) | no | **0** behind, 0 ahead (upstream itself is dormant — last push 2026-02-12) |

**The context one — `Pmoves-pipecat-context-hub` — is the sharpest case.** It is the fork the operator named, it has the richest prose provenance of the four, it is registered with `sync: true`, and **it is not in the workflow that would honour that `sync: true`.** It has been sitting 456 commits behind since it was registered.

---

## Gap 1 — `sync: true` in the registry does not mean the workflow syncs it

`pmoves/config/fork_registry.json` and `.github/workflows/fork-sync.yml` are two independent lists. The registry says **32** forks want `sync: true`. The workflow's `FORKS` block enumerates **30** forks. Six registered `sync: true` forks are absent from the workflow:

- `Pmoves-pipecat-context-hub` (`pipecat-ai/pipecat-context-hub`)
- `PMOVES-KeYlOkODe` (`Kilo-Org/kilocode`)
- `PMOVES-ScaleTail` (`tailscale-dev/ScaleTail`)
- `PMOVES-natscli-CHIT-EeZz` (`nats-io/natscli`)
- `Pmoves-Glancer` (`nicolargo/glances`)
- `Pmoves-nats.net` (`nats-io/nats.net`)

All six are also outside the **GH App token scope** (136 repos listed in `fork-sync.yml`'s `repositories:` block — none of the six are in it). That is consistent and deliberate: the token is least-privilege, minted per the workflow's own list. The consequence is that a `sync: true` registration is **a claim with no mechanism behind it**.

**Why it matters:** the registry ratchet reports `83/83 decided` and exits 0. That is a *decision* gate, not a *coverage* gate. It cannot see this gap, because the gap is between the registry and the workflow — two files the ratchet never cross-checks.

**This is the same class as the gap the fork registry ratchet was written to close** ("an undeclared submodule-fork is invisible to rules 1-3, which is exactly how PMOVES.YT sat 206 commits behind"). The cross-check exists for `.gitmodules` → registry. It does not exist for registry → workflow.

---

## Gap 2 — two of the four pipecat forks are unregistered entirely

`Pmoves-pipecat-client-web-transports` and `Pmoves-pipecat-mcp-server` appear in **no** registry entry, **no** `_first_party` list, **no** `_excluded` list, and **no** `.gitmodules` submodule. They are prose-only.

Both are described in `PIPECAT_FLEET_REVIEW.md` with real roles:
- **`client-web-transports`** — 7 browser-side transports (daily, livekit, moq, small-webrtc, websocket, openai-realtime, gemini-live). The schooling doc names it the direct replacement candidate for flute's hand-rolled `flute_pipecat/transports/fastapi_ws.py`. **117 commits behind.**
- **`mcp-server`** — the voice/screen MCP server exposing tools to MCP clients, with a headless `bot.py` harness for a Jetson/KVM. **Upstream is dormant** (last push 2026-02-12, 155 stars) so the fork is not behind at all — but the doc's "needs upstream drift check" is still an open item, and the fork is invisible to the machinery that would answer it.

---

## Gap 3 — the flute container was 65 days stale because the image build is manual-only

The operator's earlier point — *"this should not be the case we have github app that is supposed to automate updates and releases"* — is **correct**, and the mechanism is now identified.

`pmoves/images.yaml` DOES declare the flute image:

```yaml
- name: pmoves-flute-gateway
  context: pmoves
  dockerfile: services/flute-gateway/Dockerfile
```

But the workflow that reads that matrix is `build-images.yml`, and its trigger block is:

```yaml
on:
  workflow_dispatch:
```

**Manual dispatch only.** There is no `push:` trigger, no `schedule:`, no `repository_dispatch:`. The `push: true` that appears at `build-images.yml:116` is the **buildx** `--push` flag, not a workflow trigger — an easy misread, and I checked it specifically.

The automated integration builder `integrations-ghcr.yml` has a `schedule:` — but it is **commented out** (`integrations-ghcr.yml:97-98`), and its matrix (`integrations-ghcr.matrix.json`, 15 entries) **does not include flute-gateway**.

**The GH App is scoped to FORKS, not IMAGES.** The `fork-sync.yml` app token mints for 136 fork repos; image publishing uses a separate `GHCR_TOKEN` / `GHCR_USERNAME` secret pair (`build-images.yml:19-20`). There is no app-driven image rebuild.

So: the flute image was 65 days stale because **nothing rebuilds it automatically.** The GH App the operator is thinking of automates *fork* sync — and flute's image is not a fork.

---

## Gap 4 — `fork_sync.py` crashes on Windows and cannot audit 6 of 82 forks

Found while measuring drift. `pmoves/tools/fork_sync.py:88-90`:

```python
return subprocess.run(
    cmd, capture_output=True, text=True, check=check, timeout=60,
)
```

`text=True` with **no `encoding=`** → Python decodes the child's stdout with the **locale** encoding. On this Windows host that is **cp1252**. A `gh api compare` payload containing a UTF-8 continuation byte raises `UnicodeDecodeError` **inside the reader thread**, which leaves `result.stdout` as `None` → `AttributeError: 'NoneType' object has no attribute 'strip'` at `fork_sync.py:103`.

**Measured: 6 of 82 registry fork compare-payloads are not cp1252-decodable:**

| Fork | Failing byte |
|---|---|
| `PMOVES-Open-Notebook` | `0x8f` @ 198160 |
| `PMOVES-hermes-agent` | `0x9d` @ 354498 |
| `PMOVES-Agent-Zero` | `0x90` @ 143048 |
| `PMOVES-BotZ-gateway` | `0x90` @ 57457 |
| `PMOVES-skills` | `0x9d` @ 39049 |
| `PMOVES-Ultimate-TTS-Studio` | `0x8f` @ 93041 |

The remaining 76 decode fine. Verified fix: `encoding="utf-8"` makes the hermes-agent payload decode cleanly (1608513 bytes → 1607058 chars) where cp1252 fails at position 354498.

**This is the same defect class already recorded** in `pmoves/docs/AGENTS/windows_cp1252_hardening_test_ratchet_LEARNINGS.md` (the `compose_data` fixture in `test_docker_hardening.py` opening files with no `encoding=`). That lane fixed the *test* fixture; this is the same bug in *tool* code, and it was not caught because CI runs on Ubuntu where the locale is UTF-8.

**Impact:** the fleet drift audit — the tool that would answer "is this fork stale?" — **cannot complete on a Windows host**. It dies partway through. Any operator asking "how far behind is X?" on the operator's own machine gets a stack trace instead of an answer.

---

## Where the doc provenance actually lives (the direct answer)

1. **`pmoves/docs/services/PIPECAT_FLEET_REVIEW.md`** — the canonical fork-family table: all four forks, their role in the voice scenario, and their state. This is the primary provenance document.
2. **`pmoves/docs/specs/pipecat-schooling-mapping-2026-09-15.md`** — the correspondence map for `context-hub` + `client-web-transports`: what each Pipecat capability maps onto in PMOVES, what is unused, and the four "patterns that eluded us" mined from the forks.
3. **`pmoves/docs/AGENTS/AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md`** — the SPARK fork-registry reconciliation lane that **registered** `Pmoves-pipecat-context-hub` (its summary table shows "Registry before: **missing** → registered").
4. **`pmoves/config/fork_registry.json`** — machine provenance for **2 of 4** (see gap 2).
5. **`pmoves/config/agent_registry.yaml:3774`** — `pipecat_context_hub` agent entry: `fork: Pmoves-pipecat-context-hub`, `transport: http`, `endpoint: null`, `status: planned`, with the planned endpoint `http://pipecat-context-hub:8204/mcp` recorded.
6. **`pmoves/config/mcp_inventory.json`** — `pipecat-context-hub` IS registered as an MCP entry in the `core_pmoves` group (wired by PR #3064 via the ACP-registry bridge), with the caveat that no agent seat has it installed.

**Cross-references:** `.gitmodules:138` pins `PMOVES-Pipecat` → `POWERFULMOVES/pmoves-pipecat` on branch `PMOVES.AI-Edition-Hardened`, gitlink `a12efa492`; `pmoves/configs/submodule_skill_registry.json:447` registers the `PMOVES-Pipecat` submodule's skills; `pmoves/configs/topology/submodule_services.yaml:98` maps the `pipecat` + `pipecat-context-hub` compose keys.

---

## Why the flute lane's own notes pointed the right way

`PIPECAT_FLEET_REVIEW.md:17-19` recorded, in September:

> "**MCP**: the voice-fabric plan Layer 1 = flute `/mcp` mount (FastAPI) exposing voice_synthesize/stream/recognize/personas/engines_list/capabilities → **NOT yet verified live** (flute container stuck Created under docker contention this session)"

and line 44: "**flute /mcp mount unverified** — Layer 1 of the voice plan; needs live check once flute runs".

**That is the same `/mcp` route** that the stale 2026-08-08 image did not serve — the route the `flute-voice-mcp` inventory entry declared and all six client configs carried as a 404. The review noted the route was unverified; nothing then verified it against the *running image*; and 65 days later the running image was still the one that lacked it. **The flute lane's ratchet (`pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py`, PR #3428) is the thing that closes that loop** — it probes the running service and asserts the responder identifies as `pmoves-flute-gateway`.

The September review also predicted the fork layer: *"mcp_inventory has ZERO pipecat entries — context-hub and mcp-server should register (stdio local for hermes/crush/a0 clients) once verified"*. `context-hub` got registered via #3064; **`mcp-server` never did** — which is gap 2.

---

## Recommended lanes (each independently shippable)

1. **Register the two unregistered pipecat forks** in `pmoves/config/fork_registry.json` with `sync` + `reason` + `branch`, so the ratchet can see them. (`client-web-transports` → `sync: true`; `mcp-server` → `sync: true`, upstream dormant but the decision should be explicit.)
2. **Close the registry → workflow gap.** Either add the 6 missing `sync: true` forks to `fork-sync.yml`'s `FORKS` block + GH App scope, or downgrade their registry `sync` to `false` with a reason. The current state — claiming `sync: true` with no mechanism — is the defect either way.
3. **Add a registry → workflow coverage ratchet** to `fork_registry_ratchet.py`: every registry fork with `sync: true` must appear in `fork-sync.yml`'s `FORKS` block. That is the cross-check the ratchet is missing, and it is the same shape as the `.gitmodules` → registry check it already does.
4. **Fix `fork_sync.py:88`** — add `encoding="utf-8"`. One line; restores the drift audit on Windows hosts.
5. **Decide the flute image rebuild path** — either add a `schedule:`/`push:` trigger to `build-images.yml`, or un-comment the `integrations-ghcr.yml` schedule and add flute-gateway to its matrix. Until one of those exists, the flute image will go stale again the same way, and the PR #3428 ratchet will be the only thing catching it.

---

## Test status

No code changed in this lane — it is a read-only provenance audit. All measurements are live `gh api` / local `git rev-list --left-right --count` against the four forks on 2026-10-30.
