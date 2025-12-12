# Docker Compose Networking and Port Configuration Best Practices (2025)

**Last Updated:** December 12, 2025
**Target:** Docker Compose v2.40.2+ / Docker Compose V5

This document provides comprehensive best practices for Docker Compose networking, port configuration, and security based on the latest 2025 standards and recent security vulnerabilities.

---

## Critical Security Advisories (December 2025)

> **Action Required:** Update Docker components before production deployment.

### CVE-2025-9074 (CRITICAL) - Docker Desktop API Exposure

| Field | Value |
|-------|-------|
| Affected | Docker Desktop < 4.44.3 |
| CVSS | 9.8 (Critical) |
| Risk | Containers can access Docker Engine API via default subnet |
| Impact | Container escape, full host compromise |
| Fix | Upgrade to Docker Desktop 4.44.3+ |
| Advisory | [Docker Security Announcement](https://docs.docker.com/security/security-announcements/) |

**Mitigation if upgrade not immediately possible:**

> **Note:** The example below uses Docker Desktop-specific addresses. The `192.168.65.0/24` subnet and `192.168.65.7` IP are typical for Docker Desktop on macOS/Windows. On Linux Engine setups, the network topology may differ.
>
> **To find your actual subnet/IP:**
> - Check Docker networks: `docker network inspect bridge`
> - Check host interfaces: `ip addr` or `ifconfig`
> - Find listening ports: `ss -tunlp | grep 2375` or `netstat -tunlp | grep 2375`
>
> Replace the subnet and IP below with your discovered values before applying the rule.

```bash
# Block API access from containers (adjust subnet/IP for your environment)
iptables -I DOCKER-USER -s 192.168.65.0/24 -d 192.168.65.7 -p tcp --dport 2375 -j DROP
```

> **Platform Notes:**
> - This iptables rule applies to **Docker Engine on Linux** only
> - **Docker Desktop on macOS/Windows**: Uses a different networking model; the VM's internal network may use different subnets (check `docker network inspect bridge`)
> - **Common subnets**: `172.17.0.0/16` (default bridge), `192.168.65.0/24` (Docker Desktop VM)
> - Always verify your actual subnet with `docker network inspect bridge | grep Subnet` before applying rules

### CVE-2025-62725 (HIGH) - Compose Path Traversal

| Field | Value |
|-------|-------|
| Affected | Docker Compose < 2.40.2 |
| CVSS | 8.9 (High) |
| Risk | Path traversal when pulling OCI artifacts |
| Impact | Arbitrary file read during build |
| Fix | Upgrade to Compose v2.40.2+ |
| Advisory | [GitHub Security Advisory GHSA-gv8h-7v7w-r22q](https://github.com/docker/compose/security/advisories/GHSA-gv8h-7v7w-r22q) |

**Verification:**
```bash
docker compose version
# Required: Docker Compose version v2.40.2 or higher
```

---

## Docker Compose V5 Changes (December 2025)

**Key changes in Docker Compose v5.0.0 ("Mont Blanc"):**

1. **New official Go SDK** - For integrating Compose functionality into applications
2. **Internal BuildKit builder removed** - Builds now delegated to Docker Bake/bake-based flow
3. **Configurable progress UI** - Enhanced progress display options
4. **`--wait` flag for `docker compose start`** - Wait for services to reach healthy state

**Reference:** [Docker Compose v5.0.0 Release Notes](https://github.com/docker/compose/releases/tag/v5.0.0)

---

## Table of Contents

1. [Critical Security Advisories](#critical-security-advisories-december-2025)
2. [Docker Compose V5 Changes](#docker-compose-v5-changes-december-2025)
3. [Port Binding Best Practices](#port-binding-best-practices)
4. [Network Architecture Patterns](#network-architecture-patterns)
5. [Service Discovery and DNS](#service-discovery-and-dns)
6. [Health Check Patterns](#health-check-patterns)
7. [Security Considerations](#security-considerations)
8. [Docker Compose v2 Features](#docker-compose-v2-features)
9. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)

---

## Port Binding Best Practices

### 127.0.0.1 vs 0.0.0.0: Security Implications

**Default Behavior:**
- By default, Docker binds published ports to all network interfaces (`0.0.0.0`)
- This exposes services to external networks, creating potential security risks

#### Security Recommendation: Use 127.0.0.1 for Internal Services

```yaml
services:
  database:
    image: postgres:16
    ports:
      - "127.0.0.1:5432:5432"  # Only accessible from Docker host
    networks:
      - backend

  api:
    image: myapp/api
    ports:
      - "127.0.0.1:8080:8080"  # Internal API, proxied by nginx
    networks:
      - backend
      - frontend

  nginx:
    image: nginx:alpine
    ports:
      - "0.0.0.0:80:80"        # Public-facing service
      - "0.0.0.0:443:443"
    networks:
      - frontend
```

**Key Principles:**

1. **Bind to 127.0.0.1 by default** - Only the Docker host can access the service
2. **Use 0.0.0.0 selectively** - Only for services that genuinely need external access
3. **Leverage reverse proxies** - Expose only the proxy (nginx/traefik) to 0.0.0.0
4. **No host ports for internal services** - Databases, caches, and internal APIs should not bind to host ports

### Port Mapping Syntax

```yaml
ports:
  # Short syntax: [HOST:]CONTAINER[/PROTOCOL]
  - "3000"                    # Random host port -> 3000 (all interfaces)
  - "3000-3005"              # Port range
  - "8000:8000"              # 8000 (all interfaces) -> 8000
  - "127.0.0.1:8001:8001"    # 8001 (localhost only) -> 8001
  - "127.0.0.1:5000-5010:5000-5010"  # Range on localhost
  - "6060:6060/udp"          # UDP protocol

  # Long syntax (Compose v2)
  - target: 80
    host_ip: 127.0.0.1
    published: 8080
    protocol: tcp
    mode: host
```

### Expose vs Ports

```yaml
services:
  webapp:
    expose:
      - "3000"     # Accessible to other containers, NOT published to host
    networks:
      - frontend

  api:
    ports:
      - "127.0.0.1:8080:8080"  # Published to host
    networks:
      - frontend
```

**Use `expose` for:**
- Inter-service communication only
- Services that should never be accessed from the host
- Documentation of container ports

**Use `ports` for:**
- Services that need host or external access
- Development environments requiring direct access
- Load balancers and ingress controllers

---

## Network Architecture Patterns

### 1. Multi-Tier Network Segmentation

**Pattern:** Separate frontend, backend, and data tiers into distinct networks.

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
  data:
    driver: bridge
    internal: true  # No external access

services:
  nginx:
    networks:
      - frontend
    ports:
      - "80:80"

  api:
    networks:
      - frontend  # Receives requests from nginx
      - backend   # Communicates with workers

  worker:
    networks:
      - backend   # Receives tasks from API
      - data      # Accesses database

  database:
    networks:
      - data      # Isolated from frontend/backend
    # NO ports exposed to host
```

**Benefits:**
- Prevents frontend from directly accessing database
- Limits lateral movement in case of compromise
- Clear separation of concerns

### 2. Internal Networks for Sensitive Services

```yaml
networks:
  public:
    driver: bridge
  private:
    driver: bridge
    internal: true  # Completely isolated from external networks

services:
  web:
    networks:
      - public
    ports:
      - "443:443"

  redis:
    networks:
      - private  # No internet access, no host access

  postgres:
    networks:
      - private  # Completely isolated
```

**Use `internal: true` for:**
- Databases that never need external connectivity
- Caches (Redis, Memcached)
- Internal message queues
- Sensitive processing services

### 3. External Networks (Pre-existing)

```yaml
networks:
  # Use network created outside Compose
  existing_network:
    external: true
    name: my-pre-existing-network

services:
  app:
    networks:
      - existing_network
```

**Use cases:**
- Integration with non-Compose containers
- Shared networks across multiple Compose projects
- Legacy infrastructure integration

### 4. Custom Bridge Networks with Static IPs

```yaml
networks:
  app_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
          gateway: 172.28.0.1

services:
  database:
    networks:
      app_net:
        ipv4_address: 172.28.0.10
```

**Warning:** Avoid static IPs unless absolutely necessary (legacy integrations, IP-based licensing). Prefer DNS-based service discovery.

### 5. Host Network Mode (Use Sparingly)

```yaml
services:
  performance_critical:
    network_mode: "host"  # Uses host's network stack directly
```

**When to use:**
- Extremely high-performance requirements
- Applications that need direct access to host network interfaces
- Specific protocols that don't work through Docker proxy

**Drawbacks:**
- Loses network isolation
- Port conflicts with host services
- Reduced portability

### 6. None Network Mode (Maximum Isolation)

```yaml
services:
  batch_processor:
    network_mode: "none"  # No network access
    volumes:
      - ./data:/data
```

**Use cases:**
- Batch processing from volumes
- Security-sensitive operations
- Services that should never have network access

---

## Service Discovery and DNS

### Automatic DNS Resolution

Docker Compose v2 provides automatic DNS-based service discovery. Each service is reachable by its service name.

```yaml
services:
  web:
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/myapp
      # 'db' resolves to the database service automatically

  db:
    image: postgres:16
```

**Key Features:**
- Service name = DNS hostname
- Automatic DNS entries for all services on the same network
- Load balancing across scaled instances (`docker-compose up --scale web=3`)

### DNS Round Robin vs VIP (Virtual IP)

```yaml
services:
  api:
    deploy:
      endpoint_mode: vip  # Virtual IP (default) - single stable IP
      # OR
      endpoint_mode: dnsrr  # DNS Round Robin - returns multiple IPs
      replicas: 3
```

**VIP (Virtual IP) Mode:**
- Single IP address for the service
- Docker handles internal load balancing
- Recommended for most use cases

**DNS Round Robin (dnsrr):**
- DNS query returns list of all container IPs
- Client-side load balancing
- Useful for advanced load balancing scenarios

### Network Aliases

```yaml
services:
  api:
    networks:
      frontend:
        aliases:
          - api-service
          - backend-api
      backend:
        aliases:
          - internal-api
```

**Use cases:**
- Multiple names for the same service
- Gradual migration (old name + new name)
- Different names in different networks

### Custom DNS Configuration

```yaml
services:
  app:
    dns:
      - 8.8.8.8
      - 8.8.4.4
    dns_search:
      - internal.company.com
    dns_opt:
      - ndots:5
```

---

## Health Check Patterns

### Basic HTTP Health Check

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Parameters:**
- `interval`: Frequency of health checks (default: 30s)
- `timeout`: Seconds to wait before declaring check failed (default: 30s)
- `retries`: Consecutive failures needed to mark unhealthy (default: 3)
- `start_period`: Grace period before starting checks (default: 0s)

### Database Health Checks

**PostgreSQL:**
```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5
```

**MySQL:**
```yaml
mysql:
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
    interval: 10s
    timeout: 5s
    retries: 3
```

**MongoDB:**
```yaml
mongo:
  healthcheck:
    test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
    interval: 10s
    timeout: 5s
    retries: 3
```

**Redis:**
```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5
```

### Dependency-Aware Startup

```yaml
services:
  database:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 5s

  api:
    depends_on:
      database:
        condition: service_healthy  # Wait for healthy status
      redis:
        condition: service_started  # Just wait for start
```

**Conditions:**
- `service_started`: Container is running (default)
- `service_healthy`: Health check passes
- `service_completed_successfully`: Container exited with code 0

### Advanced Health Check with Script

```yaml
services:
  app:
    healthcheck:
      test: ["CMD-SHELL", "/app/health-check.sh"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

**health-check.sh:**
```bash
#!/bin/sh
# Check multiple dependencies
curl -sf http://localhost:8080/health || exit 1
redis-cli -h redis ping || exit 1
pg_isready -h postgres -U user || exit 1
exit 0
```

### Common Pitfalls

1. **Missing curl/wget in minimal images:**
   ```dockerfile
   # Add to Dockerfile
   RUN apk add --no-cache curl  # Alpine
   # OR
   RUN apt-get update && apt-get install -y curl  # Debian/Ubuntu
   ```

2. **Health check too aggressive:**
   - Increase `interval` for slow-starting services
   - Increase `start_period` for services with long initialization
   - Increase `retries` for services with occasional hiccups

3. **Health check on wrong port:**
   - Use container port, not host port: `http://localhost:8080` not `http://localhost:80`

### Debugging Health Checks

```bash
# Check container health status
docker ps

# View health check logs
docker inspect --format='{{json .State.Health}}' container_name | jq

# Run health check manually
docker exec container_name curl -f http://localhost:8080/health
```

---

## Security Considerations

### Critical Vulnerability: CVE-2025-9074

**Impact:** Docker Desktop vulnerability allowing local containers to access Docker Engine API via subnet (192.168.65.7:2375) without authentication.

**CVSS Score:** 9.3/10.0 (Critical)

**Mitigation:**
- **Upgrade immediately** to Docker Desktop 4.44.3 or later
- Affects Windows and macOS (Linux not vulnerable)
- Can lead to container escape and host filesystem access

> **Note:** The `192.168.65.7:2375` reference is specific to Docker Desktop on macOS/Windows. See the [Critical Security Advisories](#critical-security-advisories-december-2025) section above for platform-specific guidance on identifying your Docker Engine API endpoint.

**Additional 2025 CVEs:**
- CVE-2025-10657: Enhanced Container Isolation issues
- CVE-2025-9164: DLL hijacking in Windows installer
- CVE-2025-3911: Sensitive information exposure in logs

### Security Best Practices

#### 1. Minimize Port Exposure

```yaml
services:
  # BAD: Unnecessary external exposure
  database:
    ports:
      - "5432:5432"  # Exposed to all interfaces

  # GOOD: Internal only
  database:
    networks:
      - backend
    # No ports published
```

#### 2. Use Internal Networks

```yaml
networks:
  db_network:
    internal: true  # No external connectivity

services:
  database:
    networks:
      - db_network

  app:
    networks:
      - db_network
      - frontend
```

#### 3. Implement Network Segmentation

- **Frontend network:** Only web-facing services
- **Backend network:** Application logic and APIs
- **Data network:** Databases and caches (internal only)

#### 4. Restrict Inter-Service Communication

```yaml
# Only allow necessary connections
services:
  web:
    networks:
      - frontend  # Can't directly access database

  api:
    networks:
      - frontend
      - backend

  database:
    networks:
      - backend  # Only accessible to API
```

#### 5. Use Secrets for Sensitive Data

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  database:
    secrets:
      - db_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password
```

#### 6. Disable Unnecessary Capabilities

```yaml
services:
  app:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only add necessary capabilities
    security_opt:
      - no-new-privileges:true
```

#### 7. Run as Non-Root User

```yaml
services:
  app:
    user: "1000:1000"  # Non-root user
    read_only: true     # Read-only filesystem
    tmpfs:
      - /tmp
      - /var/run
```

#### 8. Firewall and Network Policies

```yaml
services:
  app:
    networks:
      backend:
        # Limit network bandwidth if needed
        ipv4_address: 172.28.0.10
    sysctls:
      - net.ipv4.ip_forward=0
      - net.ipv6.conf.all.forwarding=0
```

---

## Docker Compose v2 Features

### Compose v2 Status

- **Compose v1 deprecated:** July 2023 (no longer in new Docker Desktop releases)
- **Compose v2:** Rewritten in Go, integrated into Docker CLI
- **Performance:** Significantly faster with parallel execution
- **Command:** `docker compose` (not `docker-compose`)

### Version Field (Obsolete)

```yaml
# OLD (Compose v1)
version: "3.8"
services:
  ...

# NEW (Compose v2) - version field is now optional/ignored
services:
  ...
```

### Enhanced Networking Features

#### 1. IPv6 Support

```yaml
networks:
  app_net:
    enable_ipv6: true
    ipam:
      config:
        - subnet: 2001:db8::/64
          gateway: 2001:db8::1
```

#### 2. Multiple Network Attachments

```yaml
services:
  app:
    networks:
      - frontend
      - backend
      - monitoring
      - logging
```

#### 3. Network-Level Driver Options

```yaml
networks:
  custom_net:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br-custom
      com.docker.network.bridge.enable_icc: "true"
      com.docker.network.bridge.enable_ip_masquerade: "true"
```

#### 4. Profiles for Environment-Specific Services

```yaml
services:
  app:
    profiles: ["production"]

  debug_proxy:
    profiles: ["development"]
    ports:
      - "9229:9229"

# Start only production services
# docker compose --profile production up
```

### Deploy Configuration (Swarm Mode)

```yaml
services:
  api:
    deploy:
      replicas: 3
      placement:
        constraints:
          - node.role == worker
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      endpoint_mode: vip
```

---

## Common Pitfalls and Solutions

### 1. Port Already in Use

**Error:**
```text
ERROR: for app  Cannot start service app: driver failed programming external connectivity:
Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Solutions:**
```bash
# Find process using port
lsof -i :8080
# OR
netstat -tuln | grep 8080

# Change port in docker-compose.yml
ports:
  - "8081:8080"  # Use different host port

# OR bind to localhost only
ports:
  - "127.0.0.1:8080:8080"
```

### 2. Service Not Reachable by Name

**Issue:** Cannot connect to `db:5432` from application.

**Causes:**
- Services not on the same network
- Using `network_mode: host` (disables service discovery)

**Solution:**
```yaml
networks:
  app_net:

services:
  app:
    networks:
      - app_net  # Must be on same network

  db:
    networks:
      - app_net  # Must be on same network
```

### 3. Health Check Failures

**Issue:** Container marked unhealthy immediately.

**Solutions:**
- Increase `start_period` for slow-starting services
- Verify health check command works: `docker exec container_name curl http://localhost:8080/health`
- Ensure health check tool is installed (curl, wget)

### 4. Docker Socket Mounting (Security Risk)

**BAD:**
```yaml
services:
  app:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # DANGEROUS
```

**Why:** Gives container root-equivalent access to host.

**Alternative:** Use Docker-in-Docker or dedicated orchestration services.

### 5. Exposed Database to Internet

**BAD:**
```yaml
services:
  postgres:
    ports:
      - "5432:5432"  # Exposed to 0.0.0.0
```

**GOOD:**
```yaml
services:
  postgres:
    networks:
      - backend
    # No ports section - internal only

  # OR if host access needed
  postgres:
    ports:
      - "127.0.0.1:5432:5432"  # Localhost only
```

### 6. Network Name Conflicts

**Issue:** `network with name "my_network" already exists`

**Solutions:**
```yaml
networks:
  my_network:
    external: true  # Use existing network
    name: my_network

# OR remove conflicting network
# docker network rm my_network
```

---

## Quick Reference Checklist

### Security Checklist
- [ ] Databases bound to 127.0.0.1 or no host port
- [ ] Internal networks used for sensitive services
- [ ] Secrets used instead of environment variables
- [ ] Services run as non-root users
- [ ] Docker Desktop updated to 4.44.3+ (CVE-2025-9074)
- [ ] Unnecessary ports not exposed
- [ ] Network segmentation implemented (frontend/backend/data)

### Performance Checklist
- [ ] Health checks configured for all services
- [ ] `depends_on` with health conditions used
- [ ] Appropriate `start_period` set for slow services
- [ ] Resource limits configured
- [ ] Parallel startup enabled (Docker Compose v2 default)

### Networking Checklist
- [ ] Custom networks defined (not default bridge)
- [ ] Services on appropriate networks only
- [ ] DNS-based service discovery used
- [ ] `internal: true` for data layer networks
- [ ] Host network mode avoided unless necessary

---

## Additional Resources

### Docker Official Documentation
- [Docker Compose Networking](https://docs.docker.com/compose/how-tos/networking/)
- [Port Publishing and Mapping](https://docs.docker.com/engine/network/port-publishing/)
- [Docker Security Announcements](https://docs.docker.com/security/security-announcements/)
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/)
- [Docker Compose Release Notes](https://github.com/docker/compose/releases)

### Security Advisories
- [CVE-2025-9074: Docker Desktop Security Advisory](https://docs.docker.com/security/security-announcements/)
- [CVE-2025-62725: Docker Compose Path Traversal (GHSA-gv8h-7v7w-r22q)](https://github.com/docker/compose/security/advisories/GHSA-gv8h-7v7w-r22q)
- [OWASP Docker Security - Network Segmentation](https://github.com/OWASP/Docker-Security/blob/main/D03%20-%20Network%20Segmentation%20and%20Firewalling.md)

---

**Document Version:** 1.0
**Last Updated:** December 2025
**Maintained by:** PMOVES.AI Platform Team