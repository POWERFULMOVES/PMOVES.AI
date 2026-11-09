---
name: pocket-init
description: >
  Initialize a Pocket agent workspace — creates the memory/ directory and an
  IDENTITY.md, then wires the IM gateway config for the messaging CLIs the agent
  will speak through (MiniMax mmx, Feishu/Lark, WeCom). Use when standing up a
  new Pocket workspace, bootstrapping an agent's identity and memory layout, or
  adding a messaging platform to an existing gateway config. Covers Pocket,
  workspace init, agent identity, IM gateway, mmx, lark, feishu, wecom,
  工作区初始化, 网关配置.
license: MIT
compatibility: Requires bash (init.sh) or PowerShell (init.ps1); the messaging CLIs are optional and needed only for the platforms actually configured.
metadata:
  author: MiniMax Agent
  adapted-by: PMOVES.AI
  version: "1.0.0-pmoves"
  category: agent-bootstrap
  upstream: none
---

# pocket-init

Bootstrap a Pocket agent workspace and its IM gateway configuration.

## Initialize

```bash
scripts/init.sh <workspace_dir>      # bash
scripts/init.ps1 <workspace_dir>     # PowerShell
```

Creates `<workspace_dir>/memory/` and seeds an `IDENTITY.md` from the template.

## Gateway configuration

`references/gateway-config.md` carries the rule that matters most here:
**read-modify-write, never write blind.** `gateway.config.json` holds settings for
every platform at once, so reading the existing file before updating it is what
keeps configuring one platform from silently dropping another.

## Messaging CLIs

| platform | reference | upstream |
|---|---|---|
| MiniMax | `references/mmx-cli.md` | `MiniMax-AI/cli` — Global (`api.minimax.io`) and CN (`api.minimaxi.com`) regions, Node 18+, active Token Plan |
| Feishu / Lark | `references/lark-cli.md` | `larksuite/cli` |
| WeCom | `references/wecom-cli.md` | `WecomTeam/wecom-cli` |

## Provenance

**PMOVES-local. There is no upstream counterpart.** Authored by MiniMax Agent on
2026-05-13 and landed in PMOVES.AI via #1484 as "skill scaffolding".

`MiniMax-AI/skills` has no `pocket-init` — verified against its full tree, its
commit history for that path (zero commits), its tags (none), and every branch.

Of the five skills that landed in that PR this is the most PMOVES-shaped: agent
identity, a memory directory, and gateway wiring are the concerns of the
[agent card](../../../pmoves/docs/AGENTS/AGNOTE4482.md) rather than of a document
format. It shipped without a `SKILL.md`, which is why the `skills` package could
not see it. This file is that missing entry point.
