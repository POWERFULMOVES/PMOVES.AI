# Topic 5: Self-Hosted Runner Registration with GitHub App Tokens

**Research Series: GitHub App Token Usage (5 of 5)**
**Date:** 2026-04-23
**Focus:** Complete technical reference for registering and managing GitHub Actions self-hosted runners using GitHub App authentication — covering single runners, scale sets, ARC (Actions Runner Controller), API endpoints, token lifecycle, and automation patterns.

---

## A) Registering Self-Hosted Runners Using GitHub App Tokens — Complete Authentication Flow

The core authentication flow for using a GitHub App to register self-hosted runners follows the same three-step pattern established in prior topics in this series (JWT → installation token → API call):

### Flow Overview

```
1. Generate JWT from PEM private key (client assertion)
   ├── Uses RS256 algorithm
   ├── Issuer: GitHub App ID
   ├── Subject: GitHub App ID
   ├── Audience: https://github.com/apps
   ├── Expiry: 10 minutes max (recommend 5 min)
   └── Signed with App's private key

2. Exchange JWT for Installation Access Token
   ├── POST /app/installations/{installation_id}/access_tokens
   ├── Auth: Bearer <JWT>
   └── Returns: installation_access_token (1-hour TTL)

3. Use Installation Token to Call Registration-Token Endpoint
   ├── POST /repos/{owner}/{repo}/actions/runners/registration-token
   ├──   OR /orgs/{org}/actions/runners/registration-token
   ├──   OR /enterprises/{enterprise}/actions/runners/registration-token
   ├── Auth: Bearer <installation_access_token>
   └── Returns: { "token": "...", "expires_at": "..." } (1-hour TTL)

4. Use Registration Token with ./config.sh
   ├── ./config.sh --url <url> --token <registration_token> --unattended
   └── Runner registers with GitHub Actions service
```

### Why GitHub App Instead of PAT for Runner Registration

| Aspect | PAT | GitHub App |
|--------|-----|------------|
| Token lifetime | Configurable (30/60/90 days, or never) | Installation token: 1 hour (auto-rotated) |
| Scope | Tied to a user account | Tied to an installation (org/repo) |
| Revocation | Manual per token | Revoke installation or uninstall app instantly |
| API rate limit | 5,000 req/hr (authenticated) | 10,000 req/hr (org-owned Enterprise Cloud apps) |
| Credential rotation | Manual (regenerate PAT, update all consumers) | Automatic (ARC handles JWT → installation token cycle) |
| Audit trail | Tied to user who created PAT | Tied to App identity, visible in audit log |
| Offboarding | Must find and revoke every PAT | Uninstall app = immediate revocation everywhere |

### Critical Distinction

The `config.sh` script does NOT know or care whether the registration token was obtained via PAT or GitHub App. It receives a short-lived registration token and uses it for a one-time registration handshake with GitHub. The authentication method choice is entirely upstream — it only affects how you obtain the registration token from the API.

---

## B) Runner Registration Token API Endpoints — Full Reference

### Classic Single Runner Registration Token Endpoints

These endpoints return a token used with `config.sh` to register a single self-hosted runner.

#### Repository-Level

```
POST /repos/{owner}/{repo}/actions/runners/registration-token
```

#### Organization-Level

```
POST /orgs/{org}/actions/runners/registration-token
```

#### Enterprise-Level

```
POST /enterprises/{enterprise}/actions/runners/registration-token
```

### Request Format (All Three)

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token
```

### Response Format (All Three)

```json
{
  "token": "AAAXXX4UVEAL3YLMZ3DIMUIC",
  "expires_at": "2023-08-03T15:55:21.860+02:00"
}
```

### Auth Methods Accepted

| Auth Method | Repo Endpoint | Org Endpoint | Enterprise Endpoint |
|-------------|---------------|--------------|---------------------|
| PAT (classic, with `repo` scope) | Yes | Yes (needs `admin:org`) | Yes (needs `manage_runners:enterprise`) |
| Fine-grained PAT | Yes | No | No |
| GitHub App installation token | Yes | Yes | **No** (not supported for enterprise-level runners) |
| `GITHUB_TOKEN` (workflow) | No (not available in workflow context for registration) | No | No |

> **Critical limitation:** GitHub App authentication is NOT supported for enterprise-level runner registration. This is a documented GitHub limitation — enterprise runners must use PAT authentication.

### Scale Set Registration Token Endpoints (Newer API)

Scale sets use a different API group and a different authentication/registration model. Rather than a simple registration-token endpoint, scale sets use the **Runner Scale Set APIs** which handle registration, JIT configuration, and job dispatch in an integrated flow.

#### Create/Get Runner Scale Set

```
POST /repos/{owner}/{repo}/actions/runner-scale-sets
POST /orgs/{org}/actions/runner-scale-sets
POST /enterprises/{enterprise}/actions/runner-scale-sets
```

#### Get Runner Scale Set (retrieve ID)

```
GET /repos/{owner}/{repo}/actions/runner-scale-sets/{scale_set_id}
GET /orgs/{org}/actions/runner-scale-sets/{scale_set_id}
GET /enterprises/{enterprise}/actions/runner-scale-sets/{scale_set_id}

```

#### Generate JIT Configuration

```
POST /repos/{owner}/{repo}/actions/runner-scale-sets/{scale_set_id}/runner-jit-config
POST /orgs/{org}/actions/runner-scale-sets/{scale_set_id}/runner-jit-config
POST /enterprises/{enterprise}/actions/runner-scale-sets/{scale_set_id}/runner-jit-config
```

Request body:
```json
{
  "name": "runner-name",
  "runnerGroupId": 1,
  "labels": ["self-hosted", "linux", "x64"]
}
```

Response: Returns a JIT config blob (base64-encoded) that contains a temporary registration token embedded within it.

#### Message Queue (Long-Poll for Jobs)

```
POST /repos/{owner}/{repo}/actions/runner-scale-sets/{scale_set_id}/message-routine
POST /orgs/{org}/actions/runner-scale-sets/{scale_set_id}/message-routine
POST /enterprises/{enterprise}/actions/runner-scale-sets/{scale_set_id}/message-routine
```

This is the long-poll endpoint used by the ARC listener pod to receive job availability messages.

### Scale Set Auth Methods

| Auth Method | Repo | Org | Enterprise |
|-------------|------|-----|------------|
| PAT | Yes | Yes | Yes |
| GitHub App installation token | Yes | Yes | **No** |

> **Same enterprise limitation applies** to scale sets as to classic runners — GitHub App auth is not supported at the enterprise level.

---

## C) Single Runners: Step-by-Step Registration via GitHub App

### Prerequisites

- GitHub App created with `administration:write` repository permission (or `self-hosted_runners` organization permission)
- App installed on the target repository or organization
- App's PEM private key downloaded
- App ID and Installation ID noted

### Step 1: Generate JWT from PEM Private Key

```bash
#!/bin/bash
# generate_jwt.sh
APP_ID="123456"
PRIVATE_KEY_PATH="./private-key.pem"

