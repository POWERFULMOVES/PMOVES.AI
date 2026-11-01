# pmoves/tools/tests/test_image_staleness_ratchet.py
"""Tests for the image-staleness ratchet gate.

The ratchet is the fleet's "can these images stay fresh?" number. It must:
  1. PASS on the real pmoves/images.yaml + .github/workflows/build-images.yml
     (after the schedule: trigger landed).
  2. REPORT a manual-only workflow (the 65-day flute-gateway bug).
  3. REPORT a bogus dockerfile path.
  4. REPORT a matrix entry missing a field THIS RATCHET requires.
  5. Say UNDECIDED (NOT DRIFTED) for a submodule-backed entry whose
     submodule is not checked out here -- "I could not check" and "it is
     broken" are different answers, and the gate must not go red on a
     CI runner that has no submodules.
  6. NOT mistake the buildx `--push` flag (`push: true` under `with:`) for
     a workflow trigger.
  7. FAIL CLOSED on a matrix it cannot parse -- an empty matrix means zero
     claims, zero problems and a green hard gate that verifies nothing.
  8. FAIL when its OWN trigger probe gags. UNDECIDED is the answer for an
     uninitialised SUBMODULE; it is the wrong answer for the gate's own
     probe breaking, because the rebuild path is then UNMEASURED, not clean.
  9. REPORT a repo-backed entry whose `context` the build IGNORES -- dead
     build input is where a silently changed behaviour hides.
 10. FAIL on a baseline entry whose image is no longer in the matrix (an
     ORPHAN): the baseline may not outlive the matrix entry it describes.

Hermetic: no network, no docker, no gh, no registry API. Runs on Linux and
Windows (no POSIX-only path handling, no shell).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "image_staleness_ratchet.py"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run(
    images: Path,
    workflow: Path,
    gitmodules: Path,
    repo_root: Path,
    known_gaps: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the ratchet against a temp tree.

    The baseline is ALWAYS passed explicitly. Without this the tool falls
    back to the REPO's real `_known_gaps.yaml`, whose 8 names describe the
    real 30-image matrix -- so every temp-tree run would report 8 ORPHANED
    baseline entries and fail, for a reason that has nothing to do with the
    tree under test. An empty baseline is the honest default here.
    """
    if known_gaps is None:
        known_gaps = repo_root / "_known_gaps.yaml"
        known_gaps.write_text("known_gaps:\n", encoding="utf-8")
    args = [
        PYTHON,
        str(RATCHET),
        "--images", str(images),
        "--workflow", str(workflow),
        "--gitmodules", str(gitmodules),
        "--repo-root", str(repo_root),
        "--known-gaps", str(known_gaps),
        "--json",
    ]
    return subprocess.run(args, capture_output=True, text=True)


