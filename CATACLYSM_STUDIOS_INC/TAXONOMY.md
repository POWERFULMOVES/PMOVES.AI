# Cataclysm Studios Inc -- Taxonomy & Progression Map

> From research napkin to production DAO -- every document filed by maturity tier.

---

## Tier Matrix

| Tier | Label | Conceptual Layer | Timeline | What Lives Here |
|------|-------|-----------------|----------|-----------------|
| **L1** | Foundation | Signal Discovery | Early research | Raw research, articles, case studies, FAQ |
| **L2** | Design | Protocol Architecture | Design phase | Tokenomics models, DAO constitution, charters, proposals |
| **L3** | Pilot | Community Proof | Fordham Hill pilot | MVP validation, Bronx cooperative field notes |
| **L4** | Platform | Technical Engine | PMOVES.AI build | 60+ microservices, projections, infra-as-code, provisions |
| **L5** | Legendary | DAO + Attribution | Audit & scale | Production audit, DAO governance, Shape Attribution |

---

## Progression Flow

```
L1-FOUNDATION          L2-DESIGN             L3-PILOT              L4-PLATFORM           L5-LEGENDARY
 Research &   -------> Tokenomics &  ------> MVP at        ------> Production    ------> DAO Governance
 Signal Discovery      Protocol Design       Fordham Hill           System Build           & Attribution

  articles.md           Food Coop             coinsetupfordham       5-Year Projections     Org Audit
  TCM FAQ               DAO Constitution      MVP Engagement         Docker-Style Scaling   Shape Attribution
  Food Research         Hybrid Tokens         Fordham Plan Draft     Provisions Infra       Swarm Attribution
                        Charters                                     Multi-Agent Paper
                                                      |
                                        CHIT Geometry Bus (through-line)
                                        ================================
                                        CGP Generator -> Zeta Filter -> Shape Attribution
                                        Dirichlet Weights -> Hyperbolic Encoder -> Swarm
```

---

## L1 -- Foundation (6 files)

Research inputs, case studies, and early signal discovery.

| File | Description |
|------|-------------|
| `articles.md` | Curated article summaries on cooperative economics and AI |
| `articles_long.md` | Extended deep-dive versions of the article research |
| `food_questionaire_research.md` | Community food access survey design and findings |
| `Cataclysmstudios_Research_SIM_TCM.md` | Simulation theory and tokenized community model research |
| `Cataclysmstudios_TCM_FAQ.md` | FAQ on the Tokenized Community Model |
| `PMOVES_FOOD_GEMREV.pdf` | Gemini-reviewed food cooperative feasibility analysis |

**Cross-references (ToKenism-Multi):**
- Research underpinnings for `integrations/projections/scenario-configs.ts` economy scenarios
- Food cooperative concepts feed into `contracts/solidity/contracts/GroupPurchase.sol`

---

## L2 -- Design (15 files across 5 subdirs)

Protocol architecture: tokenomics, governance structures, and strategic proposals.

### tokenomics/ (7 files)

| File | Description |
|------|-------------|
| `Food Cooperative & Group Buying System design.md` | Core cooperative buying system architecture |
| `Food Cooperative & Group Buying System - Tokenomics & Smart Contract Design.md` | Token economics and smart contract specification |
| `Food Cooperative & Group Buying System -- Tokenomics & Smart Contract Design (v2.0).md` | v2 revision with refined token mechanics |
| `Integrating Hybrid Manufacturing Technologies.md` | Hybrid manufacturing integration with token incentives |
| `Integrating Tokenized Cooperative Models 3d.md` | 3D modeling of cooperative tokenized structures |
| `pmoves_hybrid_tokens.md` | Hybrid utility token specification (stable + utility) |
| `pmoves_hybrid_tokens.pdf` | PDF export of hybrid token spec |

### charters/ (5 files)

| File | Description |
|------|-------------|
| `Fordham_Hill_Board_Deck_v0.2.pptx` | Board presentation deck for Fordham Hill cooperative |
| `Fordham_Hill_Business_Deck_v0.2.pptx` | Business case deck for external stakeholders |
| `Fordham_Hill_Residents_Deck_v0.2.pptx` | Resident-facing overview deck |
| `Infra_Cloud_Guild_Charter_v0.1.docx` | Infrastructure Cloud Guild founding charter |
| `RPE_Topic_Synthesis_Appendix_v0.1.docx` | Research, Protocol, Engineering topic synthesis |

### constitution/ (1 file)

| File | Description |
|------|-------------|
| `Cataclysm_DAO_Constitution_v0.1.docx` | DAO constitutional framework and governance rules |

### content-strategy/ (1 file)

| File | Description |
|------|-------------|
| `Cataclysmstudios_YouTube_Channel_Content_Strategy.md` | YouTube channel content strategy and publishing plan |

### proposals/ (1 file)

| File | Description |
|------|-------------|
| `Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.docx` | Formal DAO proposal for the Fordham Hill pilot |

**Cross-references (ToKenism-Multi):**
- Tokenomics designs implemented in `contracts/solidity/contracts/` (FoodUSD.sol, GroToken.sol, GroupPurchase.sol, GroVault.sol, CoopGovernor.sol)
- DAO constitution maps to `integrations/contracts/chit/` modules (cgp-generator.ts, zeta-filter.ts)
- Hybrid token spec realized in `integrations/contracts/chit/shape-attribution.ts`

---

## L3 -- Pilot (8 files)

MVP implementation and real-world validation at the Fordham Hill cooperative (Bronx, NY).

| File | Description |
|------|-------------|
| `Cataclsymstudios_MVP_&_Community_Engagement.md` | MVP scope and community engagement strategy |
| `Cataclysmstudios_MVP_and_CONTENT.md` | Content production plan for MVP launch |

