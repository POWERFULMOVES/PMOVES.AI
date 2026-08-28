# Jetson Refresh-Day Runbook

**Intent:** One-device-at-a-time operator guide for reflashing `nemotron-1` and `nemotron-2` to JetPack 7 and getting them back into the PMOVES fleet with minimal ambiguity.

**Primary source:** `deploy/provision/jetson/README.md`

**Helper agent:** `.claude/agents/jetson-refresh-operator.md`

---

## Non-Negotiables

1. Use an x86_64 Ubuntu 22.04 host with NVIDIA SDK Manager installed.
2. Reflash one Jetson at a time.
3. Generate the Tailscale auth key before you power-cycle into recovery mode.
4. Keep a known-good USB-C data cable on hand. Power-only cables waste time.
5. Do not schedule this during demos or client-facing windows.

## Pre-Flight Per Device

On a trusted PMOVES node:

```bash
make -C pmoves fleet-enroll ROLE=edge DEVICE=nemotron-1
```

Capture the `TAILSCALE_AUTHKEY` output before touching the Jetson.

On the Ubuntu 22.04 host:

```bash
sdkmanager --version
lsusb | grep -i nvidia
```

The `lsusb` check should only be run after you put the Jetson into recovery mode.

## Reflash Sequence

1. Power the Jetson off completely.
2. Hold the recovery button while applying power.
3. Verify recovery mode on the host with `lsusb | grep -i nvidia`.
4. Start the reflash:

```bash
sudo TAILSCALE_AUTHKEY=tskey-xxx \
  bash deploy/provision/jetson/jetpack7-reflash.sh --device nemotron-1
```

5. Let SDK Manager run to completion. Do not interrupt the flash.
6. After reboot, let the script attempt post-flash bootstrap automatically.

## If Automatic Post-Flash Copy Fails

Use the configured Jetson SSH username explicitly:

```bash
scp deploy/provision/jetson/post-flash-bootstrap.sh pmovesnvme@192.168.55.1:/tmp/
scp -r deploy/provision/jetson/nemotron-branding pmovesnvme@192.168.55.1:/tmp/
ssh pmovesnvme@192.168.55.1 'sudo DEVICE=nemotron-1 TAILSCALE_AUTHKEY=tskey-xxx bash /tmp/post-flash-bootstrap.sh'
```

Swap `192.168.55.1` for LAN or Tailscale reachability if that is how the device comes up.

## Verification

From a trusted PMOVES host:

```bash
make -C pmoves jetson-verify DEVICE=nemotron-1
```

Expected checks:

- JetPack 7 / L4T r37
- CUDA 12.8
- Docker + GPU runtime
- Tailscale presence
- NATS reachability from the operator side
- running containers or a clear warning that the compose stack is not up yet

## Repeat For `nemotron-2`

Do not overlap the two reflashes. Finish verification on `nemotron-1`, then repeat the exact sequence for `nemotron-2`.

## Stop/Go Gates

- **Stop** if SDK Manager is not running on Ubuntu 22.04 x86_64.
- **Stop** if `lsusb` does not show the recovery-mode NVIDIA device.
- **Go** once the device responds on USB-C ethernet, LAN, or Tailscale and the bootstrap script can be copied.
- **Stop** if `make -C pmoves jetson-verify` cannot SSH to the device. Fix reachability before trying to interpret higher-level failures.