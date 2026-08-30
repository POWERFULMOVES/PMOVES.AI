# Hermes Integration Notice

> **Status:** Active — Local Mesh MOF Agent for PMOVES SDK
> **Date:** 2026-05-19
> **TAC Tree:** `pmoves/configs/tac_trees/hermes-warp-pi-agent.tac.yaml`

---

## Summary

**Hermes is NOT deprecated.** Hermes is a **local mesh MOF agent** that will be integrated into PMOVES SDK Super CLI suit.

### Integration Stack

| Component | Purpose | Source |
|-----------|---------|--------|
| **Hermes** | Local mesh MOF agent | `hermes-mod.git` (customizable) |
| **Pi Agent** | Lightweight local assistance | TBD (assess/integrate) |
| **Warp** | Modern terminal manager | `warpdotdev/WARP` (now open source) |

---

## Super CLI Suit

The PMOVES SDK Super CLI suit will provide unified command surface:

```bash
pmoves hermes <command>    # MOF mesh operations
pmoves warp <workflow>     # Warp terminal workflows
pmoves pi <command>        # Pi Agent lightweight assistance
```

---

## MOF Lattice Integration

Hermes operates as a **pore in the PMOVES MOF lattice**:

- **Mesh Discovery:** Via Tailscale (`pmoves-b850-ai-top` hostname pattern)
- **Event Bus:** NATS subjects (`hermes.agent.session.v1`, `hermes.mesh.*`)
- **Profile-Based:** Configuration via `pmoves/config/profiles/*.yaml`

---

## Follow-Up Work

See TAC tree for full integration plan:

```bash
# Track integration progress
cat pmoves/configs/tac_trees/hermes-warp-pi-agent.tac.yaml

# Phase breakdown:
# Phase 1: Hermes Assessment & Fork
# Phase 2: Warp Terminal Integration
# Phase 3: Pi Agent Integration
# Phase 4: Super CLI Suit Assembly
# Phase 5: MOF Mesh Integration
# Phase 6: Documentation & Validation
```

---

## Correction Note

**Previous deprecation notice (2026-05-19 initial version) was incorrect.**

Hermes via `hermes-mod.git` **allows customization** and is **part of the PMOVES roadmap**. The document has been corrected from "HERMES_DEPRECATION.md" to "HERMES_INTEGRATION.md".

---

## Related Documentation

- `pmoves/configs/tac_trees/hermes-warp-pi-agent.tac.yaml` — Integration TAC tree
- `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` — B850 profile
- `pmoves/docs/AGENTS/AGNOTE4482.md` — MOF architecture reference
- `PMOVES-ClawZ/` — OpenClaw framework (separate from Hermes)
