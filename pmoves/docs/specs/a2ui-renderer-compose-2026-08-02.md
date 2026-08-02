# a2ui-renderer compose lane — Issue #2228 (2026-08-02)

> Cold-read spec for the a2ui-renderer first-class compose lane. If you
> are a fresh local model picking this work up next session, this is the
> document that tells you what shipped, why, and what's left.

## TL;DR

The a2ui-renderer was a service-source orphan: the TypeScript service
existed at `pmoves/services/a2ui-renderer/`, the Remotion bundle compiled,
the `/render/provenance` endpoint worked — but there was **no compose
stanza, no Makefile target, and no registry** saying "render this living
doc into an MP4 artifact". This lane makes it a first-class fleet
capability. Three deliverables:

1. **Compose stanza + Makefile tokens** (P1 commit)
2. **Living-docs hook** = `render_living_doc.py` + `check_renderable_freshness.py` + 18-test smoke suite (functional commit)
3. **Registry awareness** = `renderable:` section in `pmoves/configs/living_docs_registry.yaml` (P1 commit)

Branch: `feat/a2ui-renderer-compose-2228`
PR: pending (push + open from `0406ad082d`)
3-stacked commits: `0552b1537c` (P1) / `0406ad082d` (functional) / docs (this spec)

## Why now

- **The living-doc lane was a render-farm ask.** The 4090-Claude sub-agent
  asked for animated living docs (the chit-tour visual re-skin, services
  catalog dashboard, AGNOTE active-claims montage) but every existing call
  site was npm-script-only inside `services/a2ui-renderer/`. A fleet
  operator on 5090 or z890 had no first-class way to bring the renderer
  up alongside the rest of the services.
- **The /render/provenance endpoint was unused.** The TypeScript service
  exposed it for ~3 months but the only callers were demo JSX components
  in the same directory. No operator-facing surface.
- **`make docs-render-living` was a placeholder.** A previous lane wired
  the Makefile target but it pointed at npm scripts; running it on
  a clean host produced "command not found".

## What shipped

### P1 — compose + Makefile + registry (commit `0552b1537c`)

`pmoves/docker-compose.yml` (new stanza after a2ui-nats-bridge):

```yaml
a2ui-renderer:
  build: { context: ., dockerfile: services/a2ui-renderer/Dockerfile }
  image: ${A2UI_RENDERER_IMAGE:-ghcr.io/powerfulmoves/pmoves-a2ui-renderer:pmoves-latest}
  container_name: pmoves-a2ui-renderer
  hostname: a2ui-renderer
  restart: unless-stopped
  <<: *tier-agent-hardened-ro
  environment:
  - PORT=8107
  - NODE_ENV=production
  - NATS_URL=${NATS_URL}
  - MINIO_ENDPOINT=${MINIO_ENDPOINT:-${S3_ENDPOINT:-minio:9000}}
  - MINIO_SECURE=${MINIO_SECURE:-false}
  - MINIO_ACCESS_KEY=${MINIO_USER:?Run make brand-defaults}
  - MINIO_SECRET_KEY=${MINIO_PASSWORD:?Run make brand-defaults}
  - MINIO_BUCKET=${A2UI_BUCKET:-outputs}
  - CHIT_REQUIRE_SIGNATURE=${CHIT_PROD_REQUIRE_SIGNATURE:-true}
  - CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}
  - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:?set SUPABASE_JWT_SECRET in env.shared}
  - PROVENANCE_AGENT_ID=${PROVENANCE_AGENT_ID:-a2ui-renderer}
  - PMOVES_NETWORKS=pmoves_app,pmoves_bus,pmoves_data
  ports:
  - ${A2UI_RENDERER_BIND:-0.0.0.0}:${A2UI_RENDERER_PORT:-8107}:8107
  profiles: [agents, media, docs]
  networks: [pmoves_app, pmoves_bus, pmoves_data]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:8107/healthz >/dev/null 2>&1 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
  depends_on:
    nats:  { condition: service_healthy }
    minio: { condition: service_healthy }
  deploy:
    resources:
      limits:       { cpus: '1.0', memory: 1G }
      reservations: { cpus: '0.25', memory: 256M }
```

Profiles are `agents` (creator pipeline), `media` (Remotion bundle has
the heavy Chromium dep), and `docs` (the `make docs-render-living` hook
needs the renderer up). The previous `up-a2ui-renderer` Makefile target
used the `creator` profile which doesn't exist; this lane fixes that
to use the three real profiles.

