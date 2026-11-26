"""The lane's RELEASE row must cite a provenance artifact that is VERIFIABLE FROM THE TREE.

THE DEFECT CLASS
----------------
A register row that says "the trail is unsigned because no signing key was
present" is a claim about the WORLD. A row that says "the trail was emitted at
this timestamp, by this agent, with this signature state, and the payload is
committed at THIS path" is a claim about ARTIFACTS -- and artifacts can be
checked by the next session without trusting the row.

MEASURED 2026-11-06: this lane's RELEASE row cited
``pmoves/docs/logs/graphiti_signed_latest.json`` -- a path ``pmoves/.gitignore:37``
excludes, so the row's ONLY provenance artifact was a receipt that does not
exist for anyone reading the repository the row is filed in. The row also
asserted that no signing key was present, without recording WHICH check was
run; ``pmoves/tools/sign_trail.py``'s ``_resolve_chit_passphrase`` consults
FIVE sources, not the four environment variables the row's wording implied.

The register has already adjudicated this class once: the 2026-08-09
``5090-CLAUDE`` row recorded that the passphrase IS present in that node's
shared env, that the register's "unsigned-local" disclaimers are "a process
gap, not a material gap", and that "sessions should attempt ``sign-trail``
before writing the disclaimer".

WHAT THIS GATE CHECKS
---------------------
The row is the CONTRACT with the next reader. So the row's claims are checked
against the artifacts they name -- not against a re-typed copy of them:

1. the lane's RELEASE row exists, and there is exactly ONE of it;
2. it declares the trail artifact it relies on;
3. that artifact EXISTS in the tree, is TRACKED by git, and is NOT gitignored
   -- an artifact outside the tree cannot verify a claim filed inside it;
4. the artifact's identity and timestamp appear in the row, so the citation is
   to a SPECIFIC payload and not to "some trail";
5. the row's declared signature state MATCHES the artifact's ACTUAL state --
   a row that says "signed" over an unsigned payload is a false provenance
   claim, and a row that says "unsigned" over a signed payload is a stale one;
6. the row records the KEY PROBE -- which sources were consulted -- rather
   than asserting a fact about the world;
7. no artifact path the row cites escapes the tree.

Hermetic: reads this repository and runs read-only `git` queries. Writes
nothing, mutates nothing.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
LEARNINGS = (
    REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "house_ci_defect_closure_LEARNINGS.md"
)

# The lane totals as they appear in the row, and as they appear in the
# LEARNINGS file -- where the taxonomy gate RECOMPUTES them.
ROW_TOTALS = re.compile(
    r"(\d+)\s+behavioural test functions\s+and\s+(\d+)\s+mutation kills"
)
LEARNINGS_TOTAL = re.compile(
    r"\*\*Total:\s*(\d+)\s+behavioural test functions\s+and\s+"
    r"(\d+)\s+mutation kills"
)

# The taxonomy's five classes, and how the row names them.
CLASSES = (
    ("reasoning-gap", "reasoning_gap"),
    ("semantic-naming drift", "semantic_naming_drift"),
    ("contract-correctness", "contract_correctness"),
    ("defense-in-depth", "defense_in_depth"),
    ("pattern-conformance", "pattern_conformance"),
)
ROW_TAXONOMY = re.compile(
    r"\(reasoning-gap (?P<reasoning_gap>\d+), "
    r"semantic-naming drift (?P<semantic_naming_drift>\d+), "
    r"contract-correctness (?P<contract_correctness>\d+), "
    r"defense-in-depth (?P<defense_in_depth>\d+), "
    r"pattern-conformance (?P<pattern_conformance>\d+)\)"
)
LEARNINGS_BUCKET = re.compile(r"^\|\s*(?P<cls>[a-z\- ]+?)\s*\|\s*(?P<count>\d+)\s*\|")

LANE_OWNER = "Mavis (mvs_ce8c1e6e34434db1ba42d3b822ecbd15)"
LANE_BRANCH = "fix/house-ci-defect-closure"

# The register's row grammar: - `<ts>` <KIND> `<owner>` branch: `<branch>` · scope: ...
ROW = re.compile(
    r"^- `(?P<ts>[^`]+)` (?P<kind>CLAIM|RELEASE|NOTE|DOCS|AMEND|SYNC) "
    r"`(?P<owner>[^`]+)` branch: `(?P<branch>[^`]+)`",
    re.MULTILINE,
)

# Every artifact path the row names, in ANY spelling -- backticked or not. The
# rule is "every path the row names is inside the tree", so the pattern must
# not depend on the row happening to quote it.
CITED_ARTIFACTS = re.compile(r"(pmoves/docs/logs/[^`\s]+\.json)")

# The declared artifact, the declared identity, the declared timestamp, the
# declared signature state, and the recorded key probe. Each is a `key: value`
# token terminated by `;`, so the row states its provenance in a form a gate can
# read field by field -- rather than in prose, where "minimax" appears in
# several places and a substring check would pass on the wrong one. The `;`
# terminator matters: a bare `\S+` would capture the sentence's full stop along
# with the value, and `minimax.` != `minimax`.
ARTIFACT_DECL = re.compile(r"trail_artifact:\s*(?P<path>[^;]+)")
AGENT_DECL = re.compile(r"trail_agent_id:\s*(?P<agent_id>[^;]+)")
TIMESTAMP_DECL = re.compile(r"trail_timestamp:\s*(?P<timestamp>[^;]+)")
STATE_DECL = re.compile(r"trail_signature_state:\s*(?P<state>[A-Z]+)")
PROBE_DECL = re.compile(r"chit_key_probe:\s*(?P<probe>[^;]+)")

# The five sources `sign_trail.py::_resolve_chit_passphrase` consults, in its
# own priority order. A probe that checks fewer than all five cannot support
# the claim "no signing key is available here".
KEY_PROBE_SOURCES = (
    "CHIT_SIGNING_KEY",
    "CHIT_PASSPHRASE",
    "CHIT_SIGNING_KEY_FILE",
    "CHIT_PASSPHRASE_FILE",
    "env.tier-",
)


def _register_text() -> str:
    return REGISTER.read_text(encoding="utf-8")


def _lane_rows() -> list[dict[str, str]]:
    """The register rows that belong to this lane."""
    out = []
    for match in ROW.finditer(_register_text()):
        if match.group("owner") != LANE_OWNER:
            continue
        if match.group("branch") != LANE_BRANCH:
            continue
        out.append(match.groupdict())
    return out


def _release_row() -> str:
    """The full text of this lane's RELEASE row."""
    text = _register_text()
    hits = []
    for line in text.splitlines():
        if not line.startswith("- `"):
            continue
        match = ROW.match(line)
        if not match:
            continue
        if match.group("kind") != "RELEASE":
            continue
        if match.group("owner") != LANE_OWNER:
            continue
        if match.group("branch") != LANE_BRANCH:
            continue
        hits.append(line)
    assert hits, (
        "this lane's RELEASE row is not in the register -- the row was removed "
        "or renamed"
    )
    return hits[0]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def _is_tracked(rel: str) -> bool:
    """True when the path is in git's index -- i.e. it would travel with the repo."""
    return _git("ls-files", "--error-unmatch", "--", rel).returncode == 0


