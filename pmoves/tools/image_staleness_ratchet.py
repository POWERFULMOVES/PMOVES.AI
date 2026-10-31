#!/usr/bin/env python3
"""Image-staleness ratchet gate.

Reads `pmoves/images.yaml` (the build matrix for
`.github/workflows/build-images.yml`) and enforces, per image:

  1. build_inputs  -- the matrix entry names the files the builder actually
     consumes, and those files are present in the tree. An entry whose
     dockerfile cannot be found cannot be rebuilt, so it is stale by
     construction.
  2. build_path    -- the workflow that builds the matrix has a trigger other
     than `workflow_dispatch`. A matrix whose only workflow is manual-only
     is a fleet that CANNOT stay fresh: flute-gateway sat 65 days stale
     because nothing rebuilt it automatically.
  3. matrix_fields -- the entry carries the fields the builder reads
     (`name`, `context`, `dockerfile`, `image`). A missing field makes the
     entry unbuildable regardless of what is on disk.

Verdicts per claim: VERIFIED / DRIFTED / UNDECIDED, mirroring
`scripts/runbook_drift.py` (fail-closed: a probe that cannot answer says
UNDECIDED, never VERIFIED). A submodule that is declared in `.gitmodules`
but not checked out in this working tree is UNDECIDED -- "I could not check"
and "it is broken" are different answers.

Zero network. Read-only against the repo tree. Standard library only (no
PyYAML): the matrix is parsed with a small, purpose-built reader for the
`images:` list, so the gate runs on any runner with a bare python.

Usage:
    python3 pmoves/tools/image_staleness_ratchet.py
    python3 pmoves/tools/image_staleness_ratchet.py --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGES_PATH = REPO_ROOT / "pmoves" / "images.yaml"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "build-images.yml"
GITMODULES_PATH = REPO_ROOT / ".gitmodules"

VERIFIED = "VERIFIED"
DRIFTED = "DRIFTED"
UNDECIDED = "UNDECIDED"

# The fields `.github/workflows/build-images.yml` actually consumes.
REQUIRED_FIELDS = ("name", "context", "dockerfile", "image")

# Triggers that rebuild the fleet without a human clicking. `workflow_dispatch`
# is explicitly NOT one of them -- a manual-only workflow is the 65-day bug.
NON_MANUAL_TRIGGERS = ("push", "schedule", "repository_dispatch")


# --------------------------------------------------------------------------
# matrix parsing (stdlib only -- no PyYAML)
# --------------------------------------------------------------------------
def _strip_inline_comment(raw: str) -> str:
    """Drop a trailing `# comment`, respecting quoted scalars."""
    out: list[str] = []
    quote: str | None = None
    for i, ch in enumerate(raw):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_images_matrix(text: str) -> list[dict]:
    """Parse the `images:` sequence out of pmoves/images.yaml.

    The file is a flat list of flat mappings of scalars; this reader handles
    exactly that shape (and refuses to guess at anything else).
    """
    images: list[dict] = []
    current: dict | None = None
    in_images = False

    for raw in text.splitlines():
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        stripped = line.strip()

        if indent == 0:
            in_images = stripped.split(":", 1)[0].strip() == "images"
            current = None
            continue
        if not in_images:
            continue

        if stripped.startswith("- "):
            current = {}
            images.append(current)
            body = stripped[2:].strip()
        elif stripped == "-":
            current = {}
            images.append(current)
            body = ""
        else:
            if current is None:
                continue
            body = stripped

        if ":" not in body:
            continue
        key, _, value = body.partition(":")
        current[key.strip()] = _scalar(value)

    return images


def parse_submodule_paths(text: str) -> set[str]:
    """Return the submodule paths declared in a .gitmodules file."""
    paths: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("path"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip() == "path":
            paths.add(value.strip())
    return paths


def parse_workflow_triggers(text: str) -> tuple[set[str], str | None]:
    """Return (trigger names, error) for a workflow's top-level `on:` block.

    Only the DIRECT children of `on:` are triggers. This matters: the
    `push: true` inside the build-push-action `with:` block is the buildx
    `--push` flag, not a workflow trigger, and reading the whole file for
    "push:" would report a manual-only workflow as automated.
    """
    lines = text.splitlines()
    start = None
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if len(raw) - len(raw.lstrip(" \t")) != 0:
            continue
        if stripped.split(":", 1)[0].strip() in ("on", '"on"', "'on'"):
            start = idx
            inline = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if inline:
                if inline.startswith("[") and inline.endswith("]"):
                    names = {
                        n.strip().strip("'\"")
                        for n in inline[1:-1].split(",")
                        if n.strip()
                    }
                    return names, None
                if inline.startswith("{") and inline.endswith("}"):
                    names = set()
                    depth = 0
                    key = ""
                    for ch in inline[1:-1]:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        if depth == 0 and ch == ":":
                            names.add(key.strip().strip("'\""))
                            key = ""
                        else:
                            key += ch
                    return names, None
                return set(), f"cannot parse inline `on: {inline}`"
            break
    if start is None:
        return set(), "no top-level `on:` block found in the workflow"

    block: list[tuple[int, str]] = []
    for raw in lines[start + 1 :]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" \t"))
        if indent == 0:
            break
        block.append((indent, stripped))

    if not block:
        return set(), "the `on:` block is empty"

    child_indent = min(indent for indent, _ in block)
    triggers = {
        stripped.split(":", 1)[0].strip()
        for indent, stripped in block
        if indent == child_indent
    }
    triggers.discard("")
    return triggers, None


# --------------------------------------------------------------------------
# probes
# --------------------------------------------------------------------------
class _Context:
    """Everything the probes read, resolved once."""

    def __init__(
        self,
        repo_root: Path,
        submodule_paths: set[str],
        triggers: set[str],
        trigger_error: str | None,
    ) -> None:
        self.repo_root = repo_root
        self.submodule_paths = submodule_paths
        self.triggers = triggers
        self.trigger_error = trigger_error


def _is_submodule(repo: str, submodule_paths: set[str]) -> bool:
    if repo in submodule_paths:
        return True
    folded = repo.casefold()
    return any(p.casefold() == folded for p in submodule_paths)


def _submodule_checked_out(path: Path) -> bool:
    """A checked-out submodule directory has content; an uninitialised one
    is present but empty."""
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def resolve_build_paths(image: dict, ctx: _Context) -> tuple[Path, Path, Path]:
    """Return (base_dir, context_dir, dockerfile_path) for a matrix entry.

    Mirrors `.github/workflows/build-images.yml`:
      context: ${{ matrix.context || format('{0}/{1}', github.workspace, matrix.repo) }}
      file:    ${{ matrix.dockerfile || format('{0}/{1}/Dockerfile', github.workspace, matrix.repo) }}

    so a `repo:`-backed entry builds inside that submodule, and an in-tree
    entry builds from the repo root (or `pmoves/`).
    """
    repo = str(image.get("repo", "") or "").strip()
    context_rel = str(image.get("context", "") or ".").strip() or "."
    dockerfile_rel = str(image.get("dockerfile", "") or "").strip()

    if repo:
        base = ctx.repo_root / repo
        context_dir = base if context_rel == "." else base / context_rel
    else:
        base = ctx.repo_root
        context_dir = base if context_rel == "." else base / context_rel

    dockerfile = context_dir / dockerfile_rel
    return base, context_dir, dockerfile


def probe_matrix_fields(image: dict, ctx: _Context) -> tuple[str, str]:
    """The entry carries every field the builder consumes."""
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not str(image.get(field, "") or "").strip()
    ]
    if missing:
        return DRIFTED, (
            f"entry is missing builder-required field(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_FIELDS)})"
        )
    return VERIFIED, (
        f"entry declares all builder-required fields: {', '.join(REQUIRED_FIELDS)}"
    )


def probe_build_inputs(image: dict, ctx: _Context) -> tuple[str, str]:
    """The build context and dockerfile the matrix names exist in the tree."""
    name = str(image.get("name", "<unnamed>"))
    repo = str(image.get("repo", "") or "").strip()
    dockerfile_rel = str(image.get("dockerfile", "") or "").strip()
    if not dockerfile_rel:
        return DRIFTED, "no `dockerfile` path to resolve"

    base, context_dir, dockerfile = resolve_build_paths(image, ctx)

    # The matrix resolves the dockerfile against the build context; the house
    # tool pmoves/tools/build_gate.py resolves a `repo:`-backed entry's
    # dockerfile against the submodule ROOT (e.g. tokenism-ui: context
    # `pmoves-nextjs`, dockerfile `pmoves-nextjs/Dockerfile`). Both readings
    # are tried for repo-backed entries and the evidence names the one that
    # matched. In-tree entries resolve against the build context only, so a
    # stray file at the repo root can never satisfy them.
    candidates = [dockerfile]
    if repo:
        alternate = base / dockerfile_rel
        if alternate != dockerfile:
            candidates.append(alternate)

    for candidate in candidates:
        if candidate.is_file():
            try:
                shown = candidate.relative_to(ctx.repo_root).as_posix()
            except ValueError:
                shown = candidate.as_posix()
            how = (
                "relative to the build context"
                if candidate == dockerfile
                else "relative to the build root"
            )
            return VERIFIED, f"build input present: {shown} ({how})"

    if repo:
        sub_path = ctx.repo_root / repo
        if _is_submodule(repo, ctx.submodule_paths) and not _submodule_checked_out(sub_path):
            return UNDECIDED, (
                f"submodule '{repo}' is declared in .gitmodules but not checked out "
                f"in this tree -- cannot resolve dockerfile '{dockerfile_rel}' "
                f"(not a broken image; init the submodule to decide it)"
            )

    tried = ", ".join(
        c.as_posix() for c in candidates
    )
    return DRIFTED, (
        f"build input missing for '{name}': tried {tried} "
        f"(context '{context_dir.as_posix()}')"
    )


def probe_build_path(image: dict, ctx: _Context) -> tuple[str, str]:
    """The image's builder has a trigger that does not need a human."""
    if ctx.trigger_error:
        return UNDECIDED, (
            f"cannot read the build workflow's triggers: {ctx.trigger_error}"
        )
    non_manual = sorted(t for t in ctx.triggers if t in NON_MANUAL_TRIGGERS)
    if non_manual:
        return VERIFIED, (
            f"build workflow declares non-manual trigger(s): {', '.join(non_manual)} "
            f"(all triggers: {', '.join(sorted(ctx.triggers))})"
        )
    all_triggers = ", ".join(sorted(ctx.triggers)) or "none"
    return DRIFTED, (
        f"build workflow triggers = {all_triggers} -- no push/schedule/"
        f"repository_dispatch, so the fleet only rebuilds when a human clicks"
    )


