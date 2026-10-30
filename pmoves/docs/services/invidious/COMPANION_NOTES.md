# Invidious Companion Observability

- Enabled PO token generation by exporting `YT_ENABLE_PO_TOKEN=true` in `.env.local`.
- Added optional env knobs for YouTube API interaction:
  - `INVIDIOUS_COMPANION_YOUTUBE_API_KEY`
  - `INVIDIOUS_COMPANION_CA_URL`
  - `INVIDIOUS_COMPANION_LOG_LEVEL`
- Updated `docker-compose.yml` to pass `YOUTUBE_API_KEY`, `YOUTUBEI_CLIENT`, and `YOUTUBEI_API_BASE` through to the container.
- Restarted the companion via `docker compose -p pmoves -f pmoves/docker-compose.yml up -d invidious-companion`.
- Logs show PO token generation succeeding and the service now remains up (health state transitions from `starting` to `healthy`).

Next steps: supply a valid API key if required for production workloads, otherwise the fallback client will continue to work for ad-hoc token generation.

### 2025-10-27

- Removed the Docker health check from `invidious-companion`. The upstream image no longer ships `wget`/`curl`, causing the Compose health probe to fail even while `http://127.0.0.1:8282/healthz` responds with 200. Validate the service with targeted HTTP checks (`curl http://127.0.0.1:8282/healthz`) or by tailing the PO token job logs.

### 2026-10-30 — keys are required, funnel-minted, and checked by `invidious-smoke`

`INVIDIOUS_HMAC_KEY` and `INVIDIOUS_COMPANION_KEY` no longer have compose defaults; the old literal defaults were public and are treated as compromised. Full audit, vendor citations and rotation road: `plans/CREDENTIAL_ROTATION_RUNBOOK_2026-10-11.md`, addendum 2026-10-30.

| Key | Vendor requirement (iv-org, read 2026-10-30) | What we mint |
|---|---|---|
| `INVIDIOUS_HMAC_KEY` -> `hmac_key` | mandatory random string; Invidious exits if empty | `random_hex` 64 |
| `INVIDIOUS_COMPANION_KEY` -> `invidious_companion_key` **and** companion `SERVER_SECRET_KEY` | exactly 16 chars (Invidious exits otherwise); companion requires `[a-zA-Z0-9]{16}`; must differ from the HMAC key | `random_hex` 16 |

Operate:

```bash
make -C pmoves invidious-keys-check    # report-only: are both keys usable on this node?
make -C pmoves invidious-keys-preflight  # mint/rotate in env.shared (also runs automatically before up/down/ps/... goals)
make -C pmoves secrets-funnel          # seal the values into the CHIT bundle
make -C pmoves secrets-ensure-check    # both must print "provisioned"
make -C pmoves up-invidious            # recreate invidious + invidious-db + invidious-companion
make -C pmoves invidious-smoke         # read-only: stats 200, companion healthz, companion accepts the funnel key
```

A new HMAC key invalidates what Invidious signs with it (CSRF tokens, cookies, pubsub verification): signed-in users re-authenticate.

Settings that differ from the current vendor compose example (reported, not changed in PR #3431):

- `private_url`: vendor now uses `http://companion:8282/companion` because the companion mounts its API under `SERVER_BASE_PATH` (default `/companion`). We use `http://invidious-companion:8282`. Whether that is still right depends on the pinned companion image; `invidious-smoke` prints which guarded path the running companion answers on, so read its output after a recreate.
- `INVIDIOUS_COMPANION_KEY` in the `invidious` container's environment is not read by Invidious: its env override is `INVIDIOUS_<FIELD>`, i.e. `INVIDIOUS_INVIDIOUS_COMPANION_KEY`. The key reaches Invidious through `INVIDIOUS_CONFIG`. `INVIDIOUS_HMAC_KEY` IS read (it overrides `hmac_key`).
- The vendor companion runs with `cap_drop: [ALL]`, `read_only: true` and `no-new-privileges`; ours does not.
- `INVIDIOUS_PG_PASSWORD` still defaults to the vendor's example `kemal`; the database is not published on a host port.
