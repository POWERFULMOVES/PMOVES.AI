# PMOVES-Mike integration (MikeOSS on SPARK)

| | |
|---|---|
| Submodule | `PMOVES-Mike/` → `https://github.com/POWERFULMOVES/PMOVES-Mike.git`, branch `main` |
| Upstream | `open-legal-products/mike` (AGPL-3.0). Fork is a parity fork: 0 ahead / 7 behind upstream at add time (2026-10-21) |
| Pinned SHA | `563c8319` (2026-10-20, `chore(deps): bump the priority-2-production group ... (#680)`) |
| First node | SPARK (DGX Spark, `linux/arm64`) |
| Known Road | `make -C pmoves up-mike` · `down-mike` · `mike-status` · `mike-config` · `mike-logs` (`pmoves/mk/mike.mk`) |
| Overlay | `pmoves/docker-compose.mike.yml` (layered on `PMOVES-Mike/docker-compose.yml`). **Staged for operator apply** in `pmoves/docs/handoffs/mike-compose-overlay-spark-2026-10-21.md` because the compose path is guard-protected. Validated with `docker compose config -q` from a scratch copy: 9 published ports, all `127.0.0.1` |
| Env | `pmoves/env.mike` (gitignored), seeded from `pmoves/env.mike.example` |
| Consumers | MiSSinGLinC validator (`pmoves/docs/AGENTS/MISSINGLINC_MINT_SPEC.md`), TitanMail MCP (Mailpit as local test inbox) |

## What Mike is

Mike (MikeOSS) is an open-source legal-AI platform for document review,
drafting and legal research: a Next.js frontend, an Express/TypeScript
backend, Supabase Auth/Postgres, and S3-compatible object storage. It verifies
citations against source documents, researches US case law through
CourtListener, signs export manifests with Ed25519, and can run models locally
through Ollama.

**Same repo as the mint spec's `PMOVES-mike`.** The MiSSinGLinC spec was
verified against `PMOVES-mike @ 204d2d5`. GitHub resolves
`POWERFULMOVES/PMOVES-mike` to `POWERFULMOVES/PMOVES-Mike` (case-insensitive
name; `gh api repos/POWERFULMOVES/PMOVES-mike` returns `full_name:
POWERFULMOVES/PMOVES-Mike`), and `204d2d533a07` is an ancestor of the pinned
SHA, 828 commits back.

## How it runs on SPARK

Mike ships its own complete stack, and every one of its default host ports
collides with something already listening on SPARK. Rather than fork the
compose, PMOVES layers an overlay on it and runs it as its own compose project:

```
docker compose -p pmoves-mike --project-directory PMOVES-Mike \
  --env-file pmoves/env.mike \
  -f PMOVES-Mike/docker-compose.yml -f pmoves/docker-compose.mike.yml ...
```

That invocation lives only inside `pmoves/mk/mike.mk`. Do not type it by hand.

- **Project `pmoves-mike`** namespaces containers (`pmoves-mike-db-1`, ...),
  volumes (`pmoves-mike_db_data`, `_storage_data`, `_redis_data`) and the
  default network. Upstream declares no `container_name`, so nothing can clash
  with `pmoves-*` services.
- **Every published port** is re-bound to `${MIKE_BIND:-127.0.0.1}` and moved
  into the `18300-18399` block with `ports: !override`. A plain overlay merge
  would add a second binding next to upstream's instead of replacing it.
  Upstream publishes gateway, backend and frontend on `0.0.0.0`; the overlay
  makes all of them loopback-only.
- **Browser-facing URLs** (GoTrue `API_EXTERNAL_URL`/`SITE_URL`, the backend's
  `FRONTEND_URL`/`API_PUBLIC_URL`, the presigned-storage `R2_PUBLIC_ENDPOINT_URL`)
  are rewritten to the remapped ports, so signup confirmation links and
  downloads resolve.
- **Secrets** come from `pmoves/env.mike`, not `PMOVES-Mike/backend/.env`.
  The overlay appends it as the last `env_file` (it wins). Upstream's optional
  `backend/.env` and root `.env` would still load if someone created them in
  the submodule. Don't create them on a PMOVES node.
