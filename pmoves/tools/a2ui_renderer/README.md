# a2ui_renderer tools

Lane 2228 (2026-08-02): CLI surface for the a2ui-renderer living-doc animation
lane. Three small scripts, all stdlib-only, all runnable from `uv` script
headers (no `pip install` required).

## Scripts

| Script | Purpose |
| --- | --- |
| `render_living_doc.py` | Convert a markdown living doc into a provenance-shaped MP4/GIF/WebM via the a2ui-renderer service (`/render/provenance`). |
| `check_renderable_freshness.py` | Read `pmoves/configs/living_docs_registry.yaml` and report entries whose source markdown is older than `ttl_days`. |
| `test_render_living_doc.py` | 18-test smoke/unit suite covering the parser, registry loader, dry-run, full HTTP path (mocked), and error paths. |

## Quick start

```bash
# 1. Bring the renderer up
make -C pmoves up-a2ui-renderer

# 2. Dry-run on a single doc (no HTTP, just parses the markdown)
python pmoves/tools/a2ui_renderer/render_living_doc.py \
    --doc pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md \
    --output /tmp/vt.json \
    --dry-run

# 3. Render it for real (POSTs to the renderer, downloads the result)
export A2UI_RENDERER_TOKEN="$SUPABASE_JWT_SECRET"
python pmoves/tools/a2ui_renderer/render_living_doc.py \
    --doc pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md \
    --output pmoves/docs/living-docs/rendered/chit-visual-tour.mp4 \
    --format mp4

# 4. Walk the whole registry
make -C pmoves docs-render-living

# 5. See which entries are due for a re-render
python pmoves/tools/a2ui_renderer/check_renderable_freshness.py \
    --registry pmoves/configs/living_docs_registry.yaml \
    --repo-root . --strict
```

## How it fits the lane

The a2ui-renderer compose stanza (added in
`pmoves/docker-compose.yml`) brings the service up at `localhost:8107` with the
`agents`, `media`, and `docs` profiles active. The Makefile (`up-a2ui-renderer`,
`down-a2ui-renderer`, `a2ui-renderer-smoke`, `a2ui-renderer-render`,
`docs-render-living`) wraps `docker compose` for the human. These three Python
scripts wrap the HTTP API for everything that should be scriptable.

See `pmoves/docs/specs/a2ui-renderer-compose-2026-08-02.md` for the cold-read
spec; the registry extension is at
`pmoves/configs/living_docs_registry.yaml` under `renderable:`.
