# PMOVES-LTX-Desktop Integration: Skill & Workflow Gap Analysis

**Date:** 2026-05-18
**Scope:** Pinokio/Gepeto/pterm skill availability, CREATORFILES workflow coverage, missing launcher inventory

---

## 1. Skill Availability Matrix

| Asset | Type | Location | Status | Notes |
|-------|------|----------|--------|-------|
| `gepeto-SKILL.md` | Doc/reference | `pmoves/docs/AGENTS/gepeto-SKILL.md` | **Documentation only** | Full Gepeto launcher-building guide, not an installed skill |
| `Pinokio-SKILL.md` | Doc/reference | `pmoves/docs/AGENTS/Pinokio-SKILL.md` | **Documentation only** | pterm-first runtime skill doc, not an installed skill |
| `PINOKIO_LAUNCHER_GUIDE.md` | Doc/reference | `.claude/PINOKIO_LAUNCHER_GUIDE.md` | **Documentation only** | On-demand context for D:\\pinokio\\ launcher work |
| `PMOVES-Pinokio-Ultimate-TTS-Studio/` | Functional launcher | Project root | **Functional** | Complete Pinokio launcher: install.js, start.js, pinokio.js, torch.js, reset.js, update.js |
| `pbnj/pinokio/api/pmoves-pbnj/SKILL.md` | Agent skill | `pbnj/pinokio/api/pmoves-pbnj/` | **Functional** | SKILL.md for PBNJ Pinokio integration |
| `pinokio-network-inventory.yaml` | Config | `pmoves/configs/` | **Reference** | LWW service classification for POWERFULMOVES node |
| `pinokio-p7.tac.yaml` | Config | `pmoves/configs/tac_trees/` | **Reference** | TAC tree for Pinokio 7 playground |
| Gepeto skill (installed) | Agent skill | `.claude/skills/` | **NOT FOUND** | No Gepeto builder skill in any local skill directory |
| Pinokio/pterm skill (installed) | Agent skill | `.claude/skills/` | **NOT FOUND** | No Pinokio runtime skill in any local skill directory |
| pterm binary | CLI tool | N/A | **NOT PRESENT** | This is a Docker container; pterm lives on the Windows host at D:\\pinokio\\bin\\npm\\pterm.cmd |
| PMOVES-LTX-Desktop | Repo/project | Not cloned | **NOT FOUND** | Not cloned locally or on remote host; exists only as GitHub repo |

### Skill Directory Summary

| Directory | Count | Pinokio/Gepeto/pterm Skills |
|-----------|-------|--------------------------|
| `skills/` (root) | 5 dirs | 0 |
| `.claude/skills/` | 9 dirs | 0 |
| `.minimax/skills/` | 5 dirs | 0 |
| `pmoves/skills/` | 4 dirs (all stubs) | 0 |
| **Total local skills** | **23** | **0** |

**Key Finding:** PMOVES has extensive Pinokio documentation but zero functional Pinokio/Gepeto/pterm agent skills installed. The only working Pinokio asset is the Ultimate-TTS-Studio launcher folder. The `gepeto-SKILL.md` and `Pinokio-SKILL.md` in `pmoves/docs/AGENTS/` are reference copies of the SKILL.md standard — they are not wired into any agent's skill path.

---

## 2. Workflow Gap Table

### 2.1 CREATORFILES Inventory (Current State)

| File | Category | Size | Referenced in PMOVES Skill? |
|------|----------|------|---------------------------|
| `ANIMA_BASE_ULTRA_WORKFLOW.json` | ComfyUI Workflow | 380K | No |
| `ANIMA_BASE_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat` | Installer | 12K | No |
| `ANIMA_BASE_ULTRA-MODELS-NODES_INSTALL.bat` | Installer | 16K | No |
| `Mickmumpitz_AI-RENDERING_SDXL_ADV_v06.json` | ComfyUI Workflow | 96K | No |
| `Mickmumpitz_AI-RENDERING_SDXL_ADV_v07.json` | ComfyUI Workflow | 84K | No |
| `Mickmumpitz_AI-RENDERING_SDXL_FREE_v02.json` | ComfyUI Workflow | 88K | No |
| `Mickmumpitz_AI-RENDERING_SDXL_IMG_ADV_v06.json` | ComfyUI Workflow | 84K | No |
| `Mickmumpitz_AI-RENDERING_SDXL_IMG_FREE_v03.json` | ComfyUI Workflow | 72K | No |
| `260504_DREADMOR_EXAMPLE_MOVIE_v01.json` | ComfyUI Workflow | 2.0M | No |
| `260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_EXAMPLE-FILES.7z` | Asset Pack | 29M | No |
| `BlenderExample_RenderSetup.rar` | Blender Scene | 868K | No |
| `Discord/` | App Binary | 262M | No (not a workflow) |
| `[EXCLUSIVE GUIDE] Install ComfyUI, Models & Advanced Workflows.pdf` | Documentation | 1.1M | No |
| `side.png` | Image | 9.2M | No |

