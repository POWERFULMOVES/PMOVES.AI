# Handoff: persona-room public edge overlay (Phase 5 host cutover)

**Change:** add `pmoves/docker-compose.persona.yml` — a PUBLIC static-serve
service (`persona-room`, unprivileged nginx) that serves the rendered persona
living-doc behind the merged Traefik edge (`docker-compose.traefik.yml`, #2221)
at **persona.pmoves.ai**.

**Why a compose edit:** the Traefik edge routes to labeled containers; serving
static files requires an nginx container declared in a compose overlay. This is a
hand-authored edge overlay in the same class as `docker-compose.traefik.yml` /
`docker-compose.sso.yml`, not a compose-split-generated file.

**Scope / safety:**
- Serves the RENDERED living-doc (a2ui shell + PreTeXt HTML + Remotion
  walkthrough) only — NOT the OpenRoom operator desktop (that adapter, Mavis-5090,
  stays private; it carries LLM config + agent sessions).
- Route is **PUBLIC**: it intentionally does NOT attach the `pmoves-forward-auth`
  middleware. The persona living-doc is public (LinkedIn-facing).
- Hardened: unprivileged nginx (uid 101, binds :8080), `no-new-privileges`,
  `cap_drop: [ALL]`, `read_only` rootfs + tmpfs for nginx's writable paths.
- Static bundle is produced by `make persona-render` into `rooms/persona/dist/`
  (gitignored); nginx serves it read-only.

**Operator runbook:**
1. Ensure the Traefik edge is up (creates the external `pmoves_external` network).
2. DNS: create `persona.pmoves.ai` → the edge host (Cloudflare; covered by the
   `*.pmoves.ai` DNS-challenge cert, resolver `cf`).
3. `make persona-render` — renders PreTeXt + Remotion into `rooms/persona/dist/`.
4. `make up-persona` — brings up the `persona-room` service; Traefik auto-discovers
   the labeled container and serves it at https://persona.pmoves.ai.
5. `make persona-health` / `make down-persona` as needed.

**Related:** `pmoves/docs/research/persona/07_linkedin_living_doc_room.md` (Phase 5
section), `pmoves/config/rooms/persona.room.livingdoc.json` (#2246), the a2ui
walkthrough (#2247), PreTeXt case study (#2238).