`pmoves/Makefile` adds:

- `up-a2ui-renderer` (was `creator` profile → now `agents media docs`)
- `down-a2ui-renderer` (new)
- `a2ui-renderer-smoke` (extended to print `/metrics` counters)
- `a2ui-renderer-render` (new, single-doc helper)
- `docs-render-living` (new, registry iterator)

Tokens: `A2UI_RENDERER_PORT=8107`, `A2UI_RENDERER_TOKEN=${SUPABASE_JWT_SECRET}`,
`A2UI_RENDERER_RENDER_DIR=pmoves/docs/living-docs/rendered`.

`pmoves/configs/living_docs_registry.yaml` extends with a new
`renderable:` section (5 entries, see below).

### Functional — Python orchestrator + freshness check + tests (commit `0406ad082d`)

- `pmoves/tools/a2ui_renderer/render_living_doc.py` (612 lines, stdlib only):
  - Two modes: `--doc <md> --output <mp4>` (single) and `--registry <yaml> --output-dir <dir>` (iterator).
  - Markdown parser builds a `ProvenanceLivingDoc` that matches the TS
    service's `normalizeProvenanceLivingDoc()` contract 1:1: 4 sections max,
    8 weighted terms max, 6 provenance refs max, 8 favorite words max,
    `merkle_root = "mkl_" + sha256(normalized content)[:16]`,
    `shape_id = "shape.doc." + sha256(source path)[:16]`,
    `duration_ms` mirrors `estimateProvenanceDurationMs()` exactly.
  - `--dry-run` writes the request body to a JSON file with no HTTP.
  - `--print-doc` dumps the parsed ProvenanceLivingDoc to stdout for debugging.
  - Forces UTF-8 on stdout/stderr at module-load time so the script is
    portable from Windows charmap without `PYTHONIOENCODING=utf-8`.
- `pmoves/tools/a2ui_renderer/check_renderable_freshness.py` (130 lines):
  - Walks the `renderable:` section, classifies each entry as
    `stale: true/false` based on `source_doc` mtime vs `ttl_days`.
  - JSON report on stdout, one-line summary on stderr.
  - `--strict` exits non-zero if any entry is stale — the right hook for
    the docs-freshness village-gate.
- `pmoves/tools/a2ui_renderer/test_render_living_doc.py` (18 tests):
  - `MarkdownParserTests` (10): H1→title, H2→sections, cap enforcement,
    merkle determinism, shape_id stability, fallback behavior, schema.
  - `RegistryLoaderTests` (3): loads renderable section, excludes tracked,
    handles empty case.
  - `DryRunTests` (1): writes valid JSON, no HTTP traffic.
  - `FullPathTests` (2): posts to an in-process mock, downloads the
    result, iterates a registry end-to-end.
  - `ErrorPathTests` (2): missing source raises, unsupported format raises.
  - **All 18 tests pass on a clean `python pmoves/tools/a2ui_renderer/test_render_living_doc.py`** (no `PYTHONIOENCODING` needed).
- `pmoves/tools/a2ui_renderer/__init__.py` (1 line): package marker.
- `pmoves/tools/a2ui_renderer/README.md` (60 lines): operator quick-start.

`ruff check pmoves/tools/a2ui_renderer/`: **All checks passed!**

### Registry — 5 renderable entries

```yaml
renderable:
  - id: chit-visual-tour-walkthrough
    source_doc: pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md
    output_key: chit-visual-tour
    format: mp4
    ttl_days: 14
    description: "Interactive code-walkthrough tour of CHIT (8 sections, 60 min read-time)"

  - id: agnote-active-claims
    source_doc: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
    output_key: agnote-active-claims
    format: mp4
    ttl_days: 3
    description: "Active claim register - fastest-moving doc, re-render weekly"

  - id: services-catalog-dashboard
    source_doc: .claude/context/services-catalog.md
    output_key: services-catalog
    format: mp4
    ttl_days: 14
    description: "Service catalog (ports, URLs, health endpoints) - drift-detected via recon"

  - id: a2ui-renderer-readme
    source_doc: pmoves/services/a2ui-renderer/README.md
    output_key: a2ui-renderer-readme
    format: mp4
    ttl_days: 30
    description: "A2UI renderer readme - the renderer that produces these artifacts"

  - id: chit-tour-public
    source_doc: pmoves/docs/handoffs/chit-tour-public-edge.md
    output_key: chit-tour-public-edge
    format: mp4
    ttl_days: 30
    description: "CHIT tour public-edge handoff - hosting + DNS + cache config"
```

