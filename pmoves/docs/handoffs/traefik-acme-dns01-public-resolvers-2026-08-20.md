# Handoff — Traefik ACME DNS-01: propagation check must use public resolvers (2026-08-20)

**Node:** 5090 (POWERFULMOVES) · **Lane:** notebook SSO (Lane 3, BLOCKER 1) · **Author:** 5090-CLAUDE (Claude Opus 4.8)

## What this fixes

The edge ACME certs (auth/health/wealth/notebook.pmoves.ai) were failing. Two causes,
resolved in order:

1. **Empty DNS token (resolved separately):** `CLOUDFLARE_DNS_API_TOKEN` was empty. Fixed
   by reusing the existing scoped `CLOUDFLARE_API_TOKEN` (pulled to this node via the
   Pattern-B prod funnel, then `secrets-rotate KEY=CLOUDFLARE_DNS_API_TOKEN` aliased it in
   `env.shared`). **Confirmed working** — lego authenticated to Cloudflare and created the
   `_acme-challenge` TXT record (the "credentials missing" error is gone).

2. **This change — propagation pre-check uses Docker's internal resolver:** with a valid
   token, lego now fails at the propagation check:

   ```
   ERR Unable to obtain ACME certificate ... dns01: time limit exceeded:
       last error: recursive nameservers: NS 127.0.0.11:53 returned NXDOMAIN
       for _acme-challenge.auth.pmoves.ai.
   ```

   `127.0.0.11:53` is Docker's embedded DNS. lego creates the TXT record via the CF API
   (works), then pre-checks that it has propagated — but it asks the *container's* resolver,
   which is not a public recursive resolver and returns NXDOMAIN for the public
   `_acme-challenge` record, so the check times out before Let's Encrypt is asked to validate.

## Fix

Point lego's DNS-01 propagation check at public recursive resolvers, in
`pmoves/docker-compose.traefik.yml` (the Traefik command):

```yaml
      - --certificatesresolvers.cf.acme.dnschallenge.resolvers=1.1.1.1:53,8.8.8.8:53
```

This overrides only the *propagation-check* resolver (the record is still created via the
Cloudflare API with the token). Cloudflare (`alex/dara.ns.cloudflare.com`) publishes the TXT
within seconds, so `1.1.1.1`/`8.8.8.8` see it and the check passes, then LE validates.

## Deploy / verify

`make -C pmoves up-edge` (recreates Traefik only; standalone Open Notebook on `:8503`
untouched). Then confirm issuance:

```
docker logs pmoves-traefik --since 3m | grep -i "certificate obtained\|acme"
# acme.json should gain a "main":"...pmoves.ai" certificate entry (was 3.4KB, no certs)
```

## Not in this change

- The stale `pmoves-auth-redirect@file` label on the running `pmoves-wger`/`pmoves-firefly`
  containers (created before #2644 landed) makes their main routers error until recreated —
  cosmetic here (the `health-api`/`auth`/`wealth` routers still drive ACME). Recreate those
  two app containers surgically (NOT `up-external` — it would start `open-notebook-ext`, a
  dual-writer `surreal_data` hazard vs the running standalone notebook).