### fordham/ (6 files)

| File | Description |
|------|-------------|
| `coinsetupfordham.md` | Token deployment configuration for Fordham Hill |
| `coinsetupforfham_update.md` | Updated token setup with revised parameters |
| `foodcomponentfordham.md` | Food cooperative component design for Fordham |
| `fordhamcoinsetup.md` | Detailed coin setup procedures |
| `Fordhamplandraft.md` | Fordham Hill implementation plan draft |
| `PMoves_frodham.md` | PMOVES integration plan for Fordham cooperative |

**Cross-references (ToKenism-Multi):**
- Pilot projections validated against `integrations/projections/calibration-engine.ts`
- Economy simulation in `integrations/projections/projection-validator.ts`
- Scenario configs in `integrations/projections/scenario-configs.ts`

---

## L4 -- Platform (100+ files across 4 subdirs)

Production system: the PMOVES.AI technical engine, financial projections, and infrastructure code.

### vision/ (2 files)

| File | Description |
|------|-------------|
| `Cataclysm Studios Platform Vision & Brand Identity.md` | Platform vision and brand identity document |
| `Visionary AI_ Global Network, Local Power.md` | Global AI network architecture vision |

### projections/ (12 compiled reports + data/ with 4 dataset directories)

Compiled reports include 5-Year Business Projections, Community Wealth Building, Containerized Micro Business Models, Docker-Style Scalable Business Containers, Fordham Hill Traditional vs Tokenomics comparison, Medical Cannabis Cooperative Integration, Phase 2 Cooperative Growing Models, and Empowering Creativity with AI and Tokenomics.

The `data/` subdirectory contains CSV datasets, Python chart scripts, and prompt files for each projection model.

### provisions/ (~50 files)

Complete infrastructure-as-code tree inherited from PMOVES-PROVISIONS:
- `backup/` -- Linux and Windows backup scripts
- `docker-stacks/` -- Compose files (Cloudflared, Jellyfin-AI, Netdata, NPM, Ollama, Portainer, RustDesk)
- `inventory/` -- Node inventory (nodes.yaml)
- `jetson/` -- NVIDIA Jetson post-install and NGC scripts
- `linux/` -- Ubuntu autoinstall and Pop!_OS post-install
- `proxmox/` -- PVE installation scripts
- `tailscale/` -- Mesh VPN setup (Linux + Windows)
- `ventoy/` -- Multi-boot USB configuration
- `windows/` -- Autounattend.xml, RustDesk, post-install PowerShell

### notes/ (1 file)

| File | Description |
|------|-------------|
| `pmoves_multi_agent_paper.md` | Multi-agent orchestration architecture paper |

**Cross-references (ToKenism-Multi):**
- NATS event bus: `integrations/nats/nats-client.ts`
- Event-driven architecture: `integrations/event-bus/event-bus.ts`, `schema-validator.ts`
- Provisions infra supports the 60+ microservice deployment documented in `.claude/CLAUDE.md`

---

## L5 -- Legendary (2 files)

Production DAO governance, organizational audit, and attribution systems.

### dao-audit/Organizational Audit & Recommendations/

| File | Description |
|------|-------------|
| `Google Drive Deep Dive & Accuracy Check.docx` | Comprehensive organizational audit and recommendations |
| `Google Drive Deep Dive & Accuracy Check.docx.pdf` | PDF export of the audit |

**Cross-references (ToKenism-Multi):**
- DAO governance code: `integrations/contracts/chit/swarm-attribution.ts`
- Shape attribution: `integrations/contracts/chit/shape-attribution.ts`
- CGP generator: `integrations/contracts/chit/cgp-generator.ts`
- Dirichlet weight allocation: `integrations/contracts/chit/dirichlet-weights.ts`
- Hyperbolic encoding: `integrations/contracts/chit/hyperbolic-encoder.ts`

---

## Evidence Layer (15 files)

Raw research outputs proving the journey from idea to implementation. See `evidence/README.md` for the full inventory.

| Category | Count | Examples |
|----------|-------|---------|
| Audio recordings | 2 | Hybrid Utility Tokens podcast (.mp3, .wav) |
| Simulation theory papers | 4 | Holographic models research (.docx, .pdf) |
| PDF exports of research chats | 9 | Research conversation snapshots |

---

## CHIT Geometry Bus -- The Through-Line

The Compressed Hierarchical Information Transmission (CHIT) system is the mathematical backbone connecting all five tiers:

```
L1 Research signals
  -> L2 Tokenomics design (CGP patterns, Zeta filtering)
    -> L3 Pilot calibration (Dirichlet weights, projection validation)
      -> L4 Production event bus (NATS subjects: tokenism.*, geometry.*)
        -> L5 DAO attribution (Shape Attribution, Swarm Attribution)
```

Key CHIT modules in `PMOVES-ToKenism-Multi/integrations/contracts/chit/`:

| Module | Tier Mapping | Purpose |
|--------|-------------|---------|
| `cgp-generator.ts` | L2 -> L4 | Generates Compressed Geometry Payloads |
| `zeta-filter.ts` | L2 -> L3 | Filters signal from noise in token economics |
| `dirichlet-weights.ts` | L3 -> L4 | Weight allocation for cooperative distributions |
| `hyperbolic-encoder.ts` | L3 -> L4 | Encodes hierarchical relationships |
| `shape-attribution.ts` | L4 -> L5 | Attributes value contributions across the network |
| `swarm-attribution.ts` | L5 | Multi-agent swarm-level attribution |
| `chit-nats-publisher.ts` | L4 | Publishes CHIT events to the NATS Geometry Bus |
