# Supabase Auth — HS256 → Asymmetric (RS256) JWT Migration

**Status:** Design + staged plan (2026-06-28). **DESIGN ONLY — no runtime change in this doc.**
**Owner lane:** Z890-CLAUDE (data tier) + OPERATOR (key-custody decisions, §7).
**Prereq:** gotrue ≥ v2.191 (RS256 signing-key support) — landed via #1891 (task #4 part A).
**Related:** `[[project_supabase_selfhosted_2026_currency]]`, `OPEN_NOTEBOOK_JWT_AUTH.md`, task #4.

## 1. Why
HS256 (today) uses **one shared secret** (`JWT_SECRET`) for **both** signing (gotrue) and
verification (PostgREST, realtime, storage, every consumer). The secret must be distributed
to every verifier → wide blast radius if leaked, painful rotation, no separation of duties.
**Asymmetric (RS256/ES256):** gotrue signs with a **private** key; verifiers use the **public**
key (or fetch JWKS). The public key is safe to distribute, rotation is zero-downtime via a
multi-key JWKS, and the private key can live in KMS (gotrue v2.191 added AWS-KMS RS256).

## 2. Current state (HS256) — verified `docker-compose.yml`
- gotrue: `GOTRUE_JWT_ALGORITHM=${SUPABASE_JWT_ALGORITHM:-HS256}`, `GOTRUE_JWT_SECRET=${JWT_SECRET}` (≈:623/:622).
- Verifiers all share `JWT_SECRET`: PostgREST `PGRST_JWT_SECRET` (:674), realtime `API_JWT_SECRET` (:799), storage `PGRST_JWT_SECRET` (:838).
- **ANON_KEY / SERVICE_ROLE_KEY are long-lived HS256 JWTs** signed with `JWT_SECRET` (the API keys themselves).

## 3. Target (asymmetric)
- gotrue signs access tokens RS256 with a private key; publishes JWKS at `${API_EXTERNAL_URL}/.well-known/jwks.json`.
- Verifiers validate via JWKS / public key (select by `kid`):
  - PostgREST: `PGRST_JWT_SECRET` set to the public JWK / JWKS (requires a PostgREST build with JWKS support — confirm against the pinned image).
  - realtime / storage: confirm JWKS support in their pinned versions before flipping; otherwise hold them on a dual-key window.

## 4. The hard parts (why this is breaking, not a flag flip)
1. **ANON/SERVICE keys are HS256 JWTs.** Switching gotrue's signer to RS256 does **not** reissue them. Either keep an HS256 verification key alongside RS256 (dual-key JWKS) so existing API keys still validate, **or** re-mint them — re-minting touches every client/env (Chrome extension, services, all `.env`/secrets). This is the stickiest point.
2. **Verifier JWKS support varies by pinned version** — PostgREST, realtime, storage must each accept a JWKS/public key. Verify per service before the flip.
3. **Live sessions** signed with the old key stay valid only while that key remains in the JWKS — keep both keys through the full token-expiry window.
4. **Key custody** — private-key storage choice (file-mounted secret vs AWS-KMS vs CHIT-managed) is an OPERATOR decision (§7).

## 5. Staged plan (zero-downtime, dual-key)
- **S1 — Keypair + dual-key JWKS:** generate an RS256 keypair; configure gotrue `GOTRUE_JWT_KEYS` (JWKS) holding **both** the current HS256 key and the new RS256 key, RS256 active for signing. Existing HS256 tokens + API keys still verify. (gotrue ≥ v2.191.)
- **S2 — Verifier JWKS:** point PostgREST/realtime/storage at the JWKS / public key, accepting both algorithms. Verify each service version supports it. No token invalidation.
- **S3 — Flip signing to RS256:** new tokens RS256-signed; old HS256 tokens valid until expiry.
- **S4 — API-key strategy:** decide (a) keep ANON/SERVICE_ROLE as HS256 in a permanent dual-key JWKS, or (b) re-mint under the publishable/secret-key model and roll to every consumer.
- **S5 — Retire HS256:** after the token-expiry window + the S4 decision, drop the HS256 key from the JWKS and rotate `JWT_SECRET` out.

Each stage is its own reviewable, deploy-validated change; MinIO-style — keep the old key available behind the dual-key JWKS through cutover so rollback is "re-activate HS256".

## 6. Verification (deploy-gated)
Cannot be validated without the running data tier (deploy spine). Per stage: login + token
issuance + a PostgREST/realtime/storage round-trip; confirm the JWKS endpoint is reachable,
tokens carry a `kid`, and verifiers select the correct key.

## 7. Operator decisions / open questions

**Decided (operator, 2026-06-28):**
1. **Key custody → file-mounted Docker secret** (the `_FILE`-mounted convention used across
   `pmoves/services/**`) for the initial rollout. **CHIT-managed custody is a follow-up** —
   migrate the private key into the CHIT secrets pipeline (voice-activated prod-credential
   model) once the file-mounted path is validated. AWS-KMS not chosen (avoids AWS dependency).

**Still open:**
2. **ANON/SERVICE_ROLE keys:** keep HS256 in a permanent dual-key JWKS, or **re-mint** (and roll to all consumers)?
3. **Rotation cadence** once on JWKS?
4. **Audit:** any RLS / `auth.jwt()` consumers or middleware that string-match the algorithm or shared secret (would break on the flip)?

> Note for S1: file-mounted custody = the RS256 private key is supplied as a file-mounted
> Docker secret and loaded into gotrue's signing-key set — i.e. the **`GOTRUE_JWT_KEYS` (JWKS)**
> mechanism from §5 S1, sourced from a mounted file rather than inline env (confirm the exact
> file-vs-inline `GOTRUE_JWT_KEYS` syntax against the gotrue ≥ v2.191 docs before S1). No
> plaintext private key in env. The dual-key JWKS (§5 S1) holds the current HS256 key + the new
> RS256 key during the transition.
