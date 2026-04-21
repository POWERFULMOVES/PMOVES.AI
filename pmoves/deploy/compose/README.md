# Standalone Compose Files — Hostinger Docker API

Self-contained compose files for deploying PMOVES services via the Hostinger
`vps-create-new-project-v1` MCP tool. Each file satisfies Hostinger API constraints:

- No external networks
- No profiles section
- No `env_file` references
- No `${VAR:-default}` defaults — bare `${VAR}` only
- Relative volume paths (resolve to `/docker/{project-name}/` on VPS)

## Files

| File | Service | Description |
|------|---------|-------------|
| `headscale-standalone.yml` | Headscale | VPN control plane (Tailscale-compatible) |
| `rustdesk-standalone.yml` | RustDesk (hbbs + hbbr) | Remote desktop relay and ID server |
| `nginx-standalone.yml` | nginx | Reverse proxy for TLS termination |

## Deployment Pattern

```
1. Hostinger MCP: vps-create-new-project-v1  (deploy compose)
2. Hostinger MCP: vps-add-firewall-rule-v1   (open service ports)
3. SSH: base64 encode + decode config files    (upload configs)
4. SSH: docker compose restart                 (pick up configs)
5. SSH: docker compose ps + curl healthz       (verify health)
```

## Config Upload Pattern

Config files cannot be uploaded via the Hostinger Docker API. Use SSH base64 decode:

```bash
# Local: encode the config file
base64 -w0 /local/path/to/config.yaml

# Remote: create directory and decode in one shot
mkdir -p /docker/{project-name}/config && echo '<base64-content>' | base64 -d > /docker/{project-name}/config/config.yaml && chmod 644 /docker/{project-name}/config/config.yaml
```

Chain multiple file uploads with `&&` to minimize SSH round-trips.

## Service-Specific Notes

### Headscale

- Requires `config.yaml` and `acl.yaml` in `/docker/{project-name}/config/`
- Post-deploy: create API key, apply ACL, create admin user
- Health: `http://localhost:8096/health`

### RustDesk

- Shared `./data` volume holds hbbs keys (`id_ed25519.pub`) and SQLite DB
- No separate config files required — environment-driven
- Post-deploy: verify both hbbs and hbbr are running, check key exchange
- Ports: 21115/tcp, 21116/tcp+udp, 21117/tcp+udp, 21118/tcp, 21119/tcp

### nginx

- Requires `nginx.conf` in `/docker/{project-name}/config/`
- Requires TLS certs in `/docker/{project-name}/certs/`
- Post-deploy: verify TLS cert, test upstream with `nginx -t`
- Health: `http://localhost:80/`

## Agent Reference

Automated deployment is handled by the **vps-deployer** agent:
`.claude/agents/vps-deployer.md`

The agent implements a 6-phase deployment workflow with pre-flight validation,
config upload, health verification, and rollback capabilities.
