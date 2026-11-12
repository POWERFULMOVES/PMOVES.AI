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
| 6 | `INVIDIOUS_COMPANION_KEY` (16ch `60eec…`) + `INVIDIOUS_HMAC_KEY` (64-hex `c51f3…`) | **public HEAD** compose fallbacks | **look generated, not placeholder** | operator: verify real vs placeholder; if real → rotate via funnel | Operator verify |
| 7 | 12:33 window msgs 88–101 | scanned | **clean** (wrangler missing-token error, HTTP-200 checks, Tokenism simulator HTML) | none | — |

## Rotation steps

1. **HF token (operator, ~2 min):** hf.co → Settings → Access Tokens → revoke the token with prefix `hf_fp…` → issue a fresh fine-grained token → deliver **only** via `make -C pmoves secrets-funnel` (never hand-copy into env files or chat).
2. **Supabase-local JWT (operator, dev):** if the `supabase-local` instance is still live, rotate its JWT secret and reissue service_role; otherwise mark the token dead. Never paste it into exports again.
3. **Invidious keys (operator):** confirm whether the 64-hex HMAC default is a documented placeholder or a generated value. If generated → rotate + funnel.
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