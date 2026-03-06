# PMOVES.AI Distributed Topology Visualization

> Visual reference for the PMOVES submodule integration architecture.

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            PMOVES.AI Parent                                   │
│                                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ TensorZero │  │    NATS    │  │   Neo4j    │  │  Supabase  │             │
│  │   :3030    │  │   :4222    │  │   :7687    │  │  :54321    │             │
│  │  (LLM GW)  │  │  (Events)  │  │  (Graph)   │  │    (DB)    │             │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
│        │               │               │               │                     │
│  ┌─────┴───────────────┴───────────────┴───────────────┴─────┐              │
│  │                    Service Mesh (NATS)                     │              │
│  └─────┬───────────────┬───────────────┬───────────────┬─────┘              │
└────────┼───────────────┼───────────────┼───────────────┼─────────────────────┘
         │               │               │               │
         ▼               ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│      DoX       │ │      BoTZ      │ │    Tokenism    │ │     Wealth     │
│  (Documents)   │ │   (Agents)     │ │  (Simulation)  │ │   (Finance)    │
└────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘
```

## Detailed Component Architecture

### DoX (Document Intelligence)

```
┌─────────────────────────────────────────────────────────────┐
│                         DoX                                  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Agent Zero (Dual Instance)                │  │
│  │                                                        │  │
│  │   ┌─────────────┐          ┌─────────────┐            │  │
│  │   │  Headless   │◄── MCP ──►│    UI      │            │  │
│  │   │   :50051    │          │   :50052    │            │  │
│  │   │             │          │             │            │  │
│  │   │ Long-running│          │ Web Interface            │  │
│  │   │ Monitoring  │          │ Interactive │            │  │
│  │   └─────────────┘          └─────────────┘            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Backend    │  │    CHIT     │  │   Search    │         │
│  │   :8484     │  │  Geometry   │  │   Index     │         │
│  │             │  │    Bus      │  │   (FAISS)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  Capabilities: PDF Processing, Q&A, Vector Search,          │
│                Geometric Visualization, MCP Hosting          │
└──────────────────────────────────────────────────────────────┘
```

### BoTZ (Agent Platform)

```
┌─────────────────────────────────────────────────────────────┐
│                         BoTZ                                 │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                Multi-Agent Orchestration             │    │
│  │                                                      │    │
│  │  P-Threads ──► Parallel Execution                   │    │
│  │  C-Threads ──► Chained Workflows                    │    │
│  │  F-Threads ──► Fusion Consensus                     │    │
│  │  Z-Threads ──► Zero-Touch Autonomous                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Archon    │  │ MCP Gateway  │  │Cipher Memory │       │
│  │              │  │    :2091     │  │    :8081     │       │
│  │  Knowledge   │  │              │  │              │       │
│  │  + Agent     │  │  JWT Auth    │  │  System 1:   │       │
│  │    Forge     │  │  Tool Proxy  │  │   Concepts   │       │
│  │              │  │              │  │  System 2:   │       │
│  │              │  │              │  │   Reasoning  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Skills Catalog                      │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │   │
│  │  │Docling │ │  E2B   │ │   VL   │ │Postman │        │   │
│  │  │ :3020  │ │ :7071  │ │Sentinel│ │ stdio  │        │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘        │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Tokenism (Simulation Framework)

