# RustDesk Self-Hosted Relay/ID Server Guide

This guide walks through building and operating a RustDesk rendezvous (`hbbs`) and relay (`hbbr`) server for the Cataclysm provisioning bundle. It covers prerequisites, firewall rules, service management (Docker and systemd), key rotation, exporting `server.conf` for Windows imaging, troubleshooting, and Tailscale integration so managed endpoints stay reachable across the tailnet.

## Prerequisites

- **Host**: Linux VM or bare-metal (Debian/Ubuntu 22.04+, Rocky 9, etc.) with at least 1 vCPU, 1 GB RAM, and persistent storage for keys/logs.
- **Network**: Static DNS names (e.g., `rustdesk-id.example.com`, `rustdesk-relay.example.com`) resolving to the server. Public IP not required if everything runs inside Tailscale, but consistent names simplify client config.
- **Privileges**: Root/`sudo` access to install packages, manage firewalls, and configure services.
- **Packages**:
  - System packages: `curl`, `wget`, `unzip`, `firewalld`/`ufw` (as preferred), `tailscale` (optional but recommended).
  - Docker workflow: Docker Engine + Compose plugin (`docker compose version`).
  - Systemd workflow: `hbbs`/`hbbr` binaries extracted to `/opt/rustdesk-server/` (see below).
- **Certificates (optional)**: If you front `hbbs` with TLS (RustDesk Pro feature) or reverse proxy, ensure certificates are in place before exposing port 21114.

## Firewall and Port Requirements

RustDesk relies on a small group of TCP/UDP ports. Open them on the host firewall and upstream security groups:

| Service | Protocol | Port(s) | Notes |
|---------|----------|---------|-------|
| `hbbs`  | TCP      | 21115, 21116 | Rendezvous (ID) service + WebSocket API.
| `hbbr`  | TCP      | 21117 | Relay channel for client-to-client data.
| `hbbr`  | UDP      | 21117 | Optional: NAT hole punching (recommended if clients are outside Tailscale).
| WebSocket | TCP    | 21118 (`hbbs`), 21119 (`hbbr`) | Needed when clients negotiate WebSocket tunnels.
| HTTPS (optional) | TCP | 21114 | Only used when enabling the Pro web console.

> Minimum open set: **21115-21117/TCP**. Enable UDP/21117 and the WebSocket ports if any clients traverse restrictive firewalls or the public internet.

Example `ufw` configuration:

```bash
sudo ufw allow 21115/tcp
sudo ufw allow 21116/tcp
sudo ufw allow 21117/tcp
sudo ufw allow 21117/udp
sudo ufw allow 21118/tcp
sudo ufw allow 21119/tcp
sudo ufw status
```

For `firewalld`:

```bash
sudo firewall-cmd --permanent --add-port=21115-21117/tcp
sudo firewall-cmd --permanent --add-port=21117/udp
sudo firewall-cmd --permanent --add-port=21118-21119/tcp
sudo firewall-cmd --reload
```

## Downloading the Server Binaries