PROBES = {
    "matrix_fields": probe_matrix_fields,
    "build_inputs": probe_build_inputs,
    "build_path": probe_build_path,
}


def _worst(verdicts: list[str]) -> str:
    if DRIFTED in verdicts:
        return DRIFTED
    if UNDECIDED in verdicts:
        return UNDECIDED
    return VERIFIED


def audit(
    repo_root: Path,
    images_path: Path,
    workflow_path: Path,
    gitmodules_path: Path,
) -> dict:
    """Run every probe over every matrix entry and return the payload."""
    images = parse_images_matrix(images_path.read_text(encoding="utf-8"))
    triggers, trigger_error = parse_workflow_triggers(
        workflow_path.read_text(encoding="utf-8")
    )
    submodule_paths: set[str] = set()
    if gitmodules_path.is_file():
        submodule_paths = parse_submodule_paths(
            gitmodules_path.read_text(encoding="utf-8")
        )

    ctx = _Context(repo_root, submodule_paths, triggers, trigger_error)

    claims: list[dict] = []
    rows: list[dict] = []
    for image in images:
        name = str(image.get("name", "<unnamed>"))
        verdicts: list[str] = []
        for probe_name, probe in PROBES.items():
            verdict, evidence = probe(image, ctx)
            verdicts.append(verdict)
            claims.append(
                {
                    "image": name,
                    "probe": probe_name,
                    "verdict": verdict,
                    "evidence": evidence,
                }
            )
        rows.append({"name": name, "verdict": _worst(verdicts)})

    counts = {VERIFIED: 0, DRIFTED: 0, UNDECIDED: 0}
    for row in rows:
        counts[row["verdict"]] += 1

    problems = [
        f"{claim['image']}: {claim['probe']}: {claim['evidence']}"
        for claim in claims
        if claim["verdict"] == DRIFTED
    ]
    undecided = [
        {"image": claim["image"], "probe": claim["probe"], "evidence": claim["evidence"]}
        for claim in claims
        if claim["verdict"] == UNDECIDED
    ]

    return {
        "images_matrix": images_path.as_posix(),
        "workflow": workflow_path.as_posix(),
        "gitmodules": gitmodules_path.as_posix(),
        "repo_root": repo_root.as_posix(),
        "total": len(images),
        "counts": counts,
        "triggers": sorted(triggers),
        "problems": problems,
        "undecided": undecided,
        "claims": claims,
        "images": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        default=IMAGES_PATH,
        help=f"Path to the image build matrix (default: {IMAGES_PATH})",
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=WORKFLOW_PATH,
        help=f"Path to the image build workflow (default: {WORKFLOW_PATH})",
    )
    parser.add_argument(
        "--gitmodules",
        type=Path,
        default=GITMODULES_PATH,
        help=f"Path to .gitmodules for the submodule cross-check (default: {GITMODULES_PATH})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Root the matrix paths resolve against (default: {REPO_ROOT})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    args = parser.parse_args()

    for label, path in (
        ("image matrix", args.images),
        ("build workflow", args.workflow),
    ):
        if not path.is_file():
            print(f"{label} not found: {path}", file=sys.stderr)
            return 2

    payload = audit(
        args.repo_root, args.images, args.workflow, args.gitmodules
    )

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        counts = payload["counts"]
        print(
            f"image-staleness ratchet: {payload['total']} image(s) - "
            f"{counts[VERIFIED]} verified, {counts[DRIFTED]} drifted, "
            f"{counts[UNDECIDED]} undecided"
        )
        print(
            f"  build path: triggers = {', '.join(payload['triggers']) or 'none'}"
        )
        for row in payload["images"]:
            print(f"  {row['name']:<38} {row['verdict']}")
        if payload["problems"]:
            print(f"  {len(payload['problems'])} problem(s):")
            for problem in payload["problems"]:
                print(f"    - {problem}")
        else:
            print("  (every image declares its build fields, resolves its build")
            print("   inputs, and has a non-manual rebuild trigger)")
        if payload["undecided"]:
            print(f"  {len(payload['undecided'])} undecided (not failed):")
            for item in payload["undecided"]:
                print(f"    - {item['image']}: {item['evidence']}")

    # DRIFTED fails the gate. UNDECIDED does NOT: a submodule that is not
    # checked out here is an unanswered question, not a broken image, and a
    # CI runner without submodules must not go permanently red.
    return 1 if payload["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
