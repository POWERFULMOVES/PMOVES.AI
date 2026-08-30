# Same-Subnet Ghost Pattern — Cross-Platform Diagnosis

> Pattern reference for fleet operators. Cross-platform diagnosis of a class of network bug that produces *selective* Docker port-bind failures and container DNS resolution failures on hosts with two or more network interfaces.
>
> **Worked example (Windows / Z890):** [`FLEET_INVENTORY_LIVE.md`](./FLEET_INVENTORY_LIVE.md) Phase 2 runbook.

## When To Reach For This Doc

You probably need this pattern doc if **all** of the following are true on a host:

1. The host has two or more configured network adapters.
2. Some Docker containers bind their published ports successfully; others on the same daemon do not.
3. Containers that fail to bind show an empty `NetworkSettings.Ports` map even though they are `Up (healthy)`.
4. Container DNS lookups intermittently fail with messages like `Temporary failure in name resolution`, `dial tcp ... actively refused`, or sporadic upstream HTTP timeouts.
5. Container restart loops affect a *subset* of services on the same daemon, not all of them.

If only some of these match, the cause is more likely upstream DNS, container-image bugs, or daemon-level networking misconfiguration. The pattern below specifically describes the **same-subnet ghost** case.

## Symptoms (Specific)

| Surface | What you see |
|---|---|
| `docker inspect <container> --format '{{json .NetworkSettings.Ports}}'` | Returns `{"<port>/tcp":[]}` (empty array) for some containers; populated for others on the same daemon |
| `docker logs <container>` (DNS-using services) | `Temporary failure in name resolution` against any upstream — including public DNS — even when the host itself can resolve the same name |
| `docker ps --filter status=restarting` | Returns a non-empty subset of the stack, looping on a ~30s cadence |
| `curl http://localhost:<port>/` against affected service | `Connection refused` despite container reporting healthy |
| Same-host service on a different exposed port | Binds and serves correctly, ruling out daemon-wide failure |

The selective nature is the tell: **one Docker daemon, same compose file, same network mode, but only a subset of services exhibit the failure.**

## Root Cause

When two or more network adapters on the host hold IP addresses inside the same RFC1918 subnet (typically the same /24), the host's routing table contains two entries for that subnet — one per adapter. Outcomes depend on adapter state and OS:

- **Windows + Docker Desktop**: the port-forwarder selects an adapter at container start and stores the binding internally. If the chosen adapter is in `Disconnected` / `Disabled` / `Tentative` address state at that moment, the publish silently no-ops. The container reports healthy because the *container* is running; only the host-side bridge mapping is missing.
- **Linux + Docker Engine**: the kernel's source-address selection (RFC 6724) picks the adapter with the higher route metric. If that adapter is admin-up but link-down (carrier-off), egress packets disappear, manifesting as DNS resolution failures inside containers — particularly Deno/Node fetch stacks that rely on libc resolver behavior the kernel routes through the broken adapter.
- **WSL2**: NAT'd into the Windows host network — inherits the Windows-side broken-route problem, but symptoms surface as Linux-style DNS errors inside the WSL distro.

The triggering condition is **a stale static IP on a disconnected secondary adapter, sharing the active primary's /24**. Common origins:

- Operator wired a second NIC for a future direct-link to another host (e.g., GPU-to-GPU peering), hardcoded an IP from the LAN range as a placeholder, then forgot to change it before disconnecting the cable.
- A USB-C dock or Thunderbolt adapter brought up an `Ethernet N` virtual NIC with a stale config from a prior network.
- Docker Desktop's WSL/Hyper-V virtual NICs occasionally provision in the LAN /24 if the host's primary NIC sits there.

## Detection (Per-Platform Commands)

### Step 1: Enumerate adapters and their IPs

#### Windows (PowerShell, elevated)

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' } |
  Format-Table InterfaceAlias, IPAddress, PrefixLength, AddressState, ifIndex
```

#### Linux (any modern distro)

```bash
ip -4 -o addr show |
  awk '/scope global/ {print $2, $4}'
```

#### macOS

```bash
for iface in $(ifconfig -l); do
  addr=$(ifconfig "$iface" 2>/dev/null | awk '/inet [0-9]/ && $2 != "127.0.0.1" {print $2}')
  [ -n "$addr" ] && echo "$iface $addr"
