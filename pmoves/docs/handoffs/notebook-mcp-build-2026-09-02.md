# Handoff — notebook-mcp: build-once-mount-twice wrapper for Open Notebook (2026-09-02)

**Node:** 5090 · **Lane:** apps-as-MCP-plugins (operator-approved entry lane, option 2) · **Author:** 5090-CLAUDE

## Why (provable reason for the protected-file edits)

The operator's direction: multi-tenant apps become **plugins usable by any agent**
([[project_apps_as_mcp_plugins_architecture]]). Chosen first lane (option 2): prove the pattern
end-to-end with **notebook**. Open Notebook was reachable only via the `pmoves_notes` Agent Zero
**plugin** (native Python tools). This builds `pmoves/services/notebook-mcp/` — an MCP server that
exposes the *same* proven Open Notebook calls (`POST /api/notes`, `POST /api/search`) over the MCP
protocol, so A0 (runtime MCP client `:8081`), deepseek-harness (`dsh-mcp-client`), and any other
MCP consumer mount ONE wrapper. Tools surface as `mcp__notebook__save_note` / `..._search_notes`.

## Protected-file edits this lane needs

1. **Dockerfile** `pmoves/services/notebook-mcp/Dockerfile` (KNOWN_ROAD=dockerfile) — python:3.12-slim,
   non-root, streamable-http MCP on :8092.
2. **compose** a `notebook-mcp` service (KNOWN_ROAD=compose) on `pmoves_app` (to reach `open-notebook`
   and be reachable by A0/dsh), reading `OPEN_NOTEBOOK_API_URL`/`OPEN_NOTEBOOK_API_TOKEN`.

## Not in this change (follow-ups)

- Wire A0's runtime MCP client (`:8081` / `seed_agent_zero_mcp.py`) at `http://notebook-mcp:8092/mcp`
  — OR keep the native `pmoves_notes` plugin (both hit the same API). A0 side is already production
  via the plugin; the MCP mount is the "any agent" generalization.
- deepseek-harness `cordis.yml` row mounting `notebook-mcp` (the dsh side; pairs with the CHIT/Cipher
  memory plugin — [[project_apps_as_mcp_plugins_architecture]]).
- `wealth-mcp` (Firefly) after the Firefly multi-tenancy A/B decision.

## Tenant / hazard notes
- The server is a thin stateless bridge reading ONE Notebook token; the per-tenant credential seam
  lives in the mounting harness (dsh `ctx.credentials` / A0 per-context header), not here.
- Open Notebook `surreal_data` dual-writer hazard — one writer per data path.

---

## Review-thread follow-up (2026-09-02, B850-CLAUDE assisting)

Three P1 review threads. Two fixed on this branch; **one is blocked on a file
B850 cannot write** and needs the 5090 (lane owner) to land it.

### 1. `mcp` pin — FIXED

`mcp>=1.2.0` had no upper bound. Measured against PyPI today:

```
$ curl -sS https://pypi.org/pypi/mcp/json | ... -> latest: 2.1.1
$ uv pip install "mcp>=1.2.0" && python -c "from mcp.server.fastmcp import FastMCP"
installed mcp == 2.1.1
IMPORT FAIL: ModuleNotFoundError No module named 'mcp.server.fastmcp'.
  This is mcp 2.x, where FastMCP was renamed to MCPServer ... or pin 'mcp<2'.
```

A fresh image build resolves 2.1.1 and `server.py` dies at import, before :8092
binds — the container crash-loops. Migration is not a rename: `MCPServer.__init__`
has no `host`/`port` params, so the bind config moves. Pinned `mcp>=1.2.0,<2`
(resolves 1.29.1, verified importing and constructing). Guarded by
`pmoves/tests/test_mcp_sdk_major_pinned.py`.

### 2. Generated-overlay drift — **BLOCKED, needs the 5090**

Reproduced, not inferred. `notebook-mcp` appears in `docker-compose.agents.yml`
but is absent from `docker-compose.yml` (grep count 0) and from `split_compose.py`
(count 0). Running the generator over a copy of this branch's monolith:

```
$ python pmoves/scripts/split_compose.py   # generator exit=0
notebook-mcp count in REGENERATED agents.yml: 0
notebook-mcp count in PR-committed agents.yml: 7
PR lines: 1397   regenerated lines: 1356      # the 41-line stanza is stripped
```

`hardening-validation.yml` → "Check split overlays are in sync with source
(drift gate)" regenerates and fails on `git status --porcelain`, so this PR
cannot go green as-is, and any later legitimate regen silently deletes the
service.

**`pmoves/docker-compose*.yml` is read-only on B850**, so this is handed back.
Two edits, both on the 5090:

- **`pmoves/scripts/split_compose.py`** — add `"notebook-mcp"` to
  `SERVICE_GROUPS["agents"]`.
- **`pmoves/docker-compose.yml`** — add the service stanza to the agents region
  (next to `notebook-sync` is a natural home). It is byte-identical to the block
  now at `docker-compose.agents.yml:1356`; the generator strips only
  `security_opt`, which this service does not set, so the committed overlay
  stanza can be moved across verbatim.

Then `make -C pmoves compose-split` and commit the regenerated overlays. Do NOT
hand-edit the overlay again — the generator is the source of truth.

Recommended env additions to that stanza while it is being written (see §3):

```yaml
    - NOTEBOOK_MCP_TENANT_TOKEN_HEADER=${NOTEBOOK_MCP_TENANT_TOKEN_HEADER:-X-Open-Notebook-Token}
    - NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN=${NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN:-}
```

### 3. Process-wide tenant token — FIXED

The docstring said the per-tenant credential seam "lives in the mounting
harness", but nothing in the server ever *read* a per-request credential — so the
documented seam did not exist and every caller shared `OPEN_NOTEBOOK_API_TOKEN`:
cross-tenant disclosure on `search_notes`, cross-tenant mutation on `save_note`.

Credential is now resolved per request — inbound
`NOTEBOOK_MCP_TENANT_TOKEN_HEADER` (default `X-Open-Notebook-Token`) wins, env
token is a single-tenant fallback, and `NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN=true`
disables that fallback so an uncredentialed request is refused instead of
borrowing the shared account. Startup prints which mode is in effect. Guarded by
`pmoves/tests/services/test_notebook_mcp_tenant_token.py` (10 tests: 9 failing
before the change, all passing after).

Compose default is unchanged (fallback active, `127.0.0.1` bind) — i.e.
single-tenant. Flip `NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN` in the same change that
exposes this service to a second tenant.

### Observation, not in scope

`pmoves/services/hf-mcp-server/requirements.txt` carries `mcp>=0.9.0`, also
unbounded. It is *currently* fine because `main.py` uses the v2 API
(`from mcp.server import MCPServer`), so resolving 2.x is what it wants — but the
same unbounded pin means an eventual 3.x breaks it the same way. Left to the
hf-mcp lane.
