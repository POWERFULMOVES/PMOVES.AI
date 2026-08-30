# docs(hermes): HERMES integration spec + research + AGNOTE updates

**Status**: MERGED (commits pushed to main -- retrospective PR for review)
**Commits**: 3
**Total lines**: ~800 (mostly docs)

## Commits

| SHA | Message |
|-----|---------|
| e84155799 | docs(hermes-docs): add HERMES integration spec + atomic commits guide |
| 00ea97528 | docs(hermes-research): add Neotron 3 Ultra + Hermes Agent research + submodule init scripts |
| a03f3eb61 | docs(hermes-docs): update AGNOTE4482PHI claim + TAC tree with revised scope |

## What Changed

- **HERMES_AGENT_INTEGRATION.md**: Full integration spec with:
  - Architecture diagram (gateway + NATS + model mesh)
  - Provider Credential Mapping (6-tier hierarchy)
  - BPM Three-Layer Bridge Architecture (BPM¹ Beats Per Minute, BPM² Bridge Protocol Module, BPM³ Business Process Management)
  - PMOVES.AI Submodule Fleet catalog (10 tiers, 50+ repos)
  - Ageless Beauty practice context (NP independent practice, HIPAA)
- **HERMES_ATOMIC_COMMITS.md**: Commit standards for PMOVES (type(scope): subject, <400 lines, CHIT-signed)
- **Neotron 3 Ultra research**: RESEARCH_Neotron3_Ultra.md + YouTube transcripts for GB10/128GB node planning
- **AGNOTE4482PHI.t1.md**: HERMES-AGENT claim covering room manifest, TAC tree, 8 node profiles, registry, operator skills, OpenShell sandbox, atomic commits guide

## Impact Assessment

- Documentation only. No runtime code changes.
- Submodule init scripts provided (bash + Windows batch) for Ageless Beauty practice.

## Security Note

- AGNOTE4482PHI.t1.md contains pre-existing IP addresses from other agents' claims (Z890-CLAUDE, SPARK-KIMI). These are operational coordination data, NOT introduced by our commits.

---
*Review requested by: elder-melchor*
