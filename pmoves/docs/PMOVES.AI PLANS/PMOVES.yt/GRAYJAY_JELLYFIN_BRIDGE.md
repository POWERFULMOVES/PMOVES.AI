# Grayjay ↔ Jellyfin Integration Plan
_Created: 2025-10-23 — Status: Draft_

This plan tracks the work required to expose PMOVES/Jellyfin media libraries through Grayjay so curators can browse and queue long-form channels directly from the Grayjay client while keeping ingestion routed through pmoves-yt and Jellyfin.

---

## 1. Goals
- Host a first-party Grayjay backend that mirrors the upstream plugin directory so users can add PMOVES services from a trusted endpoint.
- Provide a Jellyfin plugin manifest/QR flow that pre-populates server credentials (API key or OAuth) for workshop users.
- Keep pmoves-yt ingest aware of Grayjay-initiated sessions (e.g., playlist capture requests) to maintain provenance and channel ownership metadata.

---

## 2. Hosting Options

| Option | Summary | Pros | Cons |
| --- | --- | --- | --- |
| Grayjay desktop `--server` mode | Run the Grayjay desktop build in “server” mode to expose the aggregated plugin catalog and media browser via a web UI/API. | Officially supported as of the 2025.10 release; minimal customization. | Requires bundling the desktop build in our stack; still experimental (nightly feature). |
| Phoenix-based Jellyfin plugin host | Deploy the open-source `grayjay-jellyfin-plugin` Phoenix app inside our infra to mint plugin QR codes. | Battle-tested UI for generating Jellyfin plugin manifests & QR codes. | Full Elixir/Phoenix runtime; needs Redis/Postgres and TLS to mirror production UX. |
| Static plugin manifest service | Serve curated plugin JSON from a lightweight FastAPI/Flask app inside PMOVES. | Easy to containerize; aligns with our Python stack. | Must replicate plugin schema manually; loses auto-update benefits from official feeds. |

### Container Artefacts

- **Grayjay server/runtime** – FUTO publishes multi-arch images under the GitLab registry `registry.gitlab.futo.org/videostreaming/grayjay/*`. Pull tags directly or mirror into our internal registry before composing.
- **Fcast (streaming helpers)** – Complementary streaming containers live at `registry.gitlab.futo.org/videostreaming/fcast/*` alongside release bundles and CI artifacts; useful for testing Grayjay plugin playback.

---

## 3. Proposed Architecture
1. **Invidious companion** stays resident (profile `invidious`) to guarantee high-reliability YouTube playback/metadata for Grayjay-sourced requests.
   - Bring up with `COMPOSE_PROFILES=invidious make up` (or merge with existing profiles); configure secrets in `env.shared`.
2. **Grayjay service**: package the desktop build (AppImage) in a thin VNC-less container that launches `Grayjay --server --bind 0.0.0.0:9095 --data /grayjay`. Add compose profile `grayjay` so operators can opt in.
   - The repo now includes `grayjay-plugin-host` (FastAPI) and `grayjay-server` compose services; start with `COMPOSE_PROFILES=grayjay docker compose up -d` and browse plugins at `http://localhost:9096/plugins`.
3. **Plugin manifest API**: implement a minimal FastAPI service (`pmoves/services/grayjay-plugin-host`) to expose:
   - `GET /plugins` – curated list (YouTube, SoundCloud, PMOVES Jellyfin).
   - `POST /plugins/jellyfin` – accepts Jellyfin URL + API key and returns plugin JSON + QR code (mirrors Phoenix behavior).
4. **Jellyfin linkage**: create Jellyfin “external channel” pointing to `pmoves-yt` results so Grayjay browsing can jump directly into Jellyfin playback.

---

## 4. Deliverables

| Area | Requirement | Owner | Status |
| --- | --- | --- | --- |
| Docker profile | Add `grayjay` profile with container images (Grayjay server + plugin host + optional Redis). | — | ☐ |
| Plugin manifest API | Scaffold FastAPI service with `/plugins` + `/plugins/jellyfin` endpoints and signed QR output. | — | ☐ |
| Secrets flow | Store Grayjay server token + Jellyfin credential template inside `env.shared.example`. | — | ☐ |
| Docs | Extend `docs/LOCAL_DEV.md` with “Grayjay profile” section (start/stop, URLs, login defaults). | — | ☐ |
| QA | Smoke checklist covering Grayjay → Jellyfin playback and pmoves-yt ingest triggered via Grayjay playlist capture. | — | ☐ |

---

## 5. Risks & Open Questions
- Server mode stability is new; monitor upstream releases for breaking changes.
- Jellyfin authentication: decide between password-based login vs. creating limited-scope API keys per Grayjay user.
- Plugin auto-update: determine whether to mirror upstream plugin feed or curate PMOVES-specific entries only.

---

## 6. Next Steps
1. Package Grayjay desktop server in a reproducible container (either multi-stage or download on start).
2. Prototype plugin manifest API returning hard-coded Jellyfin entry; confirm Grayjay client can import it.
3. Wire grayjay-triggered ingest jobs back into Supabase via `user_sources` so personalization dashboards show Grayjay activity.
4. Add monitoring (health endpoint + logs) so Grayjay outages surface in the standard ops dashboards.