**Duplicates detected:** 5 files have ` (1)` copies — SDXL_ADV_v06, SDXL_FREE_v02, SDXL_IMG_ADV_v06, SDXL_IMG_FREE_v03, EXAMPLE-FILES.7z, BlenderExample_RenderSetup.rar

### 2.2 Downloads → CREATORFILES Gap (Files That Should Be Moved)

| File in Downloads | Size | Why It Belongs in CREATORFILES |
|-------------------|------|-------------------------------|
| `260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_ADV.json` | 461K | Movie-Builder v1.0 Advanced workflow — core asset |
| `260504_MICKMUMPITZ_MOVIE-BUILDER_1-0_SMPL.json` | 394K | Movie-Builder v1.0 Simple workflow — core asset |
| `260507_MICKMUMPITZ_MOVIE-BUILDER_1-1_ADV.json` | 461K | Movie-Builder v1.1 Advanced — newer version |
| `260507_MICKMUMPITZ_MOVIE-BUILDER_1-1_SMPL.json` | 394K | Movie-Builder v1.1 Simple — newer version |
| `LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat` | 7.5K | LTX-2-3 ComfyUI Manager installer — matches ANIMA_BASE pattern |
| `LTX-2-3-MODELS-NODES_INSTALL.bat` | 12.8K | LTX-2-3 models/nodes installer — matches ANIMA_BASE pattern |
| `LTX-2-3-AUTO_INSTALL-RUNPOD-V2.sh` | 17K | LTX-2-3 Linux/RunPod installer — only .sh variant, critical for cloud |

### 2.3 PMOVES-LTX-Desktop Relationship

