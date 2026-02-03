# Glancer add-on

This optional add-on layers a lightweight Glancer service into the provisioning bundle. It ships as a dedicated compose file and environment template so the service can be started independently of the core PMOVES stack.

## Contents
- `docker-compose.glancer.yml` — compose file defining the Glancer service and port mappings.
- `glancer.env.example` — template for image overrides, port selection, and the health endpoint.

## Usage
1. Copy `glancer.env.example` to `glancer.env` and adjust the values for your environment.
2. Start Glancer locally or on a provisioned host:
   ```bash
   docker compose -f addons/glancer/docker-compose.glancer.yml --env-file addons/glancer/glancer.env up -d glancer
   ```
3. Verify readiness via the mini CLI status command. It will report container state and health when Docker is available.

Glancer is optional; the bundle manifest only marks it as staged when `pmoves mini bootstrap --with-glancer` is used.