# JWT payload
NOW=$(date +%s)
EXPIRY=$((NOW + 300))  # 5 minutes

HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
PAYLOAD=$(echo -n "{\"iat\":${NOW},\"exp\":${EXPIRY},\"iss\":${APP_ID}}" | base64 -w0 | tr '+/' '-_' | tr -d '=')

HEADER_PAYLOAD="${HEADER}.${PAYLOAD}"
SIGNATURE=$(openssl dgst -sha256 -sign "${PRIVATE_KEY_PATH}" <(echo -n "${HEADER_PAYLOAD}") | base64 -w0 | tr '+/' '-_' | tr -d '=')

JWT="${HEADER_PAYLOAD}.${SIGNATURE}"
echo "${JWT}"
```

### Step 2: Exchange JWT for Installation Access Token

```bash
INSTALLATION_ID="654321"
JWT=$(bash generate_jwt.sh)

RESPONSE=$(curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${JWT}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens")

INSTALLATION_TOKEN=$(echo "${RESPONSE}" | jq -r '.token')
echo "Installation token: ${INSTALLATION_TOKEN:0:10}..."
```

Response:
```json
{
  "token": "ghs_xxxxxxxxxxxxxxxxxxxx",
  "expires_at": "2023-08-03T16:00:00Z",
  "permissions": {
    "administration": "write",
    "actions": "read"
  },
  "repository_selection": "selected",
  "repositories": [
    {
      "id": 12345,
      "name": "my-repo",
      "full_name": "owner/my-repo",
      "private": false
    }
  ]
}
```

### Step 3: Get Registration Token Using Installation Token

**For a repository runner:**

```bash
OWNER="myorg"
REPO="my-repo"

RESPONSE=$(curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token")

REGISTRATION_TOKEN=$(echo "${RESPONSE}" | jq -r '.token')
EXPIRES_AT=$(echo "${RESPONSE}" | jq -r '.expires_at')

echo "Registration token: ${REGISTRATION_TOKEN}"
echo "Expires at: ${EXPIRES_AT}"
```

**For an organization runner:**

```bash
ORG="myorg"

RESPONSE=$(curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/orgs/${ORG}/actions/runners/registration-token")

REGISTRATION_TOKEN=$(echo "${RESPONSE}" | jq -r '.token')
```

### Step 4: Configure Runner with Registration Token

```bash
./config.sh \
  --url "https://github.com/${OWNER}/${REPO}" \
  --token "${REGISTRATION_TOKEN}" \
  --name "my-app-registered-runner" \
  --labels "self-hosted,linux,x64,app-auth" \
  --unattended \
  --replace
```

Output:
```
# Authentication
√ Connected to GitHub

# Runner Registration
√ Runner successfully added
√ Runner connection is good

# Runner settings
√ Settings Saved.
```

### Step 5: Start the Runner

```bash
./run.sh
```

### Complete One-Liner (for scripting)

```bash
#!/bin/bash
set -euo pipefail

APP_ID="123456"
INSTALLATION_ID="654321"
PRIVATE_KEY_PATH="./private-key.pem"
OWNER="myorg"
REPO="my-repo"
RUNNER_NAME="app-runner-$(hostname)"

# Step 1: Generate JWT
NOW=$(date +%s)
EXPIRY=$((NOW + 300))
HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
PAYLOAD=$(echo -n "{\"iat\":${NOW},\"exp\":${EXPIRY},\"iss\":${APP_ID}}" | base64 -w0 | tr '+/' '-_' | tr -d '=')
HEADER_PAYLOAD="${HEADER}.${PAYLOAD}"
SIGNATURE=$(openssl dgst -sha256 -sign "${PRIVATE_KEY_PATH}" <(echo -n "${HEADER_PAYLOAD}") | base64 -w0 | tr '+/' '-_' | tr -d '=')
JWT="${HEADER_PAYLOAD}.${SIGNATURE}"

# Step 2: Get installation token
INSTALLATION_TOKEN=$(curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${JWT}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens" | jq -r '.token')

# Step 3: Get registration token
REG_TOKEN=$(curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token" | jq -r '.token')

# Step 4: Configure and start
./config.sh \
  --url "https://github.com/${OWNER}/${REPO}" \
  --token "${REG_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "self-hosted,linux,x64" \
  --unattended --replace

./run.sh
```

---

## D) Scale Sets: Configuration Using GitHub App Tokens

### The Runner Scale Set APIs

Scale sets use a fundamentally different API model than classic single runners. Instead of a simple registration-token endpoint, scale sets use a multi-phase API:

1. **Scale Set Registration:** Create a scale set entity on GitHub's side
2. **JIT Configuration:** Per-runner, generate a just-in-time config containing an embedded temporary token
3. **Message Queue:** Long-poll connection for job dispatch

### How ARC Communicates with These APIs

ARC's controller manages three Kubernetes CRDs that map to these API phases:

| Kubernetes CRD | API Phase | Description |
|----------------|-----------|-------------|
| `AutoscalingRunnerSet` | Scale Set Registration | Registers/updates the scale set on GitHub |
| `EphemeralRunner` | JIT Configuration | Requests JIT config for each runner pod |
| `AutoscalingListener` | Message Queue | Long-polls GitHub for job messages |

**Registration flow in ARC (from source code):**

| Step | Action | Code Location |
|------|--------|---------------|
| 1 | Resolve credentials, create GitHub client | `autoscalingrunnerset_controller.go:397-402` |
| 2 | Build `actions.RunnerScaleSet` request | `autoscalingrunnerset_controller.go:403-415` |
| 3 | Call `CreateRunnerScaleSet` API | `autoscalingrunnerset_controller.go:416-424` |
| 4 | Store scale set ID in annotations | `autoscalingrunnerset_controller.go:426-453` |

**JIT config generation flow:**

| Step | Action | Code Location |
|------|--------|---------------|
| 1 | EphemeralRunner created by EphemeralRunnerSet | `ephemeralrunner_controller.go:183-216` |
| 2 | Call `generate-jitconfig` API with runner name/labels | `ephemeralrunner_controller.go:560-626` |
| 3 | Handle `AgentExistsException` by removing stale runner | `ephemeralrunner_controller.go:590-625` |
| 4 | Pass JIT config to runner pod as `RUNNER_JITCONFIG` env var | — |

### The runner-scale-set-manifest Endpoint

The JIT config endpoint returns a base64-encoded configuration blob:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/orgs/${ORG}/actions/runner-scale-sets/${SCALE_SET_ID}/runner-jit-config" \
  -d '{
    "name": "ephemeral-runner-abc123",
    "runnerGroupId": 1,
    "labels": ["self-hosted", "linux", "x64", "my-scale-set"]
  }'
```

Response:
```json
{
  "encodedJitConfig": "base64-encoded-config-blob..."
}
```

The runner pod decodes this and uses it for registration — no separate `config.sh` step is needed. The JIT config contains the embedded temporary registration token, URL, and all runner settings.

### Key Difference: No config.sh for Scale Set Runners

Scale set runners do NOT use `config.sh`. Instead:
- ARC generates a JIT config via the API
- The JIT config is passed to the runner as an environment variable (`RUNNER_JITCONFIG`) or a file
- The runner binary reads the JIT config directly
- This eliminates the need to pass any credentials (PAT or App tokens) to runner pods

---

## E) ARC (Actions Runner Controller) Full Configuration with GitHub App Credentials

### GitHubConfigSecret: Required Fields

```yaml
githubConfigSecret:
  # NOTE: IDs MUST be strings — use quotes!
  # The github_app_id can be the numeric app_id OR the client_id
  github_app_id: "123456"
  github_app_installation_id: "654321"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF...(full key)
    ...
    -----END RSA PRIVATE KEY-----
```

### auth-mode Setting

ARC does NOT use an explicit `auth-mode` field in the Helm values. Instead, it **auto-detects** the authentication method based on which fields are present in `githubConfigSecret`:

| Fields Present | Detected Auth Mode | Implementation Class |
|----------------|-------------------|---------------------|
| `github_token` | PAT | `oauth2.StaticTokenSource` |
| `github_app_id` + `github_app_installation_id` + `github_app_private_key` | GitHub App | `ghinstallation.Transport` |
| (pre-defined secret reference) | Determined by secret contents | Either of above |

This logic is in `github/github.go:24-37` of the ARC source code.

### Runner Scale Set Listener Configuration

The listener is a long-running pod that maintains a persistent HTTPS connection to GitHub:

```yaml
listenerTemplate:
  spec:
    containers:
      # IMPORTANT: Do NOT change the container name — it must be "listener"
      # If renamed, ARC treats it as a sidecar and won't apply listener config
      - name: listener
        securityContext:
          runAsUser: 1000
        resources:
          limits:
            cpu: "1"
            memory: 1Gi
          requests:
            cpu: "1"
            memory: 1Gi
```

### Complete Helm Values YAML Example (GitHub App Auth)

```yaml
# values-app-auth.yaml
# ARC Runner Scale Set with GitHub App authentication

## Target: Organization-level scale set
githubConfigUrl: "https://github.com/myorg"

## GitHub App authentication (auto-detected by ARC)
githubConfigSecret:
  github_app_id: "123456"
  github_app_installation_id: "654321"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF...(replace with full PEM key)
    ...
    -----END RSA PRIVATE KEY-----

## Scale set settings
runnerScaleSetName: "my-org-scale-set"
runnerGroup: "default"
maxRunners: 10
minRunners: 0

## Proxy settings (optional)
# proxy:
#   http:
#     url: http://proxy.corp.com:8080
#     credentialSecretRef: proxy-auth
#   https:
#     url: http://proxy.corp.com:8443
#   noProxy:
#     - localhost
#     - 10.0.0.0/8

## Listener pod template
listenerTemplate:
  spec:
    containers:
      - name: listener
        securityContext:
          runAsUser: 1000
        resources:
          limits:
            cpu: "1"
            memory: 1Gi
          requests:
            cpu: 500m
            memory: 512Mi

## Runner pod template
template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        command: ["/home/runner/run.sh"]
        env:
          - name: RUNNER_DEBUG
            value: "1"
        resources:
          limits:
            cpu: "2"
            memory: 4Gi
          requests:
            cpu: "1"
            memory: 2Gi
        securityContext:
          runAsUser: 1000
    tolerations:
      - key: "github-runner"
        effect: "NoSchedule"
        operator: "Exists"
    nodeSelector:
      runner-type: "github-actions"

## Container mode: "dind" (Docker-in-Docker) or "kubernetes"
# containerMode: "kubernetes"

## GitHub Server TLS (for GHES)
# githubServerTLS:
#   certificateFrom:
#     configMapKeyRef:
#       name: github-ca-cert
#       key: ca.crt
#   runnerMountPath: /usr/local/share/ca-certificates/
```

### Pre-Defined Secret Alternative (Recommended for Production)

Instead of embedding the private key in values.yaml, create the secret separately:

```bash
# Option A: From literal values
kubectl create secret generic arc-github-app-secret \
  --namespace=arc-runners \
  --from-literal=github_app_id=123456 \
  --from-literal=github_app_installation_id=654321 \
  --from-literal=github_app_private_key='-----BEGIN RSA PRIVATE KEY-----
MIIEow...
-----END RSA PRIVATE KEY-----'

# Option B: From file (cleaner for large keys)
kubectl create secret generic arc-github-app-secret \
  --namespace=arc-runners \
  --from-literal=github_app_id=123456 \
  --from-literal=github_app_installation_id=654321 \
  --from-file=github_app_private_key=./private-key.pem
```

Then reference it in values.yaml:

```yaml
githubConfigUrl: "https://github.com/myorg"
githubConfigSecret: arc-github-app-secret
maxRunners: 10
minRunners: 0
```

---

## F) config.sh Script Flags for Registering a Runner

### Core Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--url` | GitHub repository/organization URL (required) | `--url https://github.com/org/repo` |
| `--token` | Registration token (required, or use `--jitconfig`) | `--token AAAXXX4UVEAL3YLMZ3` |
| `--name` | Custom runner name (default: hostname) | `--name my-runner-01` |
| `--labels` | Comma-separated labels for job routing | `--labels self-hosted,linux,x64` |
| `--unattended` | Run without interactive prompts | `--unattended` |
| `--replace` | Replace existing runner with same name | `--replace` |

### Runner Group Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--runnergroup` | Assign to a specific runner group | `--runnergroup my-custom-group` |

### Ephemeral Runner Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--ephemeral` | Register as ephemeral (auto-removed after 1 job) | `--ephemeral` |
| `--jitconfig` | Path to JIT config file (for scale set runners) | `--jitconfig /path/to/jitconfig.json` |

### Update and Work Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--disableupdate` | Disable automatic runner updates | `--disableupdate` |
| `--work` | Working directory for runner | `--work /home/runner/_work` |

### Service Installation Flags (Linux)

| Flag | Description | Example |
|------|-------------|---------|
| `--user` | System user to run the runner service | `--user runner` |
| `--service` | Install as a systemd service | (implied with `svc.sh install`) |

### How App Token Differs from PAT When Passed to config.sh

**It doesn't differ at all.** The `config.sh` script receives a registration token — a short-lived opaque string returned by the registration-token API endpoint. The script has no knowledge of whether that token was obtained via:

- A PAT (classic or fine-grained)
- A GitHub App installation token
- The GitHub web UI
- The `gh` CLI

The registration token is the same format regardless of upstream auth method. The auth method only affects step 3 (obtaining the registration token from the API), not step 4 (passing it to `config.sh`).

### Typical config.sh Invocations

```bash
# Standard registration
./config.sh \
  --url https://github.com/myorg/myrepo \
  --token AAAXXX4UVEAL3YLMZ3 \
  --name my-runner \
  --labels self-hosted,linux,x64 \
  --unattended

# Ephemeral runner (auto-removed after job)
./config.sh \
  --url https://github.com/myorg/myrepo \
  --token AAAXXX4UVEAL3YLMZ3 \
  --name ephemeral-$(cat /proc/sys/kernel/random/uuid) \
  --labels self-hosted,linux,x64 \
  --ephemeral \
  --unattended

# Organization runner with custom group
./config.sh \
  --url https://github.com/myorg \
  --token AAAXXX4UVEAL3YLMZ3 \
  --name org-runner-01 \
  --labels self-hosted,linux,x64 \
  --runnergroup "ci-runners" \
  --unattended

# Replace existing runner
./config.sh \
  --url https://github.com/myorg/myrepo \
  --token AAAXXX4UVEAL3YLMZ3 \
  --name my-runner \
  --replace \
  --unattended
```

---

## G) ARC's GitHub App Authentication Mode vs PAT Mode

### What Changes in Helm Values

**PAT mode:**
```yaml
githubConfigSecret:
  github_token: "ghp_xxxxxxxxxxxxxxxxxxxx"
```

**GitHub App mode:**
```yaml
githubConfigSecret:
  github_app_id: "123456"
  github_app_installation_id: "654321"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    ...
    -----END RSA PRIVATE KEY-----
```

That's it. No other Helm value changes are needed. ARC auto-detects the auth mode from which fields are present.

### How ARC Auto-Rotates App Tokens

ARC uses the `github.com/bradleyfalzon/ghinstallation/v2` library, which implements `http.RoundTripper`. The rotation flow:

```
1. ARC controller starts up
2. Reads github_app_id, github_app_installation_id, github_app_private_key from secret
3. Creates ghinstallation.Transport with these credentials
4. On FIRST API call:
   a. Generates JWT from private key (RS256, 5-min expiry)
   b. POST /app/installations/{id}/access_tokens with JWT
   c. Receives installation_access_token (1-hour TTL)
   d. Caches the installation token
   e. Uses it for the API call
5. On SUBSEQUENT API calls:
   a. Checks if cached installation token is still valid
   b. If valid → use cached token (no API call needed)
   c. If expired → regenerate JWT → get new installation token → cache it
6. This repeats automatically, forever
```

**Code-level details:**
- File-based key: `ghinstallation.NewKeyFromFile` (`github/github.go:70`)
- Inline string key: `ghinstallation.New` (`github/github.go:75`)
- The transport layer is a "stack" of transports (`github/github.go:93-97`)

### PAT Mode Token Rotation (or Lack Thereof)

With PAT mode:
- The PAT is static — wrapped in `oauth2.StaticTokenSource`
- No automatic rotation
- When the PAT expires (if configured with an expiry date), ARC starts failing all API calls
- Manual intervention required: generate new PAT, update Kubernetes secret, restart controller

### Comparison Table

| Aspect | PAT Mode | GitHub App Mode |
|--------|----------|-----------------|
| Token source | Static string in secret | Dynamically generated from private key |
| Token refresh | None (manual) | Automatic (hourly) |
| API rate limit | 5,000 req/hr | 10,000 req/hr (org-owned Enterprise Cloud apps) |
| Secret rotation | Update secret manually | Rotate private key via GitHub UI (rarely needed) |
| Failure mode | Silent auth failures when PAT expires | Self-healing (regenerates token automatically) |
| Security surface | Long-lived credential in K8s secret | Private key in K8s secret (but tokens are short-lived) |
| Enterprise support | Yes | **No** (enterprise-level runners not supported) |

### Registration Token Caching in ARC

ARC caches registration tokens to avoid hitting GitHub API rate limits. Tokens are cached with a 30-minute buffer (`runnerStartupTimeout`) to ensure they remain valid while a runner pod is initializing. This is implemented in `github/github.go:156-178`.

---

## H) Runner Registration Token Lifecycle

### Classic Runner Registration Token

| Property | Value |
|----------|-------|
| Expiry | 1 hour from creation |
| Validity | Single use (can register one runner) |
| Scope | Repo, org, or enterprise (based on endpoint used) |
| Refresh | Must call the API again to get a new token |
| Format | Opaque string (e.g., `AAAXXX4UVEAL3YLMZ3DIMUIC`) |

The token expiry is confirmed in the API documentation: "The token expires after one hour." (GitHub Docs: REST API endpoints for self-hosted runners)

### Scale Set JIT Token

| Property | Value |
|----------|-------|
| Expiry | ~60 minutes from generation |
| Validity | Single use (tied to a specific runner name) |
| Scope | Specific runner within a scale set |
| Delivery | Embedded in base64-encoded JIT config blob |
| Conflict handling | `AgentExistsException` if runner name already registered |

Confirmed via GitHub Community Discussion #25699 and runner source code analysis (Issue #4248).

### Ephemeral Runner Registration

When `--ephemeral` is used with `config.sh`:
- Runner registers normally with the registration token
- After completing exactly one job, GitHub automatically de-registers the runner
- No need for manual cleanup
- The registration token itself still expires in 1 hour (same lifecycle)

### How ARC Handles Token Refresh Automatically

**For classic runners (legacy ARC mode):**
1. ARC periodically requests new registration tokens before the current one expires
2. The 30-minute buffer ensures tokens are refreshed well before the 1-hour deadline
3. New runner pods get fresh tokens from the cache

**For scale set runners (modern ARC mode):**
1. The listener maintains a persistent connection using the App's installation token
2. When the installation token expires (1 hour), `ghinstallation.Transport` auto-generates a new one
3. Each ephemeral runner gets its own JIT config with an embedded token — no shared registration token
4. If a JIT token expires before the runner starts, ARC regenerates it (handles `AgentExistsException`)

### Token Lifecycle Diagram

```
GitHub App Private Key (static, long-lived)
  │
  ├──→ JWT (5-min TTL, generated on-demand)
  │     │
  │     └──→ Installation Access Token (1-hour TTL, cached by ARC)
  │           │
  │           ├──→ Classic: Registration Token (1-hour TTL, cached with 30-min buffer)
  │           │     │
  │           │     └──→ config.sh uses it → Runner registered
  │           │
  │           └──→ Scale Set: JIT Config (60-min TTL, per-runner)
  │                 │
  │                 └──→ Runner pod uses it → Runner registered
  │
  └──→ (key rotation: rare, manual via GitHub App settings UI)
```

---

## I) Complete YAML Examples

### Example 1: ARC Helm Values with GitHub App Auth (Full Working Example)

```yaml
# arc-app-auth-values.yaml

# Target GitHub scope
githubConfigUrl: "https://github.com/myorg"

# GitHub App credentials (auto-detects as GitHub App auth mode)
githubConfigSecret:
  github_app_id: "987654"
  github_app_installation_id: "345678"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEAwZ8k5VhO3xN2LpQRmFjKdS7gHnW...
    ...full PEM key...
    -----END RSA PRIVATE KEY-----

# Scale set naming
runnerScaleSetName: "org-ci-runners"

# Runner group assignment
runnerGroup: "default"

# Scaling parameters
maxRunners: 20
minRunners: 2

# Container mode for Docker workloads
containerMode: "dind"

# Listener configuration
listenerTemplate:
  spec:
    containers:
      - name: listener
        securityContext:
          runAsUser: 1000
        resources:
          limits:
            cpu: "1"
            memory: 1Gi
          requests:
            cpu: 500m
            memory: 512Mi

# Runner pod template
template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        command: ["/home/runner/run.sh"]
        env:
          - name: RUNNER_DEBUG
n            value: "0"
          - name: DOTNET_CLI_TELEMETRY_OPTOUT
n            value: "1"
        resources:
          limits:
            cpu: "4"
            memory: 8Gi
          requests:
            cpu: "2"
            memory: 4Gi
        securityContext:
          runAsUser: 1000
    nodeSelector:
      kubernetes.io/os: linux
      node-role: ci-worker
    tolerations:
      - key: "dedicated"
        value: "github-runner"
        effect: "NoSchedule"
```

### Example 2: GitHubConfigSecret YAML (Standalone)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: arc-github-app-credentials
  namespace: arc-runners
type: Opaque
stringData:
  github_app_id: "987654"
  github_app_installation_id: "345678"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEAwZ8k5VhO3xN2LpQRmFjKdS7gHnW...
    ...full PEM key...
    -----END RSA PRIVATE KEY-----
```

### Example 3: RunnerScaleSet Manifest YAML with GitHub App Auth

```yaml
apiVersion: actions.github.com/v1alpha1
kind: RunnerScaleSet
metadata:
  name: org-ci-runners
  namespace: arc-runners
spec:
  githubConfigUrl: "https://github.com/myorg"
  githubConfigSecret: arc-github-app-credentials
  runnerScaleSetName: "org-ci-runners"
  runnerGroup: "default"
  maxRunners: 20
  minRunners: 2
  template:
    spec:
      containers:
        - name: runner
n          image: ghcr.io/actions/actions-runner:latest
          command: ["/home/runner/run.sh"]
          resources:
            limits:
              cpu: "4"
              memory: 8Gi
            requests:
              cpu: "2"
              memory: 4Gi
  listenerTemplate:
    spec:
      containers:
        - name: listener
          resources:
            limits:
              cpu: "1"
              memory: 1Gi
            requests:
              cpu: 500m
              memory: 512Mi
```

### Example 4: autoscaling-runners.yaml with App Auth (Legacy ARC Mode)

> Note: This is the **legacy** ARC mode using `RunnerDeployment`/`RunnerSet` CRDs. The modern mode uses `RunnerScaleSet` (see Example 3). Included for completeness.

```yaml
apiVersion: actions.summerwind.dev/v1alpha1
kind: RunnerDeployment
metadata:
  name: org-runners
  namespace: arc-runners
spec:
  replicas: 3
  template:
    spec:
      githubConfigUrl: "https://github.com/myorg"
      githubConfigSecret: arc-github-app-credentials
      runnerGroup: "default"
      labels:
        - name: self-hosted
        - name: linux
        - name: x64
        - name: app-auth
      containers:
        - name: runner
          image: ghcr.io/actions/actions-runner:latest
          command: ["/home/runner/run.sh"]
          resources:
            limits:
              cpu: "2"
              memory: 4Gi
            requests:
              cpu: "1"
              memory: 2Gi
```

### Example 5: Complete Deployment Sequence (bash)

```bash
#!/bin/bash
set -euo pipefail

NAMESPACE="arc-runners"
RELEASE_NAME="arc-runner-set"
CHART_REPO="oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set"

# 1. Create namespace
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 2. Create GitHub App secret (from file — recommended)
kubectl create secret generic arc-github-app-credentials \
  --namespace="${NAMESPACE}" \
  --from-literal=github_app_id="987654" \
  --from-literal=github_app_installation_id="345678" \
  --from-file=github_app_private_key=./private-key.pem \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Install/upgrade the scale set
helm upgrade --install "${RELEASE_NAME}" \
  --namespace "${NAMESPACE}" \
  -f arc-app-auth-values.yaml \
  "${CHART_REPO}"

# 4. Verify
echo "=== Pods ==="
kubectl -n "${NAMESPACE}" get pods

echo "=== Runner Scale Sets ==="
kubectl -n "${NAMESPACE}" get runnerscalesets.actions.github.com

echo "=== Listeners ==="
kubectl -n "${NAMESPACE}" get autoscalinglisteners.actions.github.com
```

---

## J) API Endpoint Differences Table

| Endpoint | Scope | HTTP Method | Auth Methods | Token Expiry | Response Fields | Notes |
|----------|-------|-------------|--------------|--------------|-----------------|-------|
| `/repos/{owner}/{repo}/actions/runners/registration-token` | Repository | POST | PAT (classic), GitHub App installation token | 1 hour | `token`, `expires_at` | Single runner registration. One token = one runner. |
| `/orgs/{org}/actions/runners/registration-token` | Organization | POST | PAT (classic, needs `admin:org`), GitHub App installation token | 1 hour | `token`, `expires_at` | Single runner registration at org level. |
| `/enterprises/{enterprise}/actions/runners/registration-token` | Enterprise | POST | PAT (classic, needs `manage_runners:enterprise`) ONLY | 1 hour | `token`, `expires_at` | **GitHub App auth NOT supported** at enterprise level. |
| `/repos/{owner}/{repo}/actions/runner-scale-sets` | Repository | POST | PAT, GitHub App installation token | N/A (entity, not token) | Scale set metadata, `id` | Creates a scale set entity. Not a token endpoint per se. |
| `/orgs/{org}/actions/runner-scale-sets` | Organization | POST | PAT, GitHub App installation token | N/A (entity, not token) | Scale set metadata, `id` | Creates a scale set entity at org level. |
| `/enterprises/{enterprise}/actions/runner-scale-sets` | Enterprise | POST | PAT ONLY | N/A (entity, not token) | Scale set metadata, `id` | **GitHub App auth NOT supported** at enterprise level. |
| `.../runner-scale-sets/{id}/runner-jit-config` | Scale Set Runner | POST | PAT, GitHub App installation token | ~60 minutes | `encodedJitConfig` (base64) | Per-runner JIT config with embedded token. Single use. |
| `.../runner-scale-sets/{id}/message-routine` | Scale Set Listener | POST (long-poll) | PAT, GitHub App installation token | Connection-based | Job messages, heartbeat | Long-poll endpoint. Connection persists. Auth via transport. |
| `/app/installations/{installation_id}/access_tokens` | GitHub App | POST | JWT (from private key) | 1 hour | `token`, `expires_at`, `permissions`, `repository_selection` | Part of the App auth flow. Not runner-specific but required upstream. |

### Key Observations

1. **Enterprise gap:** GitHub App authentication is systematically unsupported at the enterprise level for all runner-related endpoints. This is a GitHub platform limitation, not an ARC limitation.
2. **Scale set tokens are per-runner:** Unlike classic registration tokens (which can theoretically register multiple runners), JIT config tokens are bound to a specific runner name.
3. **Message queue uses transport auth:** The long-poll endpoint authenticates via the same HTTP transport (PAT or App installation token), so token rotation affects active listener connections.

---

## K) Auto-Configure a New Runner on Boot Using App Token

### Cloud-Init Example

```yaml
# cloud-init.yaml
# Usage: pass as user-data when launching a VM

package_update: true

packages:
  - jq
  - curl
  - docker.io

write_files:
  - path: /opt/github-runner/register-runner.sh
    owner: root:root
    permissions: '0755'
    content: |
      #!/bin/bash
      set -euo pipefail

      APP_ID="123456"
      INSTALLATION_ID="654321"
      PRIVATE_KEY_PATH="/opt/github-runner/private-key.pem"
      OWNER="myorg"
      REPO="my-repo"
      RUNNER_NAME="vm-runner-$(hostname)"
      RUNNER_DIR="/opt/github-runner/actions-runner"

      # Step 1: Generate JWT
      NOW=$(date +%s)
      EXPIRY=$((NOW + 300))
      HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
      PAYLOAD=$(echo -n "{\"iat\":${NOW},\"exp\":${EXPIRY},\"iss\":${APP_ID}}" | base64 -w0 | tr '+/' '-_' | tr -d '=')
      HEADER_PAYLOAD="${HEADER}.${PAYLOAD}"
      SIGNATURE=$(openssl dgst -sha256 -sign "${PRIVATE_KEY_PATH}" <(echo -n "${HEADER_PAYLOAD}") | base64 -w0 | tr '+/' '-_' | tr -d '=')
      JWT="${HEADER_PAYLOAD}.${SIGNATURE}"

      # Step 2: Get installation token
      INSTALLATION_TOKEN=$(curl -sf -X POST \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer ${JWT}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens" | jq -r '.token')

      # Step 3: Get registration token
      REG_TOKEN=$(curl -sf -X POST \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token" | jq -r '.token')

      # Step 4: Download runner (if not already present)
      if [ ! -f "${RUNNER_DIR}/run.sh" ]; then
        RUNNER_VERSION="2.321.0"
        cd /opt/github-runner
        curl -fLo actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
          https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
        tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
        rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
      fi

      # Step 5: Configure runner
      cd "${RUNNER_DIR}"
      ./config.sh \
        --url "https://github.com/${OWNER}/${REPO}" \
        --token "${REG_TOKEN}" \
        --name "${RUNNER_NAME}" \
        --labels "self-hosted,linux,x64,cloud-vm" \
        --unattended \
        --replace \
        --ephemeral

      # Step 6: Start runner
      ./run.sh

  - path: /opt/github-runner/private-key.pem
    owner: root:root
    permissions: '0600'
    content: |
      -----BEGIN RSA PRIVATE KEY-----
      MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF...
      ...full PEM key...
      -----END RSA PRIVATE KEY-----

runcmd:
  - /opt/github-runner/register-runner.sh
```

### Systemd Service Example

```ini
# /etc/systemd/system/github-runner.service
[Unit]
Description=GitHub Actions Self-Hosted Runner (App Auth)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=runner
WorkingDirectory=/opt/github-runner/actions-runner

# Environment variables
Environment=APP_ID=123456
Environment=INSTALLATION_ID=654321
Environment=PRIVATE_KEY_PATH=/opt/github-runner/private-key.pem
Environment=OWNER=myorg
Environment=REPO=my-repo
Environment=RUNNER_NAME=systemd-runner-$(hostname)

# Run the registration + start script
ExecStartPre=/opt/github-runner/register-and-run.sh
ExecStart=/opt/github-runner/actions-runner/run.sh

# Restart on failure but not on normal exit
Restart=on-failure
RestartSec=30

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/github-runner/actions-runner

[Install]
WantedBy=multi-user.target
```

```bash
#!/opt/github-runner/register-and-run.sh
# Pre-start script that fetches a fresh registration token
set -euo pipefail

NOW=$(date +%s)
EXPIRY=$((NOW + 300))
HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
PAYLOAD=$(echo -n "{\"iat\":${NOW},\"exp\":${EXPIRY},\"iss\":${APP_ID}}" | base64 -w0 | tr '+/' '-_' | tr -d '=')
HEADER_PAYLOAD="${HEADER}.${PAYLOAD}"
SIGNATURE=$(openssl dgst -sha256 -sign "${PRIVATE_KEY_PATH}" <(echo -n "${HEADER_PAYLOAD}") | base64 -w0 | tr '+/' '-_' | tr -d '=')
JWT="${HEADER_PAYLOAD}.${SIGNATURE}"

INSTALLATION_TOKEN=$(curl -sf -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${JWT}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens" | jq -r '.token')

REG_TOKEN=$(curl -sf -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${INSTALLATION_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runners/registration-token" | jq -r '.token')

./config.sh \
  --url "https://github.com/${OWNER}/${REPO}" \
  --token "${REG_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "self-hosted,linux,x64,systemd" \
  --unattended \
  --replace
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable github-runner.service
sudo systemctl start github-runner.service

# Check status
sudo systemctl status github-runner.service

# View logs
sudo journalctl -u github-runner.service -f
```

> **Why this works on reboot:** Unlike Docker's `--restart unless-stopped` (which restarts the container but doesn't refresh the expired registration token), the systemd service runs the `ExecStartPre` script on every start — which fetches a fresh registration token. This means the runner always has a valid token after reboot.

---

## L) Limitations and Requirements

### Required GitHub App Permissions

| Scope | Repository Level | Organization Level |
|-------|-----------------|-------------------|
| `administration:write` | Required for repo runners | — |
| `Self-hosted runners` (org permission) | — | Required for org runners |
| `Actions` | `read` (minimum) | `read` (minimum) |
| `Metadata` | `read` (always auto-granted) | `read` (always auto-granted) |

### PAT Permissions (for comparison)

| Scope | Repository Runners | Organization Runners | Enterprise Runners |
|-------|-------------------|---------------------|---------------------|
| `repo` (full control) | Required | Required | — |
| `admin:org` (full control) | — | Required | — |
| `admin:public_key` (read) | — | Required | — |
| `admin:repo_hook` (read) | — | Required | — |
| `admin:org_hook` (full control) | — | Required | — |
| `notifications` (full control) | — | Required | — |
| `workflow` (full control) | — | Required | — |
| `manage_runners:enterprise` | — | — | Required |

### Runner Group Restrictions

- Runners can be assigned to runner groups via `--runnergroup` flag (classic) or `runnerGroup` Helm value (scale sets)
- The GitHub App must have permissions on the runner group's scope
- If the runner group has restricted access (specific repos only), the app must be installed on those repos
- Default group (`default`) is accessible to all repos in the org

### Scale Set Scope Limitations

| Constraint | Detail |
|------------|--------|
| **No repo-level scale sets with App auth** | Scale sets at the repo level technically work with App auth, but the primary use case is org/enterprise. Repo-level scale sets have limited practical value. |
| **No enterprise-level App auth** | GitHub App authentication is NOT supported for enterprise-level runners (classic or scale set). This is a documented GitHub limitation. Enterprise runners MUST use PAT. |
| **Org or enterprise scope required** | Scale sets are designed for org-level or enterprise-level deployment. Repo-level is technically possible but not the intended use case. |

### Enterprise-Level Runner Gap (Critical)

This is the most significant limitation:

> **GitHub App authentication is NOT supported for enterprise-level runners of any kind — neither classic single runners nor scale sets.** Enterprise runners require PAT authentication with the `manage_runners:enterprise` permission.

This limitation is:
- Documented in the official ARC authentication docs
- Confirmed in the ARC source code comments (`github/github.go`)
- Discussed in multiple GitHub Community discussions
- Not scheduled for resolution as of 2026-04-23

### Other Constraints

| Constraint | Detail |
|------------|--------|
| **Only one auth method at a time** | ARC cannot simultaneously use PAT and GitHub App. The `Config` struct selects one method based on which fields are present (`github.go:24-37`). |
| **Private key rotation is manual** | Unlike installation tokens (which auto-rotate), the App's private key must be rotated manually via the GitHub App settings web UI. There is no API for private key rotation. |
| **One App per ARC instance** | A single ARC controller instance uses one set of GitHub credentials. To manage runners across multiple orgs, you need either: (a) one App installed on all orgs, or (b) multiple ARC instances. |
| **App installation must match scope** | If `githubConfigUrl` points to `https://github.com/myorg`, the App must be installed on that organization. A repo-level installation won't work for org-level endpoints. |
| **Registration token is single-use in practice** | While the API doesn't explicitly forbid reusing a registration token, it's designed for one-time use. After a runner registers with a token, attempting to register another runner with the same token may fail. Always generate a fresh token per runner. |
| **JIT config conflicts** | If a runner with the same name already exists in the scale set, the JIT config generation returns `AgentExistsException`. ARC handles this by removing the stale runner, but this adds latency. Use unique runner names (UUIDs). |
| **Rate limits apply to token generation** | Each registration token API call counts against the authenticated user/App's rate limit. With 5,000 req/hr (PAT) or 10,000 req/hr (App), this is rarely an issue, but burst scenarios (hundreds of runners starting simultaneously) can hit secondary limits (100 concurrent requests, 500/min burst). |
| **Runner version compatibility** | The JIT config feature requires runner version 2.300+ or later. Older runner versions cannot use JIT config and must use the classic `config.sh` + registration token flow. |
| **GHES rate limit difference** | For GitHub Enterprise Server, API rate limits are configurable. The 10,000 req/hr benefit of GitHub Apps only applies to GitHub Enterprise Cloud. On GHES, PAT and App have equivalent rate limits. |

### Best Practices Summary

1. **Use GitHub App auth for production** — automatic token rotation eliminates a class of operational failures
2. **Use pre-defined K8s secrets** — don't embed private keys in values.yaml files
3. **Use ephemeral runners** — `--ephemeral` flag or scale set mode for security isolation
4. **Use scale sets over classic runners** — JIT config eliminates credential passing to runner pods
5. **Set `minRunners: 0` for cost optimization** — scale to zero when no jobs are queued
6. **Use unique runner names** — UUIDs prevent JIT config conflicts
7. **Monitor ARC logs** — watch for auth failures, rate limits, and JIT conflicts
8. **Plan for enterprise runner PAT rotation** — since App auth isn't available, set up a PAT rotation schedule (30-day expiry recommended)

---

## Sources

- [Deploying runner scale sets with ARC — GitHub Docs](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets)
- [Authenticating ARC to the GitHub API — GitHub Docs](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/authenticate-to-the-api)
- [REST API endpoints for self-hosted runners — GitHub Docs](https://docs.github.com/en/rest/actions/self-hosted-runners)
- [Self-hosted runners reference — GitHub Docs](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
- [Runner scale sets — GitHub Docs](https://docs.github.com/en/actions/concepts/runners/runner-scale-sets)
- [Actions Runner Controller — GitHub Docs](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller)
- [Get started with ARC — GitHub Docs](https://docs.github.com/actions/tutorials/use-actions-runner-controller/quickstart)
- [Support for ARC — GitHub Docs](https://docs.github.com/en/actions/concepts/runners/support-for-arc)
- [ARC authentication docs — GitHub Repo](https://github.com/actions/actions-runner-controller/blob/master/docs/authenticating-to-the-github-api.md)
- [ARC Helm values.yaml — GitHub Repo](https://raw.githubusercontent.com/actions/actions-runner-controller/master/charts/gha-runner-scale-set/values.yaml)
- [ARC GitHub Repository](https://github.com/actions/actions-runner-controller)
- [actions/scaleset Go client — GitHub](https://github.com/actions/scaleset)
- [Authentication Methods — DeepWiki](https://deepwiki.com/actions/actions-runner-controller/6.2-authentication-methods)
- [Runner Scale Set API Integration — DeepWiki](https://deepwiki.com/actions/actions-runner-controller/6.3-runner-scale-set-api-integration)
- [Modern Helm Charts — DeepWiki](https://deepwiki.com/actions/actions-runner-controller/4.2-modern-helm-charts-(gha-runner-scale-set))
- [Runner Configuration — DeepWiki](https://deepwiki.com/grafana/github-actions-runner/5-runner-configuration)
- [Registering self-hosted runners using GitHub App — Medium](https://medium.com/@timburkhardt8/registering-github-self-hosted-runners-using-github-app-9cc952ea6ca)
- [Register self-hosted runner with GitHub App — blog.madkoo.net](https://blog.madkoo.net/2023/07/24/register-self-hosted/)
- [Deploying ARC on Kubernetes with GitHub App — Medium](https://medium.com/@blackhorseya/deploying-github-actions-runner-controller-on-kubernetes-with-github-app-authentication-1983089d3980)
- [Running GitHub Self-Hosted Runners Reliably — Namespace.so](https://namespace.so/blog/running-github-self-hosted-runners-reliably)
- [Operationalizing GitHub Runners — Infinite Refactor](https://infiniterefactor.com/posts/20260122-operationalizing-github-runners/)
- [ARC on Kubernetes — rtfm.co.ua](https://rtfm.co.ua/en/github-actions-running-the-actions-runner-controller-in-kubernetes/)
- [GitHub Runner Registration Token Validity — GitHub Discussion #1799](https://github.com/actions/runner/discussions/1799)
- [JIT Token Expiration — GitHub Issue #4248](https://github.com/actions/runner/issues/4248)
- [Enterprise Scale Set App Auth — GitHub Community Discussion #181523](https://github.com/orgs/community/discussions/181523)
- [ARC App Auth on Multiple Orgs — GitHub Issue #1067](https://github.com/actions/actions-runner-controller/issues/1067)
- [The Two GitHub ARCs — Ken Muse](https://www.kenmuse.com/blog/the-two-github-arcs/)
- [Securing GHActions with ARC — some-natalie.dev](https://some-natalie.dev/blog/securing-ghactions-with-arc/)
- [Best Practices for Self-Hosted Runners on AWS — AWS Blog](https://aws.amazon.com/blogs/devops/best-practices-working-with-self-hosted-github-action-runners-at-scale-on-aws/)
- [Ephemeral Runner Security — SmartScope](https://smartscope.blog/en/Infrastructure/github-actions-ephemeral-runner-security-implementation/)

---

*End of Topic 5 of 5 — GitHub App Token Usage Research Series*
*Series topics: (1) SLSA Provenance, (2) PAT Rotation Automation, (3) Create GitHub App Token, (4) GitHub Pages Deployment, (5) Self-Hosted Runner Registration*
