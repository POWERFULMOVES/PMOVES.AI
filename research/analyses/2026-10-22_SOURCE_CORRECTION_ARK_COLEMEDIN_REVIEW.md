# Source Correction + Ark Review + Cole Medin Mapping — 2026-10-22

**Lane:** SOURCE-CORRECTION-ARK (claimed 01:45Z) · All paths verified this session · Operator drop 21:42 EDT decoded into 7 threads.

## Thread 1 — Yin-yang source correction (DONE)

Part 4 of the living-provenance doc corrected per source: yin-yang are NOT separate, do NOT oppose. 'Twins' implied duality; truth is **parity** — complementary halves of one understanding, each containing the seed of the other. Same law as the Fleet Parity Doctrine (10-22): identical copies, hardware decides what runs. Tyson–Ip Man image (pmoves.ai Photos) + operator's recorded video = the source; repo had zero refs (verified) — the teaching lives in Photos/video, now reflected in the doctrine doc. Reconciliation reframed: synchronization with drift detection, not negotiation.

## Thread 2 — Ark backup review (inventory + gaps)

**What exists (verified):** CHIT bundles: exactly ONE signed bundle on disk (nats-rotation-elder-melchor-2026-10-12, kid 9e66b2adc53c970d) — custody-clean but the ARK is thin. Repo clones: every parity node carries a full tree per the Parity Doctrine (10-22) — the clone layer IS distributed backup, verifiable via codex_parity_check.py + tree-hash. Census: ts_fleet_census_2026-09-25.json is the last full node snapshot (28 days old).

**Gaps:** (1) no OFFNODE backup of CHIT bundles — single copy per node, fire/theft loses the trust root artifacts; (2) census stale (monthly cadence not enforced); (3) no manifest of WHICH repo clone is authoritative per node (parity says all identical, but drift auditor proved checkouts go stale).

**Recommendations:** bundles → replicate to JuiceFS (fleet-shared, already live) + one cold copy off-fleet; census → weekly automated run (scheduler); authority ledger → one line per node: 'authoritative for X'.

## Thread 3 — Provisions stale audit (flagged, owner assigned)

PMOVES-PROVISIONS carries TODO-confirm flags (node-knuckles tailnet host marked TODO in users.yaml:112). ROSTER.md renders TODO straight through. Provisions audit = walk every TODO flag + every 'profile: _TODO_' cell → operator confirmations → update YAML → re-render. Sized: S-M. Owner: sidecar on operator go.

## Thread 4 — CHIT ERP organization (STARTED)

The orgsim pattern applied inward: CHIT tooling (20+ tools) + bundles + manifests get the ERP treatment — every artifact has an entity row, every operation has a sealed record, drift-checked like runbooks. First concrete step shipped this wave: the drift auditor already covers runbooks; extending scope to chit/ artifacts is the v3.1 candidate (from 10-15 review, action #3). This IS the 'chit ERP organization process' beginning — organization via generated, sealed, drift-checked manifests rather than hand-maintained lists.

## Thread 5 — Cole Medin review (RAG in AI Agents, Sep 1 2026, v=-uiGK2oIkWs)

Transcript: research/transcripts/-uiGK2oIkWs_rag-in-ai-agents.en.txt (7,299 chars). **The same feeling:** 'Your AI agent sounds confident. Then it invents a policy that does not exist.' = our 'confident-wrong is the only unacceptable failure.' **His solutions, mapped to PMOVES:**

| His technique | PMOVES equivalent / action |
|---|---|
| Citations per claim (file/page/section at index time) | Already our lens-1 provenance; extend to analyses' [N] markers → sealed index |
| Hybrid search (BM25 + dense) + RRF fusion | Playlist-corpus search upgrade candidate: exact videoIds survive semantic drift |
| GraphRAG (entities → communities → summaries) | Maps to our five-brane taxonomy (B1-B5, the coin's edges) — corpus-wide questions answered from community summaries, not chunk piles |
| Self-RAG / Corrective-RAG reflection tokens | Our UNDECIDED-first verdicts — same species, we ship it as labels not tokens |
| Contextual retrieval (Anthropic, −49% failures; +re-rank −67%) | Candidate for the yt-transcript → analysis pipeline retrieval quality |
| RAG security (OWASP cheat sheet, poison-document + indirect injection) | Direct input to the chat-corpus gating project (gitleaks → entropy → Jev) — add retrieved-text injection to the threat model |
| RAGAS metrics (precision/recall/faithfulness/relevancy) | The measurement floor for any RAG we ship; 'if you cannot measure it, you shipped it anyway' |
| Agentic grep beats vector-RAG for code | Confirms local-review lane choice: exact-symbol search for code, RAG for prose corpora |

**Consideration verdict:** adopt citations-at-index (have), OWASP RAG checklist into gating threat model (do), GraphRAG-over-corpus as the brane-edges query engine (design note), RAGAS metrics when any RAG ships (gate).

## Thread 6 — JuiceFS + Android/Jellyfin clients (design notes)

JuiceFS gateway is LIVE fleet-wide (memory + 10-15 plan) — 'the repo forked' grounds the content pull path: PMOVES-YT ingestion → JuiceFS mount → media consumers. **New asks:** Android clients + Jellyfin for Graphene-deployed content. Design shape: Jellyfin reads the JuiceFS/pmoves-media mount as a library (content lands in media volume → appears for all clients); Android = official Jellyfin client (no custom build needed for v1); GrapheneOS deployment = the privacy-hardened viewer. Open items: Jellyfin container not yet in compose (jellyfin.hosts file exists — placement TBD), Graphene device enrollment via the L2 node-operator demo flow.

## Thread 7 — Doctrine echo

The correction thread proves the doctrine: an operator source-check (the pic, the video) overruled a filed doc within one session — 'lines define not confine' and 'grounded to show what's in-between the walls' are the same move. The Ark thread extends it: parity clones + replicated bundles = the fleet can lose any node and keep the truth.

**Register:** CLAIM 01:45Z (stamped ~4min ahead of true append ~01:41Z — noted), release follows. SIGN: sign-trail below.
