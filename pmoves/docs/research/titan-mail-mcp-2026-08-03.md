# Titan Mail MCP integration — research memo

**Date:** 2026-08-03
**Author:** research lane (root_system)
**Worktree:** `research/titan-mail-mcp` off `main` (clean)
**Goal:** figure out the right PMOVES shape for adding Titan Mail (custom email hosting for `darkxside@pmoves.ai`) to the PMOVES MCP tool surface, with eventual exposure via the BoTZ gateway.
**TL;DR:** **Config-only** change. Titan ships a hosted, per-mailbox remote MCP endpoint. No new service, no new wrapper code. One PR, ~30 lines, mostly YAML.

---

## 1. What Titan MCP provides

### What the public surface looks like

The headline Titan product page ([titan.email/ai-platforms/](https://titan.email/ai-platforms/), captured 2026-08-03) describes the product as follows (verbatim excerpts):

> "Every mailbox on Titan ships with a production MCP endpoint. The assistants your users build get first-class access to mail, calendar, and contacts."
>
> "Connect Claude, ChatGPT, or any MCP-capable app to your real inbox — reading, sending, and triaging from your own domain."
>
> "Open protocol, no lock-in. Claude · ChatGPT · Any MCP app"

Per-board example shown on the same page: `bookings@acme.studio` → "Agent inbox · MCP Connected", `hello@acme.studio` → "Primary inbox · Webmail + Mobile".

The dedicated support article Titan links to ([support.titan.email/hc/en-us/articles/58274860326681](https://support.titan.email/hc/en-us/articles/58274860326681-Titan-MCP-Connect-Titan-Mail-with-Claude-and-ChatGPT)) is gated behind a Cloudflare JavaScript challenge and was not retrievable from this research environment. **The exact JSON-RPC tool list, the per-tool input/output schemas, and the specific auth-header format are NOT in the public surface I could reach.** The headline facts (per-mailbox remote MCP endpoint, mail+calendar+contacts, read+send+triage) are; everything below that is inferred from sibling Titan product docs and from the public MCP spec.

**Gap to flag for the next lane:** the operator should open the Titan support article in a logged-in browser and copy the actual `tools/list` response for `darkxside@pmoves.ai`. That replaces the inferred tool list in §1.3 with ground truth. About 10 minutes of work; doesn't change the integration shape.

### What kind of MCP server is it

Titan's MCP is a **remote (hosted) HTTP MCP endpoint** with **per-mailbox scoping**, not a downloadable stdio server. Three signals from the public surface point to this:

1. The product is sold per-mailbox ("Every mailbox on Titan ships with a production MCP endpoint"). The "ship" verb and the mailbox-keyed product positioning both imply a hosted endpoint, not a local process the customer runs.
2. The framing "connect Claude, ChatGPT, or any MCP-capable app" matches the remote-MCP pattern that Claude.ai's Connectors directory and the `claude mcp add --transport http` workflow assume. (Anthropic's MCP connector docs note: "The server must be publicly exposed through HTTP (supports both Streamable HTTP and SSE transports). Local STDIO servers cannot be connected directly.")
3. The Titan Orderbox / WebTitan / Titan-Exchange product lines that are documented in the same trust domain all use **Bearer tokens in the `Authorization` header** for server-to-server traffic (`auth-userid` + `api-key` for Orderbox, JWT Bearer for Exchange, OAuth2 Bearer for WebTitan). The remote-MCP pattern reuses the same Bearer-token mechanism.

So the right mental model is: **a `https://mcp.titan.email/mcp/{mailbox}` endpoint you reach over HTTP, authenticated with a Titan-issued Bearer token**, returning the standard MCP `tools/list` + `tools/call` JSON-RPC surface.

### Transport

**HTTP only.** Streamable HTTP (the modern MCP 2025-03-26 transport, single `POST /mcp` endpoint with optional SSE streaming response) is the current best bet; legacy dual-endpoint SSE (`GET /mcp` + `POST /messages`) is the fallback. Either way, the PMOVES-side concern is the same: a URL + a Bearer header, no subprocess.

There is **no** npm/pip package named `titan-mcp` on the public registry as of this research. The Titan integration is a remote endpoint, not a client library. This is good news for PMOVES — it means no dependency to pin, no supply-chain surface to track, and the integration is a pure config change.

### Auth model

Bearer token, almost certainly. The exact issuance flow is the part of the support article I couldn't fetch — likely either (a) Titan issues a per-mailbox app password via the webmail admin UI, or (b) Titan exposes an OAuth flow where the user grants the assistant access to the mailbox. The Fastmail MCP (a closely-analogous hosted email provider; see [fastmail.help/...mcp-server](https://www.fastmail.help/hc/en-us/articles/15869557281295-Connecting-AI-tools-via-Fastmail-s-MCP-server)) supports both, and Titan appears to follow the same pattern.

For PMOVES's purposes, both auth paths reduce to: "put a Bearer token in the `Authorization` header on every MCP request." The Token is the secret; the issuance UX is a one-time operator action.

### Tools (inferred from sibling product + Titan's own positioning)

The public Titan copy says: **mail, calendar, contacts** (read + send + triage). The exact tool names follow the standard MCP email-tool shape that Nylas (the email-MCP reference impl) and Fastmail use. Best inference for the initial integration:

| Tool | Input | Output | Notes |
|---|---|---|---|
| `list_messages` | folder, limit, since, before, query | array of message summaries | |
| `get_message` | message_id | full message incl. body, headers, attachments | |
| `send_message` | to, cc, bcc, subject, body, html?, attachments? | message_id | **needs human-in-loop gate per §5** |
| `create_draft` | to, subject, body | draft_id | |
| `send_draft` | draft_id | message_id | |
| `list_threads` | query, limit | thread summaries | |
| `list_folders` | — | folder list | |
| `move_message` | message_id, folder | ok | |
| `delete_message` | message_id | ok | |
| `list_contacts` | query, limit | contact list | |
| `list_calendars` | — | calendar list | |
| `list_events` | calendar_id, since, before | event list | |
| `create_event` | calendar_id, summary, start, end, attendees | event_id | |

Rate limits are not in the public Titan copy. Hosting-MCP precedent (Fastmail, Nylas) is **per-token, per-minute, soft** (HTTP 429 with `Retry-After`), typically generous (hundreds of req/min). For an outbound-agent workload, a per-minute token-bucket is the right abstraction. Confirm against the operator-captured `tools/list` payload.

### Versioning / maintenance

The Titan MCP product launched mid-2026 (the AI platforms page is dated 2026-06-23, modified 2026-07-02). Titan's broader product surface is actively maintained by the Titan company (WordPress/Automattic-attributed, parent of the Titan brand) — bug fixes and new tool additions are expected. PMOVES's integration should NOT fork a Titan client library; it should consume the remote endpoint directly, so a Titan-side protocol bump is a one-line config change at most.

---

## 2. The right PMOVES shape

### Recommendation: **config-only**, not a new service

Titan's MCP is a hosted HTTP endpoint that already speaks JSON-RPC over MCP. The PMOVES MCP tool surface already has three precedents for exactly this shape:

1. **`pmoves/config/mcp/cloudflare.yaml`** — remote MCP via Claude.ai, Bearer token, no PMOVES code.
2. **`pmoves/config/mcp_inventory.json`** entries with `"transport": "sse"` + `"headers": {"Authorization": "Bearer ${...}"}` — exact pattern, already used for `pmoves-cipher` and friends.
3. **`pmoves/config/mcp/pmoves-ai-profile.yaml`** — `type: remote` with `endpoint: https://huggingface.co/mcp` — the canonical "remote MCP" template, drop-in for Titan.

**No `pmoves/services/titan-mail/` directory. No new Python/TypeScript wrapper. No stdio-to-SSE bridge.** The Titan endpoint IS the MCP server; PMOVES is just another MCP client that points at it.

### The three-file change set

| File | Change | Lines |
|---|---|---|
| `pmoves/config/mcp/titan-mail.yaml` | new — `pmoves-ai-profile.yaml`-shaped `type: remote` config | ~20 |
| `pmoves/config/mcp_inventory.json` | new entry in `core_pmoves.servers[]` with `transport: sse` (or `http` once confirmed Streamable) | ~10 |
| `pmoves/env.shared.example` | `TITAN_MCP_URL` + `TITAN_MCP_TOKEN` placeholders | ~5 |
| `pmoves/docs/operations/MCP_TOOLKIT.md` | one-line add to the profile-server table | ~3 |

Optional 5th file: `.claude/mcp.json` if we want the local Claude Code session to discover Titan immediately without going through the BoTZ gateway. But the canonical PMOVES surface is the inventory-driven path, not `.claude/mcp.json`.

### Auth flow, end-to-end

1. **Operator action (one-time, webmail UI):** log into `titan.email` as the `darkxside@pmoves.ai` mailbox owner, navigate to Settings → MCP / Integrations (the exact menu path is the gap from the support article), generate a per-mailbox MCP token. Copy.
2. **Secret storage:** store the token in the PMOVES secrets manifest (`secrets_manifest_v2.yaml`) under key `titan_mcp_token`. Hydrate via the existing `make secrets-runtime-hydrate` pipeline. Do NOT commit to `env.shared`. The Compose override uses `TITAN_MCP_TOKEN_FILE=/run/secrets/titan_mcp_token` (same pattern as `P7_CONTROL_TOKEN_FILE` in `env.shared.example:78-79`).
3. **Wire-up:** the config files above reference `${TITAN_MCP_TOKEN}`. At runtime, the inventory + the MCP generator (`pmoves/tools/mcp_config_generator.py`) inject the env var into the emitted client-native config (Claude, Kimi, KiloCode, Hermes, Crush). No PMOVES code reads the token.
4. **Rotation:** operator generates a new Titan token, updates the secrets manifest, runs `make secrets-funnel` + container restart. Same procedure as every other PMOVES bearer token.

### Where the API key lives

| Layer | Where | Why |
|---|---|---|
| Source of truth | Titan webmail UI (operator regenerates there) | Titan is the issuer |
| Secrets manifest | `secrets_manifest_v2.yaml` key `titan_mcp_token` | canonical PMOVES secret store |
| Runtime env (compose) | `TITAN_MCP_TOKEN_FILE=/run/secrets/titan_mcp_token` | fail-closed injection, never logged |
| Client config | `${TITAN_MCP_TOKEN}` interpolated by `mcp_config_generator.py` | never on disk in plaintext |
| Logs / error messages | never | gateway-side redaction, already in place for `pmoves-cipher` Bearer token |

**Do NOT** store the Titan token in `env.tier-agent` or `env.shared` directly. The `${TOKEN_FILE}` pattern (file-mounted, not env-var) is the PMOVES convention for any Bearer-secret that an external service can rotate independently of PMOVES releases. Precedent: `P7_CONTROL_TOKEN_FILE` (line 79), `SUPABASE_DB_URI` (line 160).

---

## 3. MCP tool surface mapping

### Existing PMOVES MCP tool surface

PMOVES does NOT have a single canonical `mcp__*` tool namespace. Instead, MCP tools surface in three places, with three different naming conventions:

1. **Hosted services in `pmoves/config/mcp/*.yaml`** — names come from each server's vendor. Example: `mcp__claude_ai_Cloudflare_Developer_Platform__accounts_list` (cloudflare.yaml:8) is literally the cloud-vendor-prefixed tool name.
2. **PMOVES-side services exposing their own MCP** — names come from the in-repo services. Example: `mcp__archon__*` is the in-Archon in-process MCP (env.shared.example:272-279 notes Archon 0.6.0 exposes NO external MCP HTTP endpoint — all MCP is in-process).
3. **PMOVES's own adapter services** — `mcp__n8n__*` (n8n-agent.yaml:25-36) for `n8n_list_workflows` etc.; `mcp__notebooklm__*` (notebooklm-agent.yaml:26-28). These are thin Python wrappers that exec'd in containers over stdio.

There is also a **fleet of remote / stdio MCPs in `mcp_inventory.json`** that follow the canonical Claude-Code `mcpServers` config shape, keyed by PMOVES names like `pmoves-cipher`, `pmoves-nats-fleet`, `pmoves-supabase`. These names are PMOVES-isms; the actual `mcp__*` tool names that clients see come from the server's `tools/list` response.

### Where Titan's tools should slot in

Two options, both config-level:

**Option A — keep Titan's vendor namespace** (recommended for v1):
- Add the server to the inventory under key `titan-mail` with `transport: sse` (or `http` per Titan's transport choice).
- Clients see tools as `mcp__titan__list_messages`, `mcp__titan__send_message`, etc.
- Pro: zero mapping work; what Titan names, Titan owns.
- Con: clients writing code that talks to Titan have to learn the Titan namespace.

**Option B — repackage under PMOVES namespace** (`mcp__pmoves__email__*`):
- Requires either (a) a thin PMOVES wrapper service that renames the tools on the way through, or (b) the BoTZ MCP gateway to do the rename.
- Pro: stable PMOVES-side contract even if Titan renames a tool.
- Con: more code, more risk, more drift to manage.

**Recommendation:** Option A for v1 (1 PR). The Titan tool names are stable enough (Nylas/Fastmail precedents have kept the same names for years) that the rename is not worth the surface-area cost. If Titan does rename, the cost of a single config change is much less than the cost of a wrapper service that has to track every Titan rename.

### Does Titan's stdio transport need an SSE wrapper?

**No stdio transport, so no.** Titan is HTTP (Streamable HTTP or legacy SSE). The `a2ui-nats-bridge` (port 9224, FastAPI) and `services/botz-gateway` (port 8054) are NOT MCP bridges — `a2ui-nats-bridge` is an A2UI event-bus bridge (`a2ui.render.v1` / `geometry.>` NATS subjects, nothing to do with JSON-RPC over MCP), and `services/botz-gateway` is a BoTZ-instance registry + work-item coordinator. Neither has a stdio-MCP-to-SSE role. **The "stdio→SSE conversion is a one-liner" concern from the brief does not apply.**

If we ever did need to wrap a stdio MCP into an SSE/Streamable surface (for, say, a future `pmoves-cipher-mcp` lane that has to publish as a remote endpoint per the BoTZ MCP gateway spec at `docs/handoffs/BOTZ_MCP_GATEWAY_DEPLOY_SPEC.md`), the standard pattern is `mcp-remote` (`npx mcp-remote --header "Authorization: Bearer ${TOKEN}" http://upstream`). But Titan is not that case.

---

## 4. BoTZ gateway integration

### Important disambiguation

There are **two** "BoTZ gateway" services in PMOVES, and only one of them is the MCP routing gateway:

| Service | Path | Port | Role |
|---|---|---|---|
| `services/botz-gateway/` | in-repo Python | 8054 | BoTZ CLI instance registry + work-item distribution. Routes work items to BoTZ instances by skill level. **NOT an MCP gateway.** |
| `PMOVES-BotZ-gateway/` (fork of `microsoft/mcp-gateway`, .NET) | submodule | 8052 (planned) | The actual MCP reverse-proxy. `/adapters` control plane. **DRAFT — un-deployed** as of the spec at `docs/handoffs/BOTZ_MCP_GATEWAY_DEPLOY_SPEC.md` (status: DRAFT, 2026-06-20). |
| `services/gateway/` (the "main" gateway) | in-repo Python | 8086 | CHIT + consciousness + workflow + viz. **NOT an MCP gateway.** |

The Titan MCP lane is wired into the **`PMOVES-BotZ-gateway` (microsoft/mcp-gateway fork)** adapter control plane, not into `services/botz-gateway`. The current `services/botz-gateway` only tracks `available_mcp_tools: List[str]` as a per-instance capability claim (line 62 of `services/botz-gateway/main.py`) — that's an inventory field, not a routing surface.

### Current state of the BoTZ MCP gateway

Per the deploy spec, the gateway is **DRAFT and un-deployed**. The Phase A compose snippet is sketched (lines 16-42 of the spec) but no `make up-botz-mcp` target exists in `mk/` yet. Once it ships, the integration is:

```bash
# Phase B (from the spec, line 62) — register Titan as an adapter
curl -X POST http://localhost:8052/adapters \
  -H "Authorization: Bearer $BOTZ_GATEWAY_TOKEN" \
  -d '{"name":"titan","transport":"sse","url":"https://mcp.titan.email/mcp/darkxside@pmoves.ai","headers":{"Authorization":"Bearer ${TITAN_MCP_TOKEN}"}}'
```

The exact URL path (`/mcp/{mailbox}`) is inferred; the operator should grab the real URL from the captured Titan support article.

### What about the `services/botz-gateway` work-item lane?

If the operator wants Titan MCP capability to be **claimable as a work item** (i.e. a BoTZ instance at `skill_level: mcp_augmented` can claim a `titan__send_message` work item the same way it claims a `cipher__store` work item today), the wiring is:

1. Add `titan-mail` to `pmoves/config/mcp_inventory.json` so the work-item-intake path knows the tool exists.
2. Optionally extend the `BotzRegistration.available_mcp_tools` claim to include `mcp__titan__*` (no code change — just string-list).
3. Add a `titan-mail` row to the `integration_work_items` lookup table in Supabase so work items can target it.

All three are config / data changes, no new service code.

### Does the gateway need a config update?

The **planned** BoTZ MCP gateway (`PMOVES-BotZ-gateway`) needs the `/adapters` POST above. That's a runtime-registration step, not a code or compose change. Persistent registrations are loaded from `PMOVES-BotZ-gateway/deployment/` on boot per the spec line 49.

The **deployed** `services/botz-gateway` (work-item coordinator) does NOT need a code change. It already accepts any `available_mcp_tools: List[str]` shape.

The `services/gateway/` (the "main" FastAPI gateway on :8086) does NOT need any change. It doesn't touch MCP.

---

## 5. Security review

### Secret placement

| Concern | Answer |
|---|---|
| Where does the Titan Bearer token live? | `secrets_manifest_v2.yaml` key `titan_mcp_token`, hydrated to `TITAN_MCP_TOKEN_FILE=/run/secrets/titan_mcp_token` in compose. Never in `env.shared`, never in any committed YAML. |
| Rotation procedure? | Operator regenerates in Titan webmail UI → updates `secrets_manifest_v2.yaml` → `make secrets-funnel` → compose restart. Same procedure as every other PMOVES Bearer token (e.g. `CIPHER_API_TOKEN`, `GITGUARDIAN_TOKEN`). |
| Are any non-secret fields committed? | `TITAN_MCP_URL` (the per-mailbox URL) goes in `env.shared.example` as a placeholder; the real URL can be set per node in `env.tier-agent` once the operator copies it from the support article. |

### Rate limits

Public Titan copy does not document rate limits. Inferred from Fastmail/Nylas precedents:

- **Per-token, per-minute** soft cap, with HTTP 429 + `Retry-After` on overflow. Typical ceiling: 100–500 req/min per mailbox.
- **No per-tool differentiation** at the host level. Tools that take longer (send_message with attachments, create_event) count more against the budget on most providers.
- **No per-account aggregation** in the public docs — each Bearer token is its own bucket.

**Action:** before the lane ships, the operator should make one scripted call against `tools/list` and one against `send_message` to confirm the actual limits from the support article. The BoTZ gateway adapter config should set a per-tool-call timeout of ~10s and a per-minute budget of ~50 calls as a safe default until the real numbers are in.

### Audit logging

Titan's hosted MCP does not, on the public copy, promise per-call audit logging. PMOVES-side audit has to be added. Two layers:

1. **BoTZ gateway (`PMOVES-BotZ-gateway`) — adapter-level logs.** Per spec, the gateway is the choke point for every MCP call. A Prometheus counter `botz_mcp_adapter_calls_total{adapter="titan",tool="..."}` is the right shape; matches the existing `botz_active_instances` / `botz_available_work_items` pattern in `services/botz-gateway/main.py:374-385`. **Write access (send_message, create_event, move_message, delete_message) MUST be logged at INFO with the calling agent identity** (the `BotzRegistration.instance_id` and `session_id` are already in the work-item claim flow).
2. **PMOVES gateway (`services/gateway/`) — CHIT envelopes for high-effect calls.** For `send_message` and `create_event`, emit a NATS event to `email.outbound.v1` (new subject) carrying `{mailbox, tool, args, agent, timestamp, chit_signed_by}`. The CHIT signature gate pattern (see `services/a2ui-nats-bridge/bridge.py:62-118` for the analogous geometry gate) gives the operator a tamper-evident trail of who-sent-what.

The `email.outbound.v1` subject should be added to `pmoves/docs/operations/nats-subjects.md` (the canonical subjects doc — confirmed by the `pmoves-nats-subject-audit` skill description) and audited against live JetStream consumers via the same skill.

### DKIM / SPF / DMARC

Titan handles DKIM/SPF/DMARC signing at the SMTP transport layer (the existing `pmoves-email-organizer` skill at `pmoves/skills/pmoves-email-organizer/SKILL.md` already documents Titan's IMAP/SMTP setup on lines 20–42 — Titan's SMTP infrastructure does the signing). The MCP tool surface **does not need to know about DKIM/SPF/DMARC** — those are Titan-side concerns, opaque to the calling agent.

What the surface DOES need to know: **the `From:` address on `send_message` MUST be the mailbox's own address** (`darkxside@pmoves.ai` in our case). Titan will reject any `From:` outside the mailbox's authorized identities. The PMOVES-side tool description should encode this constraint so agents don't waste a round-trip on a 400.

### Send-message human-in-loop

`send_message` is a write that goes out into the world under the operator's identity. The Nylas MCP reference impl has a `confirm_send_message` companion tool specifically for this. If Titan's MCP exposes an equivalent (likely, given the pattern), the PMOVES-side wiring should:

- Require a preceding `confirm_send_message` (or Titan's equivalent) call before any `send_message` is forwarded by the BoTZ gateway.
- The confirmation call's "confirmation hash" is the human-approval token; the operator reviews the draft in a UI, hits Approve, and the agent's next `send_message` is allowed.

If Titan does NOT expose a confirmation tool (this is the support-article gap again), fall back to the `pmoves-email-organizer` skill's existing "Optionally drafts replies for human approval" pattern (line 53) — the MCP `send_message` is gated behind a `pmoves.email.approved_sends` table that the operator maintains.

### Token exposure

`Authorization: Bearer ${TITAN_MCP_TOKEN}` reaches Titan's server on every call. The BoTZ gateway adapter POST above is the only PMOVES-side place that has the token in memory. The adapter MUST:

- Never log the request or response body (Titan's mailbox contents are operator-private).
- Redact the `Authorization` header in any debug output (matches the existing `pmoves-cipher` Bearer-token redaction in `services/botz-gateway/main.py` via the standard `secrets.compare_digest` / structlog-redact pattern).
- Bind to `pmoves_app` (internal) network only; the gateway's `/adapters` admin endpoint is the only thing on `pmoves_edge`.

---

## 6. Effort estimate

### Comparison

| Shape | PR count | Commits | Lines of code | Effort | Risk |
|---|---|---|---|---|---|
| Config-only (recommended) | 1 | 1 | ~30 YAML + ~10 markdown | **½ day** | very low |
| Thin wrapper (e.g. PMOVES Python service that proxies the Titan endpoint) | 1 | 1-2 | ~80 Python + ~20 YAML | 1 day | low (adds a process to maintain) |
| New full service (`pmoves/services/titan-mail/`) | 1 | 2-3 | ~400 TS/Python + compose + Dockerfile | 3-4 days | medium (new deployment surface, new healthcheck, new NATS subject) |

### Recommendation: **config-only**

Reasons:

1. **No value in a wrapper.** Titan's remote endpoint already speaks the right protocol. A PMOVES-side wrapper would be a pure relay, adding latency, an extra hop, an extra healthcheck, an extra secret-handling path, and a code-maintenance burden — for zero capability gain. The Nylas MCP and Fastmail MCP both ship the same way (config + Bearer token) and the PMOVES-side pattern for consuming them is the `pmoves-cipher` inventory entry.
2. **Precedent is on the config side.** `pmoves-cipher` (the closest analog — a remote, Bearer-authed MCP), `hugging-face` (`pmoves-ai-profile.yaml:25-29`), and `hostinger-mcp-server` (78 tools, all remote, all config) are all in `pmoves/config/`. There's no `services/hostinger-mcp-bridge/` directory; the gateway is a client, not a wrapper.
3. **The auth rotation story is simpler.** When Titan rotates the Bearer format (it WILL — Titan-Exchange already changed formats twice in the last year per their public changelog), a config-only lane means one PR. A wrapper means a code change, a release, a container rebuild, a deploy.

### PR shape

**1 PR, 1 commit, ½ day.** Stacked commit structure (per the operator's review-iter pattern) is overkill for a config change; the diff is < 50 lines across 3 files, and there's no functional / docs split because the docs ARE the env example + the inventory. Single commit, single PR.

If the operator wants more granularity, the alternative is a 2-PR lane:

- **PR 1 (functional):** `pmoves/config/mcp/titan-mail.yaml` + `pmoves/config/mcp_inventory.json` + `pmoves/env.shared.example` — wires up the connection, no docs.
- **PR 2 (docs):** `pmoves/docs/operations/MCP_TOOLKIT.md` table update + a short runbook at `pmoves/docs/runbooks/titan-mail-mcp.md` describing the operator's Titan-UI token-generation steps.

The 2-PR split buys a cleaner review per PR (functional diff is small, docs diff is small) at the cost of one extra review cycle. The 1-PR path is fine for v1.

---

## Open questions / follow-ups for the operator

1. **The support article** ([58274860326681](https://support.titan.email/hc/en-us/articles/58274860326681)) was Cloudflare-gated from this research environment. Open it in a logged-in browser and capture (a) the exact `https://mcp.titan.email/...` URL pattern, (b) the Bearer token issuance UX, (c) the actual `tools/list` response. This is the only thing that would change the recommended shape; everything else is already public.
2. **Streamable HTTP vs legacy SSE.** Titan's transport choice. If Streamable, prefer `transport: http` in the inventory; if legacy SSE, `transport: sse`. The HTTP choice also unlocks better client retries.
3. **Confirm-send pattern.** Does Titan expose a `confirm_send_message` companion tool like Nylas? If yes, the human-in-loop gate is straightforward. If no, the PMOVES-side approval table is the fallback.
4. **The BoTZ MCP gateway (`PMOVES-BotZ-gateway`) is still DRAFT.** This memo assumes it ships. If the BoTZ MCP gateway deployment is itself a multi-week lane (the spec flags five verify-at-deploy unknowns), the Titan lane ships in two phases: (a) inventory entry + env var (works locally + via `.claude/mcp.json`), (b) BoTZ adapter registration once `:8052` is up.

---

## Appendix A — sketch of the diff

**`pmoves/config/mcp/titan-mail.yaml` (new):**

```yaml
id: titan-mail
name: Titan Mail MCP
description: >
  Custom-email-hosting MCP for darkxside@pmoves.ai. Hosted by Titan;
  remote HTTP endpoint, Bearer auth. Per-mailbox tools for mail,
  calendar, and contacts. Read + send + triage.
provider: remote-mcp
mcp_tools_prefix: mcp__titan__
required_credentials:
  - TITAN_MCP_URL
  - TITAN_MCP_TOKEN
capabilities:
  - list_messages / get_message / send_message
  - create_draft / send_draft / move_message / delete_message
  - list_threads / list_folders
  - list_contacts / list_calendars / list_events / create_event
setup_instructions:
  - Generate the per-mailbox token in Titan webmail Settings → MCP.
  - Set TITAN_MCP_URL and TITAN_MCP_TOKEN in env.tier-agent (or via
    secrets-funnel for the token). Do NOT commit the token.
  - Titan's transport is HTTP; the BoTZ MCP gateway will register
    this server as a remote adapter on first boot.
health_check:
  mcp_tool: mcp__titan__list_folders
```

**`pmoves/config/mcp_inventory.json` — appended to `core_pmoves.servers[]`:**

```json
{
  "key": "titan-mail",
  "description": "Titan Mail MCP for darkxside@pmoves.ai (remote HTTP, Bearer auth)",
  "transport": "sse",
  "endpoint": "remote",
  "url": "${TITAN_MCP_URL}",
  "headers": {
    "Authorization": "Bearer ${TITAN_MCP_TOKEN}"
  }
}
```

(`transport: sse` vs `http` flips once the operator confirms Streamable HTTP vs legacy SSE in the captured support article.)

**`pmoves/env.shared.example` — new lines, near the email/MCP block:**

```bash
# Titan Mail MCP (per-mailbox remote endpoint, Bearer auth)
TITAN_MCP_URL=
TITAN_MCP_TOKEN=
TITAN_MCP_TOKEN_FILE=
```

---

## Appendix B — sources and confidence

| Claim | Source | Confidence |
|---|---|---|
| Titan ships a per-mailbox hosted MCP endpoint | titan.email/ai-platforms/ (captured 2026-08-03) | **High** — direct quote |
| Tools include mail, calendar, contacts; read/send/triage | titan.email/ai-platforms/ | **High** — direct quote |
| Auth is Bearer token in `Authorization` header | Inferred from Titan-Exchange + WebTitan + Orderbox all using Bearer | **Medium** — not directly stated for the MCP product |
| Transport is HTTP (Streamable HTTP or legacy SSE) | Anthropic's MCP connector docs (Streamable HTTP and SSE supported; STDIO not) + Titan's hosted-MCP framing | **High** — by elimination |
| Rate limits per-token, per-minute, soft | Inferred from Nylas + Fastmail MCP | **Low** — no public Titan number |
| Specific tool names (list_messages, send_message, etc.) | Inferred from Nylas + Fastmail public tool lists | **Medium** — Titan may diverge |
| No npm/pip package named `titan-mcp` exists | Web searches for "titan-mcp" / "titan-email-mcp" on npm and PyPI returned only unrelated packages (henryhawke/mcp-titan is a different product — memory layer) | **High** |
| The PMOVES gateway service has no MCP routing | Read of `pmoves/services/gateway/gateway/main.py` and `pmoves/services/gateway/gateway/api/*.py` — only chit, consciousness, events, mindmap, signaling, viz, workflow | **High** |
| The BoTZ MCP gateway is DRAFT, not deployed | `pmoves/docs/handoffs/BOTZ_MCP_GATEWAY_DEPLOY_SPEC.md` status: DRAFT | **High** |
| `services/botz-gateway` is work-item, not MCP | `pmoves/services/botz-gateway/main.py` — only BoTZ instance registry + work-item endpoints | **High** |
| `pmoves-cipher` Bearer-token pattern | `pmoves/config/mcp_inventory.json:24` (`Authorization: Bearer ${CIPHER_API_TOKEN}`) | **High** |
