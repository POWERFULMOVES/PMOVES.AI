# Governance Roster — Governance Overlay

> **Who governs what.** Rendered from
> [`../PMOVES-PROVISIONS/roster/users.yaml`](../PMOVES-PROVISIONS/roster/users.yaml) +
> [`groups.yaml`](../PMOVES-PROVISIONS/roster/groups.yaml), surfacing the governance slice:
> guild roles, charters, DAO attribution. Sits in L5-LEGENDARY alongside the org audit.
> Discovery view → [`../ROSTER.md`](../ROSTER.md); access view →
> [`../PMOVES-PROVISIONS/ACCESS_ROSTER.md`](../PMOVES-PROVISIONS/ACCESS_ROSTER.md).

## Governing instruments

| Instrument | Location | Governs |
|-----------|----------|---------|
| **DAO Constitution** | [`L2-DESIGN/constitution/Cataclysm_DAO_Constitution_v0.1.md`](../L2-DESIGN/constitution/Cataclysm_DAO_Constitution_v0.1.md) | Membership, decision rights, treasury |
| **Infra Cloud Guild Charter** | [`L2-DESIGN/charters/Infra_Cloud_Guild_Charter_v0.1.md`](../L2-DESIGN/charters/Infra_Cloud_Guild_Charter_v0.1.md) | Fleet infra authority + scope |
| **AGNOTE4482 signoff** | `pmoves/docs/AGENTS/AGNOTE4482.md` | Multi-agent convergence, claims, persona-schema changes |
| **CHIT Attribution** | `PMOVES-ToKenism-Multi/integrations/contracts/chit/` | Resonance/attribution (not blame) across contributors |

## Guilds → governance

| Guild | Charter | Governance role | Members |
|-------|---------|-----------------|---------|
| **Core** | — | Final signoff (Emperor); memory custody | darkxside, cipher, node-4090 |
| **DAO Governance** | DAO Constitution | Constitution amendments, org audit, attribution | darkxside |
| **Infra Cloud** | Guild Charter v0.1 | Fleet infra decisions, exit-node + secrets policy | 11 actors (see roster) |
| **Delivery** | — | Implementation signoff via Three-Body (Delivery body) | claude-4090, kilocode, codex |
| **Voice / FlOO$** | — | Persona/voice suit governance → PERSONAS.md (AGNOTE4482) | minimax-floos |

## Decision rights (current)

- **Emperor (darkxside)** — final signoff on direction, merges, releases (Emperor-CHIT-Humility).
- **Three-Body** — Delivery / Control / Memory separation for change flow (AGNOTE4482).
- **Persona/suit changes** — governed by PERSONAS.md under AGNOTE4482 signoff, not ad hoc.
- **Attribution** — resonance tracking via CHIT, not blame; the concerto self-heals and covers.

## Open governance TODOs

- Human DAO membership beyond the founder is unpopulated — add members to `users.yaml:humans`
  and record their decision rights here.
- Guild charters exist only for Infra Cloud; Core/Delivery/Voice charters are TODO if formalized.
- Fordham Hill pilot participants (L3) are not yet carded as governance actors.

---

_Governance data is owned in the roster YAML + the constitution/charters; this overlay is a rendered
view. Amendments follow the DAO Constitution + AGNOTE4482 signoff._
