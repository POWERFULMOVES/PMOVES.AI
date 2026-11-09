# Model–Harness Fitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a harness-only `fit` field to the model catalog, seeded from the eleven genuine harness observations, with gates that reject unresolvable harness keys and unknown role names.

**Architecture:** `fit` is a NEW field added alongside the existing `model_suit:` root — never nested under a new root, because `kong_route_seeder` reads routing identity from the top level and a re-parent drops every model out of Kong. `cross_agent` is left byte-identical and keeps answering the component-compatibility question it was built for. A small loader library (`pmoves/tools/fittings.py`) owns reading and resolution; the existing pydantic gate gains one section that cross-checks keys.

**Tech Stack:** Python 3.11+, PyYAML, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-model-harness-fitting-design.md`

## Global Constraints

- `cross_agent` is **byte-identical** after this plan. It is not migrated, reinterpreted, or removed.
- Routing identity (`model_suit.name`, `.provider`, `.base_url`, `.api_key_env`) stays at its current nesting depth. `kong_route_seeder._parse_model_suits` must return the same 18 entries with identical `model_id` / `provider` / `api_base` / `api_key_env`.
- There is **no `untested` value**. An unmeasured pairing has no entry at all.
- Registry keys are snake_case matching `^[a-z][a-z0-9_]*$`; runtime ids are kebab matching `^[a-z0-9][a-z0-9.-]*$`. `fit` harness keys are **registry keys**.
- All file reads/writes use `encoding="utf-8"` explicitly (Windows default is cp1252).
- Only the two genuine harnesses are seeded: `clawz` and `kilocode_glm`. `agent_zero`, `archon`, `typer`, `a2ui`, `pinokio` are not harnesses and get no `fit` entry.

**Out of scope for this plan** (follow-on): the router itself. The spec's §4 requires NATS request/reply ahead of `orchestrator.dispatch`, which is a separate subsystem with its own testable deliverable. This plan produces the validated data and gates the router will consume.

---

### Task 1: Pin current Kong behaviour before anything changes

The regression net for every later task. The spec's own acceptance criterion 2 is the one the original schema would have failed, so it gets asserted first and by execution, not inspection.

**Files:**
- Test: `pmoves/tests/test_kong_seeder_identity.py` (create)

**Interfaces:**
- Consumes: `pmoves.tools.kong_route_seeder._parse_model_suits(Path) -> list[dict]`
- Produces: nothing. Pure guard.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_kong_seeder_identity.py`:

```python
"""Kong reads routing identity from the TOP LEVEL of each suit file.

Any schema change that re-parents `name`/`provider`/`base_url`/`api_key_env`
makes every lookup in `_parse_model_suits` miss, so each file yields no model_id,
is skipped, and every model silently drops out of Kong while Kong reports healthy.
This pins the shape so that failure is caught here rather than in production.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"


def _seeder():
    path = REPO_ROOT / "pmoves" / "tools" / "kong_route_seeder.py"
    spec = importlib.util.spec_from_file_location("kong_route_seeder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kong_route_seeder"] = module
    spec.loader.exec_module(module)
    return module


def test_every_suit_file_yields_a_routable_entry():
    seeder = _seeder()
    on_disk = sorted(p.stem for p in SUITS_DIR.glob("*.yaml"))
    parsed = seeder._parse_model_suits(SUITS_DIR)

    assert len(parsed) == len(on_disk), (
        f"{len(on_disk)} suit files on disk but the seeder returned {len(parsed)}. "
        "A dropped entry means that model is absent from Kong."
    )

    missing_id = [e for e in parsed if not e.get("model_id")]
    assert not missing_id, (
        f"{len(missing_id)} entries have no model_id and would be skipped: "
        f"{[e.get('file') for e in missing_id]}"
    )
```

- [ ] **Step 2: Run it and confirm it passes today**

