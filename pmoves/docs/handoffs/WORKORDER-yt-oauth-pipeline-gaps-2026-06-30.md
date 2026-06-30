# WORKORDER — YT host-OAuth pipeline gaps (secrets + Supabase reachability)

**Author:** 5090-CLAUDE (Opus 4.8) · 2026-06-30
**Status:** OPEN — queued for **z890** (secrets/Supabase infra lane)
**Trigger:** Validating the Google OAuth vertical (PR #1908) end-to-end revealed three pipeline gaps. Gap #1 is fixed in PR #1908; #2 and #3 are z890 infra. The host-side `yt-cookies-bootstrap` ingest stays blocked until #3 is resolved.
**Verified state:** all OAuth creds are present and the preflight now passes (`client id` 72, `client secret` 35, `service role key` 164, `VAULT_ENC_KEY` 32). The blockers below are infra, not credentials.

---

## Gap #1 — `with-env.sh` exec-form (FIXED in PR #1908, but root issue remains)

`scripts/with-env.sh` is a **source-only** loader (no `exec "$@"`). Calling it as `bash scripts/with-env.sh <cmd>` silently does **not** run `<cmd>`. The yt-cookies targets used this form, so the preflight always reported "not configured" and `auth`/`bootstrap` never launched.

- **Fixed (PR #1908):** all 6 yt-cookies invocations converted to the canonical `bash -lc '. ./scripts/with-env.sh; <cmd>'` source-form.
- **Still open (z890 call):** a repo-wide survey found **17 `bash with-env.sh` exec-form callers** vs 27 correct `. with-env.sh` source-form. The other ~16 exec-form callers are silently broken too. Options: (a) add `exec "$@"` to the end of `with-env.sh` (no-op when sourced with no args; fixes all exec-form callers at once — verify no source-form caller passes positional args), or (b) convert the 16 callers to source-form. Recommend (a) after an audit.

## Gap #2 — `SERVICE_ROLE_KEY` dev/prod tangle (DARKXSIDE-flagged)

The resolved `SERVICE_ROLE_KEY` is `iss: supabase-demo` (164 chars) — **correct for a local self-hosted Supabase** (the local stack signs with the demo JWT secret). But:
- It's **defined across 4 files** (`env.shared` ×2, `env.tier-supabase`, `env.tier-api`, `env.tier-ui`).
- `env.tier-supabase` carries a **literal 64-char** `SERVICE_ROLE_KEY` that differs from the resolved 164-char demo key (not a forward-ref).
- The GitHub secret + funnel bundle also carry a **211-char** `SUPABASE_SERVICE_ROLE_KEY` (possibly a different/cloud project key).

**Risk:** a future change to load-order or a service reading the 64/211 variant instead of the resolved 164 demo key → silent dev/prod cross-wire. **Action:** trace all 4 definitions, decide the single source of truth per environment (local-demo vs any hosted project), collapse the duplicates, and document which key the local stack's JWT secret actually validates. Confirm via a live PostgREST round-trip (200 vs 401).

## Gap #3 — Supabase not reachable from the host (blocks the host-OAuth store)

No Supabase service publishes a host port (`kong` shows `8000-8001/tcp` with **no** `->host` mapping). But the OAuth `auth` CLI **must** run on the host (it opens a browser via `run_local_server` for Google consent) and then stores the refresh token to Supabase PostgREST. From the host, `http://supabase-kong:8000` is unresolvable and `localhost:8000` refuses (nothing published) → the token store fails even though consent succeeds.

**Options (design decision):**
1. **Publish Kong `8000` to the host** (compose port mapping) + set `SUPABASE_URL` to a host-reachable value for the CLI. Simplest; widens host exposure (gate to loopback `127.0.0.1:8000`).
2. **Store-via-container:** the host CLI captures the token, then a short `docker exec` into an on-network container performs the PostgREST upsert. No new host exposure; more moving parts.
3. **Run the whole `auth` in a container** with the consent port forwarded to the host browser. Most isolated; trickiest UX.

Recommend option 1 with a **loopback-only** Kong publish for the dev workflow, documented in the YT cookies runbook.

---

## Acceptance
- [ ] `with-env.sh` exec-form root issue resolved (the other ~16 callers) — decision recorded.
- [ ] `SERVICE_ROLE_KEY` collapsed to one source-of-truth per environment; live 200 round-trip evidence; no 64/211 vs 164 ambiguity.
- [ ] Host can reach Supabase for the OAuth store; `make yt-cookies-bootstrap` completes the consent→store→harvest chain end-to-end.
- [ ] Runbook updated; then the design-video ingest (`N1Cl5cYmegE`) can run via the canonical path.

## Coordination
z890 owns secrets/Supabase infra. PR #1908 (5090) ships the code side (loopback acquire + `GOOGLE_CLIENT_ID` reuse + `SUPABASE_SERVICE_ROLE_KEY` fallback + the gap-#1 fix). These three gaps are the infra that makes the host-OAuth ingest actually run.
