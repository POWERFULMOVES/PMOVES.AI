# Credential Exposure Audit & Rotation Runbook — 2026-10-11

Scope: the "12:33 dump" = chat export `GORMW3Kt` (142 messages + 9 aux files, redaction-only scan, 13 token-pattern classes), cross-checked against `research/transcripts`, this chat (`sljcxXsM`), the working tree, and public `git HEAD` by exact-value match. **No secret value was ever printed in this audit** — masked prefixes only.

## Verdict summary

| # | Material | Found in | Classification | Action | Owner |
|---|---|---|---|---|---|
| 1 | HF token `hf_fp…37ch` | chat msgs (2 chats), NOT in git | **REAL-format key** | **ROTATE NOW** | Operator |
| 2 | Supabase JWT `eyJhbGci…188ch` — HS256, `iss=supabase-local`, `role=service_role`, exp 2036 | chat msg 49 only | dev-scoped real JWT | rotate at leisure + scrub copy | Operator |
| 3 | `OPENAI_API_KEY`/`TENSORZERO_API_KEY` inline fallbacks (18ch `-tens…` twins) | working-tree compose files, NOT in HEAD; quoted in chat | dev placeholders, uncommitted drift | hardening lane (remove secret defaults) | This agent (CLAIM 10:20Z) |
| 4 | `MCP_SERVER_TOKEN` dev- placeholder (19ch) | **public HEAD** (compose defaults + comment L3530 + claim register doc) | documented placeholder; **active env.shared value differs** — no live-token leak | hardening lane (genericize) | This agent |
| 5 | Flask `SECRET_KEY` 22ch default `pmove…` | **public HEAD** compose fallback | phantom default (session-signing) | hardening: `${SECRET_KEY:?required}` | This agent |
| 6 | `INVIDIOUS_COMPANION_KEY` (`<16 hex>`) + `INVIDIOUS_HMAC_KEY` (`<64 hex>`) | **public HEAD** compose fallbacks (and git history) | **generated-looking -> treated as COMPROMISED** (2026-10-30) | compose `${VAR:?}` + funnel mint + published-value denylist; see addendum 2026-10-30 | Operator (recreate) |
| 7 | 12:33 window msgs 88–101 | scanned | **clean** (wrangler missing-token error, HTTP-200 checks, Tokenism simulator HTML) | none | — |

## Rotation steps

1. **HF token (operator, ~2 min):** hf.co → Settings → Access Tokens → revoke the token with prefix `hf_fp…` → issue a fresh fine-grained token → deliver **only** via `make -C pmoves secrets-funnel` (never hand-copy into env files or chat).
2. **Supabase-local JWT (operator, dev):** if the `supabase-local` instance is still live, rotate its JWT secret and reissue service_role; otherwise mark the token dead. Never paste it into exports again.
3. **Invidious keys:** RESOLVED 2026-10-30 -- whether placeholder or generated no longer matters: both values are in public git history, so they are compromised either way. Rotation is automatic on the next funnel run; see the 2026-10-30 addendum at the end.
4. **Compose hardening (this agent, CLAIM `fix/compose-no-secret-defaults`, PR gated on your go):** secret-class vars get fail-closed `${VAR:?required}` or empty defaults; placeholder strings genericized in comments/docs so future greps can't confuse them with credentials.

## Post-rotation hygiene

- Scrub the rotated values from `GORMW3Kt` msgs 13/23/24/49 (this agent, one command, on your go — values are dead after rotation anyway).
- Open gap (honest): other chat folders in `/a0/usr/chats/*/` were **not** pattern-swept — only `GORMW3Kt`, `sljcxXsM`, and `research/transcripts` were. Offer: full-corpus sweep as a follow-up lane.
- Consider a pre-export secret-scan hook on chat exports (lane proposal, not filed).

## Verified vs assumed

**Verified:** scan coverage for the three locations above; exact-match cross-exposure counts (chats / workdir / HEAD) per value; JWT public claims only (signature not validated, payload not trusted); HEAD-membership per value; repo `POWERFULMOVES/PMOVES.AI` is **PUBLIC** (checked live).

