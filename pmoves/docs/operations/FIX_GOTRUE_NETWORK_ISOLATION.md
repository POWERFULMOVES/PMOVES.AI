# Fix GoTrue Network Isolation (Docker Compose Topology)

## Problem Analysis (2026-04-24)

**Symptom:** `pmoves-supabase-gotrue-1` enters restart loop with DNS resolution errors:

```text
hostname resolving error (lookup supabase-db on 127.0.0.11:53: server misbehaving)
failed to connect to database: connection error
```

**Pattern:**
- GoTrue fails to resolve `supabase-db` hostname even when database is healthy
- Other Supabase services on the same network (Kong, PostgREST) have the same issue
- Services on `pmoves_data` network (Pooler, Realtime) connect successfully
- Error is specific to services on `pmoves_api` network trying to reach the database

## Root Cause

**Network Topology Mismatch:**

```
pmoves-supabase-db-1       → pmoves_data network only
pmoves-supabase-gotrue-1    → pmoves_api network only
pmoves-supabase-postgrest-1 → pmoves_api network only
pmoves-supabase-pooler-1    → pmoves_data network only ✓
```

GoTrue, PostgREST, Storage, and other API services are on `pmoves_api` network,
but the database is ONLY on `pmoves_data` network. Docker Compose networks
are isolated - containers on different bridge networks cannot reach each other
by service name, even when they're in the same compose file.

**Why Pooler Works:**
Pooler is on `pmoves_data` (same network as database), so it can resolve
`supabase-db` successfully. GoTrue/PostgREST are on `pmoves_api` and cannot.

**Docker's Embedded DNS Confusion:**
The error message says "127.0.0.11:53: server misbehaving" because Docker's
embedded DNS on `pmoves_api` network doesn't have a record for `supabase-db`
(that service only exists on `pmoves_data` network). This is NOT a DNS server
failure - it's a network topology problem.

## Solution Options

### Option 1: Add Database to pmoves_api Network (RECOMMENDED)

Add the database to BOTH networks so it's accessible from all services:

```yaml
# In docker-compose.yml under supabase-db:
networks:
  - pmoves_data
  - pmoves_api  # Services on pmoves_api need DB access
```

**Pros:**
- Single-line fix
- Maintains service name connection strings
- All services can reach database without code changes
- Follows Docker Compose networking best practices (multi-network services)

**Cons:**
- None significant - database is now accessible from both networks (desired behavior)

### Option 2: Move API Services to pmoves_data Network

Move GoTrue, PostgREST, Storage, etc. to `pmoves_data` network:

```yaml
# In docker-compose.yml for each api service:
networks:
  - pmoves_data  # Instead of pmoves_api
```

**Pros:**
- All database clients on same network as database

**Cons:**
- Breaks API tier isolation (api services should be on api network)
- Requires changes to multiple services
- May affect Kong → PostgREST routing
- Architectural regression - API and data tiers become conflated

### Option 3: Use External DNS Resolvers (DO NOT USE)

Configure GoTrue with external DNS:

```yaml
dns:
  - 1.1.1.1
  - 8.8.8.8
```

**Why This Is Wrong:**
- The external DNS fix in SUPABASE_OPERATIONS.md is for Edge Functions
  trying to reach EXTERNAL hostnames (deno.land), NOT internal services
- Docker embedded DNS is required for internal service discovery
- External DNS resolvers cannot resolve Docker service names
- This fix does NOT help with network isolation problems

**Historical Note:**
This approach was attempted on 2026-04-24 and made the problem worse,
breaking PostgREST and other services. The documentation was corrected
to clarify that external DNS is for EXTERNAL hostname resolution only.

### Option 4: Hardcoded IP Address (DO NOT USE)

Replace service name with IP in connection string:

```yaml
GOTRUE_DB_DATABASE_URL=postgres://...@172.30.1.3:5432/...
```

**Pros:**
- Bypasses DNS entirely

**Cons:**
- IP addresses change across Docker daemon restarts
- Breaks Docker Compose service discovery
- Anti-pattern - violates containerization best practices
- Requires manual IP lookup and updates

## Recommended Fix

**Implement Option 1 (Add Database to pmoves_api Network)**

### Changes to `pmoves/docker-compose.yml`

**Before (line 576-577):**
```yaml
networks:
  - pmoves_data
```

**After:**
```yaml
networks:
  - pmoves_data
  - pmoves_api  # Services on pmoves_api need DB access
```

### Why This Works

Docker Compose services can be attached to multiple networks. When the database
is on both `pmoves_data` and `pmoves_api`:

1. **Services on pmoves_data** (Pooler, Realtime) reach DB via `pmoves_data`
2. **Services on pmoves_api** (GoTrue, PostgREST, Storage) reach DB via `pmoves_api`
3. **Docker's embedded DNS** resolves `supabase-db` on both networks correctly
4. **No code changes required** - connection strings remain `supabase-db:5432`

This is the canonical Docker Compose pattern for multi-tier architectures where
a data layer service needs to be accessible from multiple isolated networks.

## Implementation Steps

1. **Edit docker-compose.yml**
   - Locate `supabase-db` service definition
   - Add `pmoves_api` to the networks list
   - Comment: "# Services on pmoves_api need DB access"

2. **Restart Supabase stack**
   ```bash
   make -C pmoves supa-restart
   ```

3. **Verify GoTrue health**
   ```bash
   docker logs pmoves-supabase-gotrue-1 --tail 30
   # Should show: "GoTrue migrations applied successfully"
   # Should show: "GoTrue API started on: 0.0.0.0:9999"
   ```