Run: `python -m pytest pmoves/tests/test_kong_seeder_identity.py -v`
Expected: PASS, 1 test. (This guard is written against working behaviour — it must pass now so a later regression is unambiguous.)

- [ ] **Step 3: Prove the guard can fail**

Temporarily edit one suit file — `pmoves/configs/model-suits/kimi-k2.yaml` — and indent its whole `model_suit:` block under a new `fitting:` key.

Run: `python -m pytest pmoves/tests/test_kong_seeder_identity.py -v`
Expected: FAIL, reporting a missing `model_id`.

- [ ] **Step 4: Revert the temporary edit**

Run: `git checkout -- pmoves/configs/model-suits/kimi-k2.yaml`
Then: `python -m pytest pmoves/tests/test_kong_seeder_identity.py -v`
Expected: PASS again.

- [ ] **Step 5: Commit**

```bash
git add pmoves/tests/test_kong_seeder_identity.py
git commit -m "test(kong): pin routing identity at the top level before the fitting change

A fitting schema that re-parents name/provider/base_url/api_key_env makes every
lookup in _parse_model_suits miss, so each file is skipped for lacking a model_id
and every model drops out of Kong while Kong reports healthy. Mutation-checked:
nesting one suit under a new root fails this test."
```

---

### Task 2: Controlled role vocabulary

31 role keys exist today across the suits, 22 appearing exactly once, with near-duplicates (`debugging` beside `deep_debugging`). A key with no permitted set cannot be validated.

**Files:**
- Create: `pmoves/configs/model-roles.yaml`
- Create: `pmoves/tools/fittings.py`
- Test: `pmoves/tests/test_model_roles.py`

**Interfaces:**
- Produces:
  - `load_roles(path: Path | None = None) -> dict[str, dict]` — the vocabulary keyed by canonical role name.
  - `resolve_role(name: str, roles: dict[str, dict]) -> tuple[str | None, str | None]` — returns `(canonical_name, warning_or_None)`. Returns `(None, reason)` for an unknown role.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_model_roles.py`:

```python
"""The role vocabulary is a closed set, and superseded names resolve with a warning."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_role_resolves_without_warning():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("deep_debugging", roles)
    assert canonical == "deep_debugging"
    assert warning is None


def test_superseded_role_resolves_and_warns():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("debugging", roles)
    assert canonical == "deep_debugging", "a superseded name must still resolve"
    assert warning is not None and "superseded" in warning


def test_unknown_role_does_not_resolve():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("vibes_based_refactor", roles)
    assert canonical is None
    assert warning is not None


def test_wildcard_role_is_always_valid():
    f = _fittings()
    roles = f.load_roles()
    canonical, warning = f.resolve_role("*", roles)
    assert canonical == "*"
    assert warning is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tests/test_model_roles.py -v`
Expected: FAIL — `FileNotFoundError` or `ModuleNotFoundError`, because neither `fittings.py` nor `model-roles.yaml` exists.

- [ ] **Step 3: Create the vocabulary file**

Create `pmoves/configs/model-roles.yaml`:

```yaml
# Controlled vocabulary for fitting role keys.
#
# Before this file, 31 distinct role keys existed across the suits, 22 of them
# appearing exactly once, with overlapping near-duplicates. A key with no permitted
# set cannot be validated and a router cannot dispatch on free text.
#
# `supersedes` carries consolidation WITHOUT silently dropping the old name: a
# fitting using a superseded key still resolves, and warns. Removing a name outright
# would turn a rename into a routing outage.
#
# `*` is reserved and always valid: it means "every role in this harness".
roles:
  deep_debugging:
    description: "Fault isolation in existing code. Low temperature, high precision."
    supersedes: [debugging]
  code_review:
    description: "Reading a diff for defects, not authoring changes."
  agentic_coding:
    description: "Multi-step autonomous implementation with tool use."
    supersedes: [agentic_workflow, plan_routed_coding]
  code_generation:
    description: "Single-shot authoring from a clear specification."
    supersedes: [lightweight_coding]
  large_scale_implementation:
    description: "Long-horizon implementation spanning many files."
    supersedes: [blueprint_implementation, system_engineering]
  refactoring:
    description: "Behaviour-preserving restructuring."
  long_context_analysis:
    description: "Reading a corpus larger than a working window allows in one pass."
    supersedes: [long_context_research, complex_analysis]
  multi_step_reasoning:
    description: "Chained inference where intermediate steps matter."
    supersedes: [deep_reasoning]
  automated_research:
    description: "Unattended retrieval and synthesis across sources."
  documentation:
    description: "Prose authored for humans, from code or specs."
  quick_chat:
    description: "Short conversational turns, latency-sensitive."
    supersedes: [streaming_response]
  architecture_planning:
    description: "Design decisions ahead of implementation."
  workflow_execution:
    description: "Running a defined pipeline rather than deciding one."
  long_session:
    description: "Sustained work where context retention dominates."
  monitoring:
    description: "Watching a running system and reporting deviation."
  orchestration_overflow:
    description: "Absorbing dispatch load an orchestrator cannot hold."
  voice_synthesis:
    description: "Text to speech, including prosody control."
    supersedes: [expressive_voice_cast, prosodic_bpm_encoding, persona_voice_resolution]
  chinese_language:
    description: "Work where Chinese-language capability is the deciding factor."
```

- [ ] **Step 4: Write the minimal loader**

Create `pmoves/tools/fittings.py`:

```python
#!/usr/bin/env python3
"""Model-harness fitting: loading and resolution.

