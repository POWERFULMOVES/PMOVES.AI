# CHIT Change Tracker

**Living Document** | **Last Updated:** 2026-04-25

> Tracks documentation changes via CHIT metadata. Each entry follows a CGP-style format: timestamp, author, layer, affected docs, and PR/commit reference. This enables an auditable trail of documentation evolution.

---

## Format

Each entry uses the following structure:

```
### YYYY-MM-DD | Layer | Author | PR/Commit
- **Action:** Created / Updated / Deprecated / Removed
- **Files:** List of affected files
- **Summary:** What changed and why
- **Cross-links:** Related documents affected
```

---

## Changelog

### 2026-04-25 | L3 | Codex CLI | working tree

- **Action:** Created / Updated
- **Files:**
  - `pmoves/docs/architecture/PMOVES_SPARK_PROVENANCE_PARITY.md` (NEW)
  - `pmoves/docs/AGENTS/AGNOTE-dgx-spark.md` (UPDATED - expanded from node stub to working lane note)
  - `pmoves/docs/DOCUMENTATION_MAP.md` (UPDATED - added parity/control-plane entries)
- **Summary:** Added a provenance-first working contract for the SPARK lane so raw content is shaped, scored, attested, and only then allowed into HiRAG. Cross-linked the new contract into the SPARK AGNOTE and the documentation map to reduce canon drift and make the Hyperdimensions + provenance lane discoverable.
- **Cross-links:** `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`, `pmoves/docs/GRAPHITI_PROTOCOL_REFERENCE.md`, `pmoves/docs/CONCH_INTEGRATION_MAP.md`, `pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md`

### 2026-02-19 | L5 | Claude Code CLI | docs/chit-living-docs branch

- **Action:** Created
- **Files:**
  - `pmoves/docs/DOCUMENTATION_MAP.md` (NEW)
  - `pmoves/docs/SERVICE_DOCS_MATRIX.md` (NEW)
  - `pmoves/docs/CHIT_CHANGE_TRACKER.md` (NEW)
  - `pmoves/docs/evidence/SUBMODULE_DOCS_AUDIT.md` (NEW)
  - `pmoves/docs/PMOVESCHIT/README.md` (UPDATED - crosslinks)
  - `.claude/context/documentation-index.md` (UPDATED - new entries)
  - `pmoves/docs/INTEGRATIONS_OVERVIEW.md` (UPDATED - 6th integration system)
- **Summary:** Documentation infrastructure creation. Established CHIT-organized living docs with 5-layer taxonomy (L1 Protocol, L2 Conceptual, L3 Applied, L4 Vision, L5 Operations). Added cellular namespace topology model capturing service publish/subscribe identity, membrane boundaries, and CHIT-signed announcements.
- **Cross-links:** All new docs crosslinked to existing PMOVESCHIT README, Integration Overview, and Documentation Index.

### 2026-02-19 | L5 | Claude Code CLI | b360f78d

- **Action:** Updated
- **Files:**
  - `.github/workflows/python-tests.yml`
  - `.github/workflows/sql-policy-lint.yml`
  - `.github/workflows/codeql.yml`
  - 13x `pmoves/services/*/tests/__init__.py` (NEW)
- **Summary:** CI fixes: resolved conftest collision (--rootdir=. + __init__.py in 13 test dirs), added 2 SQL migrations to lint allowlist, added continue-on-error for JS/TS CodeQL.
- **Cross-links:** L5 CI configuration.

### 2026-02-18 | L5 | CLI + Human | PR #665

- **Action:** Created / Updated
- **Files:**
  - `pmoves/docs/SUBMODULE_LAYER_VALIDATION.md`
  - `pmoves/docs/evidence/submodule_layer/*.json` + `*.md`
- **Summary:** Taxonomy restructure with submodule validation evidence for all 41 submodules. Layer validation tool output captured as evidence artifacts.
- **Cross-links:** L3 Submodules Catalog, L5 Evidence Directory.

### 2026-02-18 | L1 | CLI + Human | PR #663

- **Action:** Created
- **Files:**
  - `PMOVES-llama-throughput-lab/` (submodule)
  - Docker compose integration
- **Summary:** Integrated llama-throughput-lab benchmark runner into compose and observability stack.
- **Cross-links:** L3 Services Catalog, L5 Monitoring.

### 2026-02-16 | L5 | CLI + Human | Phase C Audit

- **Action:** Created
- **Files:**
  - `pmoves/docs/evidence/production_audit/2026-02-16_codex_targeted_smokes.md`
  - Multiple submodule audit reports
- **Summary:** Phase C security audit of 8 critical submodules. Identified P1 issues: root containers, NATS auth missing, JWT fail-open, Cypher injection, default credentials.
- **Cross-links:** L5 Production Audit Dashboard.

---

## Statistics

| Metric | Value |
|--------|-------|
| Total entries | 6 |
| L1 Protocol changes | 1 |
| L2 Conceptual changes | 0 |
| L3 Applied changes | 1 |
| L4 Vision changes | 0 |
| L5 Operations changes | 4 |
| Documents created | 18+ |
| Documents updated | 8 |
| Documents deprecated | 0 |

---

## How to Add Entries

When making documentation changes:

1. Add a new entry at the top of the Changelog section
2. Use the format template above
3. Classify the change by CHIT layer (L1-L5)
4. Include the PR number or commit hash
5. List all affected files
6. Update the Statistics table
7. Update cross-links in affected documents

CI integration: The `integration-contract-gate.yml` workflow can be extended to auto-append entries when documentation files change.

---

*See also: [DOCUMENTATION_MAP.md](DOCUMENTATION_MAP.md) for layer taxonomy and [SERVICE_DOCS_MATRIX.md](SERVICE_DOCS_MATRIX.md) for service documentation cross-reference.*
