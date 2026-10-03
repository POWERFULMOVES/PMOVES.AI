# NATS Credential Rotation — Dual-Credential Bridge (Option B)

> Lane: `fix/nats-credential-rotation-2026-10-01` · Operator decision **B**, 2026-10-03.
> Constraint: rotate the leaked default credential **without recreating client
> containers**.

## Background

Services logged the NATS URL with userinfo unredacted (2,233 lines / 30 days /
8 containers) into an unauthenticated Loki on `0.0.0.0:3100`; the leaked pair is
the known default (`nats:<default>`). Log redaction landed in #3244. This
runbook rotates the credential itself.

## Vendor-docs basis (reviewed 2026-10-03)

- **`authorization` / `users` is SIGHUP-reloadable, in place, with no client
  disconnects** — "Reloadable keys take effect on a reload, in place, with no
  reconnect: Account, user, and permission definitions"
  (docs.nats.io/learn/deployment/config-management; the configuration/loading
  reference marks `authorization` reloadable: yes).
- A failed reload is atomic — the new config applies cleanly or nothing changes.
  Validate first: `nats-server -c <conf> -t`.
- **Multi-user shape**: `authorization { users: [ {user, password}, ... ] }`;
  passwords may be bcrypt hashes (`nats server passwd` or any bcrypt
  generator; golang x/crypto/bcrypt verifies `$2a$`/`$2b$`).
- **Quote bcrypt hashes** — an unquoted `$NAME` token resolves as a config env
  variable.
- Existing authenticated connections keep their user for the connection's
  life; a reload applies to new/reconnecting clients. That is exactly what the
  bridge exploits.
- One caveat honored here: `store_dir` is non-reloadable, so the rendered conf
  pins the same `/data/js` the CLI flag used.

## Mechanism

The `nats` compose service now mounts `./data/nats/auth.conf` (rendered, never
hand-edited) and drops the `--user/--pass` CLI flags. The conf carries BOTH:

| user | password | role |
|---|---|---|
| `NATS_USER` (default `nats`) | bcrypt of `NATS_PASSWORD` | current — every client today |
| `NATS_USER_V2` (default `nats-v2`) | bcrypt of `NATS_PASSWORD_V2` | rotation target |

Clients get `NATS_PASSWORD_V2` into their env through the secrets funnel
(`nats_password_v2` manifest entry → `env.shared.generated` + tier files) and
adopt it **as each is naturally recreated**. No wave, no deadline per client.

## Runbook (operator-gated live steps)

```bash
# 0. Fill the new credential through the funnel (no hand-edited env):
#    make -C pmoves secrets-funnel     # after NATS_PASSWORD_V2 exists in the vault

# 1. Render + validate the bridge conf (fail-closed on empty):
make -C pmoves nats-auth-render
make -C pmoves nats-auth-validate

# 2. Adopt the conf — ONE server recreate; clients auto-reconnect:
env -u NATS_URL make -C pmoves up-bus    # env -u: never let a session-exported
                                         # NATS_URL shadow env.shared (the
                                         # documented compose precedence trap)

# 3. Migration meter (repeat any time; zero old-user connections = done):
make -C pmoves nats-auth-status

# 4. Final phase — only when step 3 shows 0 connections on the old user:
make -C pmoves nats-auth-render-final
make -C pmoves nats-auth-validate
make -C pmoves nats-auth-reload
#    expect: docker logs <nats> --tail 5 → "Reloaded server configuration"

# 5. Negative probe — the OLD credential must now be rejected:
#    (connect with the old password; expect an authorization error)
```

## Deliberately NOT in this lane

- The **Loki lockdown/wipe** (the actual leak sink, `0.0.0.0:3100`) — separate
  operator decision.
- TLS on the bus — the spec'd hub (`PMOVES-nats-server`) covers it; this bridge
  runs on the stock image, transport encrypted by Tailscale as today.
- Migrating `NATS_PASSWORD` → the new value inside `env.shared` wholesale —
  happens with the drop (step 4), so un-migrated clients never break mid-flight.
