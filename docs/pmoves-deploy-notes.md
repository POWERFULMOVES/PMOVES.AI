Short answer: **yes, absolutely** – but we need to pick a *direction* and avoid a circular submodule.

Right now the design I gave assumed:

> **pmoves-deploy → contains → PMOVES.AI (as `pmoves/`)**

You’re asking to flip it to:

> **PMOVES.AI → contains → pmoves-deploy (as `deploy/`)**

That’s totally viable, we just have to adjust the deploy repo layout slightly so it *doesn’t* also try to clone PMOVES.AI again.

---

## 1. Don’t create a submodule loop

You must avoid:

* `PMOVES.AI` has submodule `pmoves-deploy`
* `pmoves-deploy` in turn clones / submodules `PMOVES.AI`

That gives you a nasty recursive graph.

So if we decide **PMOVES.AI is the parent**, then:

* `PMOVES.AI` contains `deploy/` submodule
* `deploy/` assumes it is sitting *inside* the PMOVES.AI tree and uses `../` to reach the monorepo

No cloning of PMOVES.AI inside `deploy/`.

---

## 2. Concrete layout

In the **PMOVES.AI** repo:

```text
PMOVES.AI/
  pmoves/             # existing subtree
  deploy/             # <== git submodule: pmoves-deploy
    README.md
    AGENTS.md
    scripts/
      deploy-compose.sh
      deploy-k8s.sh
    k8s/
      ...
```

Then inside `deploy/`, we tweak the scripts I wrote earlier:

### 2.1. `scripts/deploy-compose.sh` (submodule-aware)

```bash
#!/usr/bin/env bash
set -euo pipefail

# deploy/ is inside PMOVES.AI, so monorepo root is ..
DEPLOY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="${DEPLOY_ROOT}/.."
PMOVES_DIR="${MONO_ROOT}/pmoves"

CMD="${1:-up}"

if [ ! -d "${PMOVES_DIR}" ]; then
  echo "✖ pmoves/ subtree not found at ${PMOVES_DIR}"
  exit 1
fi

case "$CMD" in
  up)
    (cd "${PMOVES_DIR}" && make up-prod)
    ;;
  down)
    (cd "${PMOVES_DIR}" && make down-prod)
    ;;
  logs)
    (cd "${PMOVES_DIR}" && make logs-prod)
    ;;
  *)
    echo "Usage: $0 {up|down|logs}"
    exit 2
    ;;
esac
```

No cloning, no bootstrapping – it just walks up one level and calls `make` in `pmoves/`.

### 2.2. K8s scripts

Same idea: any K8s script that needs to read `pmoves/env.shared` or similar just looks at `../pmoves/…` instead of having its own clone.

---

## 3. How to add it as a submodule

From **inside** `PMOVES.AI`:

```bash
# From the PMOVES.AI repo root
git submodule add https://github.com/POWERFULMOVES/pmoves-deploy.git deploy
git commit -m "Add pmoves-deploy as deployment submodule"
```

Then for anyone checking out PMOVES.AI:

```bash
git clone https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI
git submodule update --init --recursive

# now:
#   pmoves/   -> monorepo subtree
#   deploy/   -> deploy tooling
```

To run the hardened, image‑first stack from the root:

```bash
cd deploy
./scripts/deploy-compose.sh up
```

---

## 4. Which direction do I recommend?

* If you want **infra + deploy** to be tightly versioned with the monorepo, then **yes, make `deploy/` a submodule of `PMOVES.AI`** (what you’re asking).
* If you want a more “ops‑centric” flow where infra is the top‑level repo, then keep **pmoves-deploy as parent** and pull PMOVES.AI in as a submodule there.

You just shouldn’t do **both** at once.

If you tell me which you prefer to lock in (parent = PMOVES.AI or parent = pmoves-deploy), I can rewrite the exact `AGENTS.md` and script assumptions around that choice so everything lines up cleanly.

