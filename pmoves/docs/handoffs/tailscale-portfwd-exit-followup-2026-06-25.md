# Tailscale Exit-Node + Port-Forwarding — Check & Follow-up (2026-06-25)

**By:** 4090-CLAUDE, live from `pmoves-laptop` (4090). Tailnet `tailcad9b4.ts.net`.
Split below: **✅ verified here on the 4090** · **operator-only** (mint keys / edit the
zero-access secrets manifest) · **z890 lane** (#3, runs on the z890 host). Builds on
`TAILSCALE_EXIT_NODE_RUNBOOK.md` ([[project_tailscale_exit_nodes]]).

## ✅ Verified live from the 4090 (read-only, sanctioned)

- **Exit nodes — all 3 KVMs online + offering:** `pmoves-kvm2` (active, **in-use by this 4090**), `pmoves-kvm4-1`, `pmoves-kvm4-2` (idle, available). ACL `autoApprovers.exitNode:[tag:exit]` + default-route approvers present; `tag:exit` owner `autogroup:admin`.
- **Exit-node DATA-PLANE confirmed:** this box's public egress IP = `167.88.38.57` = `pmoves-kvm2` (Hostinger DC), i.e. egress provably leaves through the exit node, not the local Starlink uplink.
- **Tailnet routing / "port forwarding" works the PMOVES-correct way** (direct tailnet IP:port, not `tailscale serve`): MagicDNS resolves (`pmoves-z890 → 100.113.38.37`); cross-node service reach `pmoves-5090:11434` → 200, `pmoves-z890:11434` → 200. `pmoves-spark` offline (matches `fleet-status`).
- **`tailscale serve` is correctly OFF** — `networking-defense-in-depth` + `node-4090-laptop` TAC trees treat serve as a workaround to avoid; real ingress = Cloudflare/nginx for `*.pmoves.ai`, Funnel ACL-permitted for exit nodes only.

## 4090-side finding — designated egress is on the SLOWEST node

Plain ICMP from the 4090 to each exit node (indicative; likely DERP-relayed RTT — confirm direct-vs-relay with `tailscale ping`/`netcheck` once the MCP is wired):

| Exit node | avg RTT | loss | note |
|---|---:|---:|---|
| **pmoves-kvm4-2** | **176 ms** | 0% | fastest |
| pmoves-kvm4-1 | 418 ms | 0% | "Phase-9Q designated egress" per memory |
| pmoves-kvm2 | 921 ms | 0% | **currently in-use by 4090** — slowest |

**Recommendation:** re-point the 4090's designated egress from `kvm2` → `kvm4-2` (or `kvm4-1`), keeping kvm2 as fallback. The switch is operator (raw `tailscale set` is guard-blocked); use the runbook safe-flip (set → curl test → auto-revert):
```
tailscale set --exit-node=pmoves-kvm4-2 --exit-node-allow-lan-access
curl -sf --max-time 12 https://api.ipify.org   # expect 167.88.39.80 (kvm4-2)
# auto-revert on failure: tailscale set --exit-node=
```

## #1 — Wire the tailscale MCP (operator-only; zero-access manifest)

The MCP entry in `.claude/mcp.json` is already correct (expects `TAILSCALE_API_KEY` + `TAILSCALE_TAILNET`). Gaps found today:
- GH secret exists but is named **`TAILSCALE_APIKEY`** (no underscore) — the manifest source mapping must point the env var `TAILSCALE_API_KEY` at it.
- **`TAILSCALE_TAILNET` is absent** from GH secrets — value is `tailcad9b4.ts.net` (or `-` for the key's default).
- Neither key is in `pmoves/chit/secrets_manifest.yaml` (zero-access → **no agent edit, no Known-Road bypass**; only the authkey is declared).

Operator steps (exact entries in `TAILSCALE_EXIT_NODE_RUNBOOK.md` §credential-wiring):
1. Add `TAILSCALE_API_KEY` (← GH `TAILSCALE_APIKEY`) and `TAILSCALE_TAILNET` (=`tailcad9b4.ts.net`) to the secrets manifest.
2. `make -C pmoves secrets-funnel` → materializes `.env.generated`.
3. Relaunch the session/MCP host so the launch env re-reads `.env.generated`.
   Then 4090 can run `netcheck`/`exit_node`/`serve`/`ping` directly for deeper testing.

## #2 — Scale exit nodes via `tag:exit` authkey (operator/admin + vps-deployer)

ACL is already wired (`autoApprovers` confirmed above) → a tagged node self-advertises AND self-approves, zero console clicks.
1. **Operator/admin:** mint a **reusable authkey carrying `tag:exit`** (Tailscale admin → Keys); store as `TAILSCALE_EXIT_AUTHKEY` via the Known Road (`env.shared` → `secrets-funnel`), never inline.
2. **vps-deployer** (Hostinger MCP + Tailscale SSH; MCP_DOCKER was disconnected this session — reconnect first): on `pmoves-kvm4-1` / `pmoves-kvm4-2` (and optionally re-tag kvm2), ensure `net.ipv4.ip_forward=1` then re-auth tagged:
   ```
   tailscale up --advertise-exit-node --advertise-tags=tag:exit --reset --authkey <key>
   ```
3. Future exit nodes (other users' boxes) reuse the same authkey → advertise + tag + auto-approve.

## #3 — z890 NATS port-proxy (HANDOFF → z890-claude, runs on the z890 host)

The z890 netsh port proxies let WSL2-Docker containers reach the **5090 NATS hub** via `host.docker.internal`. This is host-local to z890 — cannot be verified or set from the 4090.
- **z890:** `make -C pmoves z890-host-verify` (check proxies present) → if missing, `make -C pmoves z890-host-setup` (idempotent, Admin PowerShell). Script: `pmoves/scripts/z890_host_setup.ps1`.
- Relates to GH secret `NATS_URL_TAILNET` (present) — confirm the leafnode upstream IP matches the 5090 hub.

See [[feedback_no_tailscale_ips]], [[feedback_use_mcp_agents_for_vps]], [[feedback_known_roads_infra]].
