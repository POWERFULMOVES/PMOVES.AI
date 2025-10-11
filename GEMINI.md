# Gemini Smoke Test Plan for PMOVES.AI

This document outlines the plan for running the smoke tests for the PMOVES.AI project. The plan is based on the information provided in the `pmoves/docs/SMOKETESTS.md` and `pmoves/README.md` files.

## 1. Environment Setup

1.  Create the `.env` file from the `.env.example` file.
2.  Append the contents of `env.presign.additions` and `env.render_webhook.additions` to the `.env` file.
3.  Optionally, for rerank configuration, append the contents of `env.hirag.reranker.additions` and `env.hirag.reranker.providers.additions` to the `.env` file.
4.  Set the `PRESIGN_SHARED_SECRET` and `RENDER_WEBHOOK_SHARED_SECRET` in the `.env` file.
5.  Ensure the MinIO buckets (`assets`, `outputs`) exist. They can be created via the MinIO Console at `http://localhost:9001`.

## 2. Preflight Check

Run the preflight check to ensure the environment is set up correctly:

```bash
make flight-check
```

or for Windows:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1
```

## 3. Start Core Stack

Start the core services:

```bash
make up
```

Wait for ~15–30s for services to become ready.

## 4. Health Checks

Perform health checks on the running services:

```bash
curl http://localhost:8088/healthz
curl http://localhost:8085/healthz
curl http://localhost:3000
curl http://localhost:8087/hirag/admin/stats
curl http://localhost:8092/healthz
```

## 5. Seed Data

Seed the database with test data:

```bash
make seed-data
```

## 6. Run Smoke Tests

Run the smoke tests:

-   **macOS/Linux:**
    ```bash
    make smoke
    ```
-   **Windows:**
    ```powershell
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1
    ```

## 7. Geometry Bus (CHIT) - End-to-end

Run the end-to-end tests for the Geometry Bus.

1.  Create `cgp.json` file.
2.  POST the event to the geometry event endpoint.
3.  Perform a jump test.
4.  Perform optional decoder tests.
5.  Get the calibration report.

## 8. Live Geometry UI + WebRTC

Test the Live Geometry UI and WebRTC functionality by opening `http://localhost:8087/geometry/` in a browser and following the instructions in `SMOKETESTS.md`.

## 9. Mesh Handshake (NATS)

Test the Mesh Handshake:

```bash
make mesh-up
```

Then follow the instructions in `SMOKETESTS.md`.

## 10. Import Capsule → DB (Offline Ingest)

Test the offline ingest functionality using the `datasets/example_capsule.json` file and the UI or `make mesh-handshake`.

## 11. YouTube → Index + Shapes

Test the YouTube ingestion and processing pipeline:

```bash
make yt-emit-smoke URL=https://www.youtube.com/watch?v=2Vv-BfVoq4g
```

## 12. Optional Smoke Tests

Run the optional smoke tests:

```bash
make smoke-presign-put
make smoke-rerank
make smoke-langextract
```

## 13. Cleanup

Stop the services and clean up the environment:

```bash
make down
```

For a destructive cleanup (removes volumes):

```bash
make clean
```