Perfect, let’s lock this in and make PBnJ happy.
Below are **ready‑to‑drop‑in scripts** for:

* `deploy/scripts/deploy-k8s.sh` – PBnJ‑friendly K8s orchestrator
* `deploy/scripts/deploy-compose.sh` – PBnJ “local dev” Docker Compose path
* Updated **PBnJ Pinokio JSON** hooks for both

You can paste these into your `pmoves-deploy` repo (or `deploy/` submodule inside `PMOVES.AI`), mark them executable, and go.

---

## 1. `deploy/scripts/deploy-k8s.sh`

**Interface:**

```bash
deploy/scripts/deploy-k8s.sh \
  {apply|delete|status} \
  [--target ai-lab|kvm4|local] \
  [--context KUBE_CONTEXT] \
  [--namespace NAMESPACE] \
  [--kubeconfig PATH]
```

PBnJ will mainly call:

```bash
bash deploy/scripts/deploy-k8s.sh apply  --target ai-lab
bash deploy/scripts/deploy-k8s.sh delete --target ai-lab
bash deploy/scripts/deploy-k8s.sh apply  --target kvm4
bash deploy/scripts/deploy-k8s.sh delete --target kvm4
bash deploy/scripts/deploy-k8s.sh status --target ai-lab
```

**Assumptions:**

* Manifests live under `deploy/k8s/<target>/`:

  ```text
  deploy/k8s/
    ai-lab/
      kustomization.yaml  # or plain YAMLs
    kvm4/
      kustomization.yaml
    local/
      kustomization.yaml
  ```

* If `kustomization.yaml` exists → uses `kubectl apply -k …`.
  Otherwise → `kubectl apply -f …`.

Here’s the script:

