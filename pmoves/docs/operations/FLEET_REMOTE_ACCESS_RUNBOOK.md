# Fleet Remote Access Runbook

> Canonical operator guide for PMOVES fleet remote access using Tailscale ACLs, RustDesk relay on KVM2, CHIT-signed enrollment, and Cipher/AGNOTE continuity.
>
> Last updated: 2026-03-28

---

## Purpose

This is the one runbook to use when the task touches:

- Tailscale tailnet membership, ACLs, tags, or stale-node cleanup
- RustDesk relay operations on KVM2
- CHIT-signed enrollment payloads for partner or guest access
- dual-lane z890 infrastructure work shared by Codex and Claude

---

## Control Stack

| Layer | System | Role | Why it matters |
|------|--------|------|----------------|
| 1 | Tailscale ACLs + tags | Network enforcement | This is the real access-control boundary. |
| 2 | RustDesk relay (`hbbs`/`hbbr`) | Operator UX + transport | Remote desktop path only; not the authorization source. |
| 3 | CHIT-signed enrollment | Time-bounded issuance | Limits who gets config, for how long, and with which tags. |
| 4 | Cipher Memory + AGNOTE4482 | Continuity + audit trail | Prevents drift between Codex/Claude sessions. |

- Tailscale is the enforcement layer. RustDesk OSS does not give PMOVES the device-level authorization model we want on its own.
- RustDesk is the transport and operator-experience layer. It should inherit the network posture defined by Tailscale tags and ACLs.
- CHIT-signed enrollment is the issuance layer for controlled onboarding.
- Cipher + AGNOTE4482 are the continuity layer for dual-agent infra work.

---

## z890 Shared Ownership

z890 Codex and z890 Claude are dual-responsible for the fleet infra lane. Before touching tailnet, relay, or remote rebuild state, load this context pack in order:

1. `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`
2. `pmoves/docs/NEXT_STEPS.md`
3. `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md`
4. `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md`
5. `pmoves/docs/TAILSCALE_NODE_HYGIENE.md`
6. `.claude/CLAUDE.md`
7. `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
8. `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
9. `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
10. `pmoves/docs/CHIT_TOOLS_CATALOG.md`
11. `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`

Shared-lane rules:

- Claim and release the lane in `AGNOTE4482PHI.t1.md`.
- Store non-trivial handoffs in Cipher using `agent_checkpoint` or `agent_completion`.
- Run `make -C pmoves secrets-funnel` before service starts, restarts, or rebuild-led bring-up.
- Prefer Known Roads make targets over raw `docker compose` manifests.
- Keep live tailnet IPs, public IPs, device IDs, email addresses, and user-associated hostnames out of committed docs and PR notes. Use placeholders in git and keep exact inventories in the admin console, a local ignored export, or Cipher.

---

## Secret Separation

| Secret | Purpose | Storage rule |
|------|---------|--------------|
| `TAILSCALE_AUTHKEY` | Join/bootstrap new nodes | GitHub environment secret, `*_FILE` mount, or local ignored file only |
| `TAILSCALE_API_KEY` | Admin API access for device lifecycle, ACL audit, and stale-node cleanup | Treat as high-privilege admin credential; never commit |
| `CHIT_PASSPHRASE` | Sign enrollment payloads | CHIT export / secrets funnel only |
| `hostinger_vps` | Root SSH key for KVM2 / KVM4-* provisioning | Local ignored file only |

- `TAILSCALE_AUTHKEY` and `TAILSCALE_API_KEY` are not interchangeable.
- Current API access tokens are admin-grade credentials. Inference from Tailscale's trust-credential model: if PMOVES automates this further, move to scoped OAuth or trust credentials with only the device and policy scopes actually needed.

---

## Known Roads First

Use make targets as the final operator path whenever one exists.

| Intent | Preferred road |
|------|----------------|
| Secrets hydration | `make -C pmoves secrets-funnel` |
| TensorZero bring-up | `make -C pmoves up-tensorzero` |
| PMOVES.YT bring-up | `make -C pmoves up-yt` |
| Publisher / agent layer bring-up | `make -C pmoves up-agents-stack` |
| BoTZ bring-up | `make -C pmoves up-bots` |
| Flute rebuild + bring-up | `make -C pmoves up-flute-gateway` |
| Full validation | `make -C pmoves verify-all` |
| z890 host hardening/bootstrap | `make -C pmoves z890-host-setup` |

Use raw `docker compose build --no-cache <service>` only as a fallback preparation step when there is no dedicated rebuild road yet. If you do that:

1. run `make -C pmoves secrets-funnel` first
2. bring the service back through the nearest make target
3. record the translation in AGNOTE / PR notes

---

## Tailscale Admin API Operations

The repo ships Tailscale OpenAPI docs under:

- `pmoves/docs/API_Docs/tailscale-api.yaml`
- `pmoves/docs/API_Docs/tailscale-api.json`

Useful endpoints from that schema:

- `GET /api/v2/tailnet/{tailnet}/devices` — list devices (`devices:core:read`)
- `DELETE /api/v2/device/{deviceId}` — delete a device (`devices:core`)
- `GET /api/v2/tailnet/{tailnet}/acl` — fetch policy file (`policy_file:read`)
- `POST /api/v2/tailnet/{tailnet}/acl` — update policy file (`policy_file`)

`-` can be used as a shorthand tailnet ID when the API key belongs to the active tailnet.
Tailscale API access tokens authenticate with HTTP Basic auth using the key as the username and an empty password.
The current Tailscale trust-credentials reference documents `GET /api/v2/tailnet/{tailnet}/acl` under `policy_file:read` and `POST /api/v2/tailnet/{tailnet}/acl` under `policy_file`.

Examples:

```bash
curl -fsS \
  -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices"

