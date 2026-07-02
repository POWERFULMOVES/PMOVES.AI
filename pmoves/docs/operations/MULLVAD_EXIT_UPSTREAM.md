# Mullvad WireGuard upstream for KVM exit nodes

**Goal:** own the fleet's egress privacy without a per-device fee. Chain a Mullvad
WireGuard tunnel as the **upstream** of the KVM Tailscale exit nodes:

```
fleet client ──Tailscale (WG)──▶ KVM exit node ──Mullvad (WG)──▶ internet
```

Fleet clients keep using the KVMs as ordinary Tailscale exit nodes (no client
change). The KVM re-encapsulates the forwarded traffic into a Mullvad tunnel, so
the public egress IP is Mullvad's, not the Hostinger VPS IP.

## Why this model (chosen 2026-07-02)

| Option | Verdict |
|--------|---------|
| **Self-host WG upstream on KVM** (this doc) | ✅ chosen — no per-device fee, we own egress, works with existing Tailscale exit nodes |
| Tailscale native Mullvad add-on ($5 / 5 devices) | recurring fee, capped at 5, no self-host control |
| Ship the forked Mullvad desktop app | wrong shape — the app is a per-device GUI client, not a server-side egress hop |

**Role of the fork (`POWERFULMOVES/PMOVES-mullvadvpn-app`):** reference only — it's
a clean snapshot (0 ahead / 129 behind upstream). We use its `mullvad-cli` /
`mullvad-api` components to *generate* WireGuard configs and pick relays; the
runtime on the KVM is plain `wg-quick` (nothing from the fork runs on the KVM).

## Design

Plain `wg-quick` interface `mlv0` with **`Table = off`** (so it does not hijack the
default route), plus **policy routing** so ONLY Tailscale-forwarded traffic uses it:

- `ip rule add iif tailscale0 lookup 51820` → packets forwarded in from Tailscale
  resolve in a dedicated table whose default route is `dev mlv0`.
- The KVM's **own** traffic (SSH, Tailscale control/DERP, apt) stays in the main
  table → naked uplink → **management never routes through Mullvad**, so a tunnel
  flap can't strand the box.
- **Masquerade** on `mlv0` for the forwarded traffic.
- **Fail-closed kill-switch:** `FORWARD -i tailscale0 ! -o mlv0 -j DROP` — forwarded
  traffic may leave *only* via the Mullvad tunnel. If `mlv0` is down, packets are
  dropped, never leaked to the Hostinger IP.
- **MTU 1420** on `mlv0` (Mullvad default). The client↔exit hop is Tailscale (≈1280);
  the exit↔internet hop is Mullvad — not a single double-encapsulated packet, so 1420
  is correct. If you see stalls on large transfers, drop to 1380 (nested-WG PMTUD).
- **DNS:** keep Mullvad's `DNS = 10.64.0.1` (in the .conf) to avoid DNS leaks.

## Scripts (both in `deploy/provision/`)

- **`kvm-mullvad-upstream.sh`** — sets up / tears down the tunnel + routing + kill-switch
  on a KVM. Idempotent, `--dry-run`, `--down`. Run on the KVM as root (over Tailscale SSH).
- **`exit-node-healthcheck.sh`** — the "are the nodes working?" probe. `--mode status`
  (safe: online + approved + reachable for every exit node) and `--mode egress`
  (opt-in: reroutes this box per node, confirms `mullvad_exit=true`, checks for leaks
  vs the no-exit baseline, then auto-restores the original exit node via a trap).

## Rollout

1. **Operator — mint the Mullvad WG config(s)** from the Mullvad account portal (or
   `mullvad-cli relay set ...` on any box) for the designated egress KVM(s). Per memory,
   `pmoves-kvm4-1` is the designated Phase-9Q egress; `pmoves-kvm2` stays a plain
   Tailscale exit fallback. Recommend starting with **one KVM as a canary**.
2. **Operator — stage the config as a secret.** The `.conf` holds a WireGuard private
   key = secret. Add it to `pmoves/chit/secrets_manifest.yaml` (a damage-control
   `zeroAccessPaths` file — operator edits directly, no agent/Known-Road bypass), then
   `make -C pmoves secrets-funnel`. Deliver to the KVM at `/root/mullvad-<relay>.conf`
   (0600). **Never commit the .conf.**
3. **Canary apply** (vps-deployer / Tailscale SSH):
   ```
   ssh -o StrictHostKeyChecking=accept-new root@pmoves-kvm4-1 \
     'bash -s -- --config /root/mullvad-us-nyc.conf --dry-run' < kvm-mullvad-upstream.sh   # preview
   # then re-run without --dry-run
   ```
4. **Verify from a fleet client:**
   ```
   ./exit-node-healthcheck.sh --mode egress --node pmoves-kvm4-1
   # expect: mullvad_exit=true, EGRESS-IP != the KVM's Hostinger IP, no LEAK
   ```
5. **Point clients** at the Mullvad-backed KVM (`tailscale set --exit-node=pmoves-kvm4-1
   --exit-node-allow-lan-access`), keep kvm2 as fallback. Roll to the other KVMs once green.

## Operational caveats

- **Tailscale restart** re-applies its own nft/ip rules; the `mlv0` PostUp rules are
  additive and survive, but after a `tailscaled` upgrade re-run the healthcheck.
- **Relay failover / key rotation:** swap the `.conf` and `wg-quick down mlv0 && up mlv0`
  (or re-run the script). Consider a cron that pings `mlv0`'s handshake age.
- **IPv6:** rules mirror v4; if the KVM has no usable v6 uplink, the kill-switch still
  fails v6 closed. Disable v6 exit advertisement if it causes issues.
- **Two planes, never conflated:** *advertise* (node-local, this script + Tailscale) vs
  *approve* (tailnet admin/autoApprover). This script touches only the node-local plane.

## References
- `deploy/provision/kvm2-exit-node.sh` — base Tailscale exit-node setup this extends
- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md` — IP-forwarding, auto-exit, Serve/Funnel, RustDesk-over-mesh
- `docs/architecture/kvm-exit-node-hosting-strategy.md` — exit-node hosting strategy
- `POWERFULMOVES/PMOVES-mullvadvpn-app` — Mullvad app fork (config/relay reference)
- Memory: `project_tailscale_exit_nodes` (tailnet `tailcad9b4.ts.net`, kvm4-1 = designated egress), `feedback_no_tailscale_ips`