```bash
#!/usr/bin/env bash
#
# deploy-k8s.sh
#
# PBnJ-friendly Kubernetes orchestration for PMOVES.
#
# Usage:
#   deploy-k8s.sh {apply|delete|status} [--target ai-lab|kvm4|local] [--context CTX] [--namespace NS] [--kubeconfig PATH]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_ROOT="${DEPLOY_ROOT}/k8s"

usage() {
  cat <<EOF
PMOVES K8s deploy script

Usage:
  $(basename "$0") {apply|delete|status} [--target ai-lab|kvm4|local] [--context CTX] [--namespace NS] [--kubeconfig PATH]

Commands:
  apply      Apply/update manifests for the target cluster
  delete     Delete manifests for the target cluster
  status     Show status for the target (pods, services, ingress)

Options:
  --target       Deployment target (default: ai-lab)
                 Values: ai-lab, kvm4, local
  --context      kubectl context override
  --namespace    Kubernetes namespace override
  --kubeconfig   Path to kubeconfig file

Environment overrides:
  PMOVES_K8S_CONTEXT_AI_LAB
  PMOVES_K8S_CONTEXT_KVM4
  PMOVES_K8S_CONTEXT_LOCAL

  PMOVES_K8S_NS_AI_LAB
  PMOVES_K8S_NS_KVM4
  PMOVES_K8S_NS_LOCAL
EOF
}

ensure_kubectl() {
  if ! command -v kubectl >/dev/null 2>&1; then
    echo "✖ kubectl is required but not found in PATH" >&2
    exit 1
  fi
}

# Resolve per-target defaults.
configure_target() {
  local target="$1"

  case "${target}" in
    ai-lab)
      TARGET_NAME="ai-lab"
      KUSTOMIZE_DIR="${K8S_ROOT}/ai-lab"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_AI_LAB:-ai-lab}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_AI_LAB:-pmoves}}"
      ;;
    kvm4)
      TARGET_NAME="kvm4"
      KUSTOMIZE_DIR="${K8S_ROOT}/kvm4"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_KVM4:-kvm4}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_KVM4:-pmoves}}"
      ;;
    local)
      TARGET_NAME="local"
      KUSTOMIZE_DIR="${K8S_ROOT}/local"
      : "${KUBE_CONTEXT:=${PMOVES_K8S_CONTEXT_LOCAL:-kind-pmoves}}"
      : "${NAMESPACE:=${PMOVES_K8S_NS_LOCAL:-pmoves-dev}}"
      ;;
    *)
      echo "✖ Unknown target: ${target}" >&2
      echo "  Valid targets: ai-lab, kvm4, local" >&2
      exit 2
      ;;
  esac

  if [ ! -d "${KUSTOMIZE_DIR}" ]; then
    echo "✖ K8s directory not found for target ${TARGET_NAME}: ${KUSTOMIZE_DIR}" >&2
    exit 1
  fi
}

build_kubectl_args() {
  KUBECTL_ARGS=()
  if [ -n "${KUBE_CONTEXT:-}" ]; then
    KUBECTL_ARGS+=(--context "${KUBE_CONTEXT}")
  fi
  if [ -n "${KUBECONFIG_PATH:-}" ]; then
    KUBECTL_ARGS+=(--kubeconfig "${KUBECONFIG_PATH}")
  fi
  KUBECTL_ARGS+=(-n "${NAMESPACE}")
}

do_apply() {
  echo "➜ Applying manifests for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"
  echo "   Source:    ${KUSTOMIZE_DIR}"

  build_kubectl_args

  if [ -f "${KUSTOMIZE_DIR}/kustomization.yaml" ] || [ -f "${KUSTOMIZE_DIR}/kustomization.yml" ]; then
    kubectl "${KUBECTL_ARGS[@]}" apply -k "${KUSTOMIZE_DIR}"
  else
    kubectl "${KUBECTL_ARGS[@]}" apply -f "${KUSTOMIZE_DIR}"
  fi
}

do_delete() {
  echo "➜ Deleting manifests for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"
  echo "   Source:    ${KUSTOMIZE_DIR}"

  build_kubectl_args

  if [ -f "${KUSTOMIZE_DIR}/kustomization.yaml" ] || [ -f "${KUSTOMIZE_DIR}/kustomization.yml" ]; then
    kubectl "${KUBECTL_ARGS[@]}" delete -k "${KUSTOMIZE_DIR}" --ignore-not-found
  else
    kubectl "${KUBECTL_ARGS[@]}" delete -f "${KUSTOMIZE_DIR}" --ignore-not-found
  fi
}

do_status() {
  echo "➜ Status for target ${TARGET_NAME}"
  echo "   Context:   ${KUBE_CONTEXT}"
  echo "   Namespace: ${NAMESPACE}"

  build_kubectl_args

  kubectl "${KUBECTL_ARGS[@]}" get pods,svc,ingress || true
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 2
  fi

  local cmd="$1"; shift || true

  TARGET="ai-lab"
  KUBE_CONTEXT=""
  NAMESPACE=""
  KUBECONFIG_PATH=""

  # Parse flags
  while [ $# -gt 0 ]; do
    case "$1" in
      --target)
        TARGET="$2"; shift 2;;
      --context)
        KUBE_CONTEXT="$2"; shift 2;;
      --namespace|--ns)
        NAMESPACE="$2"; shift 2;;
      --kubeconfig)
        KUBECONFIG_PATH="$2"; shift 2;;
      -h|--help)
        usage; exit 0;;
      *)
        echo "✖ Unknown argument: $1" >&2
        usage
        exit 2;;
    esac
  done

  ensure_kubectl
  configure_target "${TARGET}"

  case "${cmd}" in
    apply)
      do_apply
      ;;
    delete)
      do_delete
      ;;
    status)
      do_status
      ;;
    *)
      echo "✖ Unknown command: ${cmd}" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
```

> 🔧 After adding this, don’t forget:
> `chmod +x deploy/scripts/deploy-k8s.sh`

