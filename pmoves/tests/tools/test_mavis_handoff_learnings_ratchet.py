"""Ratchet: the Mavis inter-agent handoff LEARNINGS file must agree with the
orchestrator code that actually shipped.

THE DEFECT CLASS
----------------
``pmoves/docs/AGENTS/mavis_inter_agent_handoff_LEARNINGS.md`` documents the
Mavis inter-agent handoff harness. For a while the file on ``main`` described
the PRE-operator-review design: it said KVM rode ``pmoves.bpm.phase.v1`` with a
``phase: kvm-focus`` discriminator, and it described the ``known_targets``
derivation only vaguely. The orchestrator on ``main`` implements the
POST-review design: ``SUBJECT_KVM_FOCUS`` is its own subject, and
``known_targets`` enumerates ``dataclasses.fields(routing)``. A LEARNINGS file
that states a design the code does not implement is a wrong answer delivered
confidently -- and it is worse than no document at all, because the next
reader has no reason to go and check.

This gate closes that class. Every expectation below is DERIVED FROM THE LIVE
CODE -- the orchestrator source, the live bootstrap config, or the live test
file's own result -- and then asserted against the document. Nothing is
typed out here and hoped to stay true.

WHAT MAKES THIS NOT A TAUTOLOGY
--------------------------------
A test that re-types the fix's own expression proves nothing. So the
expectations are never literals typed here:

* the KVM subject comes from parsing ``SUBJECT_KVM_FOCUS`` out of
  ``pmoves/tools/orchestrator.py`` (and is cross-checked against the imported
  module constant, so the source and the module cannot drift apart);
* the subject ``publish_kvm_focus`` publishes on comes from parsing the
  function body, not from assuming it;
* the ``known_targets`` derivation comes from parsing the property body;
* the wire target comes from the LIVE routing block in ``example.cgp.yaml``;
* the rejected-placeholder set comes from parsing
  ``_NON_ACTIONABLE_NODES`` out of the orchestrator source;
* the DIRECTION of that guard is measured against the live
  ``_is_actionable_node``: a placeholder that is NOT in the set is asked
  whether it is actionable, so the document's "deny-list, not allow-list"
  claim is checked against the code rather than against prose;
* the test counts come from RUNNING ``pmoves/tools/tests/test_orchestrator.py``
  and reading pytest's own summary line.

If the orchestrator changes, this gate fails and the document has to be
updated in the same change. That is the point.

THE MUTATION-KILL HARNESS
-------------------------
``pmoves/tests/tools/test_mavis_handoff_learnings_ratchet_mutation_kill.py``
proves this gate bites: it puts the stale wording back into the LEARNINGS
file and requires the NAMED test here to die.

Run it directly to see the gate's shape:

    python -m pytest pmoves/tests/tools/test_mavis_handoff_learnings_ratchet.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pmoves.tools.load_bootstrap import Routing  # noqa: E402
from pmoves.tools.orchestrator import (  # noqa: E402
    SUBJECT_BPM_PHASE,
    SUBJECT_KVM_FOCUS,
    SUBJECT_TASK,
    MockPublisher,
    Orchestrator,
)

LEARNINGS = (
    REPO_ROOT
    / "pmoves"
    / "docs"
    / "AGENTS"
    / "mavis_inter_agent_handoff_LEARNINGS.md"
)
ORCHESTRATOR = REPO_ROOT / "pmoves" / "tools" / "orchestrator.py"
ORCHESTRATOR_TESTS = REPO_ROOT / "pmoves" / "tools" / "tests" / "test_orchestrator.py"

# Where the repo's own test functions live. Used to prove that a test the
# LEARNINGS names actually EXISTS -- the Lesson 3 claim about
# `test_routing_for_returns_a_copy_not_a_reference` was false on main because
# the file that used to hold it was deleted.
_TEST_ROOTS = (
    REPO_ROOT / "pmoves" / "tools" / "tests",
    REPO_ROOT / "pmoves" / "tests",
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _norm(text: str) -> str:
    """Collapse all whitespace runs to single spaces.

    The LEARNINGS file hard-wraps its prose, so a claim like
    ``target_alias: "hermes"`` is split across a line break inside its
    backticks. Normalising lets the assertions below match the CLAIM rather
    than the author's line breaks -- and a mutation that changes the claim
    still changes the normalised text.
    """
    return re.sub(r"\s+", " ", text)


def _source() -> str:
    return ORCHESTRATOR.read_text(encoding="utf-8")


def _assigned_literal(name: str) -> str:
    """The string the orchestrator SOURCE assigns to `name`.

    Read out of the file, not typed here, so the gate tracks the code even if
    an import is stale or monkeypatched.
    """
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']", _source(), re.MULTILINE
    )
    assert match, f"{name} is not assigned a string literal in {ORCHESTRATOR.name}"
    return match.group(1)


def _function_body(name: str) -> str:
    """The source text of a method, up to the next method at the same indent."""
    src = _source()
    match = re.search(rf"^([ \t]*)def {re.escape(name)}\b", src, re.MULTILINE)
    assert match, f"{name} is not defined in {ORCHESTRATOR.name}"
    indent = match.group(1)
    rest = src[match.end():]
    nxt = re.search(rf"^{re.escape(indent)}def \w", rest, re.MULTILINE)
    end = match.end() + (nxt.start() if nxt else len(rest))
    return src[match.start():end]


def _kvm_publish_subject_constant() -> str:
    """The subject CONSTANT `publish_kvm_focus` publishes on.

    Parsed from the function body, so the gate does not assume the KVM
    surface stayed where it is.
    """
    body = _function_body("publish_kvm_focus")
    match = re.search(r"self\.publisher\.publish\(\s*([A-Z_][A-Z0-9_]*)", body)
    assert match, (
        "publish_kvm_focus does not publish on a named subject constant -- "
        "the LEARNINGS' KVM claim cannot be checked"
    )
    return match.group(1)


def _declared_non_actionable_nodes() -> set[str]:
    """The placeholder node names the orchestrator refuses to switch to."""
    match = re.search(
        r"_NON_ACTIONABLE_NODES\s*=\s*frozenset\(\{([^}]*)\}\)", _source()
    )
    assert match, (
        "_NON_ACTIONABLE_NODES is not declared in the orchestrator source -- "
        "the LEARNINGS' placeholder claim cannot be checked"
    )
    return set(re.findall(r"\"([^\"]+)\"", match.group(1)))


def _claimed_non_actionable_nodes(doc: str) -> str:
    """The placeholder node names the LEARNINGS claims are refused, verbatim.

    Returned as the raw claimed TEXT, not a split set: one of the rejected
    placeholders is ``n/a``, which a naive ``/`` split would tear into ``n``
    and ``a``. The check below therefore compares the claimed text against the
    code's set by containment plus a residue test, rather than by splitting.
    """
    match = re.search(r"rejects `([^`]+)`\s+alongside\s+`([^`]+)`", doc)
    assert match, (
        "the LEARNINGS no longer states which placeholder nodes are rejected -- "
        "if the wording changed, update this gate in the same change"
    )
    return " ".join(match.groups())


def _named_tests_in(doc: str) -> set[str]:
    """The test function names the LEARNINGS cites (backticked, code-shaped)."""
    return set(re.findall(r"`(test_[a-z0-9_]+)`", doc))


def _section(doc: str, heading: str) -> str:
    """The text of one ``## <heading>`` section, up to the next ``##``.

    Section-scoped, because some claims are only true (or only false)
    inside the lesson that makes them: a gate that scanned the whole file
    would fire on an unrelated sentence.
    """
    lines = doc.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"## {heading}"):
            start = index
            break
    assert start is not None, f"the LEARNINGS has no '## {heading}' section"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _defined_test_names() -> set[str]:
    """Every ``def test_*`` in the repo's own test trees."""
    names: set[str] = set()
    for root in _TEST_ROOTS:
        for path in root.rglob("test_*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - unreadable file
                continue
            names.update(
                re.findall(r"^\s*def (test_[a-z0-9_]+)", text, re.MULTILINE)
            )
    return names


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """`load_bootstrap()` resolves the schema and the example CGP by RELATIVE
    path, so the suite must run from the repo root to load the LIVE config."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture()
def doc() -> str:
    """The LEARNINGS file, read fresh.

    Read per-test, never cached at import, because the mutation-kill harness
    rewrites this file on disk and expects the child pytest process to see the
    MUTATED bytes.
    """
    return LEARNINGS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def orchestrator_test_counts() -> tuple[int, int]:
    """(tests, subtests) as pytest reports them for the orchestrator test file.

    Measured by RUNNING the file, because the LEARNINGS' count claim is about
    the test file's actual result, not about a number someone remembered.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(ORCHESTRATOR_TESTS),
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:warnings",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    out = proc.stdout + proc.stderr
    summary = ""
    for line in reversed(out.splitlines()):
        if re.search(r"\d+ passed", line):
            summary = line
            break
    assert summary, (
        "could not read a test count from the orchestrator test run:\n"
        f"{out[-4000:]}"
    )
    passed = re.search(r"(\d+) passed", summary)
    subtests = re.search(r"(\d+) subtests passed", summary)
    assert passed and subtests, (
        "the orchestrator test run did not report both a test count and a "
        f"subtest count:\n{summary}"
    )
    assert not re.search(r"skipped|failed|error", summary, re.IGNORECASE), (
        f"the orchestrator test run was not clean: {summary}"
    )
    return int(passed.group(1)), int(subtests.group(1))


# ── Lesson 2: the KVM subject ────────────────────────────────────────────────


def test_the_learnings_names_the_kvm_subject_the_orchestrator_publishes_on(doc: str) -> None:
    """The doc must name the subject the code actually publishes KVM focus on.

    The expectation is parsed out of the orchestrator source and cross-checked
    against the imported module constant, so the two cannot drift apart and
    the document cannot name a subject the code does not use.
    """
    subject = _assigned_literal("SUBJECT_KVM_FOCUS")
    assert subject == SUBJECT_KVM_FOCUS, (
        "the orchestrator module and its source disagree about "
        f"SUBJECT_KVM_FOCUS ({subject!r} vs {SUBJECT_KVM_FOCUS!r})"
    )
    assert subject in _norm(doc), (
        f"the LEARNINGS does not name the KVM subject the orchestrator uses "
        f"({subject!r})"
    )


def test_the_learnings_does_not_pick_the_phase_discriminator_design(doc: str) -> None:
    """The stale design chose (B): KVM rides the BPM phase stream.

    The gate reads the CODE's choice -- which subject ``publish_kvm_focus``
    actually publishes on -- and requires the document to agree. A document
    that still selects the phase-discriminator design describes a contract
    the code does not implement.
    """
    published_on = _assigned_literal(_kvm_publish_subject_constant())
    phase = _assigned_literal("SUBJECT_BPM_PHASE")
    assert published_on != phase, (
        "the orchestrator publishes KVM focus on the BPM phase stream -- the "
        "LEARNINGS' own-subject claim is now false and must be updated"
    )
    assert "Picked (B)" not in doc, (
        "the LEARNINGS still selects the phase-discriminator design that the "
        "operator review rejected"
    )
    assert "**(B) Reuse" not in doc, (
        "the LEARNINGS still lists the phase-discriminator design as an option"
    )


def test_the_kvm_focus_surface_is_not_published_on_the_phase_stream() -> None:
    """The behavioural half of the Lesson 2 claim, against the LIVE code.

    A dispatch to a remote node must publish a KVM focus event and must NOT
    publish an event on the BPM phase subject -- the phase stream is
    contracted as the five lifecycle phases.
    """
    pub = MockPublisher()
    orch = Orchestrator(publisher=pub, timeout_s=5, poll_s=0.05)
    orch.dispatch("render", agents=["kiloclaw"])
    subjects = [s for s, _ in pub.published]
    assert SUBJECT_KVM_FOCUS in subjects
    assert SUBJECT_BPM_PHASE not in subjects
    focus = next(p for s, p in pub.published if s == SUBJECT_KVM_FOCUS)
    assert "phase" not in focus, (
        "the KVM focus payload still carries a phase discriminator"
    )


# ── Lesson 1: how known_targets is derived ───────────────────────────────────


def test_the_learnings_agrees_with_the_orchestrator_on_how_known_targets_is_derived(
    doc: str,
) -> None:
    """The doc must describe the derivation the code actually uses.

    The expectation is parsed out of the ``known_targets`` property body, so a
    code change that swaps ``dataclasses.fields(...)`` back for a literal peer
    tuple fails this gate instead of leaving a false sentence behind.
    """
    body = _function_body("known_targets")
    assert "dataclasses.fields(" in body, (
        "known_targets no longer derives its peers from dataclasses.fields -- "
        "the LEARNINGS' Lesson 1 claim must be updated in the same change"
    )
    assert "dataclasses.fields" in doc, (
        "the LEARNINGS no longer says how known_targets is derived"
    )


def test_adding_a_routing_field_widens_the_dispatch_surface(doc: str) -> None:
    """Lesson 1's promise, checked against the LIVE code.

    The doc says adding a routing entry to the CGP auto-widens the dispatch
    surface with zero orchestrator code. That is a claim about behaviour, so it
    is checked by behaviour: a routing dataclass with an extra field must show
    up in ``known_targets`` on its own.
    """
    orch = Orchestrator(publisher=MockPublisher(), timeout_s=5, poll_s=0.05)
    base = orch.bootstrap.routing

    @dataclasses.dataclass
    class _ExtendedRouting(Routing):
        futurepeer: dict = dataclasses.field(default_factory=dict)

    orch.bootstrap.routing = _ExtendedRouting(
        kiloclaw=base.kiloclaw,
        hermes=base.hermes,
        pinokio=base.pinokio,
        futurepeer={"node": "5090", "target": "fp-1"},
    )
    assert "futurepeer" not in Orchestrator(
        publisher=MockPublisher(), timeout_s=5, poll_s=0.05
    ).known_targets, (
        "the pre-condition is wrong: an unused routing field is already "
        "accepted, so this test would prove nothing"
    )
    assert "futurepeer" in orch.known_targets, (
        "adding a routing field did NOT widen the dispatch surface -- the "
        "LEARNINGS' Lesson 1 promise is false"
    )
    assert "widens the dispatch surface" in _norm(doc), (
        "the LEARNINGS no longer states the routing-widens promise"
    )


# ── Lesson 4: the wire target ────────────────────────────────────────────────


def test_the_learnings_agrees_with_the_orchestrator_on_the_wire_target(
    doc: str,
) -> None:
    """The doc must name the CONFIGURED target the live routing block carries.

    The value comes from the live ``example.cgp.yaml`` routing entry, and the
    behavioural half confirms the envelope really carries it (with the alias
    alongside), so the document cannot drift away from the wire.
    """
    orch = Orchestrator(publisher=MockPublisher(), timeout_s=5, poll_s=0.05)
    entry = orch.routing_for("hermes")
    configured = entry.get("target")
    alias = "hermes"
    assert configured and configured != alias, (
        "the live routing entry no longer carries a configured target distinct "
        f"from the alias: {entry!r}"
    )

    pub = MockPublisher()
    orch.publisher = pub
    orch.dispatch("draft", agents=[alias])
    payload = next(p for s, p in pub.published if s == SUBJECT_TASK)
    assert payload["target"] == configured
    assert payload["target_alias"] == alias

    normalised = _norm(doc)
    assert f'`target: "{configured}"`' in normalised, (
        f"the LEARNINGS does not name the configured wire target "
        f"{configured!r} on the envelope"
    )
    assert f'`target_alias: "{alias}"`' in normalised, (
        f"the LEARNINGS does not name the alias {alias!r} that rides alongside it"
    )


# ── Lesson 5: placeholders are not machine names ─────────────────────────────


def test_the_learnings_placeholder_set_matches_the_orchestrators_non_actionable_nodes(
    doc: str,
) -> None:
    """The doc must list exactly the placeholders the code refuses.

    The set comes from parsing ``_NON_ACTIONABLE_NODES`` out of the
    orchestrator source, and the behavioural half confirms the live
    implementation really rejects each one, case-insensitively and
    whitespace-trimmed.
    """
    declared = _declared_non_actionable_nodes()
    claimed = _claimed_non_actionable_nodes(doc)
    for token in sorted(declared, key=len, reverse=True):
        assert token in claimed, (
            f"the LEARNINGS does not list {token!r} among the rejected "
            f"placeholder nodes (it claims: {claimed!r})"
        )
    # The doc must not claim a placeholder the orchestrator would happily
    # switch to. Whatever is left of the claimed text once every rejected
    # placeholder has been removed must be nothing but separators.
    residue = claimed
    for token in sorted(declared, key=len, reverse=True):
        residue = residue.replace(token, "")
    assert not residue.strip(" /,"), (
        "the LEARNINGS claims placeholder nodes the orchestrator does NOT "
        f"reject: {residue!r}"
    )
    for token in sorted(declared):
        assert not Orchestrator._is_actionable_node(token), token
        assert not Orchestrator._is_actionable_node(token.upper()), token
        assert not Orchestrator._is_actionable_node(f"  {token}  "), token


def test_the_learnings_describes_the_placeholder_guard_as_a_deny_list(
    doc: str,
) -> None:
    """The doc must name the guard's DIRECTION -- and the direction is
    MEASURED against the live code, not assumed.

    ``_is_actionable_node`` returns true for every node name that is NOT in
    ``_NON_ACTIONABLE_NODES``, so the set is a DENY-LIST: a placeholder is
    actionable -- a real machine, worth a KVM request -- until someone adds
    it to the set. A document that calls the guard an allow-list of
    actionable values, or calls the set forward-compatible, states the
    opposite of what the code does, and the reader who believes it ships a
    config carrying ``hold`` and gets a focus request for a machine named
    ``hold``.

    The four probes below are the ones the doc itself names as the
    placeholders an operator might add (``hold``, ``pending``, ``TBA``,
    ``???``). They are asserted ACTIONABLE, because that is what the
    shipped deny-list makes of them.
    """
    declared = _declared_non_actionable_nodes()
    assert declared, (
        "the orchestrator declares no non-actionable nodes -- the guard is no "
        "longer the deny-list the LEARNINGS describes"
    )
    for fresh in ("hold", "pending", "tba", "???"):
        assert Orchestrator._is_actionable_node(fresh), (
            f"the orchestrator now REJECTS {fresh!r} -- the deny-list grew, so "
            "the LEARNINGS' direction claim must be re-measured and updated in "
            "this same change"
        )

    lesson5 = _section(doc, "Lesson 5")
    assert "deny-list" in lesson5, (
        "the LEARNINGS no longer calls the placeholder guard a deny-list -- "
        "if the wording changed, update this gate in the same change"
    )
    assert "not an allow-list" in lesson5, (
        "the LEARNINGS no longer says the guard is not an allow-list -- if the "
        "wording changed, update this gate in the same change"
    )
    assert "forward-compat" not in _norm(doc), (
        "the LEARNINGS still calls the placeholder guard forward-compatible -- "
        "the guard is a deny-list, so a new placeholder is actionable until it "
        "has been added to the set"
    )


# ── the test names the document cites ────────────────────────────────────────


def test_the_learnings_named_tests_exist_in_the_repo(doc: str) -> None:
    """Every test the LEARNINGS names must actually exist.

    Lesson 3 named ``test_routing_for_returns_a_copy_not_a_reference`` as its
    regression check. On ``main`` that test did not exist: it lived in
    ``pmoves/tests/test_orchestrator_kvm.py``, which was deleted as stale. The
    document was pointing at a regression check that was not there.
    """
    named = _named_tests_in(doc)
    assert named, (
        "the LEARNINGS names no test at all -- this gate has lost its teeth"
    )
    defined = _defined_test_names()
    for name in sorted(named):
        assert name in defined, (
            f"the LEARNINGS names {name}, which does not exist in the repo's "
            "test trees"
        )


# ── Lesson 3: the regression check the document names ─────────────────────────


def test_routing_for_returns_a_copy_not_a_reference() -> None:
    """Lesson 3's regression check, restored to the tree.

    ``routing_for`` returns ``dict(entry)`` rather than the live dict. If a
    future "optimize the dict copy" drops the copy, a caller that mutates the
    returned dict silently mutates the bootstrap's routing, which is shared
    across every dispatch.
    """
    orch = Orchestrator(publisher=MockPublisher(), timeout_s=5, poll_s=0.05)
    entry = orch.routing_for("kiloclaw")
    assert entry, "the live routing block has no kiloclaw entry to copy"
    entry["node"] = "mutated-by-caller"
    assert orch.routing_for("kiloclaw")["node"] != "mutated-by-caller", (
        "routing_for returned a live reference -- a caller can now mutate the "
        "shared bootstrap routing"
    )


# ── the counts the document claims ───────────────────────────────────────────


def test_the_learnings_test_counts_match_the_orchestrator_test_file(
    doc: str,
    orchestrator_test_counts: tuple[int, int],
) -> None:
    """The doc's "17/17 + 12 subtests pass" claim must still be true.

    The numbers come from RUNNING the orchestrator test file and reading
    pytest's own summary, so this is a measurement, not a remembered number.
    """
    tests, subtests = orchestrator_test_counts
    match = re.search(r"(\d+)/(\d+) \+ (\d+) subtests pass", _norm(doc))
    assert match, (
        "the LEARNINGS no longer states the orchestrator test counts in the "
        "form 'N/N + M subtests pass' -- if the wording changed, update this "
        "gate in the same change"
    )
    assert int(match.group(1)) == tests, (
        f"the LEARNINGS claims {match.group(1)} tests; the orchestrator test "
        f"file now runs {tests}"
    )
    assert int(match.group(2)) == tests, (
        f"the LEARNINGS claims {match.group(2)}/{match.group(1)}; the "
        f"orchestrator test file now runs {tests}"
    )
    assert int(match.group(3)) == subtests, (
        f"the LEARNINGS claims {match.group(3)} subtests; the orchestrator "
        f"test file now runs {subtests}"
    )