4. **Test database connectivity**
   ```bash
   docker exec pmoves-supabase-gotrue-1 wget -O- http://localhost:9999/health
   # Should return: {"version":"...","database":{"connected":true},...}
   ```

5. **Verify other API services**
   ```bash
   docker ps --filter "name=supabase" --format "table {{.Names}}\t{{.Status}}"
   # GoTrue, PostgREST, Storage should all be healthy
   ```

## Testing Checklist

- [ ] GoTrue container starts without restart loop
- [ ] GoTrue logs show "GoTrue migrations applied successfully"
- [ ] GoTrue logs show "GoTrue API started on: 0.0.0.0:9999"
- [ ] Database connection test succeeds (`"database":{"connected":true}`)
- [ ] Healthcheck returns HTTP 200
- [ ] PostgREST can reach database via service name
- [ ] Storage can reach database via service name
- [ ] Pooler still works (on pmoves_data network)
- [ ] Realtime still works (on pmoves_data network)
- [ ] Kong can reach GoTrue and PostgREST via service names

## Related Documentation

- `SUPABASE_OPERATIONS.md` - Kong OOM, Edge Functions DNS, Realtime key sizing
- `FIX_RUNNER_RESTART_LOOP.md` - Example documentation pattern
- Docker Compose Networking: https://docs.docker.com/compose/networking/
- Docker Multi-Host Networking: https://docs.docker.com/network/network-tutorial-host-standards/

## Network Topology Reference

**Correct PMOVES Supabase Network Layout:**

| Service | Networks | Purpose |
|---------|-----------|---------|
| `supabase-db` | `pmoves_data`, `pmoves_api` | Data layer (accessible from both) |
| `supabase-gotrue` | `pmoves_api` | Auth API tier |
| `supabase-postgrest` | `pmoves_api` | REST API tier |
| `supabase-storage` | `pmoves_api` | Storage API tier |
| `supabase-kong` | `pmoves_api` | API Gateway |
| `supabase-pooler` | `pmoves_data` | Connection pooler (data tier) |
| `supabase-realtime` | `pmoves_api` | Realtime API tier |
| `supabase-meta` | `pmoves_data` | Metadata service |
| `supabase-analytics` | `pmoves_data` | Analytics backend |

**Key Principle:**
- `pmoves_api`: API services that need to be behind Kong gateway
- `pmoves_data`: Backend services that work directly with data
- Database must be on BOTH networks because all services need it

## Common Mistakes

### Mistake 1: Using External DNS for Internal Services

Applying the Edge Functions external DNS fix to GoTrue:

```yaml
# WRONG - This is for EXTERNAL hostname resolution (deno.land)
dns:
  - 1.1.1.1
  - 8.8.8.8
```

**Why It's Wrong:**
- Edge Functions fix is for reaching EXTERNAL hosts (deno.land) from containers
- Internal Docker service discovery requires Docker's embedded DNS
- External resolvers cannot resolve Docker service names
- This does NOT fix network isolation problems

### Mistake 2: Hardcoded IP Addresses

Using IP addresses instead of service names:

```yaml
# WRONG - IP addresses change, breaks service discovery
GOTRUE_DB_DATABASE_URL=postgres://...@172.30.1.3:5432/...
```

**Why It's Wrong:**
- IP addresses are dynamic (change on container restart)
- Breaks Docker Compose service discovery
- Makes compose files non-portable
- Anti-pattern - violates containerization principles

### Mistake 3: Network Tier Confusion

Moving all services to `pmoves_data` network:

```yaml
# WRONG - Breaks API tier isolation
networks:
  - pmoves_data  # Everything on data network
```

**Why It's Wrong:**
- Conflates API tier and data tier
- Makes Kong (on pmoves_api) unable to reach PostgREST
- Architectural regression - tiers should be isolated
- Future network policies become impossible

## Historical Context

**Session 2026-04-24:**
- Initial symptom: GoTrue crash-loop with DNS errors
- Incorrect hypothesis: Docker embedded DNS failure on Windows
- Wrong fix attempted: External DNS resolvers (1.1.1.1, 8.8.8.8)
- Result: Made problem worse, broke PostgREST and other services
- Root cause identified: Network isolation (DB on pmoves_data, GoTrue on pmoves_api)
- Correct fix applied: Added database to pmoves_api network
- Result: All services healthy, GoTrue connecting successfully

**Key Learning:**
Docker's embedded DNS error "server misbehaving" doesn't always mean DNS is broken.
It often means the hostname doesn't exist on the current network - a network topology
problem, not a DNS resolver problem.

## Validation Against Docker Compose Best Practices

This fix follows official Docker Compose networking patterns:

1. **Multi-Network Services**: Services can belong to multiple networks
   - Documented: https://docs.docker.com/compose/networking/#specify-custom-networks
2. **Network Isolation**: Different tiers can be on different networks
   - API services on pmoves_api, data services on pmoves_data
3. **Shared Services**: Database is on multiple networks to serve all tiers
   - Standard pattern for multi-tier architectures

No official Docker documentation prohibits attaching a service to multiple networks.
This is the recommended pattern for services that need to be accessible from isolated
network tiers.

## Platform-Specific Notes

**Linux/Mac:**
- Same network topology applies
- Fix is cross-platform compatible
- No platform-specific changes needed

**Windows Docker Desktop:**
- Same fix applies
- No Windows-specific DNS issues (the initial error was network isolation, not DNS)
- External DNS still needed for Edge Functions reaching deno.land (documented separately)

**Production (Linux Servers):**
- Network isolation is production best practice
- Keep pmoves_api/pmoves_data separation
- Database on both networks is standard pattern
