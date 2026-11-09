# Mavis Harness v0 (PMOVES.AI side)

The Mavis multi-agent orchestrator + BPM/pomodoro scheduler + CGP bootstrap loader. The PMOVES.AI side of a 3-repo coordinated slice (the other two are PMOVES-hermes-agent and PMOVES-pinokio forks; see LEARNINGS for the cross-repo plan).

## What's in this directory

| Path | What it is | Tests |
|---|---|---|
| `load_bootstrap.py` | Reads a `pmoves.bootstrap/v1` CGP, validates it, returns a typed `Bootstrap` object, exports `PMOVES_BOOTSTRAP_*` env vars | `tests/test_load_bootstrap.py` (22/22 pass) |
| `orchestrator.py` | Multi-agent dispatcher. Publishes tasks to `pmoves.agent.task.v1`, polls for results, merges outputs. Includes `MockPublisher` for tests and `Publisher` protocol for the real pmoves-nats-mcp transport. | `tests/test_orchestrator.py` (12/12 pass) |
| `bpm_cron.py` | BPM engine. Each scheduled item is a 5-phase task (define/assign/execute/review/close) with pomodoro focus blocks (25/5 min by default, env-driven). Publishes phase + pomodoro events to NATS. | `tests/test_bpm_cron.py` (22/22 pass) |
| `../contracts/schemas/pmoves-bootstrap/v1.schema.json` | The CGP contract (JSON Schema, Draft 2020-12). Aligned to the canonical CHIT Geometry Packet spec at `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` - same envelope, `pmoves.bootstrap/v1` profile, `super_nodes: []` for the empty-geometry case. | (Schema sync test in `test_load_bootstrap.py`) |
| `../contracts/schemas/pmoves-bootstrap/example.cgp.yaml` | The example CGP with real values from memory (minimax/dimensional/5090/Tailscale/RustDesk/Hostinger/Cloudflare). The fork consumer PRs read this to verify their loaders. | (Validated by `test_load_bootstrap.py::test_example_validates_against_schema`) |

## How the 3 pieces fit together

```
                            pmoves.bootstrap/v1
                                     │
                                     ▼
                          load_bootstrap.py
                                     │
                          Bootstrap (typed dataclasses)
                                     │
                          env vars + Publisher
                                     │
                ┌────────────────────┴────────────────────┐
                │                                          │
                ▼                                          ▼
          orchestrator.py                            bpm_cron.py
                │                                          │
                ▼                                          ▼
       pmoves.agent.task.v1                    pmoves.bpm.phase.v1
       pmoves.agent.result.v1                  pmoves.bpm.pomodoro.v1
                │                                          │
                └──────────────► N A T S ◄─────────────────┘
                                     │
                       ┌─────────────┴─────────────┐
                       │                           │
                       ▼                           ▼
              PMOVES-hermes-agent fork    PMOVES-pinokio fork
              (reads CGP, subscribes       (reads CGP when launching
              to agent.task, publishes     a PMOVES-tagged app,
              to agent.result)             exposes services as env)
```

The orchestrator is the dispatcher (publishes work). The BPM cron is the scheduler (drives the operator's day through phases + pomodoro blocks). The CGP bootstrap is the contract that ties them together - both read it at init and export the relevant fields as env vars.

## Quick start

```python
from pmoves.tools.load_bootstrap import load_bootstrap
from pmoves.tools.orchestrator import Orchestrator, MockPublisher
from pmoves.tools.bpm_cron import BpmCron, BpmTask, Phase

# 1. Load the CGP (reads from default example, validates, exports env)
bs = load_bootstrap()

# 2. Start the BPM cron
pub = MockPublisher()  # or wrap pmoves-nats-mcp
cron = BpmCron(publisher=pub)
task = BpmTask(
    name="react-to-yt-abc",
    description="React to https://youtu.be/abc and generate a Pillar 4 visual",
    agents=["mavis", "kiloclaw"],
)
cron.start(task)  # publishes define-started + first pomodoro-started

# 3. Use the orchestrator to dispatch per phase
orch = Orchestrator(bootstrap=bs, publisher=pub)
result = orch.dispatch(
    task="render the 6-eye third-eye character as the Pillar 4 encoding skin",
    agents=["mavis", "kiloclaw"],
)
# (In production, results come back via pmoves.agent.result.v1 subscription;
#  in tests, the caller injects AgentResult directly.)

# 4. Mark the phase done + advance
cron.complete_block(task.name)
cron.record_deliverable(task.name, Phase.DEFINE, "intent captured: Pillar 4 encoding visual")
cron.advance(task.name)  # moves to ASSIGN, publishes phase events
```

## What this slice does NOT do (intentional, follow-up)

- **Hermes fork consumer PR** - the `bootstrap_loader.py` + `tools_bridge.py` + tests live in `POWERFULMOVES/PMOVES-hermes-agent`, separate worktree
- **Pinokio fork consumer PR** - the `pmoves_loader.js` + `pmoves_apps/` starter manifests live in `POWERFULMOVES/PMOVES-pinokio`, separate worktree
- **Real pmoves-nats-mcp integration** - the v0 wire-up uses `MockPublisher`; a real `NatsPublisher` wraps `pmoves-nats-mcp` and lands in a follow-up once the MCP is stable
- **The actual Hermes subscriber** - v0 sets up the wire (the `hermes` routing target in the CGP); when the operator stands Hermes up on a node, the subscriber picks up tasks
- **Ace Studio / Veo integrations** - app-level, follow-up slice once the harness is proven end-to-end
- **KVM control surface** - the operator's earlier flag; RustDesk is the control surface, not a harness concern unless we add RustDesk-NATS-dispatch in a later slice

## Why these specific files

- `load_bootstrap.py` is at the top level (not in `harness/`) because future Mavis sessions will import it as `from pmoves.tools.load_bootstrap import ...` - keeping it at the top level matches the convention of other Mavis tools (comfyui_client, render_skin, pinokio_launch)
- `orchestrator.py` and `bpm_cron.py` follow the same pattern
- The CGP schema lives at `contracts/schemas/pmoves-bootstrap/` because it's a contract, not a tool - the schema dir convention is already established (see `contracts/schemas/agent-graphiti/`)
- The LEARNINGS file is at `pmoves/tools/LEARNINGS/mavis-harness-v0_LEARNINGS.md` to match the per-tool LEARNINGS pattern
