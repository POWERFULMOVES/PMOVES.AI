# Handoff: CHIT tour public edge overlay (chit.pmoves.ai)

**Change:** add `pmoves/docker-compose.chit-tour.yml` — a PUBLIC static-serve
service (`chit-tour`, unprivileged nginx) that serves the CHIT Visual Tour behind
the merged Traefik edge (`docker-compose.traefik.yml`, #2221) at
**chit.pmoves.ai**.

**Why a compose overlay:** the Traefik edge routes to labeled containers; serving
static files requires an nginx container declared in a compose overlay. This is a
hand-authored edge overlay in the same class as `docker-compose.traefik.yml` /
`docker-compose.sso.yml` / `docker-compose.persona.yml`, not a
compose-split-generated file.

**Scope / safety:**
- Serves the static tour (`website/chit-tour/`) with **live data** regenerated
  from the agent registry by `make chit-tour-data` (roster + subjects, #2076).
- Route is **PUBLIC**: it intentionally does NOT attach the `pmoves-forward-auth`
  middleware. The CHIT tour is public.
- Hardened: unprivileged nginx (uid 101, binds :8080), `no-new-privileges`,
  `cap_drop: [ALL]`, `read_only` rootfs + tmpfs for nginx's writable paths.
- Strict CSP in `config/nginx/chit-tour.conf`: all assets are local (fonts, D3,
  Three, data.js) — no CDN — so `script-src 'self'`; `style-src 'self'
  'unsafe-inline'` only (D3/Three runtime positioning), tighter than the persona
  room (which needs the MathJax CDN).

**Operator runbook:**
1. Ensure the Traefik edge is up (creates the external `pmoves_external` network).
2. **DNS:** create `chit.pmoves.ai` → the edge host (Cloudflare; covered by the
   `*.pmoves.ai` DNS-challenge cert, resolver `cf`). Same step-class as the still
   pending `persona.pmoves.ai` record — batch both in one Cloudflare pass.
3. `make chit-tour-data` — regenerate the live roster/subjects into
   `website/chit-tour/data.generated.js`.
4. `make up-chit-tour` — brings up the `chit-tour` service; Traefik auto-discovers
   the labeled container and serves it at https://chit.pmoves.ai.
5. `make chit-tour-health` / `make down-chit-tour` as needed.

**DNS record (Cloudflare, operator):**

| Name | Type | Target | Proxy | Cert |
|---|---|---|---|---|
| `chit.pmoves.ai` | A / CNAME | Traefik edge host | (per edge policy) | auto via `*.pmoves.ai` DNS-challenge (`cf`) |

**Surface note:** apex `pmoves.ai` + `www.pmoves.ai` are Cloudflare (CF site). The
tour lives on **pmoves.ai proper** (the self-hosted Traefik edge), NOT the CF
site — consistent with the persona room. The `website/chit-tour/` files also ship
to the CF site via `make pmoves-ai-deploy`; this overlay makes the edge the
canonical public home.

**Related:** #2076 (tour re-skin + live data), `docker-compose.persona.yml` +
`docs/handoffs/persona-room-public-edge.md` (the pattern this mirrors),
`docker-compose.traefik.yml` (#2221 edge).