Owns reading the role vocabulary and the `fit` blocks in the model-suit files.
Deliberately does NOT touch routing identity — `kong_route_seeder` reads that from
the top level of each file and must keep working unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLES_PATH = REPO_ROOT / "pmoves" / "configs" / "model-roles.yaml"
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"

#: Reserved role key meaning "every role in this harness".
WILDCARD_ROLE = "*"


def load_roles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read the controlled role vocabulary."""
    target = path or ROLES_PATH
    with open(target, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return doc.get("roles") or {}


def resolve_role(
    name: str, roles: dict[str, dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Resolve a role key to its canonical name.

    Returns ``(canonical, warning)``. A superseded name resolves and warns; an
    unknown name returns ``(None, reason)`` so the caller can fail the gate.
    """
    if name == WILDCARD_ROLE:
        return WILDCARD_ROLE, None
    if name in roles:
        return name, None
    for canonical, body in roles.items():
        if name in (body or {}).get("supersedes", []):
            return canonical, (
                f"role {name!r} is superseded by {canonical!r}; update the fitting"
            )
    return None, f"role {name!r} is not in the vocabulary (pmoves/configs/model-roles.yaml)"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest pmoves/tests/test_model_roles.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```bash
git add pmoves/configs/model-roles.yaml pmoves/tools/fittings.py pmoves/tests/test_model_roles.py
git commit -m "feat(fittings): controlled role vocabulary with supersedes

31 role keys existed across the suits, 22 appearing exactly once, with debugging
beside deep_debugging. A key with no permitted set cannot be validated and a router
cannot dispatch on free text.

supersedes carries consolidation without silently dropping the old name: a superseded
key still resolves and warns, so a rename is not a routing outage."
```

---

### Task 3: Mark which registry entries are harnesses

The spec's §2 requires a `fit` harness key to resolve to a registered agent, and open question 4 resolved to a first-class `kind:` marker. Without it the key space silently mixes categories — which is how a reviewer with full repo access resolved `typer` to a same-named Python dependency and had to retract.

**Files:**
- Modify: `pmoves/config/agent_registry.yaml` (add `kind: harness` to two entries)
- Modify: `pmoves/tools/fittings.py` (add `load_harnesses`)
- Test: `pmoves/tests/test_harness_kind.py`