def _tree(
    tmp_path: Path,
    *,
    images_yaml: str,
    workflow_yaml: str,
    gitmodules: str = "",
    files: dict | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Materialise a mini repo tree and return (images, workflow, gitmodules, root)."""
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    images_path = root / "pmoves" / "images.yaml"
    images_path.parent.mkdir(parents=True, exist_ok=True)
    images_path.write_text(images_yaml, encoding="utf-8")
    workflow_path = root / ".github" / "workflows" / "build-images.yml"
    workflow_path.write_text(workflow_yaml, encoding="utf-8")
    gitmodules_path = root / ".gitmodules"
    gitmodules_path.write_text(gitmodules, encoding="utf-8")
    for rel, body in (files or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return images_path, workflow_path, gitmodules_path, root


GOOD_WORKFLOW = """\
name: build-images-matrix

on:
  workflow_dispatch:
  schedule:
    - cron: '23 4 * * *'

jobs:
  build:
    name: Image Build
    runs-on: [self-hosted, Linux, X64]
    steps:
      - uses: docker/build-push-action@v7
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: true
"""

MANUAL_ONLY_WORKFLOW = """\
name: build-images-matrix

on:
  workflow_dispatch:

jobs:
  build:
    name: Manual Image Build
    runs-on: [self-hosted, Linux, X64]
    steps:
      - uses: docker/build-push-action@v7
        with:
          push: true
"""

ONE_IMAGE = """\
images:
  - name: pmoves-flute-gateway
    context: pmoves
    dockerfile: services/flute-gateway/Dockerfile
    image: ghcr.io/powerfulmoves/pmoves-flute-gateway
"""

DOCKERFILE_BODY = "FROM scratch\n"

# A repo-backed entry that sets `context: .` -- the shape EVERY repo-backed
# entry in the real matrix has.
REPO_BACKED_IMAGE = """\
images:
  - name: pmoves-repo-backed
    repo: PMOVES-Foo
    context: .
    dockerfile: Dockerfile
    image: ghcr.io/powerfulmoves/pmoves-repo-backed
"""

GITMODULES_ONE = (
    '[submodule "PMOVES-Foo"]\n'
    "\tpath = PMOVES-Foo\n"
    "\turl = https://github.com/POWERFULMOVES/PMOVES-Foo.git\n"
)

KNOWN_GAPS_ONE = """\
known_gaps:
  pmoves-repo-backed: "the declared Dockerfile is absent at the pinned commit"
"""

# A workflow with NO readable `on:` block: the gate's own probe gags. This
# is NOT the same as a manual-only workflow -- the trigger is right there in
# the file, the probe simply cannot read it, so the rebuild path is
# UNMEASURED rather than clean.
UNREADABLE_TRIGGER_WORKFLOW = """\
name: build-images-matrix

jobs:
  build:
    name: Image Build
    runs-on: [self-hosted, Linux, X64]
    steps:
      - uses: docker/build-push-action@v7
        with:
          push: true
"""

# A repo-backed entry whose `context` the build IGNORES. The workflow
# resolves `${{ matrix.repo && format('{0}/{1}', github.workspace, matrix.repo)
# || matrix.context }}`, so for a repo-backed entry `context` is dead build
# input -- and this is the shape the lane's own `pmoves-tokenism-ui` entry
# has.
DEAD_CONTEXT_IMAGE = """\
images:
  - name: pmoves-tokenism-ui
    repo: PMOVES-ToKenism-Multi
    context: pmoves-nextjs
    dockerfile: pmoves-nextjs/Dockerfile
    image: ghcr.io/powerfulmoves/pmoves-tokenism-ui
"""

GITMODULES_TOKENISM = (
    '[submodule "PMOVES-ToKenism-Multi"]\n'
    "\tpath = PMOVES-ToKenism-Multi\n"
    "\turl = https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi.git\n"
)

# Matrix shapes this reader does not understand, and the phrase each one
# must be failed with. The reader REFUSES to guess: a shape it cannot parse
# used to yield an empty matrix, and an empty matrix made the gate green
# while verifying nothing.
UNPARSABLE_MATRICES = {
    "flow-style entry": (
        "images:\n"
        "  - {name: pmoves-flute-gateway, context: pmoves, "
        "dockerfile: services/flute-gateway/Dockerfile}\n",
        "flow-style",
    ),
    "renamed images key": (
        "matrix:\n"
        "  - name: pmoves-flute-gateway\n"
        "    dockerfile: services/flute-gateway/Dockerfile\n",
        "no top-level `images:` key",
    ),
    "re-indented images key": (
        "  images:\n"
        "    - name: pmoves-flute-gateway\n"
        "      dockerfile: services/flute-gateway/Dockerfile\n",
        "no top-level `images:` key",
    ),
    "entry with no colon": (
        "images:\n"
        "  - pmoves-flute-gateway\n",
        "no `key: value` field",
    ),
    "empty images list": (
        "images:\n",
        "empty",
    ),
    "nested block": (
        "images:\n"
        "  - name: pmoves-flute-gateway\n"
        "    build-args:\n"
        "      FOO: bar\n",
        "nested block",
    ),
}


def _claims(out: dict, image: str, probe: str) -> dict:
    for claim in out["claims"]:
        if claim["image"] == image and claim["probe"] == probe:
            return claim
    raise AssertionError(f"no claim for {image}/{probe}: {out['claims']}")


# --------------------------------------------------------------------------
# the real tree
# --------------------------------------------------------------------------
def test_real_matrix_and_workflow_pass():
    """The REAL pmoves/images.yaml + REAL build-images.yml pass the ratchet."""
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--json"], capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["total"] == 30, out["total"]
    assert out["counts"]["DRIFTED"] == 0, out["problems"]
    assert out["problems"] == []
    # Every image must have a non-manual rebuild path, or the fleet can
    # silently go stale again -- that is the whole point of the ratchet.
    for claim in out["claims"]:
        if claim["probe"] == "build_path":
            assert claim["verdict"] == "VERIFIED", claim
    # And every image must carry the fields the builder consumes.
    for claim in out["claims"]:
        if claim["probe"] == "matrix_fields":
            assert claim["verdict"] == "VERIFIED", claim


def test_real_workflow_has_a_non_manual_trigger():
    """The real build-images.yml declares `schedule:` -- the direct fix."""
    sys.path.insert(0, str(RATCHET.parent))
    try:
        import image_staleness_ratchet as ratchet
    finally:
        sys.path.pop(0)

    text = (
        REPO_ROOT / ".github" / "workflows" / "build-images.yml"
    ).read_text(encoding="utf-8")
    triggers, err = ratchet.parse_workflow_triggers(text)
    assert err is None, err
    assert "schedule" in triggers, triggers
    assert "workflow_dispatch" in triggers, triggers


def test_real_matrix_parses_to_thirty_images():
    sys.path.insert(0, str(RATCHET.parent))
    try:
        import image_staleness_ratchet as ratchet
    finally:
        sys.path.pop(0)

    text = (REPO_ROOT / "pmoves" / "images.yaml").read_text(encoding="utf-8")
    images = ratchet.parse_images_matrix(text)
    assert len(images) == 30, len(images)
    names = {i["name"] for i in images}
    assert "pmoves-flute-gateway" in names
    assert "pmoves-agent-zero" in names


# --------------------------------------------------------------------------
# NEGATIVE CONTROL: the ratchet must be able to fail
# --------------------------------------------------------------------------
def test_manual_only_workflow_is_drifted(tmp_path):
    """A workflow with only `workflow_dispatch:` cannot keep the fleet fresh."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=MANUAL_ONLY_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    assert out["triggers"] == ["workflow_dispatch"], out["triggers"]
    claim = _claims(out, "pmoves-flute-gateway", "build_path")
    assert claim["verdict"] == "DRIFTED", claim
    assert "workflow_dispatch" in claim["evidence"], claim
    assert any("build_path" in p for p in out["problems"]), out["problems"]


def test_bogus_dockerfile_path_is_drifted(tmp_path):
    """A dockerfile path that does not exist means the image cannot be rebuilt."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        # NOTE: no Dockerfile written -- the path is bogus on purpose.
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim
    assert "build input missing" in claim["evidence"], claim


def test_missing_required_field_is_drifted(tmp_path):
    """An entry without a field THIS RATCHET requires is DRIFTED.

    The ratchet requires `name` (the build tags the image from it) and
    `dockerfile` (the build opens it). It does NOT require `image`: the
    build never reads that field -- the tag comes from `${{ matrix.name }}`
    -- so requiring it would make law of a DEAD FIELD. The thing a dead
    `context` actually breaks has its own probe (`dead_context`).
    """
    bad = """\
images:
  - name: pmoves-flute-gateway
    context: pmoves
"""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=bad,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "matrix_fields")
    assert claim["verdict"] == "DRIFTED", claim
    assert "dockerfile" in claim["evidence"], claim


def test_the_dead_image_field_is_not_required(tmp_path):
    """An entry WITHOUT `image` is VERIFIED -- the build never reads it.

    The positive control for the policy above: the image tag comes from
    `${{ matrix.name }}`, so `image:` is dead build input. A ratchet that
    demanded it would red-light a perfectly buildable entry.
    """
    without_image = """\
images:
  - name: pmoves-flute-gateway
    context: pmoves
    dockerfile: services/flute-gateway/Dockerfile
"""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=without_image,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "matrix_fields")
    assert claim["verdict"] == "VERIFIED", claim
    assert "image" not in claim["evidence"], claim


# --------------------------------------------------------------------------
# UNDECIDED vs DRIFTED: the distinction the gate depends on
# --------------------------------------------------------------------------
SUBMODULE_IMAGE = """\
images:
  - name: pmoves-agent-zero
    repo: PMOVES-Agent-Zero
    ref: heads/PMOVES.AI-Edition-Hardened
    context: .
    dockerfile: DockerfileLocal
    image: ghcr.io/powerfulmoves/pmoves-agent-zero
"""

GITMODULES = """\
[submodule "PMOVES-Agent-Zero"]
\tpath = PMOVES-Agent-Zero
\turl = https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
"""


def test_uninitialised_submodule_is_undecided_not_drifted(tmp_path):
    """A submodule that is not checked out here is UNDECIDED, and the gate
    stays green -- a CI runner without submodules must not go permanently red."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES,
        # NOTE: PMOVES-Agent-Zero/ is deliberately absent (not checked out).
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "UNDECIDED", claim
    assert claim["verdict"] != "DRIFTED"
    assert "not checked out" in claim["evidence"], claim
    assert out["counts"]["DRIFTED"] == 0
    assert out["counts"]["UNDECIDED"] == 1
    assert out["problems"] == []


def test_checked_out_submodule_with_missing_dockerfile_is_drifted(tmp_path):
    """Same submodule, now checked out, and the dockerfile really is gone:
    THAT is DRIFTED. The UNDECIDED verdict above is not a blanket excuse."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES,
        # The submodule directory exists with content (checked out) but
        # holds no DockerfileLocal.
        files={"PMOVES-Agent-Zero/README.md": "submodule content\n"},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim
    assert out["counts"]["UNDECIDED"] == 0


def test_non_submodule_missing_path_is_drifted(tmp_path):
    """A `repo:` that is NOT a declared submodule is genuinely absent -> DRIFTED."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules="",  # PMOVES-Agent-Zero is not a declared submodule here
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim


# --------------------------------------------------------------------------
# trigger parsing
# --------------------------------------------------------------------------
def test_buildx_push_flag_is_not_a_workflow_trigger(tmp_path):
    """`push: true` under `with:` is the buildx --push flag, not a trigger."""
    workflow_only_push_flag = """\
name: build-images-matrix

on:
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: docker/build-push-action@v7
        with:
          push: true
"""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=workflow_only_push_flag,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    assert "push" not in out["triggers"], out["triggers"]
    claim = _claims(out, "pmoves-flute-gateway", "build_path")
    assert claim["verdict"] == "DRIFTED", claim


def test_good_tree_is_all_verified(tmp_path):
    """Positive control: a correct tree verifies every claim."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["total"] == 1
    assert out["counts"] == {
        "VERIFIED": 1,
        "DRIFTED": 0,
        "UNDECIDED": 0,
        "KNOWN-GAP": 0,
    }
    for claim in out["claims"]:
        assert claim["verdict"] == "VERIFIED", claim
        assert claim["evidence"], claim


def test_a_repo_backed_entry_resolves_inside_its_submodule(tmp_path):
    """A `repo:`-backed entry builds inside that submodule.

    The workflow resolves `context` to `github.workspace/matrix.repo` when
    `repo:` is set, and `file` relative to that context. The ratchet must
    mirror that exactly, or it verifies a file the build never opens.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES_ONE,
        files={"PMOVES-Foo/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-repo-backed", "build_inputs")
    assert claim["verdict"] == "VERIFIED", claim
    assert "PMOVES-Foo/Dockerfile" in claim["evidence"], claim


def test_a_repo_backed_entry_does_not_accept_a_workspace_root_dockerfile(tmp_path):
    """A Dockerfile at the WORKSPACE ROOT must not satisfy a repo-backed entry.

    This is the defect the ratchet shipped with: it resolved a repo-backed
    entry against the submodule while the WORKFLOW resolved it against the
    workspace root, so the two disagreed about which file the build opens.
    The ratchet accepted EITHER reading, which meant it could VERIFY a file
    the build would never read -- and would not have noticed that the file
    the build DOES ask for is missing.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        # The Dockerfile sits at the WORKSPACE ROOT -- not inside PMOVES-Foo.
        files={"Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-repo-backed", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim
    assert r.returncode == 1, r.stdout + r.stderr


def test_a_baselined_gap_is_reported_and_does_not_fail_the_gate(tmp_path):
    """A KNOWN gap is reported on every run and does not fail the gate.

    It is not DRIFTED (the fleet has accepted and recorded it) and it is not
    VERIFIED (the image still cannot be rebuilt). It stays VISIBLE, so it
    cannot be forgotten.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={},
    )
    gaps = tmp_path / "gaps.yaml"
    gaps.write_text(KNOWN_GAPS_ONE, encoding="utf-8")
    r = _run(images, workflow, gitmodules, root, known_gaps=gaps)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-repo-backed", "build_inputs")
    assert claim["verdict"] == "KNOWN-GAP", claim
    assert "absent at the pinned commit" in claim["evidence"], claim
    assert out["counts"]["KNOWN-GAP"] == 1, out["counts"]
    assert out["problems"] == []
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_fixed_gap_is_stale_and_fails_the_gate(tmp_path):
    """A baselined gap that is FIXED fails until it is dropped from the file.

    Otherwise the baseline keeps saying "this is broken" about an image that
    now builds, and the next person to break it gets no warning -- the same
    contract as `validate_command_anchors.py`'s stale-baseline check.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES_ONE,
        files={"PMOVES-Foo/Dockerfile": DOCKERFILE_BODY},
    )
    gaps = tmp_path / "gaps.yaml"
    gaps.write_text(KNOWN_GAPS_ONE, encoding="utf-8")
    r = _run(images, workflow, gitmodules, root, known_gaps=gaps)
    out = json.loads(r.stdout)
    assert out["stale_gaps"] == ["pmoves-repo-backed"], out["stale_gaps"]
    assert r.returncode == 1, r.stdout + r.stderr


def test_a_new_gap_fails_the_gate(tmp_path):
    """A gap that is NOT in the baseline fails immediately."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={},
    )
    gaps = tmp_path / "gaps.yaml"
    gaps.write_text("known_gaps:\n", encoding="utf-8")
    r = _run(images, workflow, gitmodules, root, known_gaps=gaps)
    out = json.loads(r.stdout)
    assert out["problems"], out
    assert r.returncode == 1, r.stdout + r.stderr


