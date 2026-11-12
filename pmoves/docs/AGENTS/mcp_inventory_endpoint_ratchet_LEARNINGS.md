# MCP inventory endpoint ratchet — LEARNINGS

**Lane:** flute-voice-mcp inventory entry — the declared endpoint was correct, the DEPLOYMENT was stale
**Branch:** `fix/mcp-inventory-endpoint-ratchet`
**Operator:** DARKXSIDE · **Author:** 5090-CLAUDE
**Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (2026-10-30T19:5x:xxZ)
**Related lane:** `test_gap_ratchet_LEARNINGS.md` (the kilo/mavis ratchet slice — lessons #9–#12 there are the direct ancestors of lesson 1.4 below)

---

## Operator direction (verbatim)

> "New lane: fix the flute-voice-mcp inventory entry — it reaches all six sibling clients' configs; I deliberately did not fold that into #3418 (blast radius)."

---

## The finding

**The inventory entry was CORRECT.** It was not edited. Editing it would have been the workaround: it accurately described the service's source, while the running deployment lagged behind that source by 65 days.

Measured on the operator's host, 2026-10-30:

```
$ docker ps --filter name=flute-gateway
pmoves-flute-gateway-1 | ghcr.io/powerfulmoves/pmoves-flute-gateway:latest | Up 2 days

$ docker image inspect ghcr.io/powerfulmoves/pmoves-flute-gateway:latest
created=2026-08-08T16:37:12Z          <-- 65 days BEFORE the route landed
```

The route the entry declares IS in the source:

| Fact | Location |
|---|---|
| `@router.post("/mcp")` | `pmoves/services/flute-gateway/mcp_bridge.py:508` |
| `@router.get("/sse")` | `pmoves/services/flute-gateway/mcp_bridge.py:529` |
| `@router.post("/messages")` | `pmoves/services/flute-gateway/mcp_bridge.py:568` |
| `app.include_router(create_mcp_router(...))` | `pmoves/services/flute-gateway/main.py:619` |
| The route landed in source | 2026-09-12, PR #3036, commit `8c366f68410` |

But the RUNNING container's route table had **no `/mcp`**. The image was built 65 days before the route existed in the source. So the entry reached all six sibling clients while pointing at a URL that answered **404**.

**Blast radius, confirmed from source:** the `flute-voice-mcp` entry declares no `clients` key, and `ServerSpec.supports_client` returns `True` for every client when `clients is None` (`pmoves/tools/mcp_config_generator.py:66-69`). The roster has six clients — `claude`, `kimi`, `opencode`, `kilocode`, `hermes`, `crush` (`pmoves/tools/mcp_config_generator.py:328-335`). The operator's "all six sibling clients" is exact.

**The fix was the DEPLOYMENT, not the config:**

```
make -C pmoves rebuild-svc SVC=flute-gateway
```

New image `created=2026-10-30T19:39:03Z`. Live probe after the rebuild:

```
$ curl -X POST http://localhost:8055/mcp -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'
HTTP 200
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"pmoves-flute-gateway","version":"1.0.0"}}}
```

> **A raw `docker compose build flute-gateway` FAILS.** Compose interpolates the whole project, and 25+ unrelated services need tier env vars that only exist in the tier env files. The Makefile resolves `COMPOSE_ENV_FILES` from `PRIMARY_ENV_FILE` + `TIER_ENV_FILES`. Use `make -C pmoves rebuild-svc SVC=flute-gateway`.

---

## 4-bucket · 5-class taxonomy

### Bucket 1 — Defects

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1.1 | **stale-deployment-masquerading-as-config-defect** | **A correct config + a stale deployment is indistinguishable from a wrong config at the config layer.** The operator's instruction was to "fix the flute-voice-mcp inventory entry". Editing the entry to match the running container would have been a WORKAROUND: it would have made the 404 look intentional, permanently broken the entry against a source that serves `/mcp`, and left the six client configs pointing at a wrong URL. The defect was in the DEPLOYED IMAGE, not in the DECLARATION. **Fix the deployment; never edit a correct declaration to match a stale runtime.** | The entry was left byte-identical. The route is in source (`mcp_bridge.py:508`, landed 2026-09-12 / `8c366f68410`); the image was `2026-08-08T16:37:12Z`. Fix = `make -C pmoves rebuild-svc SVC=flute-gateway`. | Any "fix the config" instruction where a runtime probe contradicts the source. |
| 1.2 | **blast-radius-not-folding** | **A fix that reaches every client's config is a separate lane by blast radius, not a nicety.** The operator explicitly did not fold the flute fix into #3418 (the MiniMax client-parity PR) because the inventory entry reaches all six clients' configs. This lane therefore carries its own branch, its own PR, its own AGNOTE row and its own LEARNINGS file. | The entry has no `clients` key → `supports_client` → `True` for all → `RENDERERS` has 6 clients (`mcp_config_generator.py:328-335`, `:66-69`). | Any fix whose reach is wider than the PR it was found in. |
| 1.3 | **route-declared-but-not-mounted** | **A route decorator in a module that is never included in the ASGI app is the same 404 with an extra step of indirection.** The ratchet asserts BOTH: the decorator exists in the source, AND `app.include_router(...)` mounts the router. Asserting only the decorator would pass against a router that is built and discarded. | `test_inventory_flute_route_is_mounted_in_service_app` asserts `create_mcp_router` appears in `main.py` AND `re.search(r"app\.include_router\(", main_source)` matches. | Any FastAPI/Starlette service whose routes live in a router module. |
| 1.4 | **not-404-is-not-a-suff assertion** | **"The endpoint did not 404" is too weak to be a pass.** ANY service holding port 8055 satisfies "not 404". The live probe therefore asserts three properties: not a 404, not a 5xx, AND `serverInfo.name == "pmoves-flute-gateway"` — so a port collision cannot masquerade as the service. | `_assert_responder_is_flute_gateway()` in `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py`. Mutation-killed: weakening the identity assert to `assert True or ...` → `test_live_probe_rejects_a_responder_that_is_not_the_flute_gateway` FAILED (DID NOT RAISE). | Any live probe against a fixed port. |
| 1.5 | **inert-control** | **A knob that looks like it controls something but does not is the same defect class this ratchet exists to catch.** The first cut of the live probe read `FLUTE_GATEWAY_URL` into `base` and then probed the INVENTORY URL — the override gated reachability but never redirected the probe. It was an override in name only. Fixed by `_probe_url(declared_url, base)`, which rebases the declared URL onto the override while preserving the PATH. | `test_live_probe_url_follows_the_base_override` asserts `_probe_url("http://localhost:8055/mcp", "http://flute-node.internal:9000") == "http://flute-node.internal:9000/mcp"` and that it differs from the original. | Any env-var override, feature flag, or env switch. |

### Bucket 2 — Decisions

| # | Class | Observation (rule) | Why | Alternative considered | Cost of alternative |
|---|-------|---------------------|-----|------------------------|---------------------|
| 2.1 | **fix-deployment-not-declaration** | Rebuild and redeploy the service; leave `mcp_inventory.json` untouched. | The declaration matches the source, which is the reference. The image is the drifted artefact. | Edit the inventory entry to remove/redirect `flute-voice-mcp` | A workaround: the entry would contradict the source, all six clients would carry a knowingly-wrong URL, and the real fault (a 65-day-old image) would be hidden. |
| 2.2 | **static-plus-live, not live-only** | The ratchet has TWO halves: a static half (always on, no network, no service) and a live half (runs when the service is reachable, skips otherwise). | The static half catches authoring-time drift in ANY checkout, including CI with no service running. The live half catches deployment staleness, which static analysis cannot see. A live-only ratchet would skip in CI; a static-only ratchet would miss exactly the defect that shipped. | Live only | Skips in CI — the ratchet would be dead where it matters most. |
| 2.3 | **skip-is-not-a-pass** | The live half skips (does not pass) when the service is unreachable, and the docstring says so explicitly. | Deployment is a separate lane from the code lane. A skip must not be read as a pass, and the docstring says so at the point of use. | Fail when unreachable | CI would be red on every checkout without a running service — noise that trains people to ignore the gate. |
| 2.4 | **separate branch-and-PR** | This lane is `fix/mcp-inventory-endpoint-ratchet`, not a commit on #3427 (the ratchet-correction PR) nor a fold into #3418. | The operator called it a NEW lane and cited blast radius. Two of its three artefacts (the ratchet, the mutation-kill) are new files, so a shared branch would have coupled two unrelated reviews. | Fold into #3427 | Couples the flute deployment fix to the mavis CLI ratchet correction; the reviews share no subject. |
| 2.5 | **mutation-kill-invokes-the-ratchet** | The harness calls the ratchet's OWN functions (`test_inventory_flute_endpoint_is_declared_in_service_source`, `test_inventory_flute_route_is_mounted_in_service_app`, `_assert_responder_is_flute_gateway`, `_probe_url`) rather than re-implementing the checks. | Lesson #12 of `test_gap_ratchet_LEARNINGS.md`: a mutation-kill that RESTATES the assertion proves nothing — the first attempt at the mavis mutation-kill re-implemented the gate inline, the mutation SURVIVED (7 passed). | Restate the checks in the harness | The harness would pass while the ratchet was broken — exactly the failure it exists to prevent. |
| 2.6 | **control-case-in-every-harness** | Every mutation-kill set includes an un-mutated control that must PASS. | Without it, a harness that fails for any reason (typo in the mutation, import error) looks like a successful kill. | Mutation cases only | False confidence in the harness. |

### Bucket 3 — Operations

| # | Class | Observation (rule) | Measured | Repeatability |
|---|-------|---------------------|----------|---------------|
| 3.1 | **make-rebuild-svc-is-the-only-working-rebuild-path** | `make -C pmoves rebuild-svc SVC=flute-gateway` resolves `COMPOSE_ENV_FILES` from `PRIMARY_ENV_FILE` + `TIER_ENV_FILES` and rebuilds + recreates the service. | A raw `docker compose build flute-gateway` FAILS: compose interpolates the entire project and 25+ unrelated services need tier env vars. | Every stale-image rebuild on this fleet. |
| 3.2 | **image-creation-date-is-the-fingerprint** | `docker image inspect <image> --format created={{.Created}}` is the cheapest way to prove an image predates a source change. | Old: `2026-08-08T16:37:12Z` (65 days before the route landed). New: `2026-10-30T19:39:03Z`. | Whenever a service "works in source but not at runtime". |
| 3.3 | **live-probe-uses-the-mcp-handshake-not-an-openapi-diff** | The probe POSTs a JSON-RPC `initialize` and reads `serverInfo.name`. It does not diff the OpenAPI schema. | Live: `{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"pmoves-flute-gateway","version":"1.0.0"}}`. | Any MCP-over-HTTP service. |
| 3.4 | **absolute-paths-only-for-mutation-harness** | The harness copies the service tree to `tmp_path` and repoints the ratchet's module constants. Any `Path.relative_to(PMOVES_ROOT)` in the ratchet's failure MESSAGE raises `ValueError` on that copy. | The first run of the harness failed 3/8 with `ValueError: ... is not in the subpath of ...pmoves` — a ratchet whose failure message raises reports the WRONG failure. Fixed with `_display_path()`, which falls back to the absolute path. | Any ratchet whose error message formats a path. |
| 3.5 | **importlib-reload-in-the-harness** | The harness calls `importlib.reload()` on the ratchet module for every case. | Without the reload, `FLUTE_SERVICE_DIR` stayed pointed at the PREVIOUS case's mutated copy, and the next case failed with "mutation setup failed: route decl not found" instead of running its assertion. | Any harness that mutates module-level state. |

### Bucket 4 — Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | **lesson-9-lineage** | "A test that can only assert absence cannot say no" — the ancestor of lesson 1.4 (not-404 is not a pass). | `pmoves/docs/AGENTS/pmoves_launcher_generator_LEARNINGS.md` lesson #9 | The same rule, one layer up: absence of an error is not evidence of a working system. |
| 4.2 | **lesson-12-lineage** | "A mutation-kill that restates the assertion instead of invoking it proves nothing." | `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` lesson #12 | Directly applied here — decision 2.5. |
| 4.3 | **sibling-harness-shape** | The mavis ratchet's mutation-kill harness is the pattern this harness follows (mutate → re-run → assert it fails → restore in `finally`). | `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | Two harnesses, one shape, so the next agent recognises the idiom. |
| 4.4 | **the-inventory-is-the-source-of-truth-for-endpoints** | `mcp_inventory.json` + `mcp_config_generator.py` are the contract; the six client configs are DERIVED from them. | `pmoves/config/mcp_inventory.json`, `pmoves/tools/mcp_config_generator.py:66-69` (supports_client), `:328-335` (RENDERERS) | Which artifact to fix is decided by asking: is the DERIVATION right, or the SOURCE? Here the source was right and the deployment was stale. |
| 4.5 | **container-rebuild-manifest** | The repo already tracks flute-gateway as a rebuild target. | `pmoves/docs/operations/CONTAINER_REBUILD_MANIFEST.md` (row 1: flute-gateway, `services/flute-gateway/Dockerfile`, `ghcr.io/powerfulmoves/pmoves-flute-gateway:latest`) | The rebuild was a known, documented obligation that had simply not been executed for 65 days. |
| 4.6 | **operator-queue-provenance** | The lane was raised in the operator's 2026-10-30 queue alongside the #3418/#3382/#3411 review work. | AGNOTE row (this lane) + `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` | One queue, several lanes, each with its own provenance so the trail stays per-lane. |

---

## Test inventory

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` (new) | 642 | 7 | The ratchet. Static half (6): the route DERIVED FROM THE INVENTORY must be declared in the serving source (×2 entries: `flute-voice` SSE + `flute-voice-mcp` HTTP), with the method derived from the inventory's `transport`; the MCP router must be the ARGUMENT of `app.include_router(...)` (×2); the entry must resolve to a URL carrying a PATH (×2 entries). Live half (1): the declared URL must answer, must not 404, must not 5xx, must carry the INVENTORY-declared credential, and the responder must identify as `pmoves-flute-gateway`. |
| `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` (new) | 543 | 13 | The PROVENANCE harness. 6 static mutations (route removed / mount removed / another router mounted / the inventory declares an unserved path / both removed / un-mutated control) + 7 live-half cases (override rebases the probe URL / a no-path URL is rejected / the declared credential is sent / an unavailable credential skips / an impostor responder is rejected / a 404 is rejected / the genuine service passes). |

Total: **20 new tests across 2 new files.** No existing file was modified — this lane is purely additive, which is what keeps its blast radius separate from #3418's.

---

## SDK provenance

- **Ratchet:** `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` — `_assert_responder_is_flute_gateway()`, `_probe_url()`, `_display_path()`, `FLUTE_SERVER_KEYS`, `FLUTE_ROUTER_MODULE`, `TRANSPORT_METHODS`, `FLUTE_SERVER_NAME`
- **Ratchet (review hardening):** `_declared_path()`, `_url_path()`, `_declared_routes()`, `_mcp_router_mounted()`, `_resolve_declared_headers()`, `_probe_headers()`
- **Ratchet (review hardening, round 2 — finding 4428873759):** `MCP_ROUTER_FACTORY`, `_decorator_route()`, `_route_decorators()`, `_factory_node()`, `_nested_def_nodes()`, `_factory_bindings()`, `_route_ownership()`, `RouterOwnershipError`, `_assert_route_on_returned_router()`
- **Ratchet (review hardening, round 3 — finding 4429144504):** `_Scope` (scope path + binding resolution), `_target_names()`, `_collect_bindings()`, `_scope_tree()`, `_factory_returns()`, `_collect_returned()`, `_decorator_is_owned()`, `_describe_returned()`, `_factory_bindings()` **RETIRED** (its text-based returned set was the defect)
- **Harness:** `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` — `RATCHET_MODULE`, `MOUNT_CALL`/`MUTATED_MOUNT_CALL`, `MCP_ROUTER_FACTORY_CALL`/`MUTATED_ROUTER_FACTORY_CALL`, `DISABLED_SUFFIX`, `TARGET_KEY`, `UNSERVED_PATH`, `_route_declaration()`
- **Harness (round 2):** `_mutate_route_onto_sibling_router()`, `test_mutation_route_moved_onto_a_sibling_router_is_killed`
- **Harness (round 3):** `_replace_factory_return()`, `_mutate_factory_onto_a_constructed_router()`, `_legacy_owned()` (a FROZEN witness of the retired text-based rule), `test_mutation_factory_returning_a_constructed_router_is_killed`, `test_mutation_factory_returning_a_tuple_is_not_cried_wolf`
- **SDK files exercised:**
  - `pmoves/services/flute-gateway/mcp_bridge.py:508` — `@router.post("/mcp")` (the declared surface)
  - `pmoves/services/flute-gateway/mcp_bridge.py:529` — `@router.get("/sse")`
  - `pmoves/services/flute-gateway/mcp_bridge.py:401` — `serverInfo.name = "pmoves-flute-gateway"` (the identity the live probe asserts)
  - `pmoves/services/flute-gateway/main.py:619` — `app.include_router(create_mcp_router(...))`
  - `pmoves/config/mcp_inventory.json:12` — `defaults.flute_mcp_local_url = "http://localhost:8055/mcp"`
  - `pmoves/config/mcp_inventory.json:210-218` — the `flute-voice-mcp` entry (no `clients` key → all clients)
  - `pmoves/tools/mcp_config_generator.py:66-69` — `ServerSpec.supports_client` (None ⇒ every client)
  - `pmoves/tools/mcp_config_generator.py:328-335` — `RENDERERS` (the six clients)
- **Deployment provenance:** `make -C pmoves rebuild-svc SVC=flute-gateway`; image `created=2026-10-30T19:39:03Z`; live `POST http://localhost:8055/mcp` → **200** with `serverInfo.name = "pmoves-flute-gateway"`.
- **CI gate:** `merge-gate.yml::python-tests` runs `pmoves/tools/pytest_ratchet.py`, which discovers `pmoves/tests/**` without a paths filter — both new files land in the ratchet automatically.

---

## Test status

- `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` → **8 passed, 1 skipped** on this host. The skip is the live half, and the skip REASON is the point of lesson 1.7: the inventory declares `X-API-Key: ${FLUTE_API_KEY}` and that variable is unset here, so the probe declines to send an unauthenticated request and says why (header name + variable name, never a value).
- With `FLUTE_API_KEY` exported (any value — the local gateway runs in dev mode), the live half **RUNS and PASSES** against the running gateway → **9 passed**: `serverInfo.name = "pmoves-flute-gateway"`.
- `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` → **14 passed**.
- Combined (credential absent): **22 passed, 1 skipped**. Combined (credential exported): **23 passed**.
- Mutation-kill re-verified by hand after the review hardening: each of the four fixes was REVERTED in place and its harness case re-run — all four reverts were **KILLED** (the harness case failed, i.e. the mutation survived the reverted ratchet). Details in 3.6 below.

---

## Hand-written exclusions

This lane modifies **no** existing file. `pmoves/config/mcp_inventory.json` is byte-identical to `origin/main` — deliberately, because the entry was correct. The container rebuild is a host deployment action, not a repository change, and leaves no diff.

---

## Open follow-ups

1. **Fleet-wide image staleness.** The 65-day-old flute image was one instance of a general condition: nothing measures whether a running container's image is NEWER than the last commit that touched its source. The `CONTAINER_REBUILD_MANIFEST.md` lists six services with pending rebuilds. A fleet-wide "running image predates its source" ratchet is the natural generalization of this lane and is **not** done here.
2. **The other five manifest services.** `tensorzero`, `publisher-discord`, `botz-gateway`, `cipher-memory`, `pmoves-yt` carry the same rebuild obligation and have not been checked for staleness on this host.
3. **The six client configs.** This lane fixed the SERVICE, which makes the six clients' existing configs correct again. It did not regenerate them — no regeneration was needed, because the configs were already right; only the server was behind.

---

## Review hardening — 2026-10-30 (PR #3428 review threads)

**Status:** four review threads on PR #3428 challenged the RATCHET itself, not the deployment. All four were valid, and each one changed the SHAPE of an assertion rather than adding a check beside it. Lesson numbering continues from the taxonomy above (1.6–1.9, 2.7–2.8, 3.6–3.7, 4.7).

**The common thread:** every one of these ratchets could pass while the defect it exists to catch was PRESENT. That is the definition of a ratchet that cannot say no — the same rule as lesson 1.4, one layer down.

### Bucket 1 — Defects

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1.6 | **hard-coded-expected-value** | **An expected value that is written INTO the test cannot see the contract change.** A hard-coded expected value can only prove that ITS OWN value still exists; it is structurally blind to the contract it is supposed to police. The expected route must be DERIVED from the inventory's own declared URL. | Finding **4427921337** (P1). The first cut hard-coded `/sse` and `/mcp` in `EXPECTED_ROUTES`; the separate URL test only asserted that SOME path existed. Repoint `flute_mcp_local_url` at `/mcp-v2` and the assertion kept hunting for the old `/mcp` decorator while every client was handed a path nothing serves — and because the live half SKIPS in CI, the same client-wide 404 could merge undetected. Fixed: `_declared_path()` parses the declared URL's path, `_declared_routes()` lifts the route decorators out of the service source's AST, and the assertion is "the path the INVENTORY declares is among the routes the SOURCE declares". The METHOD is derived too, from the inventory's `transport` field (`TRANSPORT_METHODS`), so a route served with the wrong verb (405) is caught statically. | Any test whose expected value is also a value the production contract can change. |
| 1.7 | **credential-blind-probe** | **A probe against an AUTHENTICATED endpoint must carry the credential the CONTRACT declares — and a credential it cannot obtain is a SKIP with a reason, never a failure and never a silent pass.** | Finding **4427921351** (P1). The flute-gateway mounts the MCP router with `dependencies=[Depends(verify_api_key)]` (`main.py:624`) and the inventory declares `X-API-Key: ${FLUTE_API_KEY}`. The probe sent no key, so on a fleet deployment it was answered 401 — and a 401 reads exactly like "the wrong service answered" to a probe whose identity check is the handshake body. The probe was rejecting a HEALTHY endpoint. Fixed: `_resolve_declared_headers()` reads the declared header NAME and its `${VAR}` source from the inventory and resolves the value from the environment; `_probe_headers()` SKIPS when the variable is unset. The value is never hard-coded, never logged and never printed — the skip reason names the header and the VARIABLE only. | Any probe of an endpoint that declares a credential (API key, token, basic-auth). |
| 1.8 | **string-presence-is-not-a-call-argument** | **"The file contains the token" is not "the call mounts the object".** An assertion about a MOUNT must inspect the CALL EXPRESSION and require the right ARGUMENT. | Finding **4427921357** (P2). The old check proved `create_mcp_router` appears in `main.py` AND that `app.include_router(` appears — two INDEPENDENT facts that a router which is built and DISCARDED satisfies, while some other router is mounted and `/sse` and `/mcp` both 404. Fixed: `_mcp_router_mounted()` parses `main.py`, requires `create_mcp_router` to be imported from the module that DECLARES the routes, and requires an `app.include_router(...)` whose ARGUMENT is that factory call — directly, or through a variable bound to it. | Any "is it wired up" assertion about a framework registration call (`include_router`, `register`, `add_handler`, `mount`). |
| 1.9 | **silent-path-demotion** | **A URL with no PATH can be neither asserted nor probed. Coercing it silently demotes the HOST to a path segment and turns the control into a decoration.** | Finding **4427972925**. `_probe_url("http://host:8055", base)` used to produce `<base>/host:8055` — a path nothing serves, reported as a 404 that reads like route drift. Now `_url_path()` raises `ValueError` naming the offending URL. It is an explicit raise, NOT an `assert`, because `pytest -O` strips asserts — and a ratchet that can be switched off by a flag is not a ratchet. | Any URL handling helper shared by a static assertion and a live probe. |

### Bucket 2 — Decisions

| # | Class | Observation (rule) | Why | Alternative considered | Cost of alternative |
|---|-------|---------------------|-----|------------------------|---------------------|
| 2.7 | **skip-on-unavailable-credential** | The live half SKIPS (does not fail) when the inventory-declared credential cannot be resolved from the environment, and the skip reason names the header and the variable. | A missing credential is an ENVIRONMENTAL condition, not a defect in the endpoint. Failing would train people to ignore the gate (the same reasoning as 2.3); probing WITHOUT the credential would reject a healthy endpoint — the very defect 1.7 exists to remove. | Fail when the credential is missing | CI red on every checkout without the secret; and the loudest possible false alarm. |
| 2.8 | **the-harness-derives-its-mutation-target** | The mutation-kill derives the decorator it mutates from the RATCHET's own inventory-derived path, instead of hard-coding `@router.post("/mcp")` the way the ratchet used to. | If the harness hard-coded the mutation target, an inventory path change would leave the mutation aimed at a route nobody asserts: the mutation would SURVIVE and the harness would report a false green — the harness would carry the same defect as the ratchet it polices (1.6). | Hard-coded mutation target | A silently-decaying harness; a false green is worse than a red. |

### Bucket 3 — Operations

| # | Class | Observation (rule) | Measured | Repeatability |
|---|-------|---------------------|----------|---------------|
| 3.6 | **hand-verification-by-revert** | Each fix was reverted IN PLACE and its harness case re-run, to prove the harness actually kills it. | All four reverts **KILLED**: the hard-coded-route revert → `test_mutation_inventory_declares_an_unserved_path_is_killed` FAILED; the string-presence mount revert → `test_mutation_mounting_another_router_is_killed` FAILED; the no-credential revert → `test_live_probe_sends_the_credential_the_inventory_declares` FAILED; the no-path-URL revert → `test_live_probe_rejects_a_declared_url_with_no_path` FAILED. The ratchet file was restored byte-identical afterwards. | Every time a ratchet assertion is rewritten, not only when it is added. |
| 3.7 | **the-live-probe-runs-or-skips-never-fails-on-the-environment** | The live half reports one of two things and never a third: it RUNS and asserts, or it SKIPS with a reason. With `FLUTE_API_KEY` unset it skips with `X-API-Key (env FLUTE_API_KEY)`; with the variable exported it RUNS and passes against the running gateway. | Live on this host: `POST http://localhost:8055/mcp` → **200**, `serverInfo.name = "pmoves-flute-gateway"`. Ratchet run with the variable exported → **7 passed** (no skip). | Every live-probe lane in this repo. |

### Bucket 4 — Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.7 | **the-four-review-threads** | The provenance of the hardening: four GitHub review threads on PR #3428, each naming the defect class it exposed. | dbId `4427921337` (P1, derive the route from the inventory) · `4427921351` (P1, send the declared credential) · `4427921357` (P2, assert the `include_router` ARGUMENT) · `4427972925` (suggestion, no-path URL guard) | The lessons above are the generalised rules; the thread ids are the exact places they came from, so the next reviewer can read the finding against the fix. |

---

## Review hardening round 2 — finding 4428873759 (PR #3428, second pass)

**Status:** one further review thread on PR #3428, against the STATIC half. Valid: the ratchet could still pass while the defect it exists to catch was PRESENT. Lesson numbering continues from the taxonomy above (1.10, 2.9, 3.8, 4.8).

**The blind spot, in one sentence:** `_declared_routes` answered *"does this file, anywhere, decorate some `.post('/mcp')` on SOME object"* — so a route declared on an UNMOUNTED sibling router in the same module satisfied BOTH static halves (the file "declares" the path AND the factory is "mounted") while every client got a 404.

### Bucket 1 — Defects

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1.10 | **declared-anywhere-is-not-attached-to-the-served-router** | **"The module declares the path SOMEWHERE" is a different fact from "the route is attached to the object that is served".** A static check that asks *is it declared?* must also ask *declared ON WHAT?* — and the answer must be the object the factory hands back. | Finding **4428873759** (suggestion). `mcp_bridge.py:508` declares `@router.post("/mcp")` on the LOCAL `router` that `create_mcp_router` returns (`mcp_bridge.py:583`). A mutation that moves the decorator to a sibling `APIRouter` satisfies the declaration census AND the mount check, because neither of them asks whether the two halves name the SAME object. Fixed: `_route_ownership()` resolves the factory's RETURNED names and its LOCALLY ASSIGNED names from the AST, `_route_decorators()` carries each decorator's SCOPE, and `_assert_route_on_returned_router()` requires the derived path's decorator to be attached to a returned object — raising `RouterOwnershipError` naming the path AND the offending router object otherwise. | Any "is it declared?" check on a registration call whose receiver is an object (`include_router`, `register`, `add_handler`) rather than a name. |

### Bucket 2 — Decisions

| # | Class | Observation (rule) | Why | Alternative considered | Cost of alternative |
|---|-------|---------------------|-----|------------------------|---------------------|
| 2.9 | **the-check-raises-a-named-exception,-not-an-assert** | The ownership check raises `RouterOwnershipError` (an `AssertionError` subclass) rather than asserting inline, and BOTH the pytest test and the mutation harness call that one named function. | `pytest -O` strips `assert` — a ratchet that can be switched off by a flag is not a ratchet (same reasoning as 1.9). The named type also lets the harness name the failure MODE instead of matching on a message, and it keeps the harness from restating the logic (lesson #12 / decision 2.5). | `assert` inside the pytest test | The harness could not distinguish this failure from the other assertions, and `-O` would silently disarm the check. |

### Bucket 3 — Operations

| # | Class | Observation (rule) | Measured | Repeatability |
|---|-------|---------------------|----------|----------------|
| 3.8 | **green-before / red-after / green-after-restore** | A mutation case that mutates a REAL source file must assert all three states on ONE copy: the ratchet passes on the pristine bytes, fails with the mutation applied, and passes again after the original bytes are restored — with the restore in a `finally`, byte-exact, verified by re-reading the file. | The sibling-router mutation: **KILLED** with `route '/mcp' (POST) is declared on 'router_sibling', but create_mcp_router() returns 'router'`. Hand-verified by revert (lesson 3.6): with the ownership check stubbed to a no-op the mutation **SURVIVES**, so the case is load-bearing. Restore verified byte-exact (`bridge.read_bytes() == pristine`). | Every mutation that edits a file the ratchet reads. |

### Bucket 4 — Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.8 | **the-fifth-review-thread** | The provenance of the round-2 hardening: a fifth GitHub review thread on PR #3428, against the static half's ownership gap. | dbId `4428873759` (suggestion, the decorator must belong to the router the factory returns) | The same trail shape as 4.7 — the thread id is where the finding was made, so the next reviewer can read it against the fix. |

---

## Test inventory (after round 2)

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` | 967 | 9 | The ratchet. Static half (8): the route DERIVED FROM THE INVENTORY must be declared in the serving source AND attached to the router `create_mcp_router` RETURNS (×2 entries: `flute-voice` SSE + `flute-voice-mcp` HTTP); the MCP router must be the ARGUMENT of `app.include_router(...)` (×2); the entry must resolve to a URL carrying a PATH (×2 entries); the ownership check says NO on a route on an unreturned router, and YES on the right shape (2 unit cases). Live half (1): the declared URL must answer, must not 404, must not 5xx, must carry the INVENTORY-declared credential, and the responder must identify as `pmoves-flute-gateway`. |
| `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` | 669 | 14 | The PROVENANCE harness. 7 static mutations (route removed / mount removed / another router mounted / the inventory declares an unserved path / the route moved onto a sibling router / both removed / un-mutated control) + 7 live-half cases (override rebases the probe URL / a no-path URL is rejected / the declared credential is sent / an unavailable credential skips / an impostor responder is rejected / a 404 is rejected / the genuine service passes). |

Total: **23 tests across the 2 files.**

---

## Review hardening round 3 — finding 4429144504 (PR #3428, third pass)

**Status:** one further review thread on PR #3428, aimed at the OWNERSHIP RULE itself — at HOW it decided ownership. Valid, and wrong in BOTH directions. Lesson numbering continues from the taxonomy above (1.11–1.12, 2.10, 3.9, 4.9).

**The blind spot, in one sentence:** the round-2 ownership rule compared **SOURCE TEXT** — the factory's returned set was the unparsed text of the `return` value, and the decorator's receiver was the unparsed text of the object it decorates — so one text could name two different objects, and one statement could name two objects at once.

### Bucket 1 — Defects

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1.11 | **text-comparison-is-not-identity** | **"Are these the same object?" must be answered by IDENTITY, never by SOURCE TEXT.** One text can name two different objects (`return APIRouter()` and `@APIRouter().post("/mcp")` are two INSTANCES), and one statement can name two objects at once (`return router, admin` is two objects, not one name spelled "router, admin"). | Finding **4429144504**. Defect (a), the FALSE NEGATIVE: `return APIRouter()` put the literal text "APIRouter()" into the returned set, and a stray `@APIRouter().post("/mcp")` unparses to the SAME text — so the text comparison concluded the STRAY instance WAS the returned router, and the blind spot lesson 1.10 exists to close stayed open. Fixed: `_factory_returns()` contributes a name ONLY for a plain `ast.Name`, DESTRUCTURES a tuple into its elements, and contributes NO name for a `return` of a CALL (an expression is not a binding); `_Scope.resolve()` resolves each name to an IDENTITY — the scope that binds it plus the name — and `_decorator_is_owned()` compares identities. The source text survives only to NAME the offending object in the failure message. | Any static check that decides "is this the SAME object?" from source: ownership, aliasing, shadowing, `include_router` arguments, handler registries. |
| 1.12 | **a-ratchet-that-cries-wolf-is-as-broken-as-one-that-never-fires** | **A check that fails CORRECT code is as broken as a check that never fires** — the first trains people to ignore the gate, the second never catches anything. A ratchet must be able to say NO *and* must stay quiet on a valid module. | Defect (b), the FALSE POSITIVE: the text-based rule recorded `return router, admin` as ONE name spelled "router, admin", so the router the factory actually returns became INVISIBLE to the rule and a VALID module FAILED the ratchet — CI red for correct code. Measured against the retired rule, the failure message read `create_mcp_router() returns '(router, admin)'`. Fixed by the tuple destructuring in 1.11, and pinned by `test_mutation_factory_returning_a_tuple_is_not_cried_wolf`, which asserts the ratchet PASSES on a legitimate two-value return. | Any gate whose failure mode must be reachable ONLY by a defect — especially a gate that blocks a merge for everyone. |

### Bucket 2 — Decisions

| # | Class | Observation (rule) | Why | Alternative considered | Cost of alternative |
|---|-------|---------------------|-----|------------------------|---------------------|
| 2.10 | **ownership-is-resolved-through-the-scope-chain** | The receiver's identity is resolved the way Python resolves the NAME: walk the scope chain, and the first scope that BINDS the name owns the object. A name the factory assigns binds to the factory's own local; a name it never assigns binds to the module-level one; an alias (`admin = router`) resolves to the object it aliases. | The scope chain is the ground truth for "which object is this name", and it makes the rule's verdict explainable: the failure message can say "the factory's own local" versus "module level" versus "a constructed router" and be CORRECT about which. | Comparing the two unparsed source texts (the retired `_factory_bindings()`) | Wrong in both directions: blind on a constructed router (1.11a) and crying wolf on a tuple (1.12). A gate that is wrong in both directions cannot be trusted in either. |

### Bucket 3 — Operations

| # | Class | Observation (rule) | Measured | Repeatability |
|---|-------|---------------------|----------|---------------|
| 3.9 | **hand-verification-by-revert (round 3), and the round-2 guarantee re-proved** | The retired text-based rule was re-implemented IN MEMORY and the harness re-run against it. A new mutation case that PASSES against the retired rule proves nothing — the case must FAIL against it. | Reverted rule → `test_mutation_factory_returning_a_constructed_router_is_killed` **FAILED** ("DID NOT RAISE RouterOwnershipError") and `test_mutation_factory_returning_a_tuple_is_not_cried_wolf` **FAILED** with `RouterOwnershipError: ... returns '(router, admin)'` — the blind spot and the cry wolf, both reproduced on demand. The round-2 case `test_mutation_route_moved_onto_a_sibling_router_is_killed` still **PASSED** against the retired rule and against the new one, so lesson 1.10's guarantee was neither weakened nor silently removed. | Every time a ratchet assertion is rewritten, not only when it is added (extends lesson 3.6). |

### Bucket 4 — Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.9 | **the-sixth-review-thread** | The provenance of the round-3 hardening: a sixth GitHub review thread on PR #3428, against the ownership rule's own implementation. | dbId `4429144504` (the ownership rule must be AST/identity-based, not text-based) | The same trail shape as 4.7 and 4.8 — the thread id is where the finding was made, so the next reviewer can read it against the fix. |

---

## Test inventory (after round 3)

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` | 1303 | 11 | The ratchet. Static half (10): the route DERIVED FROM THE INVENTORY must be declared in the serving source AND attached to the router `create_mcp_router` RETURNS (×2 entries: `flute-voice` SSE + `flute-voice-mcp` HTTP); the MCP router must be the ARGUMENT of `app.include_router(...)` (×2); the entry must resolve to a URL carrying a PATH (×2 entries); the ownership check says NO on a route on an unreturned router, YES on the right shape, YES on a factory that returns a TUPLE, and NO on a factory that returns a CONSTRUCTED router (4 unit cases). Live half (1): the declared URL must answer, must not 404, must not 5xx, must carry the INVENTORY-declared credential, and the responder must identify as `pmoves-flute-gateway`. |
| `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` | 955 | 16 | The PROVENANCE harness. 9 static mutations (route removed / mount removed / another router mounted / the inventory declares an unserved path / the route moved onto a sibling router / the factory returns a CONSTRUCTED router / the factory returns a TUPLE / both removed / un-mutated control) + 7 live-half cases (override rebases the probe URL / a no-path URL is rejected / the declared credential is sent / an unavailable credential skips / an impostor responder is rejected / a 404 is rejected / the genuine service passes). |

Total: **27 tests across the 2 files.**

### Test status (after round 3)

- `pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py` → **10 passed, 1 skipped** with `FLUTE_API_KEY` unset (the live half skips, naming `X-API-Key (env FLUTE_API_KEY)`).
- The same file with `FLUTE_API_KEY` exported → **11 passed, 0 skipped** — the live half RAN against the running gateway and passed (`serverInfo.name = "pmoves-flute-gateway"`).
- `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` → **16 passed** (unchanged by the credential).
- Combined (credential absent): **26 passed, 1 skipped**. Combined (credential exported): **27 passed**.
- Revert-verified (lesson 3.9): against the retired text-based rule, the two new cases **FAIL** and the round-2 sibling-router case still **PASSES**.

