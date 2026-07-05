# Research Summary: NousResearch Hermes Agent Deep Dive (Neotron Labs Livestream)
**Source:** https://www.youtube.com/watch?v=pgQDbRMa2Eg  
**Date:** 2026-06-04  
**Relevance:** PMOVES.AI HERMES Agent integration architecture and security

---

## Executive Summary
NousResearch (Johnny, Karen) demoed Hermes Agent running inside **OpenShell** -- a sandboxing/policy environment that gates egress, masks secrets, and supports multi-user (Alice/Bob) agent instances. The demo showcased PR workflow automation, skill creation, environment variable masking, and integration with Discord/Telegram/Slack/GitHub. Key positioning: Hermes is the **"agent infrastructure layer."**

## Architecture Components

### 1. OpenShell (Sandboxing Layer)
| Feature | Description |
|---------|-------------|
| Policy-based egress | Controls what sandboxes can talk to (Telegram, Discord, Slack, GitHub) |
| Environment variable masking | Secrets masked inside sandbox, substituted at egress |
| Multi-user | Alice (pre-onboarded) + Bob (onboarded live) |
| Onboard scripts | Automated sandbox creation per user |
| Strict access controls | Policy gates prevent unauthorized external access |

### 2. Hermes Agent Core
- Runs inside OpenShell sandbox
- Has memory (learns workflows as you go)
- Supports PR workflows: review, create, merge (rebase)
- GitHub API integration (token masked inside sandbox)
- Skill creation from PR workflows ("salvage" workflow as skill)
- Discord/Telegram/Slack platform integrations

### 3. Workflow Automation Demoed
1. **Alice's PR workflow:**
   - Hermes finds repo, reviews PR #1
   - Connects to GitHub API, pulls PR details
   - Cherry-picks commits, creates review
   - Merges PR using rebase
   - Salvages workflow as reusable skill

2. **Bob's onboarding:**
   - Onboard script creates Bob's sandbox
   - Environment variables passed through
   - Token masking demo: `echo $GITHUB_TOKEN` shows masked value inside sandbox, substituted at egress
   - Policy enforcement: forbidden domains blocked

3. **Multi-tenancy:**
   - Per-user sandboxes
   - Per-user skills (Bob doesn't automatically get Alice's skills)
   - Admin policy controls

## Key Quotes
- "Hermes is built to cultivate that feeling inside of a user system"
- "Models are going to make harnesses better. This is the beginning of another big loop"
- "We're serving the agent infrastructure layer today"
- "Yarn enabled agentic coding and reasoning by extending context length massively"

## NousResearch Team Insights
| Person | Role | Contribution |
|--------|------|--------------|
| Johnny | ML Engineer / Agent Dev | Data work, application work, agent work, demo lead |
| Karen | Operations / Partnerships | First Hermes model training, Discord ops, partnerships, agent infrastructure |
| Team | Collective | "Giga brains", open-source volunteer researchers |

## PMOVES.AI Relevance

### Security Architecture Enhancement
**OpenShell concepts should inform PMOVES agent room security:**
1. **Policy-based egress** per room/sandbox
2. **Environment variable masking** for secrets (CHIT secrets funnel alignment)
3. **Multi-user sandboxing** within agent rooms
4. **Strict access controls** before production promotion

### HERMES Agent Room Update
Current `hermes-agent.room.control.json` should add:
- `sandbox_policy` section mirroring OpenShell egress controls
- `multi_user` flag for Alice/Bob-style tenancy
- `workflow_salvage` capability (learn from PRs, create skills)
- `memory_enabled: true` (Hermes learns workflows)

### Model Infrastructure Alignment
- NousResearch works closely with NVIDIA Neotron series
- Hermes models + Neotron models = natural pairing
- "Yarn" context extension technology mentioned for long-context agentic coding
- Neutron 3 Ultra is positioned as ideal backend for Hermes Agent

### Integration Opportunities
1. **OpenShell-style sandboxing** for PMOVES agent rooms
2. **PR workflow skills** for `.claude/skills/hermes-agent-integration/`
3. **Multi-user agent instances** per PMOVES node
4. **Environment variable masking** in CHIT secrets funnel
5. **Policy gating** for external API access (GitHub, Discord, etc.)

### Action Items
1. [ ] Evaluate OpenShell integration for PMOVES agent rooms
2. [ ] Add `sandbox_policy` to `hermes-agent.room.control.json`
3. [ ] Create `hermes-pr-workflow` skill for GitHub PR automation
4. [ ] Document environment variable masking in CHIT secrets funnel
5. [ ] Update `HERMES_AGENT_INTEGRATION.md` with OpenShell security model
6. [ ] Add Neotron 3 Ultra + Hermes pairing note to Spark node profile