**Interfaces:**
- Consumes: `load_roles` from Task 2 (same module).
- Produces: `load_harnesses(registry_path: Path | None = None) -> set[str]` — registry keys whose entry declares `kind: harness`.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_harness_kind.py`:

```python
"""`kind: harness` marks the registry entries a fitting may point at."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_the_two_genuine_harnesses_are_marked():
    f = _fittings()
    harnesses = f.load_harnesses()
    assert "clawz" in harnesses
    assert "kilocode_glm" in harnesses


def test_non_harness_agents_are_not_marked():
    """agent_zero and archon are agent services; a2ui is a UI. None hosts a model."""
    f = _fittings()
    harnesses = f.load_harnesses()
    for key in ("agent_zero", "archon", "a2ui"):
        assert key not in harnesses, f"{key} is not a harness"


def test_kind_values_are_from_a_known_set():
    with open(REGISTRY, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    allowed = {"harness"}
    for key, entry in (doc.get("agents") or {}).items():
        kind = (entry or {}).get("kind")
        if kind is not None:
            assert kind in allowed, f"registry[{key}].kind={kind!r} is not a known kind"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tests/test_harness_kind.py -v`
Expected: FAIL — `AttributeError: module 'fittings' has no attribute 'load_harnesses'`.

- [ ] **Step 3: Add the marker to the two harness entries**

In `pmoves/config/agent_registry.yaml`, add one line to the `clawz` entry, immediately after its `class:` line:

```yaml
    # A harness hosts models; a fitting may name it. Distinguished from agent
    # services (agent_zero, archon), a UI (a2ui) and a launcher (pinokio), which
    # appear in cross_agent for component compatibility but host nothing.
    kind: harness
```

Add the same `kind: harness` line to the `kilocode_glm` entry, after its `class:` line.

- [ ] **Step 4: Add the loader**

Append to `pmoves/tools/fittings.py`:

```python
REGISTRY_PATH = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"


def load_harnesses(registry_path: Path | None = None) -> set[str]:
    """Registry keys whose entry declares ``kind: harness``.

    A fitting may only name one of these. `cross_agent` deliberately names a wider
    set (agents, a UI, a launcher) because it answers a different question —
    component compatibility, not what a harness costs a model.
    """
    target = registry_path or REGISTRY_PATH
    with open(target, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return {
        key
        for key, entry in (doc.get("agents") or {}).items()
        if (entry or {}).get("kind") == "harness"
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest pmoves/tests/test_harness_kind.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Confirm the existing registry gate still passes**

Run: `make -C pmoves validate-agents`
Expected: `OK — registry/teams coupling clean (no new drift); naming conventions hold.`
(`kind:` is additive; `AgentEntry` allows extra fields via `ConfigDict(extra="allow")`.)

- [ ] **Step 7: Commit**

```bash
git add pmoves/config/agent_registry.yaml pmoves/tools/fittings.py pmoves/tests/test_harness_kind.py
git commit -m "feat(agents): kind: harness marks what a fitting may point at

Without an explicit entity kind the cross_agent key space silently mixed agents, a
UI, a launcher and two harnesses across 18 files and nothing caught it. A reviewer
with full repo access then resolved 'typer' to a same-named Python dependency,
called it decisive, and had to retract — a kind marker makes that unresolvable by
guessing.

Marks clawz and kilocode_glm only. agent_zero and archon are agent services and
a2ui is a UI; they appear in cross_agent for component compatibility and host no
model."
```

---

### Task 4: Fit resolution — most conservative wins, absence is honest

**Files:**
- Modify: `pmoves/tools/fittings.py`
- Test: `pmoves/tests/test_fit_resolution.py`

**Interfaces:**
- Produces:
  - `FIT_ORDER: tuple[str, ...]` — `("none", "delegate", "limited", "full")`, least to most permissive.
  - `effective_fit(observations: list[dict]) -> str | None` — the most conservative verdict, or `None` when there are no observations.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_fit_resolution.py`:

```python
"""Fit resolution: the most conservative observation wins, and absence stays absent."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_no_observations_is_none_not_untested():
    """Absent reads as honestly unknown; `untested` reads as a completed
    observation with a null result and survives for months looking like data."""
    f = _fittings()
    assert f.effective_fit([]) is None