done
```

### Step 2: Look for two adapters in the same /24

If the output of Step 1 contains two or more entries whose first three octets match (e.g., `192.168.7.42` and `192.168.7.99`), you have a candidate same-subnet collision. Cross-check whether the secondary adapter is actually in carrier-up state:

#### Windows

```powershell
Get-NetAdapter | Format-Table Name, Status, MacAddress, LinkSpeed
```

`Status: Disconnected` on an adapter that holds an IP in the LAN /24 → confirmed ghost.

#### Linux

```bash
ip -o link show | awk '{print $2, $9}'
```

`state DOWN` or `NO-CARRIER` on an adapter with a global-scope IP → confirmed ghost.

#### macOS

```bash
ifconfig <ifname> | grep -E 'status|inet '
```

`status: inactive` (or absent) on an adapter holding an IP → confirmed ghost.

### Step 3: Confirm the routing table reflects the collision

#### Windows

```powershell
Get-NetRoute -DestinationPrefix "<your_lan_24_cidr>"
```

Two rows with the same destination but different `InterfaceIndex` → the kernel has two paths and is choosing one of them at container-start time.

#### Linux

```bash
ip route show | grep "<your_lan_24_cidr>"
```

Two `dev` entries for the same subnet → same problem.

#### macOS

```bash
netstat -rn | grep "<your_lan_24_cidr>"
```

## Fix

Two options. Option A is preferred when the secondary adapter has a real future role (direct-link to another host, dedicated management VLAN). Option B is preferred when the secondary adapter is simply abandoned.

### Option A — Re-IP the secondary adapter to a dedicated, unused subnet

Pick a CIDR that does not collide with any in-use LAN, container bridge, Tailscale CGNAT (`100.64.0.0/10`), or VPN range. `10.99.0.0/24`, `10.250.0.0/24`, and `192.168.250.0/24` are commonly safe.

#### Windows

```powershell
Remove-NetIPAddress -InterfaceAlias "<secondary_alias>" -IPAddress "<ghost_ip>" -Confirm:$false
New-NetIPAddress     -InterfaceAlias "<secondary_alias>" -IPAddress "10.99.0.1" -PrefixLength 24
```

#### Linux

```bash
sudo ip addr del <ghost_ip>/<prefix> dev <secondary_iface>
sudo ip addr add 10.99.0.1/24 dev <secondary_iface>
# Persist via your distro's network manager (NetworkManager, systemd-networkd, /etc/network/interfaces, etc.)
```

#### macOS

```bash
# networksetup -setmanual requires: <service> <ip> <subnet> <router>
# Use 0.0.0.0 for router if the ghost subnet has no default gateway
sudo networksetup -setmanual "<service_name>" 10.99.0.1 255.255.255.0 0.0.0.0
```

### Option B — Disable the secondary adapter entirely

Use this when the adapter is unused.

#### Windows

```powershell
Disable-NetAdapter -Name "<secondary_alias>" -Confirm:$false
```

#### Linux

```bash
sudo ip link set <secondary_iface> down
# Persist via your distro's network manager so it does not come up at next boot
```

#### macOS

```bash
sudo networksetup -setnetworkserviceenabled "<service_name>" off
```

### After Either Option

Restart the affected Docker stack so containers re-bind through the now-unambiguous routing table:

```bash
docker compose down
docker compose up -d
```

## Verify (All Six Must Pass)

1. **Routing table shows one path for the LAN /24.** Step 3 of Detection should now return exactly one row for the LAN subnet.
2. **Affected containers have non-empty `NetworkSettings.Ports`.**
   ```bash
   docker inspect <previously_failing_container> --format '{{json .NetworkSettings.Ports}}'
   ```
   Should now return `{"<port>/tcp":[{"HostIp":"0.0.0.0","HostPort":"<port>"}]}` or equivalent.
3. **Host can curl the published port.**
   ```bash
   curl -fsS http://localhost:<port>/healthz
   ```
4. **DNS-using containers stop logging name-resolution failures.**
   ```bash
   docker logs <previously_failing_container> --tail 20
   ```
5. **No services in restart loop.**
   ```bash
   docker ps --filter status=restarting
   ```
   Should be empty.
6. **Other adapters not regressed.** Re-run Step 1 of Detection — primary adapter still holds its address; no new collision.

## Rollback

If the fix makes anything worse, the inverse of each step restores the prior state.

#### Windows

```powershell
# Reverse Option A
Remove-NetIPAddress -InterfaceAlias "<secondary_alias>" -IPAddress "10.99.0.1" -Confirm:$false
New-NetIPAddress    -InterfaceAlias "<secondary_alias>" -IPAddress "<ghost_ip>" -PrefixLength <prefix>

# Reverse Option B
Enable-NetAdapter -Name "<secondary_alias>" -Confirm:$false
```

#### Linux

```bash
sudo ip addr del 10.99.0.1/24 dev <secondary_iface>
sudo ip addr add <ghost_ip>/<prefix> dev <secondary_iface>
sudo ip link set <secondary_iface> up
```

#### macOS

```bash
# networksetup -setmanual requires: <service> <ip> <subnet> <router>
sudo networksetup -setmanual "<service_name>" <ghost_ip> <netmask> <router>
sudo networksetup -setnetworkserviceenabled "<service_name>" on
```

## Why This Pattern Generalizes

This bug is **not** specific to Docker Desktop on Windows, although Windows surfaces it most aggressively. Any system where:

- multiple NICs are configured with addresses in the same subnet, and
- one of those NICs is in a transient or inconsistent link state, and
- a userspace process (Docker, Kubernetes kubelet, libvirt, a VPN client) chooses an outbound interface at startup and caches that choice

…can hit the same family of symptoms. The fix shape — make exactly one adapter own each subnet, then restart the userspace process — applies regardless of OS or container runtime.

## Prevention

Three defenses in increasing order of effort:

1. **Hygiene rule:** never assign a static IP from your LAN /24 to a secondary adapter, even as a placeholder. Pick a CIDR you have reserved for direct-link or management use.
2. **Pre-flight detector:** run a same-subnet scan as part of any new-node onboarding. PMOVES tracks this as a planned addition to `glances-autodetect` (see W0 Substrate lane).
3. **Inventory cross-check:** if you run a managed switch / Unifi controller, periodically diff the controller's adapter view against each host's self-reported adapters to catch ghost MACs and stale VLAN bindings.

## Related Docs

- [`FLEET_INVENTORY_LIVE.md`](./FLEET_INVENTORY_LIVE.md) — Z890 Phase 2 runbook (Windows/PowerShell instance of this pattern)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.W0-SUBSTRATE.md` — W0 lane brief (planned tooling that automates Detection Steps 1-3)
