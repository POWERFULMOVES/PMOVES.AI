# TensorZero: Cloud-First Architecture & Supabase Integration

## Summary
This PR transitions TensorZero to a production-ready "Cloud-First" architecture, integrating it directly with the core Supabase data tier and implementing Agent Zero compatibility.

## Key Changes

### 1. Robustness & Routing (Cloud-First)
-   **Cloud Priority:** Configured `functions.orchestrator` to accept `system` prompts and prioritize `primary_cloud` (GPT-4o/Claude) with a `local_fallback` (Qwen 3).
-   **Agent Zero Helper:** Created `tensorzero/config/functions/orchestrator/system.minijinja` to bypass rigid system schemas, allowing Agent Zero's dynamic system prompts to pass through unmodified.
-   **Schema Relaxation:** Removed `system_schema` validation in `tensorzero.toml`.

### 2. Infrastructure & Security (Supabase Integration)
-   **Postgres Logic:** Moved TensorZero from a standalone container to the **main Supabase Postgres cluster** (`host.docker.internal:65432`).
-   **Dedicated Schema:** Created a distinct `tensorzero_schema` owned by the `tensorzero` user to resolve permission conflicts with Supabase's `public` schema.
-   **Secure Credentials:** Removed all hardcoded passwords from `docker-compose.yml`. Configured dynamic URL construction using `.env` variables (`TENSORZERO_PG_USER`, `PASSWORD`).

### 3. Documentation
-   Added `docs/PMOVES_Services_Documentation_Complete.md`: A comprehensive reference for all services, ports, and integration points.

## Verification
-   **Endpoints:** `/api-keys` (Postgres dependent) is now accessible.
-   **Identity:** Confirmed `tensorzero-gateway` connects to Supabase via logs (`Postgres: enabled`).
-   **Routing:** Verified fallback logic in `tensorzero.toml`.

## Post-Merge Actions
- [ ] Verify Supabase Backup policies cover the new `tensorzero` database.
- [ ] Confirm `OPENAI_MODEL` env var is propogated to Agent Zero containers.