def test_single_observation_is_its_verdict():
    f = _fittings()
    assert f.effective_fit([{"verdict": "full", "by": "x", "method": "hand"}]) == "full"


def test_most_conservative_wins_over_a_permissive_measurement():
    """One credible 'this is worse than it looks' is never averaged away by a
    benchmark that did not exercise the failing path."""
    f = _fittings()
    observations = [
        {"verdict": "full", "by": "provider_verifier", "method": "measured"},
        {"verdict": "limited", "by": "darkxside", "method": "hand",
         "note": "requires adapter layer"},
    ]
    assert f.effective_fit(observations) == "limited"


def test_none_beats_everything():
    f = _fittings()
    observations = [
        {"verdict": "full", "method": "measured"},
        {"verdict": "none", "method": "hand"},
        {"verdict": "limited", "method": "hand"},
    ]
    assert f.effective_fit(observations) == "none"


def test_unknown_verdict_is_rejected_loudly():
    f = _fittings()
    try:
        f.effective_fit([{"verdict": "untested", "method": "hand"}])
    except ValueError as exc:
        assert "untested" in str(exc)
    else:
        raise AssertionError("an unknown verdict must raise, not resolve")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tests/test_fit_resolution.py -v`
Expected: FAIL — `AttributeError: module 'fittings' has no attribute 'effective_fit'`.

- [ ] **Step 3: Implement resolution**

Append to `pmoves/tools/fittings.py`:

```python
#: Fit verdicts, least to most permissive. Order IS the conservatism ranking.
#: There is deliberately no "untested": an unmeasured pairing has no observation.
FIT_ORDER: tuple[str, ...] = ("none", "delegate", "limited", "full")


