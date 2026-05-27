#!/usr/bin/env bash
# prompt-keyword-surfacer.sh — UserPromptSubmit hook (Layer 1: COMBINER pipeline)
#
# Scans user prompt for PMOVES domain keywords and surfaces the relevant
# code-mode tools, agent classes, and skills as additionalContext.
# Claude sees these before processing — tools surface semantically.
#
# Always exits 0 with decision=approve. Never blocks.

set -o pipefail 2>/dev/null || true

PROMPT="${CLAUDE_USER_PROMPT:-}"

if [ -z "$PROMPT" ]; then
    echo '{"decision":"approve"}'
    exit 0
fi

SURFACED=""
append() { SURFACED="${SURFACED}${SURFACED:+\\n}$1"; }

# ── Website / Deploy / Cloudflare ──────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(website|deploy|cataclysmstudios|cloudflare|pages|wrangler|landing)'; then
    append "DEPLOY surface:"
    append "  code-mode-hostinger-sites  -> hosting_* create/deploy/list (pmoves-full)"
    append "  code-mode-cf-deploy        -> wrangler pages deploy (pmoves-cf-deploy)"
    append "  memory entity: cataclysmstudios-deploy -> dns-operator + site-deployer"
    append "  Plan: .claude/plans/cataclysmstudios-com-goes-through-cloudl-glistening-aurora.md"
fi

# ── DNS / Domain / Nameserver ───────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(dns|nameserver|domain|ns1|ns2|zone|record|mx |spf|dkim)'; then
    append "DNS surface:"
    append "  code-mode-hostinger-dns    -> DNS_* + domains_updateNameserversV1"
    append "  agent class: dns-operator  -> pmoves-full profile"
    append "  Domain ID 9582301 (cataclysmstudios.com) | email: titan.email"
fi

# ── VPS / Server ────────────────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(vps|virtual.?machine|restart vps|reboot|firewall|snapshot vps)'; then
    append "VPS surface:"
    append "  code-mode-hostinger-vps    -> VPS_* lifecycle/firewall/metrics"
    append "  Fleet: KVMII=630926  CLOUD2.KVMIV=1125072  CLOUD1.KVMIV=1184789"
fi

# ── Research / Fetch / Scrape ────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(research|fetch|scrape|browse|screenshot|puppeteer|youtube|transcript)'; then
    append "RESEARCH surface:"
    append "  code-mode-researcher       -> puppeteer + fetch + yt_transcript + memory"
    append "  agent class: researcher    -> pmoves-full profile"
fi

# ── File / Build / Docs ──────────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(context7|library docs|code-mode-builder)'; then
    append "BUILDER surface:"
    append "  code-mode-builder          -> filesystem + context7 + memory"
    append "  agent class: builder       -> pmoves-full profile"
fi

# ── Hermes / AutoClaw / COMBINER ─────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(hermes|autoclaw|4090|combiner|pipeline|node.?agent)'; then
    append "HERMES surface:"
    append "  Branch: feat/hermes-4090-evolution (Phases 0-6)"
    append "  Plan: PMOVES COMBINER (cataclysmstudios-com-goes-through-cloudl-glistening-aurora.md)"
    append "  Activate: mcp-activate-profile({ name: \"pmoves-full\" })"
fi

# ── Archon / Skill / Creator ─────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(archon|skill creator|onboard agent|mint.?skill|agent.?class)'; then
    append "ARCHON surface:"
    append "  /archon:creator-onboard    -> new agent class + skill scaffold"
    append "  /archon:mint-skill         -> register skill in marketplace"
fi

# ── Cipher / Memory / Graph ──────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(cipher|memory graph|knowledge graph|search_nodes|open_nodes)'; then
    append "CIPHER surface:"
    append "  /cipher:search  Docker MCP: search_nodes() open_nodes() read_graph()"
    append "  Graph: 12 entities + 17 relations (seeded 2026-05-25)"
    append "  Cipher SSE: http://localhost:8105/sse"
fi

# ── NATS / Events ────────────────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(nats|publish event|jetstream|nats subject)'; then
    append "NATS surface:"
    append "  pmoves-nats-fleet MCP      -> cross-node pub/sub (PR #1490)"
    append "  /nats:publish /nats:status -> skill entrypoints"
fi

# ── TAC / CHIT / Claims ───────────────────────────────────────────────────────
if echo "$PROMPT" | grep -iqE '(tac tree|chit|sign.?trail|village.?rule|phi\.t1|agnote)'; then
    append "GOVERNANCE surface:"
    append "  make -C pmoves sign-trail SUMMARY=... AGENT=4090-CLAUDE"
    append "  Claims: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"
fi

# No keywords matched — silent pass
if [ -z "$SURFACED" ]; then
    echo '{"decision":"approve"}'
    exit 0
fi

# Emit matched context as message (visible to Claude, not user)
MSG="<user-prompt-submit-hook>\nCOMBINER keyword match — surfaced tools:\n\n${SURFACED}\n</user-prompt-submit-hook>"
printf '{"decision":"approve","message":"%s"}' "$(echo "$MSG" | sed 's/"/\\"/g')"
exit 0
