# Cloudflare — DNS-01 token + OAuth paths (edge certs & CF management)

**Node-agnostic runbook.** Two Cloudflare credential models, what each is for, and the
exact steps. Written for the notebook-SSO edge lane (Traefik ACME cert = Lane 3
BLOCKER 1), but the token/OAuth split applies to any PMOVES ↔ Cloudflare work.

`pmoves.ai` is Cloudflare-authoritative (`alex/dara.ns.cloudflare.com`, verified
2026-08-20), so Cloudflare DNS-01 is the correct ACME challenge for the edge hosts.

## The one distinction that decides everything

| | **Scoped API token** | **OAuth (client / MCP)** |
|---|---|---|
| Shape | static bearer token | consent flow → short-lived tokens on a user's behalf |
| Headless? | yes | no (needs a browser consent redirect) |
| Feeds Traefik/lego? | **YES — the only option** | no |
| Good for | the ACME resolver env var | our tooling / MCP authenticating to CF to *manage* things |

**Traefik's ACME library (lego) is headless and reads a static token from
`CLOUDFLARE_DNS_API_TOKEN`.** An OAuth client cannot serve that. So the two paths are
**complementary, not either/or**: OAuth is how *we* (or our tooling/MCP) authenticate to
Cloudflare — including to *mint* the DNS token — and the minted static token is what the
cert resolver actually consumes.

---

## Path A — the scoped DNS token for the cert (required for BLOCKER 1)

Least-privilege token: `Zone:DNS:Edit` + `Zone:Zone:Read`, scoped to the **single
`pmoves.ai` zone** (DNS-01 creates/deletes a `_acme-challenge` TXT record; Zone Read
lets lego find the zone). This is the CF "Edit zone DNS" template.

### A1 — automated (repeatable, CI-friendly): `make cf-dns-token-provision`

```bash
# Admin credential — env ONLY, never on the command line. Needs API Tokens Write + Zone Read.
export CF_ADMIN_API_TOKEN=<an admin CF API token>

# 1) Dry run — resolves the zone + permission groups and prints the EXACT policy it
#    would create. Mints nothing. Verify the zone id and scope look right.
make -C pmoves cf-dns-token-provision

# 2) Apply — creates the token AND funnels it as CLOUDFLARE_DNS_API_TOKEN.
make -C pmoves cf-dns-token-provision APPLY=1
```

The tool (`pmoves/tools/cf_dns_token_provision.py`) hands the new secret straight to
`make secrets-rotate KEY=CLOUDFLARE_DNS_API_TOKEN` via the child-process env var
`PMOVES_ROTATE_VALUE` — **the value never touches argv, stdout, or chat.** Only
non-secret material is printed (zone id, permission-group ids, the new token's id).

Where `CF_ADMIN_API_TOKEN` comes from: an existing admin token, **or** mint a throwaway
one via Path B (OAuth) / the CF dashboard. It only needs `API Tokens Write` + `Zone
Read`; revoke it afterward if it was throwaway.

### A2 — manual (one-off): CF dashboard template

Profile → **API Tokens** → **Create Token** → **Edit zone DNS** template → **Zone
Resources: pmoves.ai** → Create → copy the value once → funnel it:

```bash
export PMOVES_ROTATE_VALUE=<pasted token>
make -C pmoves secrets-rotate KEY=CLOUDFLARE_DNS_API_TOKEN
```

### A3 — finish the cert (either route)

```bash
make -C pmoves up-edge        # recreate Traefik → it re-attempts ACME for the edge routes
# verify: acme.json now has a "main" entry for wealth/health/auth/notebook.pmoves.ai
```

Recreating Traefik does **not** touch the standalone Open Notebook on `:8503`.

---

## Path B — OAuth (management / tooling access to Cloudflare)

OAuth lets an application act on the operator's behalf **after consent**, with limited
scopes and short-lived tokens — a more secure, revocable alternative to embedding a
long-lived admin token. Two PMOVES uses:

### B1 — complete the `cloudflare-api` remote MCP OAuth (fastest live win)

`.claude/mcp.json` already registers `cloudflare-api` → `https://mcp.cloudflare.com/mcp`
(Cloudflare's official remote MCP; the entire CF API via two Code-Mode tools). It
authenticates by **OAuth on first connect** using the operator's admin-scoped account.
Completing that consent (operator's hands — it opens a browser) unlocks, from within a
session:

- listing/managing `pmoves.ai` DNS records (e.g. adding the `notebook.pmoves.ai` record
  for public browser reach), and
- **minting/verifying** the `Zone:DNS:Edit` token for Path A live — no static
  `CF_ADMIN_API_TOKEN` needed.

Once connected, Path A's token can be created through the MCP instead of
`cf-dns-token-provision`; the make target remains the headless/CI route.

### B2 — a self-managed OAuth client for PMOVES tooling (durable posture)

Cloudflare dashboard → **Manage account → OAuth clients**
(`dash.cloudflare.com/?to=/:account/oauth-clients`; feature GA 2026-06-03). Steps:

1. Create an application; it starts **`private`** (usable only by members of this
   account — correct for internal PMOVES tooling; no domain verification needed).
2. Select **only the scopes the tool needs** (scope names mirror API-token permissions —
   e.g. DNS edit + zone read for edge-cert tooling). Users review scopes at consent.
3. Register the tool's **redirect URI**; receive `client_id` / `client_secret`.
4. Feed `client_id`/`client_secret` through the secrets pipeline (never chat) — same
   funnel discipline as any credential.

Use this when a PMOVES service/script should authenticate to Cloudflare via OAuth
(consent + short-lived tokens) instead of holding a long-lived admin token. Making the
client **public** (for any Cloudflare user) additionally requires client-domain
verification — not needed for internal use.

### Not this: Cloudflare Access "managed OAuth" / SaaS-OIDC apps

`/accounts/{id}/access/apps` with `saas_app.auth_type: oidc` turns **Cloudflare Access
into an OIDC IdP for your apps**. That's an *alternative* to the self-hosted `sso-auth`
forward-auth gateway (a different SSO architecture), not part of the edge-cert or
CF-management story. Noted here only to disambiguate — it is a separate strategic
decision, not a step in this runbook.

---

## Security invariants

- Secrets (`CLOUDFLARE_DNS_API_TOKEN`, OAuth `client_secret`, `CF_ADMIN_API_TOKEN`) move
  **only** through the env pipeline / `secrets-rotate` — **never** pasted in chat, and
  never on a command line (use env vars).
- Scope every credential to the minimum: single zone, DNS-edit + zone-read for the cert;
  narrowest scope list for an OAuth client.
- A token's value is shown once. If Path A's funnel fails after minting, the tool prints
  the token **id** (never the value) so you can re-funnel or revoke the orphan.