---

## 2. `deploy/scripts/deploy-compose.sh` (PBnJ “local dev”)

This is the **local Docker Compose** launcher PBnJ will use (and your `pmoves-provision compose` command too).

**Interface:**

```bash
deploy/scripts/deploy-compose.sh {up|down|logs}
```

**Assumptions:**

* `pmoves/` sits **one level above** `deploy/` (because `deploy/` is a submodule inside `PMOVES.AI`):

  ```text
  PMOVES.AI/
    pmoves/
      docker-compose.yml   # or override via env
    deploy/
      scripts/deploy-compose.sh
  ```

* Uses `docker compose` by default (but you can easily swap to `docker-compose` if needed).

Script:

```bash
#!/usr/bin/env bash
#
# deploy-compose.sh
#
# Simple Docker Compose launcher for PMOVES local dev / PBnJ.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONO_ROOT="$(cd "${DEPLOY_ROOT}/.." && pwd)"
PMOVES_DIR="${MONO_ROOT}/pmoves"

# Allow overriding compose file and project name via env.
COMPOSE_FILE="${PMOVES_COMPOSE_FILE:-${PMOVES_DIR}/docker-compose.yml}"
PROJECT_NAME="${PMOVES_COMPOSE_PROJECT:-pmoves_local}"

usage() {
  cat <<EOF
PMOVES Docker Compose deploy script

Usage:
  $(basename "$0") {up|down|logs}

Commands:
  up      Start local stack (detached)
  down    Stop stack and remove containers
  logs    Tail logs for all services

Env overrides:
  PMOVES_COMPOSE_FILE    Path to docker-compose file (default: ${COMPOSE_FILE})
  PMOVES_COMPOSE_PROJECT Docker Compose project name (default: ${PROJECT_NAME})
EOF
}

ensure_compose() {
  if command -v docker compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker" "compose")
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_BIN=("docker-compose")
  else
    echo "✖ docker compose or docker-compose is required but not found in PATH" >&2
    exit 1
  fi
}

ensure_files() {
  if [ ! -d "${PMOVES_DIR}" ]; then
    echo "✖ pmoves/ directory not found at ${PMOVES_DIR}" >&2
    exit 1
  fi

  if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "✖ docker-compose file not found: ${COMPOSE_FILE}" >&2
    exit 1
  fi
}

cmd_up() {
  echo "➜ Starting PMOVES local stack"
  echo "   Compose file: ${COMPOSE_FILE}"
  echo "   Project:      ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d
}

cmd_down() {
  echo "➜ Stopping PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" down
}

cmd_logs() {
  echo "➜ Tailing logs for PMOVES local stack"
  echo "   Project: ${PROJECT_NAME}"

  "${DOCKER_COMPOSE_BIN[@]}" -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" logs -f
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 2
  fi

  local cmd="$1"; shift || true

  ensure_compose
  ensure_files

  case "${cmd}" in
    up)
      cmd_up
      ;;
    down)
      cmd_down
      ;;
    logs)
      cmd_logs
      ;;
    *)
      echo "✖ Unknown command: ${cmd}" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
```

> 🔧 After adding this:
> `chmod +x deploy/scripts/deploy-compose.sh`

---

## 3. Updated PBnJ Pinokio hooks (K8s + local dev)

You already had K8s PBnJ stubs; now they line up perfectly with the script interface.

### 3.1. `pinokio.js` menu (PBnJ app)