def test_missing_matrix_file_returns_2():
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--images", "/nonexistent/images.yaml"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


# --------------------------------------------------------------------------
# FAIL CLOSED: the gate must not be green because it read nothing
# --------------------------------------------------------------------------
@pytest.mark.parametrize("shape", sorted(UNPARSABLE_MATRICES))
def test_an_unparsable_matrix_fails_closed(tmp_path, shape):
    """A matrix the reader cannot understand must NOT be a green gate.

    The reader refuses to guess, and refusing means FAILING. A shape it
    cannot parse used to yield an empty list, and an empty list meant zero
    claims, zero problems and exit 0 -- a green hard gate that verified
    nothing, on exactly the tree it exists to police.
    """
    matrix_text, expected_phrase = UNPARSABLE_MATRICES[shape]
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=matrix_text,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode != 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    assert payload["total"] == 0, payload
    assert payload["claims"] == [], payload
    assert payload["problems"], payload
    assert expected_phrase in payload["error"], payload["error"]
    # The failure names the shape mismatch on stderr too, so the human sees
    # it in the CI log and not only in the JSON payload.
    assert expected_phrase in r.stderr, r.stderr


def test_a_gagged_trigger_probe_fails_the_gate(tmp_path):
    """The gate's OWN probe breaking must fail the gate.

    UNDECIDED is the house answer for an uninitialised SUBMODULE -- "I
    could not check". It is the WRONG answer for the gate's own trigger
    probe gagging: the trigger is in the workflow file, and the check whose
    origin story is "the trigger silently disappeared and nobody noticed"
    must not go green because the probe broke.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=UNREADABLE_TRIGGER_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout + r.stderr
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "build_path")
    assert claim["verdict"] == "INSTRUMENT-ERROR", claim
    assert out["errors"], out
    assert out["errors"][0]["probe"] == "build_path", out["errors"]
    # It is its OWN class, not DRIFTED: nothing is proven broken.
    assert claim["verdict"] != "DRIFTED", claim
    assert out["problems"] == [], out["problems"]


# --------------------------------------------------------------------------
# dead build input: a `context` the build IGNORES
# --------------------------------------------------------------------------
def test_a_repo_backed_entry_with_a_dead_context_is_drifted(tmp_path):
    """A repo-backed entry that declares a `context` the build ignores.

    The workflow resolves
    `${{ matrix.repo && format('{0}/{1}', github.workspace, matrix.repo) || matrix.context }}`,
    so `context` is DEAD for a repo-backed entry. A non-`.` value there is
    dead build input hiding in plain sight -- and it is exactly where a
    silently changed behaviour hides.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=DEAD_CONTEXT_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES_TOKENISM,
        # The repo IS present here, so the mismatch is measurable.
        files={
            "PMOVES-ToKenism-Multi/pmoves-nextjs/Dockerfile": DOCKERFILE_BODY,
        },
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-tokenism-ui", "dead_context")
    assert claim["verdict"] == "DRIFTED", claim
    # The evidence names WHICH entry and WHICH ignored context.
    assert "pmoves-tokenism-ui" in claim["evidence"], claim
    assert "pmoves-nextjs" in claim["evidence"], claim
    assert r.returncode == 1, r.stdout + r.stderr
    assert any("dead_context" in p for p in out["problems"]), out["problems"]


