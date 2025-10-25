# PMOVES.AI Repository Overview
[![PMOVES Integrations CI](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/pmoves-integrations-ci.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/pmoves-integrations-ci.yml)

Welcome to the PMOVES.AI repository! This project powers a distributed, multi-agent orchestration mesh for advanced research and development in knowledge management, workflow automation, and rich media processing.

This README provides a high-level overview of the repository. For a detailed guide to getting started, please see the [PMOVES Stack README](pmoves/README.md).

## Table of Contents
- [Getting Started](#getting-started)
- [Key Directories](#key-directories)
- [Essential Documentation](#essential-documentation)
- [Service Index](#service-index)
- [Repository Navigation](#repository-navigation)

## Getting Started

Ready to dive in? Here’s the quickest way to get the PMOVES.AI stack up and running on your local machine.

1.  **Bootstrap the Environment:** The core of the PMOVES.AI stack is managed via Docker Compose. To get started, you'll need to configure your environment variables. A `Makefile` at the root of the `pmoves` directory provides a convenient way to do this.

    ```bash
    cd pmoves
    make bootstrap
    ```

    This command will guide you through setting up the necessary `.env` files and secrets.

2.  **Start the Services:** Once your environment is configured, you can start the core services using another `make` command:

    ```bash
    make up
    ```

    This will bring up the essential services, including the database, storage, and the main application gateways.

3.  **Seed the Data:** To populate the services with initial data, run the following command:

    ```bash
    make bootstrap-data
    ```

    This will apply SQL migrations, seed the graph database, and load a demo data corpus.

For more detailed instructions, including how to manage different Supabase backends and run optional services, please refer to the [PMOVES Stack README](pmoves/README.md).

## Key Directories

*   **`CATACLYSM_STUDIOS_INC/`**: Contains provisioning bundles and infrastructure automation scripts for both homelab and production hardware. Here you'll find everything from unattended OS install configurations to Jetson bootstrap scripts.
*   **`docs/`**: High-level documentation covering the architecture, strategy, and integration guides for the PMOVES ecosystem.
*   **`pmoves/`**: The heart of the application. This directory contains the primary application stack, including all service code, Docker Compose definitions, datasets, and the Supabase schema.

## Essential Documentation

For a deeper understanding of the project, we recommend exploring the following documents:

*   [PMOVES Stack README](pmoves/README.md): The primary guide for setting up and running the orchestration mesh locally.
*   [Local Tooling Reference](pmoves/docs/LOCAL_TOOLING_REFERENCE.md): A comprehensive index of environment scripts, `make` targets, and Supabase workflows.
*   [Architecture Primer](docs/PMOVES_ARC.md): A deep dive into the mesh topology and the responsibilities of each service.
*   [Complete Architecture Map](pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md): A detailed diagram of the full integration mesh.
*   [Multi-Agent Integration Guidelines](docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md): Best practices for coordinating the various agents and automation hubs.

## Service Index

The PMOVES.AI ecosystem is composed of a number of specialized "muscle" services. Here are some of the key players:

**Geometry + CHIT Core**
*   `hi-rag-gateway-v2/`: The main gateway for handling geometry-related requests.
*   `mesh-agent/`: A bridge for republishing geometry data across different deployments.
*   `evo-controller/`: A service for tuning geometry parameters.

**Orchestration & Knowledge**
*   `agent-zero/`: The main decision engine and bridge for ingesting events.
*   `archon/`: An agent builder and knowledge management service.
*   `n8n/`: A workflow orchestrator for automating tasks.

**External Integrations**
*   `open-notebook/`: A Streamlit UI and SurrealDB API for research assets.
*   `wger/`: A service for ingesting health and fitness metrics.
*   `firefly-iii/`: A service for ingesting personal finance data.
*   `jellyfin-bridge/`: A service for syncing media metadata from Jellyfin.

For a complete list of services and their responsibilities, please see the [Service Docs Index](pmoves/docs/services/README.md).

## Repository Navigation

Need a full directory tour? Regenerate `folders.md` using the embedded script to explore the repository structure at depth two before diving deeper into service-specific documentation.