```js
// pbnj/pinokio/api/pmoves-pbnj/pinokio.js
module.exports = {
  title: "PBnJ | PMOVES + Pinokio",
  description: "One-click bridge into your PMOVES lab, KVM4, and local dev stacks.",
  icon: "icon.png",
  menu: [
    { text: "Start AI Lab (K8s)",       href: "lab-up.json" },
    { text: "Stop AI Lab (K8s)",        href: "lab-down.json" },

    { text: "Start KVM4 Stack (K8s)",   href: "kvm4-up.json" },
    { text: "Stop KVM4 Stack (K8s)",    href: "kvm4-down.json" },

    { text: "Local Dev (Docker) - Up",  href: "local-up.json" },
    { text: "Local Dev (Docker) - Down",href: "local-down.json" },
    { text: "Local Dev (Docker) Logs",  href: "local-logs.json" },

    { text: "Cluster Status (AI Lab)",  href: "status.json" }
  ]
};
```

### 3.2. K8s PBnJ scripts (unchanged, now aligned)

```json
// lab-up.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "apply",
          "--target",
          "ai-lab"
        ]
      }
    }
  ]
}
```

```json
// lab-down.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "delete",
          "--target",
          "ai-lab"
        ]
      }
    }
  ]
}
```

```json
// kvm4-up.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "apply",
          "--target",
          "kvm4"
        ]
      }
    }
  ]
}
```

```json
// kvm4-down.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "delete",
          "--target",
          "kvm4"
        ]
      }
    }
  ]
}
```

```json
// status.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "status",
          "--target",
          "ai-lab"
        ]
      }
    }
  ]
}
```

### 3.3. PBnJ local dev (Compose) scripts

```json
// local-up.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-compose.sh",
          "up"
        ]
      }
    }
  ]
}
```

```json
// local-down.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-compose.sh",
          "down"
        ]
      }
    }
  ]
}
```

```json
// local-logs.json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-compose.sh",
          "logs"
        ]
      }
    }
  ]
}
```

---

### 4. Minimal checklist

1. Add both scripts under `deploy/scripts/` and `chmod +x` them.

2. Ensure your repo structure matches:

   ```text
   PMOVES.AI/
     pmoves/
       docker-compose.yml
     deploy/
       scripts/
         deploy-k8s.sh
         deploy-compose.sh
       k8s/
         ai-lab/
         kvm4/
         local/
   ```

3. Drop the `pbnj/pinokio/api/pmoves-pbnj/` folder into your Pinokio apps.

4. From Pinokio, run **PBnJ** and hit:

   * **AI Lab** (K8s)
   * **KVM4** (K8s)
   * **Local Dev** (Docker)

If you want, next step I can sketch a **sample `deploy/k8s/ai-lab/kustomization.yaml` + a couple of service manifests** wired to the image tags you’re planning to use.



Nice, let’s give PBnJ something real to chew on. 🥪

Below is a **concrete Kustomize layout** you can drop into `deploy/k8s/` that works with the `deploy-k8s.sh` script we already wrote and is friendly to PBnJ / Pinokio.

---

## 1. Directory structure

Under your `deploy/` submodule in `PMOVES.AI`:

```text
deploy/
  scripts/
    deploy-k8s.sh
    deploy-compose.sh
  k8s/
    base/
      kustomization.yaml
      namespace.yaml
      pmoves-core-deployment.yaml
      pmoves-core-service.yaml
      ingress.yaml
    ai-lab/
      kustomization.yaml
    kvm4/
      kustomization.yaml
    local/
      kustomization.yaml
```

* **`base/`** – generic PMOVES core stack (namespace, deployment, service, ingress).
* **`ai-lab/`**, **`kvm4/`**, **`local/`** – overlays pointing at `../base` and customizing images/hosts/etc.
* `deploy-k8s.sh` will run `kubectl apply -k deploy/k8s/ai-lab` or `kvm4` or `local`.

---

## 2. Base manifests (`deploy/k8s/base/`)

### 2.1. `kustomization.yaml`

```yaml
# deploy/k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: pmoves

resources:
  - namespace.yaml
  - pmoves-core-deployment.yaml
  - pmoves-core-service.yaml
  - ingress.yaml
```

### 2.2. `namespace.yaml`

