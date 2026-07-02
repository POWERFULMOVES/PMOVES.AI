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
2. **Operator — stage the config as a secret** (verified path; the manifest is a
   damage-control `zeroAccessPaths` file — operator edits directly, **no agent /
   Known-Road bypass**). The `.conf` is multi-line, and `secrets_sync.py._drop_multiline()`
   silently skips any secret value containing newlines (the fix for the old
   `env.tier-agent` OpenSSH-key corruption) — so **base64 the whole file to a single line**
   rather than storing it raw:
   ```bash
   # [operator] one-line encode
   base64 -w0 mullvad-us-nyc.conf        # → paste as the value below
   ```
   Add a scalar entry to `pmoves/chit/secrets_manifest.yaml` (matches the existing
   `type: cgp` KEY=value shape, e.g. `hostinger_ssh_private_key`):
   ```yaml
   - id: mullvad_us_nyc_conf
     source: {type: cgp, label: MULLVAD_US_NYC_CONF_B64}
     targets: [{file: env.tier-agent, key: MULLVAD_US_NYC_CONF_B64}]
     required: false
   ```
   Then funnel it into the tier env:
   ```bash
   make -C pmoves chit-export        # env.shared → CGP bundle   [operator]
   make -C pmoves secrets-funnel     # → MULLVAD_US_NYC_CONF_B64 in env.tier-agent
   ```
   (CHIT slash-commands `/chit:encode` are GEOMETRY-BUS packets, NOT secrets — secret
   encode/decode is internal to `make chit-export`/`secrets-funnel`.) See
   `SECRET_ROTATION_RUNBOOK.md` + `.claude/context/credentials-workflow.md` for the
   canonical source-priority chain. **Never commit the `.conf` or the b64.**
3. **Deliver to the KVM** (decode locally → pipe over Tailscale SSH → wipe local;
   no b64 blob ever lands on the VPS; precedent = `deploy-claw.sh`):
   ```bash
   grep MULLVAD_US_NYC_CONF_B64 pmoves/env.tier-agent | cut -d= -f2 | base64 -d \
     > pmoves/secrets/mullvad-us-nyc.conf && chmod 600 pmoves/secrets/mullvad-us-nyc.conf
   cat pmoves/secrets/mullvad-us-nyc.conf | ssh root@pmoves-kvm4-1 \
     "cat > /root/mullvad-us-nyc.conf && chmod 600 /root/mullvad-us-nyc.conf"
   rm pmoves/secrets/mullvad-us-nyc.conf
   ```
4. **Canary apply** (vps-deployer / Tailscale SSH):
   ```
   ssh -o StrictHostKeyChecking=accept-new root@pmoves-kvm4-1 \
     'bash -s -- --config /root/mullvad-us-nyc.conf --dry-run' < kvm-mullvad-upstream.sh   # preview
   # then re-run without --dry-run
   ```
5. **Verify from a fleet client:**
   ```
   ./exit-node-healthcheck.sh --mode egress --node pmoves-kvm4-1
   # expect: mullvad_exit=true, EGRESS-IP != the KVM's Hostinger IP, no LEAK
   ```
6. **Point clients** at the Mullvad-backed KVM (`tailscale set --exit-node=pmoves-kvm4-1
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