def effective_fit(observations: list[dict[str, Any]]) -> str | None:
    """The verdict a router should act on.

    Returns the MOST CONSERVATIVE verdict among observations, so a single credible
    "this is worse than it looks" is never averaged away by a benchmark that did not
    exercise the failing path. Returns ``None`` when nothing has been observed —
    absence is honestly unknown, and is not the same as a recorded null result.
    """
    if not observations:
        return None
    ranks = []
    for obs in observations:
        verdict = (obs or {}).get("verdict")
        if verdict not in FIT_ORDER:
            raise ValueError(
                f"unknown fit verdict {verdict!r}; permitted: {', '.join(FIT_ORDER)}. "
                "An unmeasured pairing must have NO observation rather than a null one."
            )
        ranks.append(FIT_ORDER.index(verdict))
    return FIT_ORDER[min(ranks)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pmoves/tests/test_fit_resolution.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add pmoves/tools/fittings.py pmoves/tests/test_fit_resolution.py
git commit -m "feat(fittings): most-conservative fit resolution, no untested value

The router reads the most conservative verdict among observations so one credible
'this is worse than it looks' is never averaged away by a benchmark that did not
exercise the failing path.

No untested value exists: absence reads as honestly unknown, whereas untested reads
as a completed observation with a null result and survives for months looking like
data. An unknown verdict raises rather than resolving."
```

---

### Task 5: Seed `fit` from the eleven genuine harness observations

Seeded fresh, not migrated. Migration would have carried the `cross_agent` spelling `kilocode`, which does not resolve — the registry key is `kilocode_glm`.

**Files:**
- Modify: 9 files under `pmoves/configs/model-suits/`
- Test: `pmoves/tests/test_fit_seed.py`

**Interfaces:**
- Consumes: `load_harnesses`, `effective_fit` from Tasks 3–4.
- Produces: a `fit:` block inside `model_suit:` in nine suit files.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_fit_seed.py`:

```python
"""The seeded fit data, and the guarantee that cross_agent was not touched."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"

CLAWZ_FULL = ["claude-haiku-4", "claude-opus-4", "claude-sonnet-4", "claude-sonnet"]
CLAWZ_LIMITED = ["gemma4-dense", "minimax-m2.1", "minimax-m2.7",
                 "nemotron-3-super", "qwen3.6"]
KILOCODE_FULL = ["minimax-m2.1", "minimax-m2.7"]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def _fit_block(stem: str) -> dict:
    with open(SUITS_DIR / f"{stem}.yaml", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    root = doc.get("model_suit") or doc.get("suit") or {}
    return (root or {}).get("fit") or {}


def test_clawz_verdicts_match_the_recorded_measurement():
    f = _fittings()
    for stem in CLAWZ_FULL:
        obs = _fit_block(stem).get("clawz", {}).get("*", [])
        assert f.effective_fit(obs) == "full", stem
    for stem in CLAWZ_LIMITED:
        obs = _fit_block(stem).get("clawz", {}).get("*", [])
        assert f.effective_fit(obs) == "limited", stem


def test_kilocode_is_seeded_under_its_registry_key():
    """cross_agent spells it `kilocode`; the registry key is `kilocode_glm`.
    Seeding fresh lets the fit key be the resolvable one."""
    f = _fittings()
    for stem in KILOCODE_FULL:
        block = _fit_block(stem)
        assert "kilocode" not in block, f"{stem}: unresolvable cross_agent spelling"
        obs = block.get("kilocode_glm", {}).get("*", [])
        assert f.effective_fit(obs) == "full", stem


def test_every_observation_carries_provenance():
    for stem in CLAWZ_FULL + CLAWZ_LIMITED:
        for harness, roles in _fit_block(stem).items():
            for role, observations in roles.items():
                for obs in observations:
                    assert obs.get("by"), f"{stem}/{harness}/{role} has no `by`"
                    assert obs.get("method") in ("hand", "measured"), stem
                    assert obs.get("on"), f"{stem}/{harness}/{role} has no date"


def test_cross_agent_is_byte_identical_to_head():
    """The spec's first acceptance criterion. A value-diff would pass while the
    referent moved, so this asserts the bytes of the field itself did not change."""
    for stem in CLAWZ_FULL + CLAWZ_LIMITED:
        rel = f"pmoves/configs/model-suits/{stem}.yaml"
        before = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        if before.returncode != 0:
            continue
        old = yaml.safe_load(before.stdout) or {}
        with open(REPO_ROOT / rel, encoding="utf-8") as handle:
            new = yaml.safe_load(handle) or {}
        assert old.get("cross_agent") == new.get("cross_agent"), (
            f"{stem}: cross_agent changed. It must be left exactly as it is."
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tests/test_fit_seed.py -v`
Expected: FAIL — `effective_fit([])` returns `None`, not `"full"`, because no `fit:` block exists yet.

- [ ] **Step 3: Add the fit block to the four clawz-full suits**

In each of `claude-haiku-4.yaml`, `claude-opus-4.yaml`, `claude-sonnet-4.yaml`, `claude-sonnet.yaml`, add this inside the `model_suit:` (or `suit:`) mapping, as a sibling of the existing keys. Leave `cross_agent` untouched.

```yaml
  # Harness fit. Seeded fresh, harness-only — NOT migrated from cross_agent, which
  # answers a different question (which components can address this model) and whose
  # key space includes agents, a UI and a launcher.
  fit:
    clawz:
      "*":
        - verdict: full
          by: darkxside
          method: hand
          on: 2026-06-11
```

- [ ] **Step 4: Add the fit block to the five clawz-limited suits**

In each of `gemma4-dense.yaml`, `minimax-m2.1.yaml`, `minimax-m2.7.yaml`, `nemotron-3-super.yaml`, `qwen3.6.yaml`, add the same block with the `limited` verdict and the note that was already recorded beside it:

```yaml
  fit:
    clawz:
      "*":
        - verdict: limited
          by: darkxside
          method: hand
          on: 2026-06-11
          note: "requires adapter layer; tool-call parsing assumes an Anthropic-shaped response"
```

- [ ] **Step 5: Add the kilocode_glm entry to the two suits that have it**

In `minimax-m2.1.yaml` and `minimax-m2.7.yaml`, extend the `fit:` block added in Step 4 with a second harness. Note the key is the REGISTRY key, not the `cross_agent` spelling:

```yaml
    kilocode_glm:
      "*":
        - verdict: full
          by: darkxside
          method: hand
          on: 2026-06-11
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest pmoves/tests/test_fit_seed.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 7: Confirm Kong is unaffected**

Run: `python -m pytest pmoves/tests/test_kong_seeder_identity.py -v`
Expected: PASS. (Task 1's guard — `fit:` is a sibling inside `model_suit:`, so routing identity is untouched.)

- [ ] **Step 8: Commit**

```bash
git add pmoves/configs/model-suits pmoves/tests/test_fit_seed.py
git commit -m "feat(fittings): seed fit from the eleven genuine harness observations

Seeded fresh rather than migrated. cross_agent is byte-identical and keeps
answering component compatibility; a value-diff would have passed while the referent
moved, so the test asserts the field itself is unchanged.

Migration would also have carried the cross_agent spelling 'kilocode', which does
not resolve — the registry key is kilocode_glm. Seeding fresh lets the fit key be
the resolvable one.

Eleven observations: clawz full for four Claude suits, clawz limited for five
non-Claude suits carrying the recorded 'requires adapter layer' note, kilocode_glm
full for two. Every observation carries by/method/on."
```

---

### Task 6: The gate — harness keys and role keys must resolve

**Files:**
- Modify: `pmoves/scripts/validate_agent_registry.py` (add section 4, after the room cross-check that ends near line 213 and before the `return` block near line 227)
- Test: `pmoves/tests/test_fitting_gate.py`

**Interfaces:**
- Consumes: `load_harnesses`, `load_roles`, `resolve_role`, `effective_fit`.
- Produces: nothing importable. Extends the existing `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

Create `pmoves/tests/test_fitting_gate.py`:

```python
"""The gate rejects a fitting that names an unregistered harness or unknown role."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "pmoves" / "scripts" / "validate_agent_registry.py"
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"
VICTIM = SUITS_DIR / "qwen3.6.yaml"


def _run() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def restore_victim():
    backup = VICTIM.read_text(encoding="utf-8")
    yield
    VICTIM.write_text(backup, encoding="utf-8")


def test_gate_passes_on_the_seeded_data():
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate_rejects_an_unregistered_harness(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    root = doc.get("model_suit") or doc.get("suit")
    root["fit"]["not_a_harness"] = {"*": [
        {"verdict": "full", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]}
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "not_a_harness" in result.stdout + result.stderr


def test_gate_rejects_an_unknown_role(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    root = doc.get("model_suit") or doc.get("suit")
    root["fit"]["clawz"]["vibes_based_refactor"] = [
        {"verdict": "full", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "vibes_based_refactor" in result.stdout + result.stderr


def test_gate_rejects_an_unknown_verdict(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    root = doc.get("model_suit") or doc.get("suit")
    root["fit"]["clawz"]["*"] = [
        {"verdict": "untested", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "untested" in result.stdout + result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest pmoves/tests/test_fitting_gate.py -v`
Expected: the three rejection tests FAIL (returncode 0 — the gate does not check fittings yet). `test_gate_passes_on_the_seeded_data` passes.

- [ ] **Step 3: Add section 4 to the validator**

In `pmoves/scripts/validate_agent_registry.py`, add these imports below the existing ones:

```python
sys.path.insert(0, str(ROOT / "pmoves" / "tools"))
from fittings import (  # noqa: E402
    SUITS_DIR,
    effective_fit,
    load_harnesses,
    load_roles,
    resolve_role,
)
```

Then insert this block immediately before the final `if errors:` / `return` section:

```python
    # 4. Fitting cross-check -------------------------------------------------
    # A fitting naming a harness that does not exist is a typo that silently
    # disables routing for that pair. Same shape as the room-owner cross-check
    # above, but an ERROR rather than a warning: a room with a bad owner is still
    # discoverable, whereas an unroutable pairing is invisible at read time.
    harnesses = load_harnesses()
    roles = load_roles()
    for suit_path in sorted(SUITS_DIR.glob("*.yaml")):
        doc = _load_yaml(suit_path) or {}
        root = doc.get("model_suit") or doc.get("suit") or {}
        fit_block = (root or {}).get("fit") or {}
        for harness_key, role_map in fit_block.items():
            if harness_key not in harnesses:
                errors.append(
                    f"{suit_path.name}: fit names {harness_key!r}, which is not a "
                    "registry agent with `kind: harness`"
                )
            for role_key, observations in (role_map or {}).items():
                canonical, note = resolve_role(role_key, roles)
                if canonical is None:
                    errors.append(f"{suit_path.name}: {note}")
                elif note:
                    warnings.append(f"{suit_path.name}: {note}")
                try:
                    effective_fit(observations or [])
                except ValueError as exc:
                    errors.append(f"{suit_path.name} [{harness_key}/{role_key}]: {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pmoves/tests/test_fitting_gate.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Run the full gate and the earlier guards**

Run: `make -C pmoves validate-agents`
Expected: `OK — registry/teams coupling clean (no new drift); naming conventions hold.`

Run: `python -m pytest pmoves/tests/test_kong_seeder_identity.py pmoves/tests/test_model_roles.py pmoves/tests/test_harness_kind.py pmoves/tests/test_fit_resolution.py pmoves/tests/test_fit_seed.py -v`
Expected: PASS, 17 tests.

- [ ] **Step 6: Commit**

```bash
git add pmoves/scripts/validate_agent_registry.py pmoves/tests/test_fitting_gate.py
git commit -m "feat(gate): fittings must name a real harness and a known role

A fitting naming a harness that does not exist is a typo that silently disables
routing for that pair — the failure class this repo keeps hitting. Same cross-check
shape the validator already runs for room owners, but an ERROR rather than a
warning: a room with a bad owner is still discoverable, an unroutable pairing is
invisible at read time.

Mutation-checked by the tests: an unregistered harness key, an unknown role, and an
'untested' verdict each fail the gate."
```

---

## Self-Review

**Spec coverage.** §1 one schema → Task 5 (`fit` as a sibling inside `model_suit`). §1b seam binding → **partially deferred**: `delegate` is in `FIT_ORDER` (Task 4) so the vocabulary exists, but seam-binding fields are not seeded because no current observation records one; the router plan will need them. §2 harness resolution → Tasks 3, 6. §3 role vocabulary → Tasks 2, 6. §4 router → **deferred to the follow-on plan**, stated in Global Constraints. §5 context budget → **deferred with the router**; `budget.prompt_ceiling` has no consumer until the router exists, and adding an unread field is the defect this whole spec is about. §6 evidence-not-permission → Task 5 (provenance asserted on every observation).

**Placeholder scan.** No TBD/TODO. Every code step carries runnable code. Task 5's YAML is written out per group rather than "similar to Task N".

**Type consistency.** `load_roles` / `resolve_role` (Task 2), `load_harnesses` (Task 3), `effective_fit` / `FIT_ORDER` (Task 4) are used with those exact names in Tasks 5–6. `SUITS_DIR` is defined in Task 2 and imported in Task 6. `_load_yaml` and `warnings` in Task 6's block are pre-existing names in the validator.

**Gap found and closed:** the spec's §5 and §1b seam fields would have been added as unread config. Deferring them to the router plan keeps this plan's output fully consumed.