curl -fsS -X DELETE \
  -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/device/<deviceId>"

curl -fsS \
  -u "${TAILSCALE_API_KEY}:" \
  -H "Accept: application/hujson" \
  "https://api.tailscale.com/api/v2/tailnet/-/acl"
```

Policy update rule:

- Always fetch the current ACL first and preserve its `ETag`.
- When writing, use `If-Match` so one operator does not silently overwrite another operator's policy change.

---

## RustDesk + KVM2 Operations

RustDesk server posture:

- `hbbs` and `hbbr` run as systemd services on KVM2
- `hbbs` must include `-r <KVM2_PUBLIC_IP>`
- partner / guest onboarding should flow through CHIT-signed enrollment plus Tailscale tags

KVM2 watcher requirements:

- `nats` CLI installed on KVM2
- `/var/log/pmoves` created before the watcher starts
- `fleet-audit-watcher.service` pointed at a NATS broker reachable from KVM2

Important current runtime note:

- The repo default NATS posture binds port `4222` to localhost only.
- That means a watcher running on KVM2 cannot publish to the default broker until one PMOVES node exposes NATS on a Tailscale-reachable interface.
- Even when remote publish is blocked, the watcher still gives useful local evidence in `/var/log/pmoves/fleet-audit.jsonl`.

---

## Minimal Session Checklist

1. `make -C pmoves secrets-funnel`
2. Refresh `tailscale status --json` or `GET /tailnet/-/devices`
3. Compare live devices/tags to `pmoves/configs/tailscale-acl-policy.json`
4. Verify `hbbs`, `hbbr`, and `fleet-audit-watcher` on KVM2
5. Confirm NATS reachability from KVM2 if remote publishing is expected
6. Apply or verify SSH hardening on VPS nodes
7. Record the session in `AGNOTE4482PHI.t1.md`
8. Store any non-trivial handoff in Cipher

---

## Related Docs

- `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md`
- `pmoves/docs/TAILSCALE_NODE_HYGIENE.md`
- `pmoves/configs/tailscale-acl-policy.json`
- `pmoves/scripts/fleet/generate-enrollment.py`
- `pmoves/scripts/fleet/fleet-audit-watcher.sh`
- `.claude/context/nats-subjects.md`
- `.claude/context/services-catalog.md`
- `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
- `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
