# Handoff — Agent comms roads (lane `fix/agent-comms-roads-2026-11-23`)

**Owner:** 5090-CLAUDE (coordinator). **Delivery body:** delivery-agent `deliver-comms-roads`. **Operator grant:** 2026-11-23 01:11 EST, verbatim: *"the instance is running on node why not ensure all the ways setup for you to comms are open i mean thats like the point of CHIT"*, and 02:15 EST: *"ok if you want to take lane s to address what audit found"*. CLAIM row filed 2026-11-23T07:17:07Z in `AGNOTE4482PHI.t1.md`.

This brief is the provable reason for the `schema` Known Road (`KNOWN_ROAD=schema:handoff:AGENT_COMMS_ROADS_2026-11-23.md`) used to add one contract schema. It is tracked by git so the guard can check it.

## Measured on node 5090, 2026-11-23 ~06:15Z

| Path | Result |
|---|---|
| Peer `SendMessage` to another Claude session on the node | works, reply in <1 min |
| Cipher `pmoves_cipher_store` (local entry, agentId `5090-claude`) | works |
| `gh pr review --comment` | works, >60 s |
| NATS publish via pinned `natsio/nats-box:0.14.5` on `pmoves_bus` | works (514 B to `claw.task.assign.v1`) |
| A0 supervisor `POST /events/publish` topic `claw.task.assign.v1` | **500** `KeyError: Unknown topic` from `services/common/events.py:schema_path` |
| `make -C pmoves nats-pub SUBJECT=… PAYLOAD='{json}'` | **fails** `test: too many arguments` (Makefile:1704) when the JSON contains spaces; the single-quoted `nats pub` arg also breaks on apostrophes. CORRECTION 07:30Z: the documented no-space example does pass on this node; my 06:19Z payload had spaces |
| Receive side (`connz?subs=1`) | 32 connections, **0 subscribers** on `claw.*`, `chit.>`, `branch.>`, `p7.>`, `owner.presence.>` until `make nats-agent-inbox` was started by hand; it then connected as `pmoves-agent-inbox-5090-CODEX` (hardcoded default in `tools/nats_agent_inbox.py:158`) and received the notice |

## Scope of the schema change

Add `pmoves/contracts/schemas/claw/task.assign.v1.schema.json` matching the payload documented in `.claude/context/nats-subjects.md` § CLAW Agent Delegation Subjects (required `from`, `to`, `task`; optional `files_released: string[]`, `after_pr: int[]`, `note: string`) and register `claw.task.assign.v1` in `pmoves/contracts/topics.json` using the existing entry shape. No other schema is touched. The A0 route is also changed to return 4xx with the known-topic list on an unknown topic instead of an unhandled 500.

## Out of scope (tracked elsewhere)

Pipecat fork pinning drift (handed to 4090-Claude over `claw.task.assign.v1` 07:17Z); Tailscale ACL read (Composio Tailscale token returns 401, local tailscale MCP down — operator secrets-pipeline item); `PMOVES-5090-CLAUDE` alias lane (pending identity-collision decision).

## Incident 2026-11-23T07:24-07:25Z (delivery body, self-reported)

While proving the nats-pub fix, 4 test payloads were published to the LIVE bus on `claw.task.assign.v1` because the stub `docker` directory was prepended to PATH as a Windows path (`C:/Users/...:$PATH`) under Git Bash, which splits PATH at the drive colon, so bash never searched the stub directory and resolved the real docker. CAUSE FOUND 07:45Z: not make, not the recipe; a cygpath-converted prefix plus an in-recipe preflight asserting `command -v docker` resolves to the stub, with `NATS_DOCKER_NETWORK` pointed at a nonexistent network, published nothing. Two payloads imitated a `pmoves-4090 -> pmoves-spark cascade-wave-B` delegation. Measured blast radius at 07:28Z on monitor 127.0.0.1:9223: exactly one subscriber (`pmoves-agent-inbox-5090-CODEX`, this node, connected 06:20Z), `leafnodes: 0`, `routes: 0`, no cluster. The four lines sit at the tail of `%LOCALAPPDATA%/pmoves/agent-inbox/5090-CODEX.jsonl` and are left in place as the record. No other node could have received them. Rule adopted for this lane: no live publishes from tests; proof is pytest with the stub-docker fixture plus `make -n`; any live check is one verifier-run publish with a payload whose `task` begins `TEST-`.
