Audit Tailscale ACLs: compare live policy against repo definition.

## Usage

Run this command to:
- Verify live Tailscale ACLs match `pmoves/configs/tailscale-acl-policy.json`
- Detect drift between repo policy and applied policy
- Review tag assignments on nodes
- Before enrolling new devices or changing access rules

## Implementation

### Step 1: Fetch live ACL policy

```bash
curl -fsS \
  -u "${TAILSCALE_API_KEY}:" \
  -H "Accept: application/hujson" \
  "https://api.tailscale.com/api/v2/tailnet/-/acl"
```

**Required:** `TAILSCALE_API_KEY` environment variable.

### Step 2: Compare with repo policy

Read the repo definition:
```
pmoves/configs/tailscale-acl-policy.json
```

Compare key sections:
- `tagOwners` — same tags defined?
- `acls` — same rules (src → dst mappings)?
- `ssh` — same SSH access rules?
- `nodeAttrs` — same attributes?
- `autoApprovers` — same exit node / route approvers?

### Step 3: Check node tag assignments

```bash
curl -fsS \
  -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices" | \
  jq '.devices[] | {hostname: .hostname, tags: .tags, os: .os}'
```

Report which nodes have which tags (hostnames only):

| Hostname | Tags | Expected Tags |
|----------|------|---------------|
| (name) | (actual) | (from topology docs) |

Flag any mismatches.

### Step 4: Report

- **ALIGNED:** Live policy matches repo — no action needed
- **DRIFT DETECTED:** List specific differences with recommendations
- **UNTAGGED NODES:** Nodes without tags that should have them
- **EXTRA RULES:** Rules in live policy not in repo (potential manual changes)

### Step 5: Policy update (if needed)

If drift is detected, the fix is to apply the repo policy:
```bash
# Fetch current ETag first
ETAG=$(curl -fsS -u "${TAILSCALE_API_KEY}:" -I \
  "https://api.tailscale.com/api/v2/tailnet/-/acl" | grep -i etag | awk '{print $2}')

# Apply repo policy with If-Match (prevents race conditions)
curl -fsS -X POST \
  -u "${TAILSCALE_API_KEY}:" \
  -H "Content-Type: application/json" \
  -H "If-Match: ${ETAG}" \
  -d @pmoves/configs/tailscale-acl-policy.json \
  "https://api.tailscale.com/api/v2/tailnet/-/acl"
```

**This is a destructive operation — always confirm with user before applying.**

## Security

- NEVER output raw Tailscale IPs or device IDs
- `TAILSCALE_API_KEY` is an admin credential — never display
- Policy updates use `If-Match` to prevent overwriting concurrent changes
- Always fetch before writing — never blind-apply

## Known Road

```
make -C pmoves fleet-stale-audit   # Includes ACL check
```

## Related

- `/fleet:status` — Quick fleet overview
- `/fleet:stale-nodes` — Clean up stale nodes
- `pmoves/configs/tailscale-acl-policy.json` — Repo ACL definition
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — Full runbook
- `pmoves/docs/API_Docs/tailscale-api.yaml` — Tailscale API schema
