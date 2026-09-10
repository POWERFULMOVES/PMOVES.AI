#!/usr/bin/env python3
"""Pydantic-backed gate for the PMOVES agent registry <-> teams coupling.

Replaces the informational one-liner in the agent-teams.yaml header with an
enforceable check (``tool can tool``: deterministic, reproducible grounding).

What it enforces
----------------
1. **Naming convention** (best practice, already used across the repo):
   - ``snake_case`` for registry keys and team ``agents:`` entries (YAML/Python
     identifiers), e.g. ``fordham_steward``.
   - ``kebab-case`` for agent-facing runtime ids (room ``agent_id``, mint
     ``agent_name``, external contributors like ``4090-claude``), derived
     deterministically as ``snake.replace("_", "-")``.
2. **Coupling**: every registry agent belongs to exactly one team, and every
   team agent exists in the registry.
3. **Ratchet**: the coupling is already broken on ``main`` (legacy drift). That
   drift is baselined below so the gate is GREEN today but FAILS on any *new*
   violation. Do not grow the baselines — reconcile them separately.
4. **Room cross-check** (advisory): every room manifest ``agent_id`` resolves to
   a registry agent (via kebab->snake) or an external contributor.
5. **Identity coupling**: every ``default_identity`` declared in
   ``node-vocabulary.yaml`` names an agent that is registered, claims the node
   it is declared for, and belongs to a team. A declaration meeting none of
   those is *declared and not wired* -- it reads as a live binding and resolves
   to nothing.

Exit code: 0 = pass (baseline-only), 1 = new violation (CI gate).
Run:  python pmoves/scripts/validate_agent_registry.py [-v]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

# Report lines use an em dash. On Windows the default console/pipe encoding is
# cp1252, not UTF-8 -- a caller capturing this process's output with
# `encoding="utf-8"` (as the test suite does) then gets a UnicodeDecodeError
# on that single byte. Force UTF-8 so stdout/stderr are decodable regardless
# of platform locale.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "pmoves" / "config" / "agent_registry.yaml"
TEAMS = ROOT / "pmoves" / "configs" / "agent-teams.yaml"
VOCABULARY = ROOT / "pmoves" / "configs" / "node-vocabulary.yaml"
ROOMS_DIR = ROOT / "pmoves" / "config" / "rooms"

sys.path.insert(0, str(ROOT / "pmoves" / "tools"))
from fittings import (  # noqa: E402
    SUITS_DIR,
    effective_fit,
    load_harnesses,
    load_roles,
    resolve_role,
)
from node_identity import (  # noqa: E402
    NON_NODE_KINDS,
    canonical_node,
    load_vocabulary,
)

SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
KEBAB = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


def snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


def kebab_to_snake(name: str) -> str:
    return name.replace("-", "_")


# --- Ratchet baseline -------------------------------------------------------
# Pre-existing origin/main coupling drift. Allowed so the gate is green today;
# NEW entries outside these sets fail. Reconcile these separately (do NOT add).
# Fully reconciled 2026-07-07 — the registry↔teams coupling is now clean, so both
# baselines are EMPTY and the gate enforces zero drift (any future violation fails).
# Round 1: botz×3 + space_agent -> orchestration, cipher_beats_analyst -> media,
#   notebooklm_agent -> research (each per its own registry topology.team).
# Round 2: a0_plugins/hermes_agent -> orchestration, autoresearch -> research,
#   clawz/pmoves_ci_bot/pr_hedge_trim -> automation; and registry entries authored for
#   nemoclaw/container_agent (infra), nemotron_claw (evolution), podcast_producer/
#   remotion_renderer/youtube_publisher (media).
BASELINE_UNTEAMED: frozenset = frozenset()
BASELINE_UNREGISTERED: frozenset = frozenset()


# --- Pydantic models (structural + naming validation) -----------------------
class AgentEntry(BaseModel):
    """A registry agent. Only the fields we gate on are typed; the rich
    taxonomy fields are permitted via ``extra='allow'``."""
    model_config = ConfigDict(extra="allow")
    name: str


class Team(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    agents: list[str] = []

    @field_validator("agents")
    @classmethod
    def _agents_snake(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if not SNAKE.match(a)]
        if bad:
            raise ValueError(f"team agent ids must be snake_case, got: {bad}")
        return v


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    errors: list[str] = []
    warnings: list[str] = []

    reg_raw = _load_yaml(REGISTRY)
    teams_raw = _load_yaml(TEAMS)

    # 1. Structural + naming validation via Pydantic ------------------------
    registry_keys: set[str] = set()
    for key, entry in (reg_raw.get("agents") or {}).items():
        if not SNAKE.match(key):
            errors.append(f"registry key not snake_case: {key!r}")
        try:
            AgentEntry.model_validate(entry or {})
        except Exception as exc:  # noqa: BLE001 - surface the pydantic error text
            errors.append(f"registry[{key}] invalid: {exc}")
        registry_keys.add(key)

    # node_affinity resolution (registry -> vocabulary direction) ---------
    # Every node_affinity token must resolve through node-vocabulary.yaml.
    # Tokens canonicalizing to NON_NODE_KINDS (placeholder, runner-label,
    # class, unresolved) pass with their kind noted -- they are declared
    # concepts, not unknown spellings. An UNKNOWN spelling fails: that is the
    # name-bound-in-one-context-consumed-in-another defect class from
    # 4090-open-findings-2026-08-31. A vocabulary that cannot load at all
    # (duplicate alias) surfaces as a gate error naming the file -- never as
    # a traceback that aborts the whole report.
    try:
        vocab = load_vocabulary(VOCABULARY)
    except ValueError as exc:
        errors.append(f"node-vocabulary.yaml: {exc}")
        vocab = None
    if vocab is not None:
        for key, entry in (reg_raw.get("agents") or {}).items():
            topology = (entry or {}).get("topology") or {}
            raw = topology.get("node_affinity")
            if raw is None:
                continue
            tokens = raw if isinstance(raw, list) else [raw]
            for token in tokens:
                token_s = str(token).strip()
                if not token_s:
                    continue
                node = canonical_node(token_s, vocab)
                if node is None:
                    errors.append(
                        f"registry[{key}] node_affinity token {token_s!r} does not "
                        "resolve in node-vocabulary.yaml (unknown spelling)"
                    )

    team_map: dict[str, list[str]] = {}
    for tkey, tval in (teams_raw.get("teams") or {}).items():
        if not SNAKE.match(tkey):
            errors.append(f"team key not snake_case: {tkey!r}")
        try:
            team = Team.model_validate(tval or {})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"team[{tkey}] invalid: {exc}")
            continue
        for a in team.agents:
            team_map.setdefault(a, []).append(tkey)

    external = set(reg_raw.get("external_contributors") or [])

    # 2. Coupling with ratchet ---------------------------------------------
    teamed = set(team_map)
    new_unteamed = sorted((registry_keys - teamed) - BASELINE_UNTEAMED)
    new_unreg = sorted((teamed - registry_keys) - BASELINE_UNREGISTERED)
    dups = {a: t for a, t in team_map.items() if len(t) > 1}

    for a in new_unteamed:
        errors.append(f"registry agent in NO team (new drift): {a} "
                      f"-> add it to a team in agent-teams.yaml")
    for a in new_unreg:
        errors.append(f"team agent NOT in registry (new drift): {a} "
                      f"(teams {team_map[a]}) -> add it to agent_registry.yaml")
    for a, t in sorted(dups.items()):
        errors.append(f"agent in >1 team: {a} -> {t}")

    # Baseline still-open drift is reported as a warning, never fatal.
    still_unteamed = sorted((registry_keys - teamed) & BASELINE_UNTEAMED)
    still_unreg = sorted((teamed - registry_keys) & BASELINE_UNREGISTERED)
    if still_unteamed:
        warnings.append(f"baseline unteamed (reconcile separately): {still_unteamed}")
    if still_unreg:
        warnings.append(f"baseline unregistered (reconcile separately): {still_unreg}")

    # 3. Room cross-check (advisory) ---------------------------------------
    for manifest in sorted(ROOMS_DIR.glob("*.json")):
        if manifest.name == "catalog.json":
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"room {manifest.name}: unreadable ({exc})")
            continue
        owner = data.get("agent_id")
        if not owner:
            continue
        if owner in external or kebab_to_snake(owner) in registry_keys:
            continue
        warnings.append(
            f"room {manifest.name}: owner agent_id {owner!r} resolves to neither "
            f"a registry agent ({kebab_to_snake(owner)!r}) nor an external contributor")

    # --- Registry rooms: -> catalog (advisory) ------------------------------
    # The mirror of the check above. That one asks "does this room's owner exist";
    # this asks "do the rooms an agent claims exist". Nothing enforced it, and a
    # fabricated name shipped: PR #2612 bound pmoves_minimax_mcp to
    # "minimax-mcp.room.model", which is in no catalog and no manifest. The
    # binding resolved to nothing and the agent could not be discovered through
    # the room plane at all.
    #
    # Advisory, like the owner check. `rooms:` has no schema and its semantics are
    # not settled -- see the note in ROOM_MANIFEST_CONTRACT.md -- so this asserts
    # only the part that is unambiguous: a named room must exist.
    catalog_path = ROOMS_DIR / "catalog.json"
    known_rooms: set = set()
    if catalog_path.is_file():
        try:
            cat = json.loads(catalog_path.read_text(encoding="utf-8"))
            entries = cat.get("rooms", cat) if isinstance(cat, dict) else cat
            if isinstance(entries, list):
                for r in entries:
                    if isinstance(r, dict):
                        rid = r.get("room_id") or r.get("id") or r.get("name")
                        if rid:
                            known_rooms.add(rid)
            elif isinstance(entries, dict):
                known_rooms.update(entries.keys())
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"rooms catalog unreadable ({exc})")
    # A manifest on disk counts too: catalog and manifests can lag each other.
    for manifest in ROOMS_DIR.glob("*.json"):
        if manifest.name != "catalog.json":
            known_rooms.add(manifest.name[: -len(".json")])

    if known_rooms:
        # `rooms:` lives under BOTH agents: and mcp_servers: -- today every
        # occurrence is under mcp_servers:, which is why an earlier draft of this
        # check scanned agents: only and caught nothing when the fabricated name
        # was reinjected. Scan both so the check cannot go quiet if the field
        # moves or spreads.
        for section in ("agents", "mcp_servers"):
            for entry_key, spec in sorted((reg_raw.get(section) or {}).items()):
                if not isinstance(spec, dict):
                    continue
                for room in spec.get("rooms") or []:
                    if room not in known_rooms:
                        warnings.append(
                            f"{section}[{entry_key}]: rooms entry {room!r} is in neither "
                            f"pmoves/config/rooms/catalog.json nor a room manifest")

    # 4. Fitting cross-check -------------------------------------------------
    # A fitting naming a harness that does not exist is a typo that silently
    # disables routing for that pair. Same shape as the room-owner cross-check
    # above, but an ERROR rather than a warning: a room with a bad owner is still
    # discoverable, whereas an unroutable pairing is invisible at read time.
    #
    # A malformed suit file (e.g. the legacy scalar shape `fit: {harness: full}`
    # a migrator would naturally write) must become a gate error naming the file,
    # never an uncaught exception -- a traceback here would abort the whole run
    # and suppress the registry/teams report for every other file.
    harnesses = load_harnesses()
    try:
        roles = load_roles()
    except ValueError as exc:
        # An erased or malformed vocabulary is a gate failure, not a crash: the
        # rest of the report must still run, per the note above. It used to be
        # neither -- load_roles() normalised `roles: {}` to `{}`, every fitting
        # uses `*`, and the gate printed "OK" over a vocabulary that no longer
        # existed.
        errors.append(f"model-roles.yaml: {exc}")
        roles = {}
    for suit_path in sorted(SUITS_DIR.glob("*.yaml")):
        doc = _load_yaml(suit_path) or {}
        if "fit" not in doc:
            continue
        fit_block = doc.get("fit")
        if not isinstance(fit_block, dict):
            errors.append(
                f"{suit_path.name}: fit: must be a mapping of harness -> role -> "
                f"[observation, ...], got {type(fit_block).__name__} ({fit_block!r})"
            )
            continue
        if not fit_block:
            # An empty map is the same artifact as an empty observation list
            # below, one level up: a completed-looking record with no data in
            # it. An unmeasured harness has no `fit` entry at all.
            errors.append(
                f"{suit_path.name}: fit: is present but empty; omit the key "
                "entirely for an unmeasured harness rather than recording an "
                "empty map"
            )
            continue
        for harness_key, role_map in fit_block.items():
            if harness_key not in harnesses:
                errors.append(
                    f"{suit_path.name}: fit names {harness_key!r}, which is not a "
                    "registry agent with `kind: harness`"
                )
            if not isinstance(role_map, dict):
                errors.append(
                    f"{suit_path.name} [{harness_key}]: expected a mapping of "
                    f"role -> [observation, ...], got {type(role_map).__name__} "
                    f"({role_map!r}) -- the legacy scalar shape "
                    "`fit: {harness: full}` is not supported"
                )
                continue
            if not role_map:
                errors.append(
                    f"{suit_path.name} [{harness_key}]: role map is empty; omit "
                    "the harness entry entirely for an unmeasured pairing rather "
                    "than recording an empty map"
                )
                continue
            for role_key, observations in role_map.items():
                canonical, note = resolve_role(role_key, roles)
                if canonical is None:
                    errors.append(f"{suit_path.name}: {note}")
                elif note:
                    warnings.append(f"{suit_path.name}: {note}")

                if not isinstance(observations, list):
                    errors.append(
                        f"{suit_path.name} [{harness_key}/{role_key}]: expected a "
                        f"list of observations, got {type(observations).__name__} "
                        f"({observations!r})"
                    )
                    continue
                if not observations:
                    # The plan's constraint (spec §4/§6): an unmeasured pairing
                    # has NO entry at all. A present-but-empty list is the same
                    # "untested" artifact under a different spelling.
                    errors.append(
                        f"{suit_path.name} [{harness_key}/{role_key}]: "
                        "observation list is empty; omit the role entry entirely "
                        "for an unmeasured pairing rather than recording a null "
                        "result"
                    )
                    continue
                malformed = [o for o in observations if not isinstance(o, dict)]
                if malformed:
                    errors.append(
                        f"{suit_path.name} [{harness_key}/{role_key}]: each "
                        f"observation must be a mapping, got {malformed!r}"
                    )
                    continue

                for obs in observations:
                    # Evidence, not a permission bit (spec §6): every observation
                    # must carry who measured it, how, and when.
                    if True in obs and "on" not in obs:
                        # Unquoted `on: 2026-08-25` parses under YAML 1.1 as the
                        # boolean key True, not the string "on" -- the date is
                        # then silently absent rather than merely missing.
                        errors.append(
                            f"{suit_path.name} [{harness_key}/{role_key}]: "
                            "observation key `on` was parsed as the boolean "
                            'True -- quote it as `"on":` in the YAML (unquoted '
                            "`on:` is a YAML 1.1 boolean key)"
                        )
                    else:
                        missing = [f for f in ("by", "method", "on") if not obs.get(f)]
                        if missing:
                            errors.append(
                                f"{suit_path.name} [{harness_key}/{role_key}]: "
                                f"observation missing required provenance "
                                f"field(s): {missing} (need by, method, on)"
                            )
                    method = obs.get("method")
                    if method is not None and method not in ("hand", "measured"):
                        errors.append(
                            f"{suit_path.name} [{harness_key}/{role_key}]: "
                            f"observation method must be 'hand' or 'measured', "
                            f"got {method!r}"
                        )

                try:
                    effective_fit(observations)
                except ValueError as exc:
                    errors.append(f"{suit_path.name} [{harness_key}/{role_key}]: {exc}")


    # Harness keys the launchers actually request (verified by grepping the
    # --harness invocations in pmoves/scripts/claude-pmoves.sh and crush-pmoves).
    _LAUNCHER_HARNESSES = frozenset({"claude-code", "crush"})

    # 5. Vocabulary default_identity -> registry/teams coupling --------------
    # `node-vocabulary.yaml` declares WHO a session on a node is:
    #     <node>.default_identity.<harness>: <agent_id>
    # Three files must agree for that to mean anything -- the vocabulary
    # DECLARES it, the registry WIRES it (topology.node_affinity), and
    # agent-teams.yaml COUPLES it. Nothing checked the first against the other
    # two. This validator never opened the vocabulary at all, and the only
    # enforcement anywhere was a hand-written, single-identity assertion for
    # knuckles.crush in test_crush_node_identity.py.
    #
    # The gap is reachable, not theoretical. PR #2766's registry conflict
    # interleaves mid-mapping (port/health/layers/evolution_stage are shared
    # context lines between two hunks), so an `--ours` resolution silently drops
    # two agents from the registry AND the teams file -- while the vocabulary,
    # which merges cleanly and conflicts with nothing, keeps declaring them. The
    # coupling check above then sees registry and teams agreeing with each other
    # and reports "no new drift". Two identities declared and not wired, green.
    # The opposite resolution deletes an agent the teams file still lists and IS
    # caught -- which is what made the existing guard asymmetric.
    #
    # node_identity.resolve_identity() already names this exact failure -- but
    # only for the one node it happens to be running on, at runtime, after the
    # merge. This is the static, whole-fleet form of the same assertions.
    #
    # ERROR, not advisory: an unresolvable identity means every session on that
    # node launches unbound, and the launchers fail OPEN (announce and continue),
    # so nothing downstream turns red on its own.
    try:
        vocab_raw = _load_yaml(VOCABULARY) or {}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"node-vocabulary.yaml: unreadable ({exc})")
        vocab_raw = {}

    # An alias claimed by two nodes makes load_vocabulary() raise GLOBALLY, so it
    # breaks identity resolution on every node at once. Report it as a gate error
    # rather than letting the traceback abort the run and suppress the
    # registry/teams report for every other file (same posture as load_roles()).
    try:
        vocab_index = load_vocabulary(VOCABULARY)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"node-vocabulary.yaml: {exc}")
        vocab_index = {}

    reg_agents = reg_raw.get("agents") or {}
    declared_identities = 0
    # P2 (review on #2787): duplicate canonical nodes. load_vocabulary()
    # builds a dict keyed by canonical, so the LAST entry silently wins at
    # resolution time while this loop would happily validate BOTH. Detect
    # before validating so a duplicate can never produce a green run that
    # resolves differently than it validated.
    seen_canonical: dict[str, str] = {}
    for entry in vocab_raw.get("nodes") or []:
        if not isinstance(entry, dict):
            continue
        node = str(entry.get("canonical", "")).strip()
        if node in seen_canonical:
            errors.append(
                f"node-vocabulary.yaml: duplicate canonical node {node!r} — "
                "load_vocabulary() keeps only the last entry, so identities "
                "declared on the earlier one silently never resolve; merge or "
                "rename the entries")
            continue
        seen_canonical[node] = "seen"
        declared = entry.get("default_identity") or {}
        if not declared:
            continue
        if not isinstance(declared, dict):
            errors.append(
                f"node-vocabulary.yaml: {node}.default_identity must be a mapping "
                f"of harness -> agent id, got {type(declared).__name__} ({declared!r})")
            continue

        # Identity does not bind to a class/placeholder/runner-label/unresolved
        # entry -- resolve_identity() refuses before it ever reads
        # default_identity. A declaration here can never take effect.
        kind = entry.get("kind", "node")
        if kind in NON_NODE_KINDS:
            errors.append(
                f"node-vocabulary.yaml: {node} declares default_identity "
                f"{sorted(declared)} but is kind={kind!r}, which is not a machine; "
                f"identity never binds to it, so the declaration is unreachable")
            continue

        for harness, agent_id in sorted(declared.items()):
            declared_identities += 1
            where = f"node-vocabulary.yaml: {node}.default_identity.{harness}"

            # P1 (review on #2786): validate the HARNESS key itself. The
            # launchers request fixed keys (claude-pmoves: --harness
            # claude-code; crush-pmoves: --harness crush); a misspelled key
            # (claude_code) validates its agent fine but can NEVER be
            # requested, so the declaration is dead at write-time.
            if harness not in _LAUNCHER_HARNESSES:
                errors.append(
                    f"{where}: unknown harness {harness!r} — launchers request "
                    f"{sorted(_LAUNCHER_HARNESSES)}; a key no launcher passes "
                    "can never bind, so this declaration is unreachable")
                continue

            if not isinstance(agent_id, str) or not agent_id.strip():
                errors.append(
                    f"{where}: expected an agent_registry.yaml key, got {agent_id!r}")
                continue
            # P2 (review on #2787): reject padding, do not trim it away.
            # load_vocabulary() preserves the raw string, so " claude_4090 "
            # would validate here (after strip) yet never resolve at runtime —
            # the validator and the resolver would disagree about the same
            # declaration. The file must carry the exact key.
            if agent_id != agent_id.strip():
                errors.append(
                    f"{where}: agent id has surrounding whitespace ({agent_id!r}) — "
                    "the resolver matches raw strings, so this can never bind; "
                    "write the exact registry key")
                continue
            agent_id = agent_id.strip()

            if agent_id not in registry_keys:
                # Claimants are the repair hint: they say whether ANY agent
                # is wired to this node. Truncated because the honest count is
                # 38 for the 5090 and 78 for the z890 -- printing them all
                # buries the one line that matters under a wall of names, and
                # this list is a pointer, not the answer. Ambiguity is exactly
                # why identity is declared rather than inferred from affinity.
                claimants = sorted(
                    k for k, v in reg_agents.items()
                    if isinstance(v, dict) and vocab_index and any(
                        canonical_node(a, vocab_index) == node
                        for a in ((v.get("topology") or {}).get("node_affinity") or []))
                )
                shown = ", ".join(claimants[:6]) or "none"
                if len(claimants) > 6:
                    shown += f", and {len(claimants) - 6} more"
                errors.append(
                    f"{where} -> {agent_id!r} is DECLARED AND NOT WIRED: it is not an "
                    f"agent in agent_registry.yaml. Every session on {node} using "
                    f"harness {harness!r} launches unbound. Register it, or remove the "
                    f"declaration. {len(claimants)} agent(s) already claim {node}: "
                    f"{shown}")
                continue

            # Registered, but for a different machine. resolve_identity() refuses
            # to bind an identity to a node it does not claim, so this is unbound
            # too -- just for a second reason.
            affinity = ((reg_agents.get(agent_id) or {}).get("topology") or {}).get(
                "node_affinity") or []
            if vocab_index and not any(
                    canonical_node(a, vocab_index) == node for a in affinity):
                errors.append(
                    f"{where} -> {agent_id!r} is registered but its own node_affinity "
                    f"{affinity!r} does not resolve to {node}. An identity that does "
                    f"not claim the node it is declared for is a misbinding; the "
                    f"resolver refuses it")

            # The coupling #2754/#2763 established: a registered identity is a
            # team member. The registry<->teams check above already enforces this
            # for every registry agent, so reaching here means the agent is BOTH
            # declared and registered yet still unteamed -- report it against the
            # declaration, which is where a reader is looking.
            if agent_id not in team_map:
                errors.append(
                    f"{where} -> {agent_id!r} is registered but belongs to no team in "
                    f"agent-teams.yaml; add it to one (see claude_b850 / crush_glm52 "
                    f"under `orchestration`)")

    # P1 (review on #2786): zero declared identities is a vacuous pass. The
    # fleet has live declarations (knuckles, 4090 at minimum); a run reporting
    # zero means every default_identity block was deleted (or the vocabulary
    # failed to parse into something the loop could read), and the gate would
    # sail through having verified nothing.
    if declared_identities == 0:
        errors.append(
            "node-vocabulary.yaml: zero default_identity declarations found — "
            "the fleet declares node identities (knuckles, 4090, ...); zero "
            "means the blocks were deleted or the file failed to load, and "
            "this gate would otherwise pass having verified nothing")

    # --- Report ------------------------------------------------------------
    print(f"registry agents: {len(registry_keys)} | team agents: {len(teamed)} "
          f"| external contributors: {len(external)} "
          f"| declared identities: {declared_identities}")
    if verbose or warnings:
        for w in warnings:
            print(f"  WARN  {w}")
    if errors:
        print(f"\nFAIL — {len(errors)} new violation(s):")
        for e in errors:
            print(f"  ERROR {e}")
        return 1
    print("OK — registry/teams coupling clean (no new drift); naming conventions "
          "hold; every declared identity is wired.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
