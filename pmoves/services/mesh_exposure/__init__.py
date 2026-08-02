"""mesh_exposure — reconciles the pinokio-apps registry to the live fleet.

The slice-4 mesh_exposure service is the *writer* that keeps three pieces
of fleet state in sync with the registry:
  1. pmoves/config/headscale/acl.yaml — mesh ACL ports per app
  2. kvm2's /etc/cloudflared/config.yml — tunnel ingress entries for L4 apps
  3. Cloudflare + Hostinger DNS records — the public hostnames

It exposes 6 endpoints:
  GET  /healthz                              service + registry + last-reconcile status
  GET  /v1/registry                           all curated entries (or specific slug)
  GET  /v1/reconcile/plan                     desired vs current state as JSON
  POST /v1/reconcile/apply                    apply the plan (write auth required)
  GET  /v1/reconcile/status                   last run + last change timestamps
  POST /v1/reconcile/preview?slug=<slug>      dry-run for a single app

Auth: reads are open. Writes (POST apply) require X-PMOVES-Meshbus-Token
in the request header, which must match NATS_MESHBUS_TOKEN at service
start. Fail-closed: if the env var is unset, writes return 503. Same
pattern as pinokio_bridge (X-PMOVES-Bridge-Token) and nats_event_bus
(X-PMOVES-NatsBus-Token) so tokens are scoped per service.

Port: 8132 (next to nats_event_bus :8131). The host convention is
z890 (infra-coordinator) since the writer has direct file access to
pmoves/config/headscale/acl.yaml and SSH reach to kvm2.
"""
__version__ = "0.1.0"
