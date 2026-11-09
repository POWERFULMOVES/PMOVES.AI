# Agent Zero tunnel overlay lands on a path nothing imports (2026-08-23)

**Status:** brief for a one-line Dockerfile destination fix
**Domain:** `dockerfile` (Known Road: `KNOWN_ROAD=dockerfile:handoff:a0-tunnel-overlay-path-2026-08-23.md`)
**Files:** `pmoves/services/agent-zero/Dockerfile`, `pmoves/services/agent-zero/Dockerfile.multiarch`, `pmoves/services/agent-zero/overrides/tunnel_manager.py`

## Symptom

`/api/tunnel_proxy` raises on every POST. From the live container log:

```
ERROR in app: Exception on /api/tunnel_proxy [POST]
ImportError: cannot import name 'NotifyData' from 'flaredantic'
  (/opt/venv-a0/lib/python3.12/site-packages/flaredantic/__init__.py)
ImportError: cannot import name 'TunnelManager' from 'helpers.tunnel_manager'
  (/a0/helpers/tunnel_manager.py)
```

The second error cascades from the first: the module fails to import its
dependency, so its own `TunnelManager` symbol never binds.

## Root cause

Installed `flaredantic==0.1.4` (pinned in `requirements.lock:1063`) exports:

```
CloudflaredError DownloadError FlareConfig FlareTunnel SSHError
ServeoConfig ServeoError ServeoTunnel TunnelConfig TunnelError base core
```

It does NOT export `NotifyData`, `NotifyEvent`, `notifier`, `MicrosoftConfig`
or `MicrosoftTunnel`. Upstream `/a0/helpers/tunnel_manager.py` imports three of
those unguarded on line 5.

PMOVES already wrote the fix. `services/agent-zero/overrides/tunnel_manager.py`
guards every flaredantic import in `try/except` and supplies its own
`NotifyEvent` / `NotifyData` dataclasses plus a `_NoopNotifier` fallback. It is
correct and would degrade gracefully exactly as its Dockerfile comment intends.

It never loads. The COPY destination is wrong:

```dockerfile
COPY ... overrides/tunnel_manager.py /git/agent-zero/python/helpers/tunnel_manager.py
```

Upstream moved these modules up a level. `helpers.tunnel_manager` resolves to
`/a0/helpers/tunnel_manager.py`; the overlay sits at
`/a0/python/helpers/tunnel_manager.py`, which nothing imports. Verified in the
running container: the `python/helpers/` copy is the PMOVES override, the
`helpers/` copy is unmodified upstream.

**Why it was silent:** `COPY` to a non-existent path always succeeds — Docker
creates the directory. Nothing asserts that a COPY destination is on the import
path, so a typo produces a file that exists, is correct, and is never read.

## Fix

1. `Dockerfile:138` and `Dockerfile.multiarch:113` — destination
   `/git/agent-zero/python/helpers/tunnel_manager.py` ->
   `/git/agent-zero/helpers/tunnel_manager.py`.
   Verified `/git/agent-zero/helpers` exists in the image.

2. `overrides/tunnel_manager.py:9` — `from python.helpers.print_style import
   PrintStyle` -> `from helpers.print_style import PrintStyle`, to match the new
   location. `/a0/python/__init__.py` does not exist, and upstream's file in
   `helpers/` uses `from helpers.*` six times. This is the only `python.`-prefixed
   import in the 180-line override.

## Verification

Requires an image rebuild (the A0 image is large; see the CPU-torch discussion).
After rebuild:

```bash
docker exec pmoves-agent-zero-1 sh -c 'sed -n "1,12p" /a0/helpers/tunnel_manager.py'
# expect the guarded override (from __future__ import annotations / try: ...),
# NOT upstream's unguarded `from flaredantic import NotifyData, NotifyEvent, notifier`

docker logs pmoves-agent-zero-1 --since 5m 2>&1 | grep -c tunnel_proxy
# expect 0 new ImportError traces
```

## Scope note

This explains the `/api/tunnel_proxy` failure only. Two other reported symptoms
-- the Plugins list showing no plugins, and an error when connecting an account
-- are NOT explained by it. `_oauth` and `_model_config` load from valid
built-ins under `/a0/plugins/` (the same-named directories under
`/a0/usr/plugins/` are config/state, not plugin overrides, and correctly carry
no `plugin.yaml`). Container egress to github.com and api.github.com returns
200. Those two need their own reproduction.

Relevant for that follow-up: `ALLOWED_ORIGINS` is unset, so A0 permits only
`*://localhost,*://localhost:*` while login is disabled. The UI is bound to
`127.0.0.1:8081`. Any access via a mesh hostname or reverse proxy fails CSRF on
every POST, which would present as an empty plugin list, non-functional toggles,
and account-connect errors simultaneously.