```
┌─────────────────────────────────────────────────────────────┐
│                       Tokenism                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Integration Coordinator                  │    │
│  │                                                      │    │
│  │  Event Bus ──► JSON Schema Validation               │    │
│  │  DoX Client ──► Document Analysis                   │    │
│  │  Firefly Client ──► Financial Validation            │    │
│  │  Contract Listeners ──► Smart Contract Events       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   Simulation     │  │  PMOVES-Wealth   │                 │
│  │     Engine       │  │                  │                 │
│  │     :5000        │  │  (Firefly-iii)   │                 │
│  │                  │  │     :8080        │                 │
│  │  Economic        │  │                  │                 │
│  │  Modeling        │  │  Financial       │                 │
│  │                  │  │  Tracking        │                 │
│  └──────────────────┘  └──────────────────┘                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Tier System                        │   │
│  │  API │ Data │ LLM │ Worker │ Media │ Agent           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Network Topology Examples

### Local Network (192.168.x.x)

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Network                             │
│                    192.168.1.0/24                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │ .10 Primary │     │.20 Workst'n │     │ .30 GPU Srv │   │
│  │             │     │             │     │             │   │
│  │ TensorZero  │     │    DoX      │     │    BoTZ     │   │
│  │ NATS        │◄───►│ Agent Zero  │◄───►│   Archon    │   │
│  │ Neo4j       │     │ Backend     │     │ MCP Gateway │   │
│  │ Supabase    │     │             │     │ Cipher      │   │
│  └─────────────┘     └─────────────┘     └─────────────┘   │
│         │                   │                   │           │
│         └───────────────────┼───────────────────┘           │
│                             │                                │
│                    ┌────────▼────────┐                      │
│                    │   .40 NAS       │                      │
│                    │                 │                      │
│                    │   Tokenism      │                      │
│                    │   Wealth        │                      │
│                    │   (CPU only)    │                      │
│                    └─────────────────┘                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Tailscale Mesh (100.x.x.x)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Tailscale Mesh VPN                                  │
│                          100.64.0.0/10                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Home Office                          Remote Office                         │
│   ┌─────────────────────┐              ┌─────────────────────┐              │
│   │ 100.64.1.10         │              │ 100.64.1.30         │              │
│   │ pmoves-primary      │◄────────────►│ pmoves-botz         │              │
│   │ TensorZero + NATS   │              │ BoTZ Gateway        │              │
│   └──────────┬──────────┘              └─────────────────────┘              │
│              │                                                               │
│   ┌──────────▼──────────┐                                                   │
│   │ 100.64.1.20         │                                                   │
│   │ pmoves-dox          │                                                   │
│   │ DoX + Agent Zero    │                                                   │
│   └─────────────────────┘                                                   │
│                                                                              │
│   Data Center                          Edge Devices                          │
│   ┌─────────────────────┐    ┌────────────────┐  ┌────────────────┐        │
│   │ 100.64.1.40         │    │ 100.64.1.50    │  │ 100.64.1.60    │        │
│   │ pmoves-tokenism     │    │ pmoves-orin-1  │  │ pmoves-orin-2  │        │
│   │ Tokenism + Wealth   │    │ Jetson Orin    │  │ Jetson Orin    │        │
│   └─────────────────────┘    └────────────────┘  └────────────────┘        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### VPS Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Internet                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Hostinger KVM Cluster                            │   │
│  │                                                                      │   │
│  │  ┌─────────────────────┐    ┌─────────────────────┐                 │   │
│  │  │      KVM4-1         │    │      KVM4-2         │                 │   │
│  │  │   (API Gateway)     │    │  (Data Services)    │                 │   │
│  │  │                     │    │                     │                 │   │
│  │  │  BoTZ MCP Gateway   │    │  DoX Backend        │                 │   │
│  │  │  Nginx Reverse Proxy│    │  NATS (TLS)         │                 │   │
│  │  │                     │    │  Neo4j              │                 │   │
│  │  └──────────┬──────────┘    └──────────┬──────────┘                 │   │
│  │             │                          │                             │   │
│  │             └──────────┬───────────────┘                             │   │
│  │                        │                                              │   │
│  │               WireGuard/Tailscale                                    │   │
│  │                        │                                              │   │
│  └────────────────────────┼─────────────────────────────────────────────┘   │
│                           │                                                  │
│  ┌────────────────────────▼─────────────────────────────────────────────┐   │
│  │                      Home Network                                     │   │
│  │                                                                       │   │
│  │  ┌─────────────────────┐    ┌─────────────────────┐                  │   │
│  │  │   GPU Workstation   │    │   Development       │                  │   │
│  │  │                     │    │                     │                  │   │
│  │  │  TensorZero         │    │  Tokenism           │                  │   │
│  │  │  Agent Zero (UI)    │    │  Wealth             │                  │   │
│  │  │  Inference          │    │  Testing            │                  │   │
│  │  └─────────────────────┘    └─────────────────────┘                  │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Communication Flows

### Document Processing Flow

```
User ──► DoX Frontend ──► DoX Backend ──► Docling
                              │
                              ├──► NATS: dox.document.ingested.v1
                              │
                              ▼
                    BoTZ (via MCP Gateway)
                              │
                              ├──► Archon (knowledge extraction)
                              ├──► Cipher (memory storage)
                              │
                              ▼
                         Tokenism
                              │
                              └──► Wealth (financial validation)
```

### Agent Task Dispatch

```
Agent Zero (DoX)
      │
      ├──► /orchestrate/decompose ──► Break into subtasks
      │
      ├──► NATS: botz.gateway.task.dispatched.v1
      │
      ▼
BoTZ MCP Gateway ──► Skills Catalog
      │
      ├──► Docling (document conversion)
      ├──► E2B (code execution)
      ├──► VL Sentinel (vision)
      │
      └──► NATS: botz.mcp.tool.executed.v1
                    │
                    ▼
            Agent Zero (aggregation)
```

### Geometry Bus Flow

```
DoX (Geometry Engine)
      │
      ├──► Analyze embeddings
      ├──► Detect manifold curvature
      │
      └──► NATS: geometry.event.manifold_update
                    │
      ┌─────────────┼─────────────┐
      │             │             │
      ▼             ▼             ▼
HyperbolicNav   Manifold3D    Tokenism
(DoX Frontend)  (DoX Frontend) (CGP listener)
```

## Port Reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| TensorZero | 3030 | HTTP | LLM Gateway |
| NATS | 4222 | NATS | Message Bus |
| NATS WS | 9222/9223 | WebSocket | Browser NATS |
| Supabase | 54321 | HTTP | Database API |
| Neo4j HTTP | 7474 | HTTP | Browser/API |
| Neo4j Bolt | 7687 | Bolt | Driver Protocol |
| DoX Backend | 8484 | HTTP | Document API |
| DoX Frontend | 3001 | HTTP | Web UI |
| Agent Zero Headless | 50051 | HTTP/MCP | Headless Instance |
| Agent Zero UI | 50052 | HTTP | Web UI |
| BoTZ Gateway | 2091 | HTTP | MCP Gateway |
| Cipher Memory | 8081 | HTTP/stdio | Memory API |
| Tokenism | 5000 | HTTP | Simulation API |
| Wealth (Firefly) | 8080 | HTTP | Finance API |

## Related Documentation

- [DISTRIBUTED_SUBMODULES.md](./DISTRIBUTED_SUBMODULES.md) - Deployment modes and configurations
- [SUBMODULE_ARCHITECTURE.md](./submodules/SUBMODULE_ARCHITECTURE.md) - Complete submodule inventory
- [env.shared.example](../env.shared.example) - Environment variable reference
