# Topology & Operations Diagrams

Mermaid diagram source files for PMOVES.AI infrastructure topology and operations. All diagrams use PMOVES design system colors.

---

## Diagram Catalog

| Diagram | Type | Description | Source |
|---------|------|-------------|--------|
| [node-topology.mmd](node-topology.mmd) | Flowchart | 6-node infrastructure topology (Z890, 5090, KVM4-1/2, KVM2, CF Edge) | TOPOLOGY.md |
| [network-routes.mmd](network-routes.mmd) | Sequence | Public → Cloudflare → KVM → service routing flow | TOPOLOGY.md |
| [ci-runner-flow.mmd](ci-runner-flow.mmd) | Flowchart | GitHub event → CF Worker → runner selection logic | WORKFLOW_RUNNER_MAP.md |
| [agent-teams.mmd](agent-teams.mmd) | Graph | 11 agent teams (61 agents) with node affinity edges | agent-teams.yaml |
| [dns-subdomain-map.mmd](dns-subdomain-map.mmd) | Flowchart | pmoves.ai DNS zone → 11 subdomains → target nodes | TOPOLOGY.md |
| [model-stack.mmd](model-stack.mmd) | Flowchart | Qwen3 model family across GPU tiers (edge → xlarge) | models.yaml |

---

## Design System Colors

| Color | Hex | Usage |
|-------|-----|-------|
| Primary (Green) | `#3ecf8e` | Active nodes, success states, data services |
| Secondary (Purple) | `#9333ea` | GPU services, orchestration, processing |
| Accent (Blue) | `#3b82f6` | Cloudflare, research, data flows |
| Warning (Amber) | `#f59e0b` | Pending items, exit proxy, backup |
| Dark Background | `#1e293b` | Subgraph backgrounds |

---

## Rendering

### GitHub Native
All `.mmd` files render natively on GitHub when viewed in the repository.

### CLI Rendering
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i diagrams/node-topology.mmd -o node-topology.png -t dark -b transparent
mmdc -i diagrams/node-topology.mmd -o node-topology.svg -t dark
```

### PMOVES UI
```tsx
import { Mermaid } from '@pmoves/ui/components/Mermaid'
import topologyDiagram from './diagrams/node-topology.mmd'
<Mermaid chart={topologyDiagram} />
```

---

## Related Diagrams

- **GEOMETRY BUS diagrams:** `pmoves/docs/geometry-bus/diagrams/` (architecture, NATS taxonomy, CHR algorithm, etc.)
- **Agent topology:** `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` (auto-generated from agent_registry.yaml)
- **Animations:** `pmoves/docs/operations/animations/` (Remotion/A2UI animation specs)
