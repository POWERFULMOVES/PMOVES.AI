# Five-Lane Wave — Review + Wiring Consolidated — 2026-10-30

**Lane:** FIVE-LANE WAVE (claimed 17:38Z 10-18, executed through 10-30) · All threads grounded in repo state this session.

## Lane 1 — Review Output Contract (SHIPPED + MERGED via #3386)

`.claude/agents/hermes-agent.md` carries the Review Output Contract (verdict-first, ≤5 findings, file:line mandatory, plain ASCII, BLOCKED-never-guess, self-application to own work products). **Today's upstream review shows the fix working:** the fresh upstream PR list is reviewed in exactly that shape.

### Upstream re-check (this session, agent-zero.ai docs + frdel/agent-zero)

- Upstream latest release: **v2.14** (2026-10-13) — our submodule pin matches (bumped in #3371).
- Upstream main has advanced since v2.14: 12+ commits including merged PRs #1986 (plugin notification arrivals + modal actions), #1966 (tool improvements), #1920 (recover leaked tool calls before Context Doctor), #1919 (surface output-limit truncation), #1943 (honor user-first plugin asset precedence), #1949/#1948/#1946/#1931 (chat-naming, disk-recheck, folder-download, preset-reload fixes) + docker ARM64 Xpra signed-index fix.
- **Pull recommendation:** cherry-pick or submodule bump after review — highest PMOVES value: **#1920 leaked-tool-call recovery** (stability), **#1943 plugin asset precedence** (our usr/plugins override pattern), **#1986 plugin notification surface** (a2ui/rooms). Watch item: f72945e enables Venice cache routing + custom provider overrides (we run Venice — review for compat).
- Docs site (agent-zero.ai/p/docs): structure unchanged (Installation → GitHub Docs → DeepWiki; Use Cases Library); no new sections forcing doc reconciliation.

## Lane 2 — FlOO$ PR review + assignment (SHIPPED 10-18)

PR #3339 (cipher roster → streamable-http POST /mcp) reviewed under the contract (VERDICT: APPROVE, FlOO$ pairing-lens UNDECIDED noted, checks 31✅/12 skip/1 pending), assigned POWERFULMOVES. Still OPEN — awaiting second review per no-self-approval. Suggested: PMOVES-Agent-Zero or EM Flash under the new contract.

## Lane 3 — GitHub agent @tagging (DESIGNED, rollout ready)

Design shipped: research/analyses/2026-10-18_GITHUB_AGENT_TAGGING_DESIGN.md — vocabulary github_login fields → per-agent gh_app_token.py installations → comment watcher → dispatch routing. Anti-impersonation via installation-token authorship. Phase 1 (vocabulary fields) is a 30-minute change when operator says go.

## Lane 4 — Elder Melchor ACK (RELAYED; still awaiting his line)

ACK t_f86a52a4 (bundle 2026-10-12, kid 9e66b2adc53c970d) relayed 10-18 via dispatch packet + register NOTE (A2A blocked — known road). No ACK recorded as of this session. Ping draft remains reviews/ELDER_MELCHOR_BUNDLE_ACK_PING_DRAFT_2026-10-14.md. Suggested escalation: tag him in the next merge-wave plan comment once @tagging Phase 3 ships.

## Lane 5 — Doctrine (CAPTURED)

5×5×2 dual, lines-define-not-confine, vases-not-genies, compound learning, vibrate-with-focus — all in the tagging design doc + reconciliation Part 4 (corrected to parity framing 10-23 per source).

## Bonus — upstream skills diff (for the skills fold-in lane)

Upstream frdel/agent-zero main vs our pin: the 12-commit window (listed above) concentrates in webui, docker, llm providers, and tools. UNVERIFIED at file level: agent/skills/ directory diff (v2.14 tag not present in the host shallow clone — fetch tags or clone the submodule to complete; fail-closed marked, not asserted). The 14 unpublished pmoves/skills/ (from the 10-22 skills-fold-in plan) remain our distribution gap — upstream pull and skills fold-in are independent lanes.
