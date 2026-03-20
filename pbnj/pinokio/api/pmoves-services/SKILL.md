---
name: pmoves-services
description: Docker Compose profile controller for PMOVES.AI production services
category: infrastructure
version: "1.0"
---

# PMOVES Services Launcher

## Overview

Pinokio launcher for PMOVES.AI Docker Compose service profiles. Provides one-click install, start, stop, and monitoring for the full PMOVES.AI stack.

## Capabilities

- **Install**: Bootstrap environment (env-setup, brand-defaults, Docker pull)
- **Start Core**: Agent Zero, Archon, BoTZ Gateway, data stores (Qdrant, Neo4j, Meilisearch, MinIO)
- **Start Voice**: Ultimate-TTS-Studio, Flute-Gateway
- **Start External**: Hi-RAG, DeepResearch, SupaSerch
- **Start Monitoring**: Prometheus, Grafana, Loki
- **Status**: Health check all running services
- **Reset**: Remove virtual environments and cached data

## Service Profiles

| Profile | Services | GPU Required |
|---------|----------|-------------|
| `core` | Agent Zero, Archon, BoTZ, NATS, data stores | No |
| `voice` | Ultimate-TTS-Studio, Flute-Gateway | Yes (CUDA) |
| `external` | Hi-RAG v2, DeepResearch, SupaSerch | Optional |
| `monitoring` | Prometheus, Grafana, Loki, cAdvisor | No |

## Agent Interpreter Integration

This launcher is discoverable by Pinokio 7 Agent Interpreter. Use the sidebar to select which profile to start, or let the AI assistant recommend profiles based on your task.

## Ports

| Port | Service |
|------|---------|
| 8080 | Agent Zero API |
| 8054 | BoTZ Gateway |
| 8086 | Hi-RAG v2 |
| 3030 | TensorZero |
| 3000 | Grafana |
| 9090 | Prometheus |