PMOVES-LTX-Desktop (https://github.com/POWERFULMOVES/PMOVES-LTX-Desktop.git) is intended to be the Pinokio launcher wrapper that:

1. Installs ComfyUI with LTX-2-3 model support (using the .bat/.sh installers)
2. Loads Mickmumpitz Movie-Builder workflows (the 4 JSONs + example files)
3. Provides 1-click launch of ComfyUI with pre-configured workflows
4. Bridges to PMOVES agent sidecars via pterm/SKILL.md

**Current state:** The repo exists on GitHub but is NOT cloned locally or on the remote host. The install scripts and workflows that should live in it are scattered across CREATORFILES and Downloads.

---

## 3. Missing Launchers List

| Launcher Name | Target Workflows/Tools | Priority | Dependencies |
|---------------|----------------------|----------|-------------|
| **PMOVES-LTX-Desktop** | LTX-2-3 ComfyUI + Movie-Builder workflows | P0 | LTX-2-3 install scripts, Movie-Builder JSONs, example files .7z |
| **PMOVES-Anima-Base-Ultra** | ANIMA_BASE_ULTRA_WORKFLOW.json + installers | P1 | ANIMA_BASE install .bat files, workflow JSON |
| **PMOVES-Mickmumpitz-SDXL** | 6 SDXL rendering workflows (ADV, FREE, IMG_ADV, IMG_FREE) | P1 | ComfyUI with SDXL models installed |
| **PMOVES-Dreadmor-Example** | DREADMOR_EXAMPLE_MOVIE_v01.json | P2 | ComfyUI with required custom nodes |
| **PMOVES-Blender-Render** | BlenderExample_RenderSetup.rar | P2 | Blender installed |
| **PMOVES-Just-Dub-It** | Audio dubbing (referenced in task spec) | P2 | Not found in CREATORFILES or Downloads — source unknown |
| **PMOVES-Cinema-Audio** | Cinema audio processing (referenced in task spec) | P2 | Not found in CREATORFILES or Downloads — source unknown |

### Launcher Type Classification

| Launcher | Type | Required Scripts |
|----------|------|-----------------|
| PMOVES-LTX-Desktop | Server launcher (ComfyUI) | install.js, start.js, reset.js, update.js, pinokio.js, pinokio.json |
| PMOVES-Anima-Base-Ultra | Server launcher (ComfyUI) | install.js, start.js, reset.js, update.js, pinokio.js, pinokio.json |
| PMOVES-Mickmumpitz-SDXL | Server launcher (ComfyUI) | install.js, start.js, reset.js, update.js, pinokio.js, pinokio.json |
| PMOVES-Dreadmor-Example | Workflow loader (could be script-only) | pinokio.js, load-workflow.js, pinokio.json |
| PMOVES-Blender-Render | Script launcher | pinokio.js, render.js, pinokio.json |
| PMOVES-Just-Dub-It | Unknown (source not found) | TBD |
| PMOVES-Cinema-Audio | Unknown (source not found) | TBD |

---

## 4. Integration Recommendations

### 4.1 Immediate Actions (This Session)

1. **Move Downloads → CREATORFILES:** Copy the 4 Movie-Builder JSONs and 3 LTX-2-3 install scripts from Downloads to CREATORFILES. Remove duplicates in CREATORFILES (files with ` (1)` suffix).

2. **Clone PMOVES-LTX-Desktop:** Clone the GitHub repo to both local and remote to establish the launcher project structure.

### 4.2 Skill Installation (Short Term)

3. **Install Pinokio runtime skill:** Copy `pmoves/docs/AGENTS/Pinokio-SKILL.md` content into a proper `.claude/skills/pinokio-runtime/SKILL.md` so agents can use `pterm` commands. Adapt paths from Windows (D:\\pinokio\\) to work with remote execution via `code_execution_remote`.

4. **Install Gepeto builder skill:** Copy `pmoves/docs/AGENTS/gepeto-SKILL.md` into `.claude/skills/gepeto-builder/SKILL.md` so agents can generate new Pinokio launchers on demand.

5. **Create PMOVES-LTX-Desktop SKILL.md:** A skill that teaches agents to:
   - Install ComfyUI with LTX-2-3 support via the .bat/.sh scripts
   - Load Movie-Builder workflows into ComfyUI
   - Queue renders via ComfyUI API
   - Monitor render progress

### 4.3 Launcher Development (Medium Term)

6. **Build PMOVES-LTX-Desktop Pinokio launcher** using the Gepeto skill or manual development following `PINOKIO_LAUNCHER_GUIDE.md`:
   - `install.js`: Run LTX-2-3-ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat, then LTX-2-3-MODELS-NODES_INSTALL.bat, then extract example files
   - `start.js`: Launch ComfyUI with `--extra-model-paths-config` pointing to LTX models
   - `pinokio.js`: Dynamic UI with workflow selector dropdown
   - Include `torch.js` for cross-platform PyTorch setup

7. **Consolidate ComfyUI launchers:** Consider whether Anima-Base-Ultra, Mickmumpitz-SDXL, and LTX-Desktop should be separate launchers or a single "PMOVES-ComfyUI" launcher with workflow profiles. The Gepeto skill generates per-app launchers, but a unified launcher with profile selection reduces maintenance.

### 4.4 Architecture Alignment

8. **pterm control plane:** The existing `Pinokio-SKILL.md` documents pterm resolution via `GET http://127.0.0.1:42000/pinokio/path/pterm`. For the Docker sidecar to control Pinokio on the Windows host, the agent needs:
   - pterm resolved via `code_execution_remote` (since pterm runs on the host, not in Docker)
   - Or direct HTTP calls to the Pinokio control plane at `http://<host-tailscale-ip>:42000/`

9. **SKILL.md standard compliance:** All new skills should follow the SKILL.md open standard (YAML frontmatter with `name` and `description`, then markdown body) so they work with Claude Code, Codex CLI, and Pinokio 7's agent interpreter.

10. **Just Dub It / Cinema Audio:** These were referenced in the task spec but no files exist in CREATORFILES, Downloads, or the PMOVES repo. Before building launchers, the source applications/workflows need to be identified and acquired.

---

## Summary

| Metric | Value |
|--------|-------|
| Local Pinokio/Gepeto/pterm agent skills | 0 of 23 total skills |
| Functional Pinokio launchers | 1 (Ultimate-TTS-Studio) |
| CREATORFILES workflows not in any skill | 10 of 10 workflows |
| Downloads files needing move to CREATORFILES | 7 |
| Duplicate files in CREATORFILES | 5 pairs |
| Pinokio launchers to build | 5-7 (depending on consolidation strategy) |
| Missing sources (Just Dub It, Cinema Audio) | 2 |
| PMOVES-LTX-Desktop repo cloned | No |