def test_a_dead_context_is_undecided_when_the_repo_cannot_be_measured(tmp_path):
    """Where the repo is not checked out, the dead context is UNDECIDED.

    The tool cannot look inside a repo that is not there, so it says "could
    not check" -- it never claims VERIFIED for a mismatch it cannot see,
    and it never claims DRIFTED on a tree that simply has no submodules.
    The dead context is still REPORTED, so it does not hide.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=DEAD_CONTEXT_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES_TOKENISM,
        # NOTE: PMOVES-ToKenism-Multi/ is deliberately absent.
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-tokenism-ui", "dead_context")
    assert claim["verdict"] == "UNDECIDED", claim
    assert "pmoves-nextjs" in claim["evidence"], claim
    assert out["problems"] == [], out["problems"]


def test_a_repo_backed_entry_with_a_dot_context_is_verified(tmp_path):
    """Positive control: `context: .` is what the build resolves."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES_ONE,
        files={"PMOVES-Foo/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-repo-backed", "dead_context")
    assert claim["verdict"] == "VERIFIED", claim
    assert r.returncode == 0, r.stdout + r.stderr


def test_an_in_tree_entry_honours_its_declared_context(tmp_path):
    """Positive control: an entry with no `repo:` resolves its own context."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "dead_context")
    assert claim["verdict"] == "VERIFIED", claim


# --------------------------------------------------------------------------
# the baseline may not outlive the matrix
# --------------------------------------------------------------------------
def test_an_orphaned_baseline_entry_fails_the_gate(tmp_path):
    """A baseline name with NO matrix entry at all is ORPHANED -- and fails.

    The stale check is one-directional: it catches a gap that got FIXED. A
    baseline entry whose image was REMOVED or RENAMED produces no claims
    at all -- not DRIFTED, not VERIFIED, not even UNDECIDED, ABSENT -- so it
    matches nothing, fails nothing and haunts the baseline forever.
    """
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    gaps = tmp_path / "gaps.yaml"
    gaps.write_text(
        "known_gaps:\n"
        '  pmoves-removed-from-the-matrix: "the declared Dockerfile is absent"\n',
        encoding="utf-8",
    )
    r = _run(images, workflow, gitmodules, root, known_gaps=gaps)
    out = json.loads(r.stdout)
    assert out["orphan_gaps"] == ["pmoves-removed-from-the-matrix"], out
    assert r.returncode == 1, r.stdout + r.stderr


def test_a_baseline_entry_that_is_still_in_the_matrix_is_not_orphaned(tmp_path):
    """Positive control: a live baseline entry is not an orphan."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=REPO_BACKED_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules="",  # not a declared submodule -> the build input is absent
        files={},
    )
    gaps = tmp_path / "gaps.yaml"
    gaps.write_text(KNOWN_GAPS_ONE, encoding="utf-8")
    r = _run(images, workflow, gitmodules, root, known_gaps=gaps)
    out = json.loads(r.stdout)
    assert out["orphan_gaps"] == [], out["orphan_gaps"]
    assert out["known_gaps"], out["known_gaps"]
    assert r.returncode == 0, r.stdout + r.stderr


# --------------------------------------------------------------------------
# zero-network guarantee
# --------------------------------------------------------------------------
def test_tool_imports_no_network_modules():
    """The ratchet must stay zero-network: no urllib/requests/socket/http."""
    source = RATCHET.read_text(encoding="utf-8")
    for banned in ("import urllib", "import requests", "import socket",
                   "import http", "from urllib", "from requests"):
        assert banned not in source, f"{banned} found in the ratchet"


def test_tool_uses_stdlib_only():
    """No third-party imports (PyYAML especially) -- the gate runs anywhere."""
    source = RATCHET.read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "from yaml" not in source


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
