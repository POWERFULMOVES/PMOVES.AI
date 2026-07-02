# Google OAuth Vertical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Google OAuth token-acquire flow work end-to-end and robustly, replacing the hand-rolled callback server with the canonical `google-auth-oauthlib` loopback flow (Desktop client), so YouTube ingestion is unblocked and the pattern generalizes to other providers.

**Architecture:** Rebuild the acquire step of `pmoves/tools/yt_oauth_flow.py` on `google-auth-oauthlib`'s `InstalledAppFlow.run_local_server(port=0)` — the audited library handles loopback binding, state, PKCE, and code exchange (deleting ~80 lines of bespoke OAuth). Accept generic `GOOGLE_OAUTH_*` creds with back-compat aliases; parameterize scopes + user_id (multi-tenant seam). Extend the preflight to the full env set; consolidate two setup docs into one walkthrough. Infra (table, PostgREST schema exposure) is already in place — verify-only.

**Tech Stack:** Python 3.11+, `google-auth-oauthlib` (new dep), `httpx`, `cryptography.Fernet`, Supabase PostgREST, GNU Make, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-06-29-google-oauth-vertical-design.md`

**Sequencing note:** The **fast path to ingest** is Task 0 (operator: Desktop client + creds) + Tasks 7–8. Tasks 1–6 are the durable rebuild + hardening that land in the same PR.

**Test command (all Python tasks):** from `pmoves/`: `python -m pytest tests/tools/test_google_oauth_flow.py -v`

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `pmoves/pyproject.toml` | Declare `google-auth-oauthlib` | Modify (`[project.optional-dependencies].dev`) |
| `pmoves/tools/yt_oauth_flow.py` | Google OAuth token-acquire CLI (auth/status/revoke) | Modify (rebuild acquire on library) |
| `pmoves/tests/tools/test_google_oauth_flow.py` | Unit tests for acquire helpers | Create |
| `pmoves/mk/yt-cookies.mk` | Make targets incl. preflight check | Modify |
| `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md` | Canonical operator walkthrough | Modify (rewrite) |
| `pmoves/docs/operations/YT_COOKIES_RUNBOOK.md` | Ops runbook | Modify (cross-link + redirect note) |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Claim register | Modify (CLAIM/RELEASE) |

---

## Task 0: Operator prerequisites (gated — runs in parallel, no code)

**Critical path to the first ingest. The operator (DARKXSIDE) performs it.**

- [ ] **Step 1: Create a Desktop OAuth client**

Google Cloud Console (same project as channel-monitor): **APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app** (e.g. `PMOVES.YT Desktop`). Confirm **YouTube Data API v3** enabled and consent-screen scope `https://www.googleapis.com/auth/youtube.readonly`. Desktop clients accept `http://127.0.0.1:<any-port>` loopback redirects with **no redirect-URI registration** — a Web client does not, so Desktop is required for the ephemeral-port flow.

- [ ] **Step 2: Funnel the credentials into `env.shared` (never chat)**

Via the secrets-funnel: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (Desktop client), `VAULT_ENC_KEY` (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), `SERVICE_ROLE_KEY` (Supabase), `SUPABASE_URL` (e.g. `http://supabase-kong:8000`).

- [ ] **Step 3: Confirm**

Run: `make -C pmoves yt-cookies-check`  → expected (after Task 5): all five report `✓`.

---

## Task 1: Add the `google-auth-oauthlib` dependency

**Files:**
- Modify: `pmoves/pyproject.toml` (`[project.optional-dependencies].dev`)

- [ ] **Step 1: Declare the dependency**

In `pmoves/pyproject.toml`, change:

```toml
[project.optional-dependencies]
dev = [
    "cryptography",
]
```
to:
```toml
[project.optional-dependencies]
dev = [
    "cryptography",
    "google-auth-oauthlib>=1.2.0",
]
```

- [ ] **Step 2: Install into the host env that runs the Make targets**

Run: `cd pmoves && uv pip install "google-auth-oauthlib>=1.2.0"`
Expected: installs `google-auth-oauthlib`, `google-auth`, `requests-oauthlib`.

- [ ] **Step 3: Verify import**