def _is_ignored(rel: str) -> bool:
    """True when git's ignore rules would EXCLUDE the path from the tree."""
    return _git("check-ignore", "-q", "--", rel).returncode == 0


def _payload(rel: str) -> dict | None:
    path = REPO_ROOT / rel
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _artifact_state(rel: str) -> tuple[bool, bool, bool, dict | None]:
    """(exists, tracked, ignored, payload) for a repo-relative artifact path."""
    exists = (REPO_ROOT / rel).is_file()
    return exists, _is_tracked(rel), _is_ignored(rel), _payload(rel)


def _artifact_is_signed(payload: dict) -> bool:
    """`sign_cgp` stamps a top-level `sig`; an unsigned payload has none."""
    return "sig" in payload


def provenance_problems(row_text: str) -> list[str]:
    """Every way in which `row_text` fails to be verifiable from the tree.

    Returned as a list so a caller can assert on the CONTENT of the complaint
    rather than on a bare boolean.
    """
    problems: list[str] = []

    declared = ARTIFACT_DECL.search(row_text)
    if not declared:
        problems.append(
            "the row declares no `trail_artifact:` -- it names no artifact a "
            "reader could check"
        )
        return problems

    rel = declared.group("path").strip().strip("`")
    exists, tracked, ignored, payload = _artifact_state(rel)

    if not exists:
        problems.append(f"{rel}: declared by the row but not present in the tree")
    if ignored:
        problems.append(
            f"{rel}: is GITIGNORED, so it cannot verify a claim filed in the "
            f"repository that ignores it"
        )
    if not tracked:
        problems.append(
            f"{rel}: is not TRACKED by git, so it cannot verify a claim filed in "
            f"the repository that does not carry it"
        )

    if payload is not None:
        agent = AGENT_DECL.search(row_text)
        if not agent:
            problems.append(
                "the row declares no `trail_agent_id:` -- its citation does not "
                "say which agent produced the artifact"
            )
        elif agent.group("agent_id").strip() != payload.get("agent_id"):
            problems.append(
                f"{rel}: the row declares trail_agent_id "
                f"{agent.group('agent_id')!r} but the artifact's agent_id is "
                f"{payload.get('agent_id')!r}"
            )

        stamp = TIMESTAMP_DECL.search(row_text)
        if not stamp:
            problems.append(
                "the row declares no `trail_timestamp:` -- its citation does not "
                "say which payload it means"
            )
        elif stamp.group("timestamp").strip() != payload.get("timestamp"):
            problems.append(
                f"{rel}: the row declares trail_timestamp "
                f"{stamp.group('timestamp')!r} but the artifact's timestamp is "
                f"{payload.get('timestamp')!r}"
            )

        state = STATE_DECL.search(row_text)
        signed = _artifact_is_signed(payload)
        if not state:
            problems.append(
                f"{rel}: the row declares no `trail_signature_state:`, so its "
                f"claim about the signature is not checkable"
            )
        elif signed and state.group("state") != "SIGNED":
            problems.append(
                f"{rel}: the artifact IS signed but the row declares "
                f"trail_signature_state: {state.group('state')}"
            )
        elif not signed and state.group("state") != "UNSIGNED":
            problems.append(
                f"{rel}: the artifact is UNSIGNED but the row declares "
                f"trail_signature_state: {state.group('state')}"
            )

    probe = PROBE_DECL.search(row_text)
    if not probe:
        problems.append(
            "the row records no `chit_key_probe:` -- it asserts a fact about the "
            "availability of a signing key instead of recording the check it ran"
        )
    else:
        clause = probe.group("probe")
        for source in KEY_PROBE_SOURCES:
            if source not in clause:
                problems.append(
                    f"the recorded key probe does not name the {source} source"
                )

    for other in CITED_ARTIFACTS.findall(row_text):
        if other == rel:
            continue
        _exists, other_tracked, other_ignored, _payload_ = _artifact_state(other)
        if other_ignored:
            problems.append(
                f"{other}: also cited by the row, and is GITIGNORED -- a citation "
                f"outside the tree verifies nothing"
            )
        if not other_tracked:
            problems.append(
                f"{other}: also cited by the row, and is not TRACKED by git"
            )

    return problems


