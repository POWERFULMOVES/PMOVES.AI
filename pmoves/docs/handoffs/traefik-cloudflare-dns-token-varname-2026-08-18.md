# Handoff — Traefik edge certs fail on Cloudflare DNS-01 env-var name (2026-08-18)

**Node:** 5090 (POWERFULMOVES) · **Lane:** notebook SSO (Lane 3) · **Author:** 5090-CLAUDE (Claude Opus 4.8)

## Symptom

Every PMOVES edge certificate (`wealth.pmoves.ai`, `health.pmoves.ai`, `auth.pmoves.ai`,
and by extension `notebook.pmoves.ai`) has been failing ACME issuance. `acme.json` holds
**zero issued certificates** (3.4 KB, no `"main"` entries). Traefik logs, as recently as
2026-08-18T17:37Z, repeat:

```
ERR Unable to obtain ACME certificate for domains
    error="cannot get ACME client cloudflare: some credentials information are missing:
    CLOUDFLARE_EMAIL,CLOUDFLARE_API_KEY or some credentials information are missing:
    CLOUDFLARE_DNS_API_TOKEN,CLOUDFLARE_ZONE_API_TOKEN"
    providerName=cf.acme domains=["wealth.pmoves.ai"]
```

This is the root cause of the 2026-08-14 notebook SSO cutover failure ("Traefik served the
default cert"). It was **misdiagnosed** then as "Cloudflare creds not in the Traefik container
env" — the token *was* present, under a name lego no longer reads.

## Root cause (CORRECTED 2026-08-18 after a recreate proved it)

**The token is EMPTY in the Traefik container** — not a name mismatch. Measured inside the
running container: `printf %s "$CLOUDFLARE_DNS_API_TOKEN" | wc -c` = **0** (and `CF_DNS_API_TOKEN`
= 0). An earlier masked-presence grep gave a false "SET" (it matched the JSON closing quote
after `=`, not a value).

`pmoves/docker-compose.traefik.yml` sources the token via compose substitution
(`environment: ...: ${CLOUDFLARE_DNS_API_TOKEN}`), and `up-edge`'s `EDGE_DC` **does** pass
`--env-file env.shared` (Makefile:4332 + COMPOSE_ENV_FILES:110-111). So substitution reads
`env.shared` correctly — and still yields empty. Therefore **`CLOUDFLARE_DNS_API_TOKEN` is
empty/absent in `env.shared`**: a real Cloudflare DNS token was never supplied. lego reports
"credentials information are missing: CLOUDFLARE_DNS_API_TOKEN" because the value it reads is
genuinely empty. The 2026-08-14 "creds not in Traefik" read was correct; the intervening
"CF_* vs CLOUDFLARE_* var-name" theory was wrong.

## Fix

**Operator-gated (the real fix):** supply a Cloudflare API token with **Zone:DNS:Edit on the
`pmoves.ai` zone** into `env.shared` as `CLOUDFLARE_DNS_API_TOKEN`, via the secrets pipeline
(`make secrets-rotate KEY=CLOUDFLARE_DNS_API_TOKEN` with `PMOVES_ROTATE_VALUE`), then
`make -C pmoves up-edge` to recreate Traefik. Option: if the existing `CLOUDFLARE_API_TOKEN`
(used by the cloudflare MCP) already carries DNS:Edit on pmoves.ai, its value can be reused —
operator decision.

**Precautionary hardening (this change, already applied):** also set the token under the
canonical name lego reads, keeping the legacy name too, so once a real value is present lego
finds it regardless of this lego version's name preference:

```yaml
    environment:
      CLOUDFLARE_DNS_API_TOKEN: ${CLOUDFLARE_DNS_API_TOKEN}
      CF_DNS_API_TOKEN: ${CLOUDFLARE_DNS_API_TOKEN}
```

Recreating Traefik is low-risk: it re-attempts ACME for existing routes and **does not touch
the standalone Open Notebook** (`:8503`), which is not behind Traefik. (Verified 2026-08-18:
recreate succeeded, token still empty as expected until the operator supplies it.)

## Blast radius

Unblocks certs for **all** edge hosts at once: wealth, health, auth — and clears the first
blocker for the notebook SSO cutover. If ACME still fails after the recreate, the next error
distinguishes the remaining possibilities (token scope/validity, or `pmoves.ai` zone not
Cloudflare-authoritative for DNS-01) — those are separate, later gates.

## Follow-ups (NOT in this change)

- Create the `notebook.pmoves.ai` DNS record (for browser reachability; DNS-01 itself does
  not need an A record).
- The notebook-ext swap (down standalone → up `open-notebook-ext`) — dual-writer `surreal_data`
  hazard, operator-gated, separate step.