**Assumed / unverified:** hf_ token still active (needs HF dashboard); Invidious keys real-vs-placeholder (needs your knowledge of the fork's defaults); no pattern sweep of remaining chat folders; JWT signature validity irrelevant (dev issuer).

---

## Full-corpus sweep — 2026-10-11 (operator-approved)

Supersedes the open-gap note above. Scope: **all 58 chat folders** (`1,314` message files), same pattern classes, batched exact-match against public HEAD. Raw matcher files were destroyed post-run (they aggregate raw values by design); this masked section is the system of record.

**Totals:** 193 unique matched values → **18 real-format credentials** (one `github_pat` hit was a filename artifact: `inject_github_pat_from_gh_cli.py`) + 25 values matching public HEAD (mostly documented dev defaults and env-read code lines).

### Rotate list (operator-side; funnel-only redelivery)

| Service | Count | Hot chats |
|---|---|---|
| GitHub tokens (`ghp_…` 40ch) | 6 | dl9okoIl ×3, Ygd5rag2, Nspx4kBU, etOeaPDG |
| GitHub PATs (93ch) | 2 | dl9okoIl, Ygd5rag2 |
| Google API keys (`AIza…`) | 4 | dl9okoIl ×3, Ygd5rag2 |
| Anthropic (`sk-ant-…`) | 2 | dl9okoIl, Nspx4kBU |
| OpenAI (`sk-proj-…`) | 1 | dl9okoIl |
| HuggingFace (`hf_…`) | 1 | GORMW3Kt, dl9okoIl |
| Slack bot (`xoxb-…`) | 1 | Ygd5rag2 |
| Tailscale authkey (`tskey-auth-…`) | 1 | Nspx4kBU, dl9okoIl |

**Hottest transcript: `dl9okoIl` — 13 of 18 real values.** Start there.

### Private key material

- `Ygd5rag2/messages/3.txt`: **8 COMPLETE RSA private key blocks** (BEGIN/END pairs verified). Origin UNKNOWN — operator must identify (deploy keys? host keys? fixtures?) and rotate.
- `Nspx4kBU/3.txt`, `dl9okoIl/146.txt`: BEGIN headers only — excerpts, no complete blocks.
- Public HEAD: **clean** — zero private-key blocks in tracked files.

### New public-HEAD finding: CHIT_PASSPHRASE phantom default

`${CHIT_PASSPHRASE:-<default>}` committed in **4 public compose files** (`docker-compose.yml`, `docker-compose.apps.yml`, `docker-compose.darkxside-sidecar.yml`, `docker-compose.spark-sidecar.yml`). A signing-passphrase default in a public repo is a phantom default on the trust root — scope added to CLAIM `fix/compose-no-secret-defaults` (still PR-gated).

**Verified:** sweep coverage (all 58 chats), masked classification, HEAD membership per value, PEM pair counts. **Unverified:** whether each real-format value is still ACTIVE (provider-side check needed); origin/purpose of the 8 RSA keys; whether the committed CHIT default equals any live passphrase (boolean check on request).

### 2026-10-12 addendum — live CHIT signing passphrase exposed to chat transcript `pIFpsFRx` (self-reported)

- **What:** a masked length-audit of env files used awk `$1` for output labeling; `KEY=value` lines contain no whitespace, so `$1` = the full line including the value. Live `CHIT_PASSPHRASE` (43ch, `pmoves/env.shared`, same value as `CHIT_PROD_PASSPHRASE` and all generated/tier copies) printed verbatim into chat `pIFpsFRx` transcript (`/a0/usr/chats/pIFpsFRx/`).
- **Blast radius:** local chat transcript only. Public HEAD unchanged and clean; per the 2026-10-11 sweep record above, the live value differs from the removed committed compose default (boolean: NO). Passphrase remained functionally valid immediately after the leak — round-trip HMAC-SHA256 verification against the elder-melchor bundle passed (kid `936d5ec10d41dc48`).
- **Disposition:** added to the rotate-list class — operator decision. Rotating the signing passphrase invalidates elder-melchor bundle verification and requires a re-signed custody bundle (operator-held key, funnel-only redelivery). No agent-side rotation.
- **Verified:** leak location (this chat only; no other transcript touched this turn), value length, bundle round-trip OK. **Not done:** full-corpus re-sweep for other occurrences; passphrase rotation. → **Both closed same day, see addendum #2.**

### 2026-10-12 addendum #2 — second exposure + EXECUTED ROTATION (both exposures closed)

**Exposure #2 (self-reported, same chat `pIFpsFRx`):** a bundle-structure check printed the head of `nats-rotation-elder-melchor-2026-10-11.signed.json` unredacted — the staged elder-melchor NATS credential (`new_value`) entered the transcript. Status at exposure: staged in env.shared, **NOT yet consumed** by the elder-melchor lane (no compose interpolation, no runtime flip). *(Bundle destroyed 2026-10-12, superseded by re-mint — historical record; see rotation log below.)*

**Operator approval:** 2026-10-12 ('go with your lean' — rotate the signing key; re-mint the staged NATS credential pre-consumption). One rotation closed both exposures.

**Executed 2026-10-12T15:21:11Z (agent0-sidecar, claim in AGNOTE4482PHI.t1.md):**
1. New `CHIT_PASSPHRASE` + `CHIT_PROD_PASSPHRASE` (matched pair) + new `NATS_PASS_ELDER_MELCHOR` generated silently (`secrets.token_urlsafe(32)`, 43ch each, never printed).
2. Replaced in `pmoves/env.shared` (all three keys existed — replace, no append); synced into `pmoves/.env.generated`, `pmoves/env.shared.generated`, `pmoves/env.tier-data`, `pmoves/env.tier-agent` (keys replaced only where present).
3. New bundle `pmoves/chit/bundles/nats-rotation-elder-melchor-2026-10-12.signed.json` — HMAC-SHA256 under the NEW passphrase, round-trip verified, chmod 600, gitignored. New kid: `9e66b2adc53c970d` (old kid `936d5ec10d41dc48` retired).
4. Old bundle `nats-rotation-elder-melchor-2026-10-11.signed.json` **destroyed** (leaked credential, pre-deployment — supersession clean).
5. Negative test passed: old key does NOT verify the new bundle. Fresh-process re-verification passed post-write.

**Consumer notes (binding):** the elder-melchor NATS lane (MODE D handoff) must verify/apply bundle `2026-10-12` with the POST-rotation passphrase from current `pmoves/env.shared` — the card's original key material is void. Outstanding enrollment/HMAC tokens issued pre-rotation verify against the OLD key until TTL expiry (≤24h) or re-mint. Fleet propagation of the new passphrase runs through the secrets funnel on owning nodes; this rotation was local to the sidecar tree.

**Verified:** old-bundle sanity under old key before mutation; masked replacement counts (3 keys env.shared, tier copies synced incl. `.env.generated`); new-bundle round-trip under new key; old-bundle destruction; negative test (old key rejects); fresh-process re-verify; OLD value absent from git-tracked files (0 hits); classification — env.shared / env.shared.generated / .env.generated / env.tier-agent / env.tier-data all carry NEW, sidecar `.example` files carry the documented 26ch dev sentinel (neither OLD nor NEW), worker/media/llm/api/supabase tiers carry no CHIT keys; sign-trail emitted 15:31:26Z. **Not done:** fleet-wide funnel propagation (owning nodes); enrollment token re-mint inventory (none known outstanding — not enumerated).

### 2026-10-30 addendum — Invidious keys: removed from compose, rotated by the funnel

**Verdict.** `INVIDIOUS_HMAC_KEY` (`<64 hex>`) and `INVIDIOUS_COMPANION_KEY` (`<16 hex>`) shipped as literal compose defaults in `pmoves/docker-compose.yml` (companion `SERVER_SECRET_KEY`, invidious env, and the `INVIDIOUS_CONFIG` YAML string) and in the generated `pmoves/docker-compose.ui.yml`. The repo is public and the values are in git history, so they are **compromised regardless of origin**. This runbook previously assumed the funnel generated them; it never did for the HMAC key, and the registry's companion spec (64 hex) could not have produced a key Invidious accepts.

**Official sources (fetched 2026-10-30 with curl, pinned by commit):**

| Source | Commit (date) | What it says |
|---|---|---|
| docs.invidious.io/installation (`iv-org/documentation` `docs/installation.md`) | `00fe454e2cfe` (2026-10-24) | Generate two keys with `pwgen 16 1`; companion `SERVER_SECRET_KEY` = "SAME_AS_INVIDIOUS_COMPANION_SECRET_KEY_FROM_INVIDIOUS_CONFIG"; "NOT recommended to use the same key as HMAC KEY"; post-install: set `hmac_key` with `pwgen 20 1`; config passed as `INVIDIOUS_CONFIG: \|` YAML |
| `iv-org/invidious` `config/config.example.yml` | `1c4b41f960e3` (2026-10-26) | `hmac_key`: mandatory random string, signs CSRF tokens, cookies and pubsub verification. `invidious_companion_key`: "needs to be exactly 16 characters long" |
| `iv-org/invidious` `src/invidious/config.cr` | `1c4b41f960e3` | exits if `hmac_key` empty; exits if companion configured and key empty, `CHANGE_ME!!`, or `size != 16`; env `INVIDIOUS_<FIELD>` overrides a top-level field |
| `iv-org/invidious-companion` `src/lib/helpers/config.ts` | `fcb0456ad5bd` (2026-10-18) | `SERVER_SECRET_KEY`: `z.string().length(16).regex(/^[a-zA-Z0-9]+$/)`; `SERVER_BASE_PATH` default `/companion` |
| `iv-org/invidious-companion` `src/routes/index.ts` | `fcb0456ad5bd` | `<base>/youtubei/v1/*` is bearer-auth guarded by `SERVER_SECRET_KEY` |

**Format.** HMAC: any non-empty random string (vendor suggests 20 chars); we mint 64 hex. Companion: exactly 16 alphanumeric, identical on both sides (`invidious_companion_key` in `INVIDIOUS_CONFIG` and companion `SERVER_SECRET_KEY`); we mint 16 hex. The two keys must differ.

**What changed (PR #3431).**
- Compose: every literal default becomes `${VAR:?set VAR via secrets funnel}`, including inside `INVIDIOUS_CONFIG`.
- `pmoves/bootstrap/registry.json`: companion generator `random_hex` 16 (was 64).
- `pmoves/mk/codex.mk`: both keys join `SECRETS_ENSURE_KEYS`. Compose interpolates the whole project even when the `invidious` profile is off (measured, compose v5.6.0), so **every node** must hold both values, including nodes that never run Invidious.
- `pmoves/tools/_secrets_common.py`: PBKDF2-SHA256 digests (not values) of the two published keys. A slot or container holding them counts as unprovisioned, so the funnel replaces them instead of harvesting them back.
- `pmoves/tools/validate_composes.py`: rule `literal-secret-default` fails CI if a credential-shaped default is reintroduced.

**Rotation road (operator, per node).**
1. `make -C pmoves secrets-funnel` (or just `make -C pmoves secrets-ensure-generated`). Mints both keys where they are absent or equal to the published values; never touches a private value already set. Do this **before** any `make up-*` on that node, or compose refuses with `required variable INVIDIOUS_HMAC_KEY is missing a value`.
2. `make -C pmoves secrets-ensure-check` -- every key must print `provisioned` with no shape warning. A node that ran `env-setup` under the old registry spec holds a **64-char** companion key: private, but Invidious exits on it. The funnel deliberately does not reshape a live value, so the check warns and the operator rotates it: `make -C pmoves secrets-rotate KEY=INVIDIOUS_COMPANION_KEY` (type and length now come from the registry: 16 hex).
3. Nodes that run Invidious: `make -C pmoves up-invidious` recreates `invidious`, `invidious-db` and `invidious-companion` with the new keys. The `docker-compose.ui.yml` copies of these services have no dedicated road (`overlay-up-ui` starts `--profile ui` only); they matter for the interpolation gate, not for the running containers.
4. `make -C pmoves invidious-smoke` (read-only): Invidious `/api/v1/stats` 200, companion `/healthz` 200, and the companion rejects a wrong bearer token but accepts the funnel's key. Exit 0 clean / 1 findings / 3 could-not-measure (`make` reports both 1 and 3 as 2; run `python3 tools/invidious_smoke.py` under `scripts/with-env.sh` for the exact code).

**Side effects of the new HMAC key.** Everything Invidious signs with `hmac_key` stops verifying -- per the vendor that is CSRF tokens, cookies, and PubSubHubbub subscription verification (the last only if `use_pubsub_feeds` is enabled; default off). Expect signed-in users to re-authenticate and any open form to need a reload. Subscriptions and preferences in `invidious-postgres-data` survive. The new companion key needs nothing beyond recreating both containers together, which `up-invidious` does.