- **Telemetry**: upstream sends scrubbed Sentry reports by default. The overlay
  sets `SENTRY_DISABLED=true` (runtime) and `NEXT_PUBLIC_SENTRY_DISABLED=true`
  (frontend build arg). Override with `MIKE_SENTRY_DISABLED=false`.
- **Google OAuth** is off by default (`MIKE_GOOGLE_AUTH_ENABLED=false`).
  Upstream enables it by default with empty client credentials.
- **Mailpit** is pinned to `axllent/mailpit:v1.31.6`; upstream uses `latest`.
  The pin keeps the API documented below the API the container serves.
- **Ollama**: the backend reaches the host Ollama at
  `http://host.docker.internal:11434/v1` (SPARK's native Ollama). This is
  upstream's default, now named `MIKE_OLLAMA_BASE_URL`.

### Port map (SPARK)

| Service | Container port | Host (default `127.0.0.1`) | Upstream default | Why remapped (SPARK occupant at time of writing) |
|---|---|---|---|---|
| frontend (Next.js) | 3000 | **18300** | `0.0.0.0:3000` | `pmoves-supabase-postgrest-1` on 127.0.0.1:3000 |
| backend (Express) | 3001 | **18301** | `0.0.0.0:3001` | 3001 listening on host |
| gateway (nginx → auth/rest) | 8000 | **18321** | `0.0.0.0:54321` | block consolidation; was public |
| db (supabase/postgres) | 5432 | **18322** | `127.0.0.1:54322` | `pmoves-supabase-db-1` |
| mailpit web UI + REST API | 8025 | **18325** | `127.0.0.1:8025` | block consolidation |
| mailpit SMTP | 1025 | **18326** | `127.0.0.1:1025` | block consolidation |
| redis | 6379 | **18379** | `127.0.0.1:6379` | `e2b-redis-1` |
| storage (RustFS S3) | 9000 | **18390** | `127.0.0.1:9000` | `pmoves-minio-1` |
| storage console | 9001 | **18391** | `127.0.0.1:9001` | `pmoves-minio-1` |

The block stays below the Linux ephemeral range (`32768-60999`), so outbound
sockets can never squat on it. `auth` (9999), `rest` (3000), `db-init`,
`createbucket` and `workflow-sync` publish nothing.

### arm64 image check (measured 2026-10-21, `docker buildx imagetools inspect`)

| Image | linux/arm64 |
|---|---|
| `supabase/postgres:17.6.1.136` | yes |
| `supabase/gotrue:v2.189.0` | yes |
| `postgrest/postgrest:v14.12` | yes |
| `nginx:alpine` | yes (`arm64/v8`) |
| `axllent/mailpit:latest` (pinned here to `v1.31.6`) | yes (`latest` measured; `v1.31.6` is the current latest release) |
| `rustfs/rustfs:latest` | yes |
| `amazon/aws-cli` | yes |
| `redis:7-alpine` | yes (`arm64/v8`) |
| `node:22-slim` (base of the locally BUILT backend + frontend) | yes (`arm64/v8`) |

The backend and frontend images are built locally from the submodule. Their
arm64 readiness comes from the inputs, not from an actual build. The base image
is multi-arch, LibreOffice comes from Debian apt (built for arm64), and both
`package-lock.json` files carry the `linux-arm64-gnu` native bindings
(`@next/swc`, `@napi-rs/canvas`, `lightningcss`, `@rolldown`, `@oxc-parser`).
**Not yet measured:** a real `make up-mike` build on SPARK.

## Secrets

The key inventory comes from the backend source: every `process.env` read under
`PMOVES-Mike/backend/src`, excluding tests. Upstream's `.env.example`
templates are zero-access to agents under the damage-control guard.

**Must be funneled (secrets pipeline → `pmoves/env.mike`):**

| Key | Required? | Notes |
|---|---|---|
| `DOWNLOAD_SIGNING_SECRET` | **yes**. Backend throws without it | 32-byte hex. Also the fallback for `SPOTLIGHT_NONCE_SECRET` |
| `USER_API_KEYS_ENCRYPTION_SECRET` | **yes**. Saving user API keys throws without it | 32-byte hex, distinct from the above. Fallback for `MCP_CONNECTORS_ENCRYPTION_SECRET` |
| `MCP_CONNECTORS_ENCRYPTION_SECRET` | optional | |
| `MANIFEST_SIGNING_KEY` | optional | Ed25519 export-manifest signing; malformed = boot failure |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` / `MISTRAL_API_KEY` / `XAI_API_KEY` | at least one, unless Ollama-only | SPARK default is Ollama, so none are required |
| `COURTLISTENER_API_TOKEN` | optional | external case-law verification |
| `GOTRUE_EXTERNAL_GOOGLE_CLIENT_ID` / `_SECRET` | only if Google auth is enabled | |

**Upstream demo credentials (loopback only):** the Supabase JWT secret
(`super-secret-jwt-token-with-at-least-32-characters-long`), the anon and
service_role JWTs signed with it, the Postgres password `postgres` (also forced
onto `supabase_auth_admin`/`authenticator` by `docker/db-init/roles.sql`), and
the RustFS admin pair `rustfsadmin`/`rustfsadmin`. Upstream hardcodes all of
them in its compose. They are acceptable only while every port is
loopback-bound, so `make up-mike` refuses a non-loopback `MIKE_BIND` unless
`MIKE_DEMO_CREDS_ROTATED=1`.
**Open item:** rotating them as a set needs overlay overrides for the
`db`/`auth`/`rest`/`db-init`/`storage`/`createbucket`/`backend`/`workflow-sync`
environments plus a replacement `roles.sql`, with all values funneled. That is
deferred until Mike leaves loopback (tailnet or Traefik exposure).

## Mailpit (Mike's mail stack, and TitanMail MCP's local test inbox)

Mike's GoTrue sends all auth mail to Mailpit (`GOTRUE_SMTP_HOST=mailpit`,
port 1025, no auth). The Mike backend sends no mail itself. Mailpit accepts any
SMTP auth (`MP_SMTP_AUTH_ACCEPT_ANY=1`) and allows it over plaintext
(`MP_SMTP_AUTH_ALLOW_INSECURE=1`). Nothing leaves the host.

- **SMTP:** `127.0.0.1:18326` from the host. Inside the `pmoves-mike_default`
  network it is `mailpit:1025`.
- **Web UI + REST API:** `http://127.0.0.1:18325`. No web auth is configured
  (`MP_UI_AUTH*` unset). That is one reason the port is loopback-only, since the
  inbox holds sign-up and password-reset links.

REST API at `v1.31.6`. Taken from Mailpit's own `server/ui/api/v1/swagger.json`
and route table `server/server.go` at tag `v1.31.6`, not from memory:

| Method | Path | Purpose |
|---|---|---|
| GET | `/livez` | liveness |
| GET | `/readyz` | readiness |
| GET | `/api/v1/info` | application info (version, DB size, message counts) |
| GET | `/api/v1/webui` | web UI configuration |
| GET | `/api/v1/messages?start=&limit=` | list message summaries (newest first) |
| PUT | `/api/v1/messages` | set read status (body: `IDs` / `Read` / `Search`) |
| DELETE | `/api/v1/messages` | delete messages (body `{"IDs":[...]}`; empty = all) |
| GET | `/api/v1/search?query=&start=&limit=&tz=` | search (Mailpit search syntax, e.g. `to:alice@x subject:"confirm"`) |
| DELETE | `/api/v1/search?query=&tz=` | delete messages matching a search |
| GET | `/api/v1/message/{ID}` | message summary incl. `Text`, `HTML`, attachments (`ID` may be `latest`) |
| GET | `/api/v1/message/{ID}/headers` | headers |
| GET | `/api/v1/message/{ID}/raw` | raw RFC 5322 source |
| GET | `/api/v1/message/{ID}/part/{PartID}` | attachment |
| GET | `/api/v1/message/{ID}/part/{PartID}/thumb` | image attachment thumbnail |
| GET | `/api/v1/message/{ID}/html-check` | HTML compatibility check |
| GET | `/api/v1/message/{ID}/link-check` | link check |
| GET | `/api/v1/message/{ID}/sa-check` | SpamAssassin check (only if configured) |
| POST | `/api/v1/message/{ID}/release` | release (relay) a message (only if SMTP relay configured; not configured here) |
| POST | `/api/v1/send` | inject a message over HTTP (JSON body: `From`, `To`, `Subject`, `Text`, `HTML`, ...) |
| GET | `/api/v1/tags` | list tags |
| PUT | `/api/v1/tags` | set tags on messages |
| PUT | `/api/v1/tags/{Tag}` | rename tag |
| DELETE | `/api/v1/tags/{Tag}` | delete tag |
| GET | `/api/v1/chaos` · PUT `/api/v1/chaos` | chaos (fault-injection) triggers |
| GET | `/view/{ID}.html` · `/view/{ID}.txt` | rendered HTML / text part |
| GET (WebSocket) | `/api/events` | live new-message / delete events |

The `latest` ID alias (`"Message database ID or \"latest\""`), the `PUT`
body (`IDs`, `Read`, `Search`), the `DELETE` body (`IDs`) and `POST /send`'s
one required field (`From`) all come from the swagger spec. They have not been
exercised against a live container yet. `GET /api/v1/info` reports the running
version.

**TitanMail MCP wiring (intended):** SMTP send to `127.0.0.1:18326`, then
assert delivery with `GET /api/v1/search?query=to:<addr>` and read the body with
`GET /api/v1/message/{ID}`. `DELETE /api/v1/messages` between test cases. This
is a test inbox only. Never point real outbound mail at it.

## What MiSSinGLinC reuses (key_modules re-verified at `563c8319`)

The spec's paths date from `204d2d5`. Upstream has since modularised the
backend (`4df3edd5`, #295, 2026-09-17: `src/lib/chat/*` → `src/modules/chat/engine/*`)
and removed `routes/caseLaw.ts` (`fee97de9`, "normalize assistant source
documents").

| Spec path (@204d2d5) | Current path (@563c8319) | Status |
|---|---|---|
| `backend/src/lib/chat/verifyCitations.ts` | `backend/src/modules/chat/engine/verifyCitations.ts` | **moved; behaviour widened**. No longer exact-match only. See below |
| `backend/src/lib/chat/citations.ts` | `backend/src/modules/chat/engine/citations.ts` | moved |
| `backend/src/lib/manifestSigning.ts` | same | present |
| `backend/src/lib/chat/tools/toolDispatcher.ts` | `backend/src/modules/chat/engine/tools/toolDispatcher.ts` | moved |
| `backend/src/lib/courtlistener.ts` | same | present |
| `backend/src/routes/caseLaw.ts` | **removed**. Replaced by `backend/src/modules/source-documents/sourceDocuments.routes.ts` (mounted at `/documents`, `GET /:documentId`) + `backend/src/modules/chat/engine/tools/courtlistenerTools.ts` / `courtlistenerTurnState.ts` | **gone; successor named** |

**Behaviour change that matters to the validator.** At `563c8319`,
`verifyQuoteAgainstSource` tries three tiers in order: (1) exact substring,
(2) whitespace-collapsed + lowercased, (3) tier 2 with punctuation stripped. It
returns the exact original excerpt and a `needs_correction` flag whenever the
match was not exact. It also handles ellipsis-abbreviated quotes (`...` / `…`,
with each segment verified independently) and cross-page quotes joined with
`[[PAGE_BREAK]]` (in order, within 5,000 chars of each other, at most 64 locate
attempts). The validator's Python port keeps that logic and reports *which*
tier matched, so "verified" never silently means "verified modulo
punctuation".

The backend's chat endpoint, which the spec lists as `POST /api/chat`, is
`POST /chat` on the backend (`chatRouter`, `requireAuth`). The frontend's
`/api/*` proxy forwards it there.

## Open items

0. **Apply the overlay** from
   `pmoves/docs/handoffs/mike-compose-overlay-spark-2026-10-21.md` (operator,
   `KNOWN_ROAD=compose:handoff:mike-compose-overlay-spark-2026-10-21.md`).
1. First real `make up-mike` on SPARK (build of backend/frontend on arm64,
   `db-init` migration, `workflow-sync`). Not run in the PR that added this
   doc, which by brief started no containers.
2. Demo-credential rotation (see § Secrets) before any non-loopback exposure.
3. `.claude/context/submodules.md` entry is **operator-apply** (the file is
   read-only under the damage-control guard, and no Known Road covers it). The
   text is in the PR body.
4. Fork is 7 commits behind upstream; `fork-sync.yml` now carries the
   `open-legal-products/mike|PMOVES-Mike|` mapping.