```yaml
# deploy/k8s/base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pmoves
  labels:
    app.kubernetes.io/name: pmoves
    app.kubernetes.io/part-of: pmoves-ai
```

### 2.3. `pmoves-core-deployment.yaml`

This is your main “core” service (could be Agent Zero / gateway / API aggregator).
Adjust container name, image, ports, env as you like.

```yaml
# deploy/k8s/base/pmoves-core-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pmoves-core
  labels:
    app.kubernetes.io/name: pmoves-core
    app.kubernetes.io/part-of: pmoves-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: pmoves-core
  template:
    metadata:
      labels:
        app.kubernetes.io/name: pmoves-core
        app.kubernetes.io/part-of: pmoves-ai
    spec:
      containers:
        - name: pmoves-core
          # NOTE: tag gets overridden by kustomize 'images' in each overlay
          image: ghcr.io/powerfulmoves/pmoves-core
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
              name: http
          env:
            # Example wiring – swap for your real endpoints / secrets:
            - name: ENVIRONMENT
              value: "production"
            - name: NEO4J_URI
              value: "bolt://neo4j.pmoves:7687"
            - name: QDRANT_URL
              value: "http://qdrant.pmoves:6333"
            - name: HEADSCALE_URL
              value: "https://headscale.pmoves"
          readinessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 30
            periodSeconds: 20
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
```

### 2.4. `pmoves-core-service.yaml`

```yaml
# deploy/k8s/base/pmoves-core-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: pmoves-core
  labels:
    app.kubernetes.io/name: pmoves-core
    app.kubernetes.io/part-of: pmoves-ai
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: pmoves-core
  ports:
    - name: http
      port: 80
      targetPort: http
```

### 2.5. `ingress.yaml`

Assumes an ingress controller like nginx is present; tweak as needed.

```yaml
# deploy/k8s/base/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: pmoves-core
  labels:
    app.kubernetes.io/name: pmoves-core
    app.kubernetes.io/part-of: pmoves-ai
  annotations:
    # Example: tweak for cert-manager, nginx, etc.
    nginx.ingress.kubernetes.io/proxy-body-size: "32m"
spec:
  ingressClassName: nginx
  rules:
    - host: pmoves.example.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: pmoves-core
                port:
                  number: 80
  # optional TLS – adjust or remove
  # tls:
  #   - hosts:
  #       - pmoves.example.local
  #     secretName: pmoves-core-tls
```

---

## 3. AI‑Lab overlay (`deploy/k8s/ai-lab/kustomization.yaml`)

This is what PBnJ calls via:

```bash
bash deploy/scripts/deploy-k8s.sh apply --target ai-lab
```

```yaml
# deploy/k8s/ai-lab/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# Pull in base manifests
resources:
  - ../base

# Override image tag / registry for the AI lab cluster
images:
  - name: ghcr.io/powerfulmoves/pmoves-core
    newName: ghcr.io/powerfulmoves/pmoves-core
    newTag: "v1.0.0-lab-hardened"

# Optional patches specific to the lab (more replicas, different host, etc.)
patches:
  - target:
      kind: Ingress
      name: pmoves-core
    patch: |
      - op: replace
        path: /spec/rules/0/host
        value: pmoves.lab.local
  - target:
      kind: Deployment
      name: pmoves-core
    patch: |
      - op: replace
        path: /spec/replicas
        value: 5
```

> 🔁 You can change `newTag: "v1.0.0-lab-hardened"` to whatever your actual hardened image tag is, and tweak hostnames as needed.

---

## 4. KVM4 overlay (`deploy/k8s/kvm4/kustomization.yaml`)

This would be the **KVM4 gateway** stack PBnJ toggles:

