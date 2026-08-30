# PMOVES.AI Conductor Tracks

This defines the Standard Operating Procedures (SOPs) and Context-Driven Development tracks for the **Gemini CLI**.

## 1. Feature Development Track
**Trigger:** `Implement [feature] in [service]`
**Steps:**
1. Consult `.claude/context/services-catalog.md` to identify the service.
2. Draft changes in a standalone git branch (`feature/gemini-[feature]`).
3. Modify code prioritizing atomic updates. Use `google-genai` for any Cognitive/Reasoning dependencies.
4. Verify tests locally via Pytest or Docker Compose checks.
5. Provide a summary of modified files for a Pull Request.

## 2. Tokenism/CGP Economics Track
**Trigger:** `Run Tokenism analysis on [data]`
**Steps:**
1. Connect to NATS via `tokenism.cgp.weekly.v1`.
2. Extract the NATS geometric payload.
3. Use Gemini 1.5 Pro to process the long-context (potentially 100k+ tokens) simulation payload.
4. Return recommended `alpha_i` and `halfLife` adjustments for the Gini coefficient optimization.

## 3. Multimodal Edge Routing Track
**Trigger:** `Cast Gemini voice to [device]`
**Steps:**
1. Confirm local Google Cast / Home device availability via MCP tool `cast_list`. (Ensure Pixel 10 Pro or Google Nest speaker).
2. Use Pipecat / Flute-Gateway (`gemini_voice.py`) to generate multi-modal audio.
3. Pipe response back to `voice.cast.request.v1`.

## 4. Archon A2A Strategic Handoff Track
**Trigger:** `Help Agent Zero solve [complex problem]`
**Steps:**
1. Agent Zero triggers MCP `a2a_strategic_handoff`.
2. Gemini CLI/SDK receives prompt payload via TensorZero.
3. Gemini processes the complex reasoning required, referencing internal PMOVES.AI schema standards from `contracts/`.
4. Gemini returns structured JSON guidance for Agent Zero to execute locally.
