# PMOVES.AI — ActivePieces (self-host)

Low-code automation companion to the [n8n fabric](../n8n/flows). Runs as its own
opt-in stack (app + worker + postgres + redis) so it can be brought up on demand
rather than baked into the main fleet compose. Flows are versioned as code in
[`flows/`](flows/) — the same convention as the 34 n8n flows.

- **Edition:** MIT open-source, self-hosted (`ghcr.io/activepieces/activepieces:0.86.3`).
- **Hosted account:** `cataclysmstudios@gmail.com` on ActivePieces Cloud.
- **Phase 1 (this):** standalone self-host. **Phase 2 (tracked):** integrate as a first-class service in the main fleet `docker-compose.yml`.

## Bring up (Known Road — `make`, not raw docker)

Use the make targets — they wrap the standalone compose with the correct
`--env-file`/project settings. Do **not** run raw `docker compose up` (it
bypasses the env-injection convention and trips the pipeline guard).

```bash
# 1. seed the (gitignored) instance env once, then hydrate its SECRET values
cp pmoves/activepieces/env.activepieces.example pmoves/activepieces/env.activepieces
# secrets — AP_ENCRYPTION_KEY, AP_JWT_SECRET, AP_POSTGRES_PASSWORD (+ AP_LICENSE_KEY
# for ee/Git Sync) — via the PMOVES secrets pipeline; do NOT hand-commit real values.
# env.activepieces is gitignored so secrets never land in the repo.

# 2. bring up / check / down
make -C pmoves up-activepieces
make -C pmoves activepieces-health
make -C pmoves down-activepieces
```

UI: <http://localhost:8087> (bound to `127.0.0.1` by default — front it with the
mesh/Tailscale rather than publishing to the LAN, per the privacy-mesh rule).

## Connecting to the hosted account (Git Sync)

Git Sync makes flows version-controlled and shared between the Cloud project and
this self-host — both point at `pmoves/activepieces/flows/`. **Git Sync is an
ActivePieces Enterprise feature** (set `AP_EDITION=ee` + `AP_LICENSE_KEY`).

**If your Cloud plan includes Git Sync:**
1. Cloud → Project Settings → **Git Sync** → connect this repo, branch, folder `pmoves/activepieces/flows`.
2. Self-host: set `AP_EDITION=ee` + `AP_LICENSE_KEY` in `env.activepieces`, then in its Project Settings → Git Sync → same repo/branch/folder.
3. Push/pull flows through git; both environments stay in sync and the flows are represented in the repo (and on the LinkedIn profile).

**Community-edition fallback (no Git Sync):**
1. Cloud → export each flow (⋯ → Export, or the flows API).
2. Commit the exported JSON into `pmoves/activepieces/flows/`.
3. Import into the self-host (Flows → Import). The repo copy is the source of truth; re-export on change.

## Secrets (via the PMOVES pipeline)

| Var | Purpose |
|-----|---------|
| `AP_ENCRYPTION_KEY` | 32-hex (256-bit) — encrypts connections at rest |
| `AP_JWT_SECRET` | session/JWT signing |
| `AP_POSTGRES_PASSWORD` | local activepieces postgres |
| `AP_LICENSE_KEY` | only when `AP_EDITION=ee` (Git Sync) |

Add these to the secrets manifest and emit via `secrets-rotate`; the compose
reads them from `env.activepieces` (which the pipeline hydrates). See
`.claude/context/credentials-workflow.md`.

## Relationship to n8n

n8n (self-hosted, in the mesh) carries the heavy, stateful, CGP/geometry-bus-wired
automations. ActivePieces carries lightweight cross-SaaS / no-code flows that don't
need to live in the mesh. Both keep flows-as-code in this repo.