Run: `python -c "from google_auth_oauthlib.flow import InstalledAppFlow; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pmoves/pyproject.toml
git commit -m "build(yt-oauth): add google-auth-oauthlib dependency"
```

---

## Task 2: Rebuild the acquire flow on `InstalledAppFlow` (delete hand-rolled server)

**Files:**
- Modify: `pmoves/tools/yt_oauth_flow.py`
- Test: `pmoves/tests/tools/test_google_oauth_flow.py`

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/tools/test_google_oauth_flow.py`:

```python
"""Unit tests for the Google OAuth acquire helpers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pmoves.tools.yt_oauth_flow as oauth


class TestBuildFlow(unittest.TestCase):
    def test_build_flow_sets_client_and_scopes(self):
        flow = oauth._build_flow(
            "cid", "csec", "https://www.googleapis.com/auth/youtube.readonly"
        )
        self.assertEqual(flow.client_config["client_id"], "cid")
        self.assertEqual(flow.client_config["client_secret"], "csec")
        self.assertIn(
            "https://www.googleapis.com/auth/youtube.readonly",
            flow.oauth2session.scope,
        )

    def test_build_flow_splits_multiple_scopes(self):
        flow = oauth._build_flow("cid", "csec", "scope-a scope-b")
        self.assertIn("scope-a", flow.oauth2session.scope)
        self.assertIn("scope-b", flow.oauth2session.scope)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py::TestBuildFlow -v`
Expected: FAIL with `AttributeError: ... has no attribute '_build_flow'`

- [ ] **Step 3: Add the library import**

In `pmoves/tools/yt_oauth_flow.py`, after the `cryptography` import block (~line 46), add:

```python
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: google-auth-oauthlib not installed. Run: uv pip install google-auth-oauthlib", file=sys.stderr)
    InstalledAppFlow = None  # type: ignore[assignment,misc]
```

- [ ] **Step 4: Delete the hand-rolled flow code**

Remove these now-obsolete pieces from `pmoves/tools/yt_oauth_flow.py`:
- the `CALLBACK_PORT` and `CALLBACK_PATH` constants (~lines 59-61)
- the entire `_OAuthCallbackHandler` class (~lines 159-189)
- the `_build_auth_url` function (~lines 192-203)
- the `_exchange_code` function (~lines 206-235)

And remove the now-unused imports from the top of the file: `http.server`, `secrets`, `threading`, `urllib.parse`, `webbrowser`. Keep `GOOGLE_AUTH_URL`, `GOOGLE_TOKEN_URL`, `GOOGLE_REVOKE_URL` (used below).

- [ ] **Step 5: Add `_build_flow` and rewrite `cmd_auth`**

Add `_build_flow` (place it where `_build_auth_url` was):

```python
def _build_flow(client_id: str, client_secret: str, scope: str) -> "InstalledAppFlow":
    """Build an InstalledAppFlow from inline client config (Desktop client shape)."""
    if InstalledAppFlow is None:
        print("ERROR: google-auth-oauthlib not installed.", file=sys.stderr)
        sys.exit(1)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": GOOGLE_AUTH_URL,
            "token_uri": GOOGLE_TOKEN_URL,
            "redirect_uris": ["http://localhost"],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, scopes=scope.split())
```

Replace the entire `cmd_auth` body (~lines 306-368) with:

```python
def cmd_auth(user_id: str = DEFAULT_USER_ID, scope: str = OAUTH_SCOPES) -> None:
    """Run the loopback OAuth2 consent flow and store the refresh token."""
    client_id, client_secret = _client_creds()
    flow = _build_flow(client_id, client_secret, scope)

    print("Opening browser for Google OAuth2 consent (loopback, ephemeral port)...")
    # Scope logged as plain concat (breaks CodeQL taint path on OAuth f-strings).
    print("  Scopes: " + scope)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    refresh_token = creds.refresh_token
    access_token = creds.token
    if not refresh_token:
        print(
            "ERROR: No refresh_token returned. Revoke prior consent at "
            "https://myaccount.google.com/permissions and retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    expires_at = None
    if creds.expiry:
        expires_at = creds.expiry.replace(tzinfo=timezone.utc).isoformat()

    fernet = _get_fernet()
    refresh_enc = _encrypt(refresh_token, fernet)
    access_enc = _encrypt(access_token, fernet) if access_token else ""

    row = _upsert_tokens(refresh_enc, access_enc, expires_at, user_id=user_id)
    print(f"Stored tokens for user '{row.get('user_id', user_id)}'.")
    print(f"  Refresh token: {'encrypted' if fernet else 'plaintext'} (length={len(refresh_token)})")
    print(f"  Access token expires: {expires_at}")
    print()
    print("Next: make yt-cookies-refresh  (to harvest initial cookie set)")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py::TestBuildFlow -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pmoves/tools/yt_oauth_flow.py pmoves/tests/tools/test_google_oauth_flow.py
git commit -m "feat(yt-oauth): rebuild acquire on google-auth-oauthlib loopback flow (delete hand-rolled server)"
```

---

## Task 3: Generic client-cred env aliases (`_client_creds`)

**Files:**
- Modify: `pmoves/tools/yt_oauth_flow.py`
- Test: `pmoves/tests/tools/test_google_oauth_flow.py`

- [ ] **Step 1: Write the failing test**

Append to `pmoves/tests/tools/test_google_oauth_flow.py`:

```python
import os
from unittest import mock


class TestClientCreds(unittest.TestCase):
    def test_prefers_google_oauth_vars(self):
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "desktop-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "desktop-secret",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_ID": "legacy-id",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET": "legacy-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._client_creds(), ("desktop-id", "desktop-secret"))

    def test_falls_back_to_channel_monitor_vars(self):
        env = {
            "CHANNEL_MONITOR_GOOGLE_CLIENT_ID": "legacy-id",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET": "legacy-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._client_creds(), ("legacy-id", "legacy-secret"))

    def test_exits_when_neither_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                oauth._client_creds()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py::TestClientCreds -v`
Expected: FAIL with `AttributeError: ... has no attribute '_client_creds'`

- [ ] **Step 3: Add the helper**

In `pmoves/tools/yt_oauth_flow.py`, add after `_require_env` (~line 80):

```python
def _client_creds() -> "tuple[str, str]":
    """Return (client_id, client_secret), preferring GOOGLE_OAUTH_* with a
    back-compat fallback to CHANNEL_MONITOR_GOOGLE_* (Phase 9Q.2 reused those).
    Exits with an error if neither pair is configured.
    """
    client_id = _env("GOOGLE_OAUTH_CLIENT_ID") or _env("CHANNEL_MONITOR_GOOGLE_CLIENT_ID")
    client_secret = _env("GOOGLE_OAUTH_CLIENT_SECRET") or _env("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "ERROR: Google OAuth client not configured. Set GOOGLE_OAUTH_CLIENT_ID/"
            "SECRET (or CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET) in env.shared.",
            file=sys.stderr,
        )
        sys.exit(1)
    return client_id, client_secret
```

(`cmd_auth` from Task 2 already calls `_client_creds()`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py::TestClientCreds -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/yt_oauth_flow.py pmoves/tests/tools/test_google_oauth_flow.py
git commit -m "feat(yt-oauth): accept GOOGLE_OAUTH_* creds with channel-monitor fallback"
```

---

## Task 4: Parameterize scopes + user_id (multi-tenant seam)

**Files:**
- Modify: `pmoves/tools/yt_oauth_flow.py` (`cmd_status`/`cmd_revoke` signatures, `_parse_args`, `main`)
- Test: `pmoves/tests/tools/test_google_oauth_flow.py`

- [ ] **Step 1: Write the failing test**

Append to `pmoves/tests/tools/test_google_oauth_flow.py`:

```python
class TestArgParsing(unittest.TestCase):
    def test_defaults(self):
        ns = oauth._parse_args(["status"])
        self.assertEqual(ns.command, "status")
        self.assertEqual(ns.user_id, oauth.DEFAULT_USER_ID)
        self.assertEqual(ns.scopes, oauth.OAUTH_SCOPES)

    def test_overrides(self):
        ns = oauth._parse_args(["auth", "--user-id", "u2", "--scopes", "s1 s2"])
        self.assertEqual(ns.user_id, "u2")
        self.assertEqual(ns.scopes, "s1 s2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py::TestArgParsing -v`
Expected: FAIL with `AttributeError: ... has no attribute '_parse_args'`

- [ ] **Step 3: Thread user_id, add `_parse_args`, rewrite `main`**

Change `cmd_status` and `cmd_revoke` signatures to accept `user_id`:

```python
def cmd_status(user_id: str = DEFAULT_USER_ID) -> None:
```
…and inside it use `row = _get_status(user_id)`.

```python
def cmd_revoke(user_id: str = DEFAULT_USER_ID) -> None:
```
…and inside it use `row = _get_status(user_id)` and `if _delete_row(user_id):`.

Replace the existing `main()` (~lines 432-452) with:

```python
def _parse_args(argv: "Optional[list[str]]" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google OAuth2 token acquire — Phase 9Q.2 / OAuth vertical",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=["auth", "refresh", "status", "revoke"],
                        help="Subcommand to run")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID,
                        help="Token owner key (multi-tenant; default operator)")
    parser.add_argument("--scopes", default=OAUTH_SCOPES,
                        help="Space-delimited OAuth scopes")
    parser.add_argument("--account-label", default="",
                        help="Human label for the account (informational)")
    return parser.parse_args(argv)


def main() -> None:
    """CLI entry point."""
    args = _parse_args()
    if args.command == "auth":
        cmd_auth(user_id=args.user_id, scope=args.scopes)
    elif args.command == "status":
        cmd_status(user_id=args.user_id)
    elif args.command == "revoke":
        cmd_revoke(user_id=args.user_id)
    else:
        cmd_refresh()
```

- [ ] **Step 4: Run the full test file to verify all pass**

Run: `cd pmoves && python -m pytest tests/tools/test_google_oauth_flow.py -v`
Expected: PASS (TestBuildFlow, TestClientCreds, TestArgParsing)

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/yt_oauth_flow.py pmoves/tests/tools/test_google_oauth_flow.py
git commit -m "feat(yt-oauth): parameterize scopes + user_id (multi-tenant seam)"
```

---

## Task 5: Extend the preflight check to the full env set

**Files:**
- Modify: `pmoves/mk/yt-cookies.mk` (`yt-cookies-check`, lines 15-35)

> Makefile target — verified by running it, not pytest.

- [ ] **Step 1: Replace the `yt-cookies-check` body**

Replace lines 15-35 of `pmoves/mk/yt-cookies.mk` with:

```make
yt-cookies-check: ## Preflight: verify Google OAuth + Supabase env vars are set
	@echo "=== YT Cookies: preflight check ==="
	@hard=0; \
	cid=$$(bash scripts/with-env.sh printenv GOOGLE_OAUTH_CLIENT_ID 2>/dev/null || true); \
	[ -z "$$cid" ] && cid=$$(bash scripts/with-env.sh printenv CHANNEL_MONITOR_GOOGLE_CLIENT_ID 2>/dev/null || true); \
	csec=$$(bash scripts/with-env.sh printenv GOOGLE_OAUTH_CLIENT_SECRET 2>/dev/null || true); \
	[ -z "$$csec" ] && csec=$$(bash scripts/with-env.sh printenv CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET 2>/dev/null || true); \
	if [ -z "$$cid" ] || [ "$$cid" = "YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com" ]; then echo "✗ GOOGLE_OAUTH_CLIENT_ID (or CHANNEL_MONITOR_*): not configured"; hard=$$((hard+1)); else echo "✓ client id: set (length=$${#cid})"; fi; \
	if [ -z "$$csec" ] || [ "$$csec" = "GOCSPX-YOUR_CLIENT_SECRET_HERE" ]; then echo "✗ GOOGLE_OAUTH_CLIENT_SECRET (or CHANNEL_MONITOR_*): not configured"; hard=$$((hard+1)); else echo "✓ client secret: set (length=$${#csec})"; fi; \
	for var in SERVICE_ROLE_KEY SUPABASE_URL; do \
		val=$$(bash scripts/with-env.sh printenv $$var 2>/dev/null || true); \
		if [ -z "$$val" ]; then echo "✗ $$var: not configured (required to store the token)"; hard=$$((hard+1)); else echo "✓ $$var: set (length=$${#val})"; fi; \
	done; \
	venc=$$(bash scripts/with-env.sh printenv VAULT_ENC_KEY 2>/dev/null || true); \
	if [ -z "$$venc" ]; then echo "⚠ VAULT_ENC_KEY: not set — token would be stored UNENCRYPTED (set it before auth)"; else echo "✓ VAULT_ENC_KEY: set (length=$${#venc})"; fi; \
	if [ $$hard -gt 0 ]; then \
		echo ""; echo "ERROR: $$hard required var(s) missing. Set them in env.shared via the secrets-funnel."; \
		echo "See PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md for the walkthrough."; \
		exit 1; \
	fi; \
	echo ""; echo "✓ Preflight passed. Ready for: make yt-cookies-auth"
```

- [ ] **Step 2: Verify it lists all checks**

Run: `make -C pmoves yt-cookies-check` (creds still absent on this host)
Expected: lines for client id, client secret, `SERVICE_ROLE_KEY`, `SUPABASE_URL`, `VAULT_ENC_KEY`, then non-zero exit with `ERROR: N required var(s) missing`.

- [ ] **Step 3: Commit**

```bash
git add pmoves/mk/yt-cookies.mk
git commit -m "feat(yt-oauth): preflight checks full acquire env set (creds + Supabase + VAULT_ENC_KEY)"
```

---

## Task 6: Consolidate the operator walkthrough doc

**Files:**
- Modify (rewrite): `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md`
- Modify: `pmoves/docs/operations/YT_COOKIES_RUNBOOK.md`

> Documentation task — verified by a consistency read.

- [ ] **Step 1: Rewrite the desktop setup doc as the single canonical walkthrough**

- `Status: Canonical • Last updated: 2026-06-29`.
- Keep §1–§3 (Desktop client creation). In §4, **delete the throwaway inline script** and replace with: "Run `make -C pmoves yt-cookies-bootstrap` — it runs `tools/yt_oauth_flow.py auth`, which uses `google-auth-oauthlib`'s loopback flow on an ephemeral `127.0.0.1` port (nothing to register), then triggers the first cookie harvest."
- Replace §5 env block with the funnel-driven set: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `VAULT_ENC_KEY`, `SERVICE_ROLE_KEY`, `SUPABASE_URL` (note `CHANNEL_MONITOR_GOOGLE_*` accepted as fallback). Secrets go through the funnel, never hand-edited in chat.
- Replace §6 (channel-monitor POST) with: "the token is stored by the CLI directly in `pmoves_core.yt_oauth_cookies` (Fernet-encrypted); no manual curl needed."
- In §8, replace the `redirect_uri_mismatch` entry with: "Desktop clients accept any `127.0.0.1` loopback port — `redirect_uri_mismatch` means the client is a **Web** type; create a **Desktop** client."

- [ ] **Step 2: Cross-link from the runbook**

In `pmoves/docs/operations/YT_COOKIES_RUNBOOK.md`, add near the top: "**Client setup:** see `PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md` (canonical). The OAuth callback uses an **ephemeral loopback port** via `google-auth-oauthlib` — no fixed `:8199` redirect to register."

- [ ] **Step 3: Consistency read**

Confirm no remaining reference to `:8199`, the throwaway script, or the channel-monitor POST path in either doc.

- [ ] **Step 4: Commit**

```bash
git add "pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md" pmoves/docs/operations/YT_COOKIES_RUNBOOK.md
git commit -m "docs(yt-oauth): consolidate to one canonical loopback walkthrough"
```

---

## Task 7: Verify PostgREST serves the token table (no code)

> Infra already in place (`pmoves_core` exposed, table exists). Confirm the running instance serves it.

- [ ] **Step 1: After creds land, run a read via the CLI**

Run: `make -C pmoves yt-cookies-status`
Expected: "No OAuth credentials stored." (clean 200, empty) — **not** a 404.

- [ ] **Step 2: If 404 — reload the schema cache (no restart)**

Run: `docker exec pmoves-supabase-db-1 psql -U postgres -d postgres -c "NOTIFY pgrst, 'reload schema';"`
Re-run Step 1. Expected: clean 200.

---

## Task 8: End-to-end — bootstrap + ingest the design video (operator-gated)

- [ ] **Step 1: One-click bootstrap**

Run: `make -C pmoves yt-cookies-bootstrap` → operator clicks **Allow** in the loopback consent tab.
Expected: "Stored tokens for user 'darkxside'." then the refresher harvest ping.

- [ ] **Step 2: Confirm authenticated state**

Run: `make -C pmoves yt-cookies-status`
Expected: Refresh token `set`; after the refresher runs, `pmoves/config/cookies/darkxside.youtube.cookies.txt` contains auth cookies (`__Secure-1PSID`/`LOGIN_INFO`), not just anonymous ones.

- [ ] **Step 3: Ingest the design video**

```bash
curl -fsS --max-time 180 -X POST http://localhost:8077/yt/ingest \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=N1Cl5cYmegE","namespace":"pmoves.youtube.ai","bucket":"assets"}' | head -c 800
```
Expected: 2xx with a video id / object path (no "Sign in to confirm you're not a bot"). Then pull `/yt/transcript` + frame screenshots for the design-language work.

---

## Task 9: CLAIM the lane + flag z890 + open PR

- [ ] **Step 1: Add a CLAIM entry**

Append to the Active Claim Register in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` a `CLAIM 5090-CLAUDE` line: branch `feat/google-oauth-vertical`, scope "Google OAuth vertical — rebuild acquire on google-auth-oauthlib loopback + preflight + walkthrough; YT ingest unblock", risks low (additive code + docs; infra verify-only), z890 pair-review requested (shared OAuth/CHIT lane).

- [ ] **Step 2: Push + open PR, tag z890**

```bash
git push -u origin feat/google-oauth-vertical
gh pr create --base main --title "feat(yt-oauth): Google OAuth vertical — google-auth-oauthlib loopback acquire" \
  --body "Implements docs/superpowers/specs/2026-06-29-google-oauth-vertical-design.md. Rebuilds the acquire flow on google-auth-oauthlib (deletes hand-rolled :8199 server / Desktop client / ephemeral loopback), GOOGLE_OAUTH_* aliases, scopes+user_id params, full-env preflight, one canonical walkthrough. Infra verified already in place. @z890 pair-review requested (shared OAuth/CHIT lane)."
```

- [ ] **Step 3: Release the lane** after merge — `RELEASE 5090-CLAUDE` with the merged PR number + ingest evidence.

---

## Self-Review

**Spec coverage:**
- §3.1 library loopback acquire core → Tasks 1 (dep) + 2 (InstalledAppFlow rebuild) + 3 (cred aliases) + 4 (scopes/user_id). ✓
- §3.2 Supabase Fernet store, multi-tenant key → existing `_upsert_tokens(user_id=...)` + Task 4 `--user-id`. ✓
- §3.3 PostgREST verify-only → Task 7. ✓
- §3.4 consumers route through it → cookie refresher already reads the table; no change. ✓
- §3.5 guided walkthrough → Task 6. ✓
- §6 testing → Tasks 2-4 unit tests + Task 5 preflight verify + Task 8 integration. ✓
- §7 coordination (CLAIM, z890) → Task 9. ✓
- §8 operator critical path → Task 0. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code or exact deletion targets. ✓

**Type/name consistency:** `_build_flow(client_id, client_secret, scope)` (Task 2), `_client_creds()` (Task 3), `_parse_args` + `cmd_auth(user_id, scope)`/`cmd_status(user_id)`/`cmd_revoke(user_id)` (Task 4). `InstalledAppFlow`, `DEFAULT_USER_ID`, `OAUTH_SCOPES`, `GOOGLE_AUTH_URL`/`GOOGLE_TOKEN_URL` referenced consistently. Deletions in Task 2 (`_OAuthCallbackHandler`, `_build_auth_url`, `_exchange_code`, `CALLBACK_PORT/PATH`, unused imports) leave no dangling references — `cmd_auth` no longer calls them. ✓