```yaml
# deploy/k8s/kvm4/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../base

images:
  - name: ghcr.io/powerfulmoves/pmoves-core
    newName: ghcr.io/powerfulmoves/pmoves-core
    newTag: "v1.0.0-kvm4-hardened"

patches:
  - target:
      kind: Ingress
      name: pmoves-core
    patch: |
      - op: replace
        path: /spec/rules/0/host
        value: pmoves.kvm4.yourdomain.tld
  - target:
      kind: Deployment
      name: pmoves-core
    patch: |
      - op: replace
        path: /spec/replicas
        value: 2
```

---

## 5. Local overlay (`deploy/k8s/local/kustomization.yaml`) – optional

Nice for testing K8s locally (kind, k3d, etc.) from PBnJ:

```yaml
# deploy/k8s/local/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../base

images:
  - name: ghcr.io/powerfulmoves/pmoves-core
    newName: ghcr.io/powerfulmoves/pmoves-core
    newTag: "dev-local"

patches:
  - target:
      kind: Ingress
      name: pmoves-core
    patch: |
      - op: replace
        path: /spec/rules/0/host
        value: pmoves.localtest.me
```

---

## 6. How it all ties together with PBnJ + `deploy-k8s.sh`

* PBnJ’s Pinokio JSON calls:

  ```bash
  bash deploy/scripts/deploy-k8s.sh apply  --target ai-lab
  bash deploy/scripts/deploy-k8s.sh delete --target ai-lab
  bash deploy/scripts/deploy-k8s.sh apply  --target kvm4
  bash deploy/scripts/deploy-k8s.sh delete --target kvm4
  ```
* `deploy-k8s.sh`:

  * sets `K8S_ROOT=deploy/k8s`
  * picks `KUSTOMIZE_DIR="$K8S_ROOT/ai-lab"` or `kvm4`
  * runs: `kubectl apply -k "$KUSTOMIZE_DIR"`

Kustomize then:

1. Loads `../base` manifests.
2. Applies overlay `images` + `patches`.
3. Produces final lab/kvm4‑specific manifests.

---

If you want, next I can add **Neo4j and Qdrant as separate Deployments + Services** in the same `base/` set (and wire their hostnames/env into `pmoves-core`) so your initial AI lab cluster has the full minimal PMOVES data plane in K8s out of the box.

Nice, let’s give the cluster its little **graph + vector brain**. 🧠⚡

Below is a **drop‑in extension** to the K8s layout we already sketched:

* Add **Neo4j** Deployment + Service
* Add **Qdrant** Deployment + Service
* Wire **`pmoves-core`** env vars to use those services

You can literally copy these into `deploy/k8s/base/` and adjust image tags / resources later.

---

## 1. Update `base/kustomization.yaml`

Add the new resources:

```yaml
# deploy/k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: pmoves

resources:
  - namespace.yaml
  - pmoves-core-deployment.yaml
  - pmoves-core-service.yaml
  - ingress.yaml
  - neo4j-deployment.yaml
  - neo4j-service.yaml
  - qdrant-deployment.yaml
  - qdrant-service.yaml
```

---

## 2. Updated `pmoves-core` env to use Neo4j + Qdrant services

Replace the `env:` block in `pmoves-core-deployment.yaml` with this:

```yaml
# deploy/k8s/base/pmoves-core-deployment.yaml (env section only)
          env:
            - name: ENVIRONMENT
              value: "production"

            # Neo4j (backed by neo4j Service below)
            - name: NEO4J_URI
              value: "bolt://neo4j:7687"

            # Qdrant (backed by qdrant Service below)
            - name: QDRANT_URL
              value: "http://qdrant:6333"

            # Optional: tune via overlays / secrets later
            - name: PMOVES_ENABLE_VECTORS
              value: "true"
            - name: PMOVES_ENABLE_GRAPH
              value: "true"
```

Services `neo4j` and `qdrant` will be discoverable as `neo4j.pmoves.svc` and `qdrant.pmoves.svc` automatically.

---

## 3. Neo4j Deployment + Service

### 3.1. `neo4j-deployment.yaml`