# ---------------------------------------------------------------------------
# The tests
# ---------------------------------------------------------------------------


def test_the_lane_release_row_exists():
    rows = [r for r in _lane_rows() if r["kind"] == "RELEASE"]
    assert rows, (
        "this lane's RELEASE row is missing from "
        f"{REGISTER.name} -- a RELEASE closes the lane, so it has to be there"
    )


def test_there_is_exactly_one_release_row_for_this_lane():
    """A row that carries a false claim is REPLACED, not appended to."""
    rows = [r for r in _lane_rows() if r["kind"] == "RELEASE"]
    assert len(rows) == 1, (
        f"this lane has {len(rows)} RELEASE rows; a superseded row must be "
        f"replaced, not appended to"
    )


def test_the_release_row_declares_a_trail_artifact():
    row = _release_row()
    declared = ARTIFACT_DECL.search(row)
    assert declared, (
        "the RELEASE row declares no `trail_artifact:` -- a provenance row that "
        "names no artifact is a claim about the world, not about the tree"
    )
    assert declared.group("path").strip("`").startswith("pmoves/docs/logs/"), (
        f"the declared artifact {declared.group('path')!r} is not under "
        f"pmoves/docs/logs/"
    )


def test_the_cited_artifact_exists_in_the_tree():
    rel = ARTIFACT_DECL.search(_release_row()).group("path").strip().strip("`")
    exists, _tracked, _ignored, _payload = _artifact_state(rel)
    assert exists, f"{rel}: declared by the RELEASE row but not present in the tree"


def test_the_cited_artifact_is_tracked_by_git():
    rel = ARTIFACT_DECL.search(_release_row()).group("path").strip().strip("`")
    _exists, tracked, _ignored, _payload = _artifact_state(rel)
    assert tracked, (
        f"{rel}: the RELEASE row's only provenance artifact is not TRACKED by "
        f"git, so it does not travel with the repository the row is filed in"
    )


def test_the_cited_artifact_is_not_gitignored():
    rel = ARTIFACT_DECL.search(_release_row()).group("path").strip().strip("`")
    _exists, _tracked, ignored, _payload = _artifact_state(rel)
    assert not ignored, (
        f"{rel}: the RELEASE row's only provenance artifact is GITIGNORED, so "
        f"nobody reading the repository can verify the claim filed beside it"
    )


def test_the_cited_artifacts_identity_and_timestamp_appear_in_the_row():
    """The citation is to a SPECIFIC payload, not to "some trail"."""
    rel = ARTIFACT_DECL.search(_release_row()).group("path").strip().strip("`")
    payload = _payload(rel)
    assert payload is not None, f"{rel}: not a readable JSON payload"
    row = _release_row()

    agent = AGENT_DECL.search(row)
    assert agent, "the RELEASE row declares no `trail_agent_id:`"
    assert agent.group("agent_id").strip() == payload.get("agent_id"), (
        f"{rel}: the row declares trail_agent_id {agent.group('agent_id')!r} but "
        f"the artifact's agent_id is {payload.get('agent_id')!r}"
    )

    stamp = TIMESTAMP_DECL.search(row)
    assert stamp, "the RELEASE row declares no `trail_timestamp:`"
    assert stamp.group("timestamp").strip() == payload.get("timestamp"), (
        f"{rel}: the row declares trail_timestamp {stamp.group('timestamp')!r} "
        f"but the artifact's timestamp is {payload.get('timestamp')!r}"
    )


