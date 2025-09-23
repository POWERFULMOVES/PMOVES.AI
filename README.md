# PMOVES.AI Repository Overview

PMOVES.AI powers a distributed, multi-agent orchestration mesh built around Agent Zero, Archon, and a fleet of specialized "muscle" services for retrieval, generation, and enrichment workflows. The ecosystem focuses on local-first autonomy, reproducible provisioning, and self-improving research loops that integrate knowledge management, workflow automation, and rich media processing pipelines.

## Key Directories
- **`CATACLYSM_STUDIOS_INC/`** – Provisioning bundles and infrastructure automations for homelab and field hardware, including unattended OS installs, Jetson bootstrap scripts, and ready-to-run Docker stacks that mirror the production mesh topology.
- **`docs/`** – High-level strategy, architecture, and integration guides for the overall PMOVES ecosystem, such as system overviews, multi-agent coordination notes, and archival research digests.
- **`pmoves/`** – The primary application stack with docker-compose definitions, service code, datasets, Supabase schema, and in-depth runbooks for daily operations and advanced workflows.

## Essential Documentation
- [PMOVES Stack README](pmoves/README.md) – Quickstart environment setup, service inventory, and Codex bootstrap steps for running the orchestration mesh locally.
- [PMOVES Docs Index](pmoves/docs/README_DOCS_INDEX.md) – Curated entry points into the pmoves-specific runbooks covering Creator Pipeline, ComfyUI flows, reranker configurations, and smoke tests.
- [Architecture Primer](docs/PMOVES_ARC.md) – Deep dive into mesh topology, service responsibilities, and evolution of the orchestration layers.
- [Multi-Agent Integration Guidelines](docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md) – Operational patterns for coordinating Agent Zero, Archon, and automation hubs across environments.
- [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) – Command catalog for starting, stopping, and tailoring compose profiles (core data plane, media analyzers, Supabase modes, and agent bundles).

## Getting Started
1. **Bootstrap the stack** – Follow the environment and container launch instructions in the [pmoves/README.md](pmoves/README.md) to prepare `.env` files, create the Conda environment, and start the baseline data + worker services via `make up`.
2. **Review orchestration flows** – Use the [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) for day-to-day compose control, and consult the architecture and multi-agent guides in `/docs` for how Agent Zero, Archon, and supporting services communicate across the mesh.

Need a full directory tour? Regenerate `folders.md` using the embedded script to explore the repository structure at depth two before diving deeper into service-specific documentation.