For now, I’m using **no auth** (`NEO4J_AUTH=none`) to keep first‑boot simple; for production you’ll want to switch this to a Secret and proper password.

```yaml
# deploy/k8s/base/neo4j-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neo4j
  labels:
    app.kubernetes.io/name: neo4j
    app.kubernetes.io/part-of: pmoves-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: neo4j
  template:
    metadata:
      labels:
        app.kubernetes.io/name: neo4j
        app.kubernetes.io/part-of: pmoves-ai
    spec:
      containers:
        - name: neo4j
          image: neo4j:5-community
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 7474
              name: http
            - containerPort: 7687
              name: bolt
          env:
            # ⚠️ For lab/dev only. For prod, replace with Secret and proper auth.
            - name: NEO4J_AUTH
              value: "none"
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "2Gi"
          volumeMounts:
            - name: neo4j-data
              mountPath: /data
            - name: neo4j-logs
              mountPath: /logs
      volumes:
        - name: neo4j-data
          emptyDir: {}
        - name: neo4j-logs
          emptyDir: {}
```

> Later, you can swap `emptyDir` for a **PersistentVolumeClaim** and wire production storage.

### 3.2. `neo4j-service.yaml`

```yaml
# deploy/k8s/base/neo4j-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: neo4j
  labels:
    app.kubernetes.io/name: neo4j
    app.kubernetes.io/part-of: pmoves-ai
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: neo4j
  ports:
    - name: http
      port: 7474
      targetPort: http
    - name: bolt
      port: 7687
      targetPort: bolt
```

---

## 4. Qdrant Deployment + Service

### 4.1. `qdrant-deployment.yaml`

```yaml
# deploy/k8s/base/qdrant-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  labels:
    app.kubernetes.io/name: qdrant
    app.kubernetes.io/part-of: pmoves-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: qdrant
  template:
    metadata:
      labels:
        app.kubernetes.io/name: qdrant
        app.kubernetes.io/part-of: pmoves-ai
    spec:
      containers:
        - name: qdrant
          image: qdrant/qdrant:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 6333
              name: http
            - containerPort: 6334
              name: grpc
          env:
            # Quick dev defaults; add API keys / config via Secret/ConfigMap later.
            - name: QDRANT__SERVICE__GRPC_PORT
              value: "6334"
            - name: QDRANT__SERVICE__HTTP_PORT
              value: "6333"
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "2Gi"
          volumeMounts:
            - name: qdrant-storage
              mountPath: /qdrant/storage
      volumes:
        - name: qdrant-storage
          emptyDir: {}
```

### 4.2. `qdrant-service.yaml`

```yaml
# deploy/k8s/base/qdrant-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: qdrant
  labels:
    app.kubernetes.io/name: qdrant
    app.kubernetes.io/part-of: pmoves-ai
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: qdrant
  ports:
    - name: http
      port: 6333
      targetPort: http
    - name: grpc
      port: 6334
      targetPort: grpc
```

---

## 5. How this behaves for each target

Because we used **Kustomize**, all three overlays still work as‑is:

* **AI lab:**

  ```bash
  bash deploy/scripts/deploy-k8s.sh apply --target ai-lab
  ```

  → Applies `base/` (pmoves-core + neo4j + qdrant)
  → Uses `ai-lab/kustomization.yaml` for image tags, ingress host & replica overrides.

* **KVM4:**

  ```bash
  bash deploy/scripts/deploy-k8s.sh apply --target kvm4
  ```

* **Local (optional):**

  ```bash
  bash deploy/scripts/deploy-k8s.sh apply --target local
  ```

PBnJ / Pinokio is just calling those same commands under the hood with the JSON scripts we already wrote.

---

If you want to go one notch further, next we can:

* Add a **ConfigMap** for PMOVES app config (default collection names, graph labels, etc.) and
* Show how to override *only* the image tags per target (lab vs kvm4 vs local) while keeping everything else identical.