RustDesk publishes `hbbs` and `hbbr` binaries on the [official releases page](https://github.com/rustdesk/rustdesk-server/releases). Grab the latest Linux archive:

```bash
cd /tmp
curl -L -o rustdesk-server-linux-amd64.zip "https://github.com/rustdesk/rustdesk-server/releases/latest/download/rustdesk-server-linux-amd64.zip"
unzip rustdesk-server-linux-amd64.zip -d rustdesk-server
sudo mkdir -p /opt/rustdesk-server
sudo install -m 0755 rustdesk-server/hbbs /opt/rustdesk-server/
sudo install -m 0755 rustdesk-server/hbbr /opt/rustdesk-server/
```

> Adjust paths/architectures (`aarch64`, `armv7`) to match the server.

## Running with Docker Compose

RustDesk publishes `docker-compose.yml` snippets, but the minimal Compose stack below is tailored for this bundle. Drop it in `/opt/rustdesk-server/docker-compose.yml`, replacing `rustdesk-relay.example.com` with the DNS name or public IP address your clients use to reach the relay:

```yaml
version: "3.9"
services:
  hbbs:
    image: rustdesk/rustdesk-server:latest
    container_name: hbbs
    command: hbbs -r rustdesk-relay.example.com
    restart: unless-stopped
    volumes:
      - ./data:/data
    environment:
      - TZ=UTC
    ports:
      - "21115:21115"
      - "21116:21116"
      - "21118:21118"
  hbbr:
    image: rustdesk/rustdesk-server:latest
    container_name: hbbr
    command: hbbr -r rustdesk-relay.example.com
    restart: unless-stopped
    volumes:
      - ./data:/data
    environment:
      - TZ=UTC
    ports:
      - "21117:21117"
      - "21119:21119"
      - "21117:21117/udp"
```

Bring the services online:

```bash
cd /opt/rustdesk-server
mkdir -p data
sudo docker compose up -d
sudo docker compose ps
```

`hbbs`/`hbbr` will automatically create the key pair inside `./data` on the first start. Keep the directory backed up and restricted (`chmod 700 data`).

To update images:

```bash
sudo docker compose pull
sudo docker compose up -d
```

## Running with systemd

If you prefer native services:

1. Create a dedicated user and directories:

   ```bash
   sudo useradd --system --home /var/lib/rustdesk --shell /usr/sbin/nologin rustdesk
   sudo mkdir -p /var/lib/rustdesk
   sudo chown rustdesk:rustdesk /var/lib/rustdesk
   sudo install -m 0755 /opt/rustdesk-server/hbbs /usr/local/bin/hbbs
   sudo install -m 0755 /opt/rustdesk-server/hbbr /usr/local/bin/hbbr
   ```

2. Create `/etc/systemd/system/hbbs.service` (swap in the same relay hostname or IP used above):

   ```ini
   [Unit]
   Description=RustDesk ID Server (hbbs)
   After=network.target

   [Service]
   User=rustdesk
   Group=rustdesk
   WorkingDirectory=/var/lib/rustdesk
   ExecStart=/usr/local/bin/hbbs -r rustdesk-relay.example.com
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target
   ```

3. Create `/etc/systemd/system/hbbr.service`:

   ```ini
   [Unit]
   Description=RustDesk Relay Server (hbbr)
   After=network.target

   [Service]
   User=rustdesk
   Group=rustdesk
   WorkingDirectory=/var/lib/rustdesk
   ExecStart=/usr/local/bin/hbbr -r rustdesk-relay.example.com
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target
   ```

4. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now hbbs hbbr
   sudo systemctl status hbbs hbbr
   ```

On first run, `/var/lib/rustdesk` gains the generated keys and a default `server.conf` template.

## Key Management and Rotation

RustDesk authenticates servers using an Ed25519 key pair generated by `hbbs`.

### Generate or rotate the server key

1. **Stop services** (Compose or systemd):

   ```bash
   # docker
   sudo docker compose stop hbbs hbbr

   # or systemd
   sudo systemctl stop hbbs hbbr
   ```

2. **Backup existing keys**:

   ```bash
   sudo cp /var/lib/rustdesk/id_ed25519 /var/lib/rustdesk/id_ed25519.bak.$(date +%Y%m%d)
   sudo cp /var/lib/rustdesk/id_ed25519.pub /var/lib/rustdesk/id_ed25519.pub.bak.$(date +%Y%m%d)
   ```

   Docker deployment stores them under `/opt/rustdesk-server/data/` instead of `/var/lib/rustdesk/`.

3. **Generate a new pair**:

   ```bash
   sudo -u rustdesk hbbs -g
   ```

   - For Docker, run `sudo docker compose run --rm hbbs hbbs -g` to regenerate inside the container.
   - The command writes `id_ed25519` and `id_ed25519.pub` into the working directory.

4. **Set permissions**:

   ```bash
   sudo chown rustdesk:rustdesk /var/lib/rustdesk/id_ed25519*
   sudo chmod 600 /var/lib/rustdesk/id_ed25519
   sudo chmod 644 /var/lib/rustdesk/id_ed25519.pub
   ```

5. **Restart services** and confirm they come back online (see Troubleshooting).

6. **Distribute the new public key** (see below) so clients trust the refreshed server.

> Keep backups of old keys until all clients switch; once obsolete, securely delete them.

### Export `server.conf` for provisioning media

1. After restarting `hbbs`, locate the generated config (Docker example):

   - Systemd: `/var/lib/rustdesk/server.conf`
   - Docker: `/opt/rustdesk-server/data/server.conf`

2. Copy the file to your workstation and open it. Confirm it points at the correct rendezvous/relay hostnames and includes the fresh `key` value.

3. Export an updated `server.conf` for Windows provisioning:

   ```bash
   cp server.conf /path/to/PMOVES.AI/CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/windows/rustdesk/server.conf
   ```

4. Commit the change **only if** the file contains non-sensitive defaults. For real deployments keep the secret on removable media and out of Git.

5. When imaging Windows machines, the provisioning scripts copy this file into `%AppData%\RustDesk\config\RustDesk2\RustDesk\config\server.conf` so clients immediately trust your server.

### Rotating client configs

- Replace `windows/rustdesk/server.conf` with the updated version before building new provisioning media.
- For already-provisioned machines, push the file via configuration management or instruct users to import it through the RustDesk UI (`Settings → Network → Import config`).

## Troubleshooting and Maintenance

| Task | Command |
|------|---------|
| Check systemd status | `sudo systemctl status hbbs hbbr`
| View live logs | `sudo journalctl -u hbbs -u hbbr -f`
| Docker logs | `sudo docker compose logs -f hbbs hbbr`
| Confirm listening ports | `sudo ss -ltnup | grep 2111`
| Verify key fingerprint | `sudo cat /var/lib/rustdesk/id_ed25519.pub`
| Connectivity test from client | `rustdesk --config server.conf` (client CLI) |

Common issues:

- **Clients cannot connect**: Ensure ports 21115-21117/TCP are open end-to-end. If running behind NAT, forward the ports or leverage Tailscale (see below).
- **Handshake fails after rotation**: Clients may still cache the old key. Confirm the new `server.conf` was deployed and restart the client.
- **Service crashes on launch**: Usually due to missing permissions on `/var/lib/rustdesk` or stale PID files. Reapply ownership to the `rustdesk` user and retry.
- **Docker container exits immediately**: `hbbs -g` may not have run yet. Remove the container, delete the empty `data/` directory, and `docker compose up -d` again to allow fresh initialization.

Logs written by `hbbs`/`hbbr` in systemd mode appear in `journalctl`. Docker mode logs stay under `docker logs` unless you mount a custom log directory.

## Tailscale Integration

Running RustDesk over Tailscale keeps the relay isolated from the public internet while remaining reachable by provisioned endpoints.

1. **Install Tailscale** on the server and authenticate it to your tailnet:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --authkey tskey-xxxx --hostname rustdesk-relay --advertise-tags=tag:infra
   ```

2. **Advertise RustDesk ports** through Tailscale ACLs:

   - Ensure your ACL grants client devices access to the server IP (`100.x.y.z`) on TCP 21115-21119 and UDP 21117.
   - If using Tailnet DNS/MagicDNS, create records like `rustdesk-id.tailnet-name.ts.net` and `rustdesk-relay.tailnet-name.ts.net` so `server.conf` can reference stable names.

3. **Bind services to all interfaces** (`-r 0.0.0.0`) so they listen on the Tailscale interface (`tailscale0`).

4. **Optionally restrict public exposure** by leaving firewall ports closed on the WAN interface and relying solely on Tailscale reachability.

5. **Monitor reachability**:

   ```bash
   tailscale status
   tailscale ping rustdesk-relay
   ```

6. **Clients on the tailnet** automatically connect through the mesh when they use the Tailscale hostnames/IPs in `server.conf`.

For hybrid setups (public + tailnet), publish both DNS names in `server.conf`. RustDesk will try them in order.

## Keeping Documentation in Sync

- Update this guide whenever RustDesk releases new port defaults, arguments, or key workflows.
- When the public key rotates, add a reminder in provisioning runbooks to refresh `windows/rustdesk/server.conf` before producing USB media.
- Record major changes (new hostnames, container image updates) in change management notes so downstream teams know when to re-image machines.

---

_Last updated: 2024-09-07_