The existing `tracked:` section is unchanged.

## How to use

```bash
# Bring the renderer up (waits for healthz, prints status)
make -C pmoves up-a2ui-renderer

# Smoke test: confirm the service is up + the metrics counters are live
make -C pmoves a2ui-renderer-smoke

# Dry-run on a single doc (no HTTP, just dumps the ProvenanceLivingDoc JSON)
python pmoves/tools/a2ui_renderer/render_living_doc.py \
    --doc pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md \
    --output /tmp/vt.json --dry-run

# Render it for real (needs SUPABASE_JWT_SECRET in env, or pass --token)
export A2UI_RENDERER_TOKEN="$SUPABASE_JWT_SECRET"
python pmoves/tools/a2ui_renderer/render_living_doc.py \
    --doc pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md \
    --output pmoves/docs/living-docs/rendered/chit-visual-tour.mp4 \
    --format mp4

# Walk the whole registry
make -C pmoves docs-render-living

# See which entries are due for a re-render
python pmoves/tools/a2ui_renderer/check_renderable_freshness.py \
    --registry pmoves/configs/living_docs_registry.yaml --repo-root . --strict

# Stop the renderer
make -C pmoves down-a2ui-renderer
```

## Validation

| Check | Result |
| --- | --- |
| `python pmoves/tools/a2ui_renderer/test_render_living_doc.py` | 18/18 OK |
| `ruff check pmoves/tools/a2ui_renderer/` | All checks passed! |
| `docker compose --profile agents --profile media --profile docs config --services \| grep a2ui-renderer` | shows `a2ui-renderer` (102 services total) |
| `make a2ui-renderer-smoke` (post `make up-a2ui-renderer`) | `healthz OK` + 5 metrics counters |
| `make docs-render-living` (dry-run) | 5/5 entries produce valid ProvenanceLivingDoc JSON |
| `make -C pmoves docs-reconcile-check` (advisory) | 3 pre-existing over-budget findings, none from this lane |

## Out of scope (intentional)

- **GHCR publishing for the heavy Chromium image** — the `Dockerfile` is
  build-on-host for now. GHCR publish + CI registry is a follow-up
  lane (the same lane that handles tokenism-simulator's GHCR promotion).
- **Cross-node NATS mesh for the a2ui-renderer publisher** — Lane 5
  added the backing `COMFY_COLLAB` stream but the cross-node leaf
  topology is a separate lane. Right now the renderer publishes to
  whichever nats container is on the same docker network.
- **Replacing gradio_client with the MCP SSE bridge for the
  `pterm list/status` of the renderer's health** — the existing
  nats_event_bus HTTP API is the right primitive for monitoring.
- **Re-render automation (cron, on-commit hook)** — the freshness
  check is the advisor; the operator (or a future cron lane) decides
  when to re-render. This lane stops at "advisor exists + manual
  trigger works".
- **Pretext submodule wiring for the chit-tour living-doc** — that's
  Issue #2227, a sister issue. This lane is the rendering lane; #2227
  is the source-submodule lane.

## Follow-up lanes

1. **GHCR publishing for a2ui-renderer** — heavy Chromium image, multi-arch.
2. **Wire `make docs-render-living` into the docs-freshness
   village-gate** (catches stale living docs the same way `ruff-budget`
   catches stale style).
3. **Issue #2227** (Pretext submodule for the chit-tour living-doc).
4. **`make docs-render-living` cron** — runs on a 7-day cadence,
   re-renders entries that are past `ttl_days`, uploads the result to
   the canonical MinIO key, updates `last_rendered_at` in the registry.
5. **Cross-node NATS mesh for the a2ui-renderer publisher** (depends
   on the cross-node NATS leaf topology lane).

## Three-body

- delivery: Mavis (this lane)
- control: DARKXSIDE (PR review + 5 required gates + admin-merge)
- memory: this spec + 3 stacked commits + 18 new test cases + 5 registry
  entries + the freshness check

## CHIT trail

`unsigned-local` (no `CHIT_PASSPHRASE` in Mavis session). After admin-merge,
the spec doc is referenced from the AGNOTE CLAIM/RELEASE entry.
