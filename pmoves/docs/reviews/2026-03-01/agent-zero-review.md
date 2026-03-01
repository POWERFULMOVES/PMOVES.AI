# Agent-Zero Code Review — 2026-03-01

## Executive Summary

Phase H successfully resolved all three previously-identified P1 issues: all Dockerfiles now carry `USER a0user`, NATS URLs universally include authenticated credentials (`nats://nats:pmoves@nats:4222`), and the `normalize_settings()`/`create_auth_token()` interaction is working as designed. The remaining security surface is dominated by two architectural choices that are inherent to the agent's purpose (running processes inside a container as root via supervisord, and SSH configured to permit root login) — these are P2 findings rather than regressions. One notable new P2 finding is a path-traversal risk in the `ImageGet` API where the directory-containment check was commented out.

---

## Critical (P1)

No P1 findings. All previously-flagged P1 issues are verified resolved.

---

## Important (P2)

### P2-1: `image_get.py` — Directory Containment Check Disabled (Path Traversal Risk)

**Confidence: 88**

**File:** `python/api/image_get.py`, lines 27-33

The path-containment guard was commented out with the rationale "no real need to check, we have the extension filter in place":

```python
# no real need to check, we have the extension filter in place
# check if path is within base directory
# if runtime.is_development():
#     in_base = files.is_in_base_dir(files.fix_dev_path(path))
# else:
#     in_base = files.is_in_base_dir(path)
# if not in_base and not files.is_in_dir(path, "/root"):
#     raise ValueError("Path is outside of allowed directory")
```

The extension filter only checks file extension. An attacker who can control the `path` parameter can craft paths like `/etc/passwd.png`. The `send_file(path)` call passes the raw `path` directly to Flask. All other file-manipulation handlers correctly use `Path.resolve()` and `startswith()` checks.

**Fix:** Re-enable the containment check or route through `FileBrowser.get_full_path()`.

### P2-2: supervisord Runs `run_ui` and `run_tunnel_api` as `root`

**Confidence: 85**

**File:** `docker/run/fs/etc/supervisor/conf.d/supervisord.conf`, lines 3, 64, 78

Although Dockerfiles set `USER a0user`, supervisord programs `run_ui` and `run_tunnel_api` explicitly run as root:

```ini
[program:run_ui]
user=root

[program:run_tunnel_api]
user=root
```

This negates the non-root `USER a0user` directive for the agent's actual runtime.

**Fix:** Change to `user=a0user`. Only `sshd` needs root to bind port 22.

### P2-3: SSH Configured to Permit Root Login

**Confidence: 85**

**Files:**
- `docker/base/fs/ins/configure_ssh.sh`, line 6
- `docker/run/fs/ins/setup_ssh.sh`, line 7

Both scripts set `PermitRootLogin yes`. The `set_root_password()` function in `settings.py` allows setting a root password at runtime via the UI. Combined with the exposed SSH port (22, mapped to 55022 externally), this is exploitable if an operator sets a root password.

**Fix:** Change to `PermitRootLogin prohibit-password` and update `code_exec_ssh_user` default to `a0user`.

### P2-4: `FileBrowser._is_allowed_file()` Upload Extension Validation Disabled

**Confidence: 82**

**File:** `python/helpers/file_browser.py`, lines 185-195

The method unconditionally returns `True` — any file type can be uploaded. Combined with the agent's code execution capability, this means security depends entirely on authentication being correctly configured.

### P2-5: `mcp_server_token` Token Entropy is Only 16 Characters (96 bits)

**Confidence: 80**

**File:** `python/helpers/settings.py`, lines 803-811

Token is SHA-256 of `runtime_id:username:password` truncated to 16 base64url characters. If auth is unconfigured (empty username/password), the token is purely a function of the predictable `runtime_id`.

---

## Suggestions

- **supervisord.conf socket world-writable** (`chmod=0777`) — restrict to `0700`
- **`docker-compose.pmoves.yml` uses deprecated `version: "3.8"`** — remove
- **`pmoves_announcer` uses deprecated `NATS.connect()` classmethod pattern** — should be `nc = NATS(); await nc.connect()`
- **Error messages in API responses leak internal details** — replace with generic messages

---

## What's Good

- **NATS auth universally applied** — All 5 locations use `nats://nats:pmoves@nats:4222`
- **Dockerfile non-root USER in all 3 images** — `docker/base/Dockerfile:44`, `docker/run/Dockerfile:40`, `DockerfileLocal:40`
- **`normalize_settings()`/`create_auth_token()` interaction clean** — No duplicate generation bug
- **MCP token-in-path scheme sound** — `DynamicMcpProxy.__call__()` gates access correctly
- **CSRF protection active** — Origin validation via `validate_ws_origin()`
- **Secrets masking thorough** — API keys, passwords masked in output, excluded from settings file
- **`FileBrowser` path traversal defenses consistent** — All handlers except `ImageGet` use `Path.resolve()` + `startswith()` checks
- **WebSocket origin validation rigorous** — Forwarded headers, port normalization, specific mismatch codes

---

## Phase C/H Fix Verification

| Check | Status | Evidence |
|---|---|---|
| Dockerfile 1 (`docker/base/Dockerfile`) non-root USER | PASS | Line 44: `USER a0user` |
| Dockerfile 2 (`docker/run/Dockerfile`) non-root USER | PASS | Line 40: `USER a0user` |
| Dockerfile 3 (`DockerfileLocal`) non-root USER | PASS | Line 40: `USER a0user` |
| NATS auth credentials in all URL references | PASS | 5 locations confirmed |
| `normalize_settings()` overwrite is intentional | PASS | No duplicate `create_auth_token()` |
| MCP endpoints have auth validation | PASS | Token-in-path in `DynamicMcpProxy` |
