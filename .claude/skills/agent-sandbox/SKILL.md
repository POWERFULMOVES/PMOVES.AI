---
name: agent-sandbox
description: Manage isolated execution environments for agents — provision a sandbox, run a task in it, capture outputs, tear down cleanly. Use when running untrusted code, testing newly minted agents from Archon's factory, or verifying skill compositions without touching the host environment. Sourced from skills/PMOVES-agent-sandbox-skill/ (fork of disler/agent-sandbox-skill).
---

# Agent-Sandbox Skill (Activation Pointer)

This skill is sourced from `skills/PMOVES-agent-sandbox-skill/`. Read that submodule's `SKILL.md` / `README.md` for full usage.

## Why activated for PMOVES.AI

Archon-as-mint will provision new agents and skills that need isolated verification before they ship from the factory. Agent-sandbox is the verification substrate for the `archon-qa-agent` subordinate flow.

## When Claude should invoke

- Running a newly minted agent's first execution against a known-good fixture.
- Testing a candidate skill composition without touching the live mesh.
- Reproducing an incident in isolation.

## Cross-references

- `archon-qa-agent` (`.claude/agents/archon-qa-agent.md`) — Archon mint QA subordinate.
- `superpowers:using-git-worktrees` — git-level isolation.
- `pmoves-mesh-preflight` skill — confirm mesh health before sandboxing against it.
