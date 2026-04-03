Fix KVM2 RustDesk relay (hbbs/hbbr) configuration.

## Usage

Run this command when:
- `/fleet:rustdesk-check` reports relay unreachable
- Nodes can't connect through the RustDesk relay
- After KVM2 reboot or maintenance
- hbbs is running but missing the `-r` relay flag

## Implementation

### Step 1: Verify relay is actually down

```bash
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>&1 && echo "Relay is REACHABLE — may not need fixing" || echo "Relay is UNREACHABLE — proceeding with fix"
```

If relay is reachable, confirm with user before proceeding.

### Step 2: Run the fix script

The canonical fix script is `pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh`. It:
1. SSHes into KVM2 via the `hostinger_vps` key
2. Updates hbbs ExecStart to include `-r` relay flag
3. Reloads systemd and restarts both hbbs + hbbr
4. Verifies the config change

```bash
make -C pmoves fleet-rustdesk-fix
```

**Required environment variables** (loaded from env.shared by the make target):
- `HOSTINGER_KVM2_IP` — KVM2 public IP (loaded from secrets, never displayed)
- SSH key at `$LOCALAPPDATA/Temp/hostinger_vps` or `/tmp/hostinger_vps`

### Step 3: Verify recovery

```bash
# Wait for services to restart
sleep 5

# Test ports again
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>&1 && echo "hbbs: RECOVERED" || echo "hbbs: STILL DOWN"
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21117' 2>&1 && echo "hbbr: RECOVERED" || echo "hbbr: STILL DOWN"
```

### Step 4: If still failing

Escalation path:
1. Check KVM2 SSH access: `ssh -o ConnectTimeout=5 root@pmoves-kvm2 "systemctl status hbbs hbbr"`
2. Check UFW: `ssh root@pmoves-kvm2 "ufw status verbose"`
3. Check disk space: `ssh root@pmoves-kvm2 "df -h /"`
4. If KVM2 is completely unreachable, check Tailscale: `tailscale ping pmoves-kvm2`

## Security

- NEVER output the KVM2 public IP, SSH key contents, or RustDesk server key
- The make target handles env variable loading from secrets
- SSH access uses key-only auth (no password)

## Known Road

```
make -C pmoves fleet-rustdesk-fix
```

## Related

- `/fleet:status` — Quick fleet overview
- `/fleet:rustdesk-check` — Full diagnostics
- `pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh` — Underlying script
- `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` — Server architecture
