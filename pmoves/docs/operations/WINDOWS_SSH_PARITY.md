# Windows SSH parity on the tailnet

**Problem:** half the fleet is unreachable by SSH, and it is not a config oversight —
**Tailscale SSH is Linux-only.** It cannot be enabled on a Windows node, no matter
how the ACLs are written. Every Windows node in the fleet therefore has *no* SSH
until plain OpenSSH Server is installed on it.

This runbook closes that gap. Written for Z890 first; the same steps apply to
5090, 4090, and MISSLING-LINK.

## Current state

Measured with `tailscale status --json` (peers reporting SSH host keys):

| Node | OS | Tailscale SSH | Reachable by SSH today |
|------|-----|---------------|------------------------|
| `pmoves-kvm2` | linux | yes | ✅ |
| `pmoves-kvm4-1` | linux | yes | ✅ |
| `pmoves-kvm4-2` | linux | yes | ✅ |
| `pmoves-spark` | linux | yes | ✅ |
| `pmoves-nano` | linux | yes | ✅ |
| `pmoves-z890` | **windows** | **impossible** | ❌ |
| `pmoves-5090` | **windows** | **impossible** | ❌ |
| `pmoves-4090` | **windows** | **impossible** | ❌ |
| `pmoves-missling-link` | **windows** | **impossible** | ❌ |
| `nano-cataclysm` | linux | no | ❌ (can be enabled) |
| `powerfulmoves` | linux | no | ❌ (can be enabled) |

Two different fixes hide behind one symptom:

- **Linux nodes without SSH** — run `tailscale set --ssh` and add an ACL `ssh` rule.
  Tailscale terminates the session itself; no `sshd` involved.
- **Windows nodes** — install OpenSSH Server and let it listen on the tailnet
  interface. Tailscale carries the packets but does not terminate the session.

"Parity" here means *equivalent reachability*, not an identical mechanism.

## Why Tailscale SSH cannot cover Windows

Tailscale SSH works by having `tailscaled` itself act as the SSH server: it
terminates the connection in-process, checks the ACL, and hands off to a login
shell. That handoff depends on Unix session primitives — PTY allocation,
`setuid`, PAM. The Windows client ships no equivalent, so `tailscale set --ssh`
is not available there.

Consequence worth internalizing: on Linux nodes, SSH authorization lives in the
**tailnet ACL** and needs no local account management. On Windows nodes it lives
in **Windows' own user database and `administrators_authorized_keys`**. Two
policy surfaces, not one. Revoking a user's tailnet access does *not* revoke
their Windows SSH login, only their route to it.

## Procedure — Z890 (Windows)

Run in an **Administrator** PowerShell on Z890.

### 1. Install and start the server

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Get-Service sshd
```

### 2. Bind to the tailnet interface only

By default `sshd` listens on `0.0.0.0`, which exposes it to whatever LAN the
machine is on. Restrict it to the Tailscale address:

```powershell
$ts = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -like '100.*' }).IPAddress
Add-Content $env:ProgramData\ssh\sshd_config "`nListenAddress $ts"
Restart-Service sshd
```

Then confirm nothing is listening on the wildcard address:

```powershell
Get-NetTCPConnection -LocalPort 22 -State Listen |
  Select-Object LocalAddress, LocalPort
```

`LocalAddress` should show only the `100.x` tailnet address.

### 3. Windows Firewall

The capability install adds an allow rule for port 22 on all profiles. Narrow it
so only the tailnet can reach it:

```powershell
Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' `
  -RemoteAddress 100.64.0.0/10
```

`100.64.0.0/10` is the CGNAT range Tailscale allocates from — this is the
tailnet as a whole, not a specific peer.

### 4. Key-based auth

Password auth over a mesh is a standing liability. Push a key from the node that
will drive Z890:

```bash
ssh-copy-id <winuser>@pmoves-z890    # or paste the pubkey manually
```

**Windows gotcha:** for accounts in the Administrators group, `sshd` ignores
`~/.ssh/authorized_keys` and reads
`C:\ProgramData\ssh\administrators_authorized_keys` instead. That file must also
have its inheritance stripped:

```powershell
icacls C:\ProgramData\ssh\administrators_authorized_keys `
  /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

Silent auth failures on a Windows admin account are almost always this file or
its ACL — not the key.

Once the key works, disable password auth in
`C:\ProgramData\ssh\sshd_config` (`PasswordAuthentication no`) and restart `sshd`.

### 5. Tailnet ACL

Plain SSH is ordinary TCP/22, so it is governed by a normal `acls` port rule —
**not** the `ssh` block, which only applies to Tailscale-terminated sessions.
Ensure something equivalent to:

```json
{ "action": "accept", "src": ["tag:pmoves"], "dst": ["tag:gpu:22"] }
```

Z890 already carries `tag:gpu` and `tag:pmoves`.

## Verification

From another fleet node:

```bash
nc -z -w3 pmoves-z890 22 && echo "port open"
ssh -o BatchMode=yes <winuser>@pmoves-z890 'hostname'
```

`BatchMode=yes` makes the check fail fast instead of hanging on a password
prompt — so a green result proves *key* auth works, not merely that something is
listening.

## Related: narrowing SSH on the Linux nodes

While auditing this, B850's `ufw` was found allowing `22/tcp` from **Anywhere**,
even though the rule above it (`Anywhere on tailscale0 ALLOW IN`) already admits
all tailnet traffic including SSH. The bare rule is therefore wider than needed:

```bash
sudo ufw status verbose        # observe: 22/tcp  ALLOW IN  Anywhere
sudo ufw delete allow 22/tcp   # tailnet SSH still works via the tailscale0 rule
```

Do this only from a session that will survive the change — a tailnet SSH session
or a local console, never a LAN SSH session you are currently sitting in.

## See also

- `pmoves/docs/operations/FLEET_INVENTORY_LIVE.md` — node inventory and access paths
- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md` — exit-node behavior
- `pmoves/docs/TAC/TAC_TAILSCALE.md` — tailnet ACL structure