def test_the_rows_signature_state_matches_the_artifacts_actual_state():
    """The row's claim about the signature must MATCH the artifact."""
    rel = ARTIFACT_DECL.search(_release_row()).group("path").strip().strip("`")
    payload = _payload(rel)
    assert payload is not None, f"{rel}: not a readable JSON payload"
    state = STATE_DECL.search(_release_row())
    assert state, "the RELEASE row declares no `trail_signature_state:`"
    signed = _artifact_is_signed(payload)
    expected = "SIGNED" if signed else "UNSIGNED"
    assert state.group("state") == expected, (
        f"{rel}: the artifact is {'signed' if signed else 'UNSIGNED'} but the "
        f"row declares trail_signature_state: {state.group('state')}"
    )


def test_the_row_records_the_chit_key_probe():
    """A disclaimer must record the CHECK, not assert a fact about the world."""
    row = _release_row()
    probe = PROBE_DECL.search(row)
    assert probe, (
        "the RELEASE row records no `chit_key_probe:` -- it asserts that no "
        "signing key was available without recording which sources were checked"
    )
    clause = probe.group("probe")
    for source in KEY_PROBE_SOURCES:
        assert source in clause, (
            f"the recorded key probe does not name the {source} source; "
            f"sign_trail.py consults five, so a probe of fewer cannot support "
            f"the claim"
        )


def test_no_cited_artifact_path_is_gitignored():
    """No citation the row makes may escape the tree."""
    row = _release_row()
    for rel in CITED_ARTIFACTS.findall(row):
        _exists, tracked, ignored, _payload = _artifact_state(rel)
        assert not ignored, (
            f"{rel}: cited by the RELEASE row and GITIGNORED -- a citation "
            f"outside the tree verifies nothing"
        )
        assert tracked, (
            f"{rel}: cited by the RELEASE row and not TRACKED by git -- a "
            f"citation outside the tree verifies nothing"
        )


def test_the_release_row_has_no_provenance_problems():
    """The whole contract, in one assertion over the shared checker."""
    problems = provenance_problems(_release_row())
    assert not problems, (
        "the RELEASE row's provenance is not verifiable from the tree:\n  - "
        + "\n  - ".join(problems)
    )


def test_the_rows_lane_totals_match_the_gated_learnings_totals():
    """A number in the row is a claim -- and the GATED number is the truth.

    The row states the lane's test and mutation totals. Those totals are
    recomputed by the taxonomy gate from the LEARNINGS file, so the row's copy
    is checked against the gated one rather than trusted. A second copy of a
    number is a second thing that can rot.
    """
    row = _release_row()
    stated = ROW_TOTALS.search(row)
    assert stated, "the RELEASE row states no lane totals"
    gated = LEARNINGS_TOTAL.search(LEARNINGS.read_text(encoding="utf-8"))
    assert gated, "the LEARNINGS file states no lane total"
    assert (int(stated.group(1)), int(stated.group(2))) == (
        int(gated.group(1)),
        int(gated.group(2)),
    ), (
        f"the RELEASE row claims {stated.group(1)} behavioural test functions "
        f"and {stated.group(2)} mutation kills; the GATED LEARNINGS total is "
        f"{gated.group(1)} and {gated.group(2)}"
    )


def test_the_rows_lesson_taxonomy_matches_the_gated_learnings_taxonomy():
    """The row repeats the taxonomy's bucket counts. Check them too."""
    row = _release_row()
    stated = ROW_TAXONOMY.search(row)
    assert stated, (
        "the RELEASE row states no lesson taxonomy counts -- "
        f"expected the form '(reasoning-gap N, semantic-naming drift N, ...)'"
    )
    gated = {}
    for line in LEARNINGS.read_text(encoding="utf-8").splitlines():
        match = LEARNINGS_BUCKET.match(line)
        if match and match.group("cls") in {name for name, _ in CLASSES}:
            gated[match.group("cls")] = int(match.group("count"))
    assert gated, "the LEARNINGS file states no bucket summary"
    for name, group in CLASSES:
        assert name in gated, (
            f"the LEARNINGS file states no {name} bucket"
        )
        assert gated[name] == int(stated.group(group)), (
            f"the RELEASE row claims {stated.group(group)} {name} lessons; the "
            f"GATED LEARNINGS summary says {gated[name]}"
        )
