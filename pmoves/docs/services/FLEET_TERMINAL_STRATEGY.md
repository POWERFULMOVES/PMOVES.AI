# Fleet Terminal Strategy — agentic terminals for PMOVES nodes

**Status:** RESEARCH COMPLETE (2026-09-05, delegated survey; sources cited per terminal)
**Operator directive:** terminals where agents can "add their own flavors" — agent-drivable,
forkable, across omarchy (Arch) / Windows fleet / headless KVMs.

## Fleet picks

| Slot | Pick | Why |
|---|---|---|
| **PRIMARY** (omarchy workstations) | **FORK Wave Terminal** | The ONLY candidate where an agent owns the entire UI: `wsh` CLI = 40+ verbs (run/edit/ai/file/blocks/secret/setconfig/getvar/ui), YAML config-as-code, BYOK local AI (Ollama — fits local-first hardening), v0.14 durable SSH sessions (tmux-like), **Apache-2.0 cleanest fork license**, AUR waveterm-bin 0.14.5 |
| **Human shell** (omarchy) | Ghostty upstream (extra 1.3.1) + light patch-fork for PMOVES theming | MIT, ~100MB, omarchy default; libghostty embeddable core (roadmap step 5 done) = future bespoke-terminal path without writing an emulator |
| **WINDOWS** (z890/5090/elder-melchor) | Same PMOVES Wave fork (Win10 1809+) + WezTerm upstream (MIT, `wezterm cli`+Lua) as light alt; Windows Terminal as recovery shell | One `wsh` surface across the entire fleet; Ghostty/Kitty/Zellij disqualified (no native Windows) |
| **HEADLESS** (KVMs, Ubuntu 24.04) | tmux 3.7c (ISC) + Atuin 18.21 (MIT, self-hosted sync) + TPM | tmux send-keys/capture-pane is the lingua franca every agent harness already speaks — do NOT fork |

## Fork vs upstream
- **FORK**: Wave (primary), Ghostty (light patch/embed), optionally Atuin sync-server (sealed fleet history)
- **UPSTREAM**: tmux, WezTerm, Warp (AGPL+MIT split = high fork-drag; AUR install where wanted), Atuin client
- **Closed/FSL (upstream-only if ever)**: Amp, Cursor CLI, Crush (FSL-1.1 fork-hostile 2yr)

## Notable findings
- **mcp-interactive-terminal** (MIT) — MCP server giving agents real interactive-terminal control inside ANY host terminal; candidate for immediate wiring into Hermes MCP inventory
- **Amazon Q Developer CLI** (Apache-2.0) — Fig's true successor, fork-safe
- **sst/opencode** (MIT, 204k stars, in Arch extra) + Gemini CLI + Codex CLI — standardize the agent-CLI trio alongside
- Warp Agent CLI is headless-ok with self-hosted Docker/K8s agent workers (Factories) — cloud-coupled though
- wispterm (MIT, 402★) — early cross-platform terminal workspace for remote dev + AI agents; watchlist

## Weight notes
Ghostty ~100MB (lightest GPU terminal) · Wave ~300-600MB Electron · Warp ~200-400MB Rust+GPU · tmux negligible.

## Next actions (feeds lane 2)
1. PMOVES-Wave fork (PowerfulMoves/waveterm) — branding + hardening + `wsh` PMOVES verbs
2. mcp-interactive-terminal into mcp_inventory.json (hermes client) — agent-controlled terminal NOW, before any fork
3. Ghostty patch-fork for omarchy theme at workstation-customization time
4. Atuin self-host on KVM infra + client in omarchy/Windows profiles
