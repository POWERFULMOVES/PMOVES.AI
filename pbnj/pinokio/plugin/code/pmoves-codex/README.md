# PMOVES Codex Pinokio Plugin

PMOVES wrapper plugin for OpenAI Codex inside Pinokio.

## Purpose

This plugin keeps the upstream Codex terminal flow but injects PMOVES mesh defaults into the target workspace:

- `PMOVES_AGENT_ZERO_URL`
- `PMOVES_AGENT_ZERO_UI_URL`
- `PMOVES_ARCHON_URL`
- `PMOVES_HIRAG_URL`
- `PMOVES_NOTEBOOK_API_URL`
- `PMOVES_NATS_URL`

The goal is to keep provider-native behavior while giving Codex a stable PMOVES contract to build against.

## Install

Copy or symlink this folder into your Pinokio plugin directory:

```bash
~/pinokio/plugin/pmoves-codex
```

On this node the live Pinokio home is `D:/pinokio`, so the effective install target is:

```text
D:/pinokio/plugin/pmoves-codex
```

## Usage

1. Open any Pinokio workspace or installed PMOVES app.
2. Choose `PMOVES Codex` from Ask AI or Plugins.
3. Codex launches in the selected workspace with PMOVES mesh defaults available in the environment.

## Notes

- This plugin does not replace Pinokio's built-in `codex` plugin.
- It is the PMOVES-customized wrapper layer for Codex-specific defaults.
- Keep direct agent-to-agent communication on the PMOVES mesh, not inside the plugin itself.
