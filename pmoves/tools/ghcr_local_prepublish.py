#!/usr/bin/env python3
"""Local-first GHCR prepublish validator for integrations matrix.

Builds (and optionally Trivy scans) integration images from
`.github/workflows/integrations-ghcr.matrix.json` before dispatching
remote self-hosted GHCR workflows.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass


LOCAL_REPO_URL = "https://github.com/POWERFULMOVES/PMOVES.AI.git"


@dataclass
class ValidationResult:
    name: str
    tag: str
    build_ok: bool
    trivy_ok: bool | None
    note: str = ""

    @property
    def ok(self) -> bool:
        if not self.build_ok:
            return False
        if self.trivy_ok is None:
            return True
        return self.trivy_ok


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> int:
    print(f"$ {shlex.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    return proc.returncode


def ensure_builder(builder: str) -> None:
    if run(["docker", "buildx", "inspect", builder]) != 0:
        rc = run(["docker", "buildx", "create", "--name", builder, "--use"])
        if rc != 0:
            raise RuntimeError(f"failed to create buildx builder '{builder}'")
    if run(["docker", "buildx", "use", builder]) != 0:
        raise RuntimeError(f"failed to select buildx builder '{builder}'")
    if run(["docker", "buildx", "inspect", "--bootstrap"]) != 0:
        raise RuntimeError("failed to bootstrap buildx builder")


def with_github_token(url: str) -> str:
    from urllib.parse import urlparse
    token = (
        os.getenv("CI_GIT_CLONE_TOKEN")
        or os.getenv("GH_PAT_PUBLISH")
        or os.getenv("GHCR_TOKEN")
    )
    parsed = urlparse(url)
    if not token or parsed.scheme != "https" or parsed.hostname != "github.com":
        return url
    # Reconstruct with token authentication
    return f"https://x-access-token:{token}@github.com{parsed.path}"


def clone_repo(url: str, ref: str, checkout_dir: pathlib.Path) -> pathlib.Path:
    checkout_dir.mkdir(parents=True, exist_ok=True)
    auth_url = with_github_token(url)
    rc = run(
        [
            "git",
            "clone",
            "--depth=1",
            "--branch",
            ref,
            auth_url,
            str(checkout_dir),
        ]
    )
    if rc != 0:
        raise RuntimeError(f"clone failed for {url}@{ref}")
    return checkout_dir


def sanitize_tag_suffix(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in text)
    cleaned = cleaned.strip("-._")
    return cleaned or "local-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-file",
        type=pathlib.Path,
        default=pathlib.Path("../.github/workflows/integrations-ghcr.matrix.json"),
        help="Path to integrations-ghcr.matrix.json",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=pathlib.Path(".."),
        help="Path to PMOVES.AI repo root (contains .github/ and pmoves/)",
    )
    parser.add_argument(
        "--integration",
        action="append",
        default=[],
        help="Integration name to validate (repeatable). Defaults to all selected scope entries.",
    )
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="Include entries not sourced from PMOVES.AI repo (requires git clone access).",
    )
    parser.add_argument(
        "--skip-trivy",
        action="store_true",
        help="Skip Trivy gate and run build-only validation.",
    )
    parser.add_argument(
        "--trivy-image",
        default="aquasec/trivy:0.57.1",
        help="Trivy container image to use.",
    )
    parser.add_argument(
        "--trivy-timeout",
        default="10m",
        help="Trivy scan timeout passed to --timeout (default: 10m).",
    )
    parser.add_argument(
        "--platform",
        default="linux/amd64",
        help="Buildx platform for local validation.",
    )
    parser.add_argument(
        "--builder",
        default="pmoves-multiarch",
        help="Docker buildx builder name.",
    )
    parser.add_argument(
        "--tag-suffix",
        default="local-smoke",
        help="Docker tag suffix for local images.",
    )
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help=(
            "Validate that matrix context/dockerfile paths exist without building images. "
            "Initializes submodules under pmoves/integrations/ shallowly as needed. "
            "Exits 1 if any path is missing."
        ),
    )
    return parser.parse_args()


def load_matrix(path: pathlib.Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("matrix file must contain a JSON array")
    return payload


def resolve_entries(
    entries: list[dict[str, object]],
    include_external: bool,
    selected_names: list[str],
) -> list[dict[str, object]]:
    filtered = entries
    if not include_external:
        filtered = [entry for entry in filtered if str(entry.get("git_url", "")) == LOCAL_REPO_URL]

    if selected_names:
        wanted = set(selected_names)
        name_to_entry = {str(entry.get("name", "")): entry for entry in filtered}
        missing = sorted(name for name in wanted if name not in name_to_entry)
        if missing:
            raise ValueError(
                f"requested integrations not available in selected scope: {', '.join(missing)}"
            )
        return [name_to_entry[name] for name in selected_names]

    return filtered


def _init_submodule(repo_root: pathlib.Path, submodule_rel: str) -> None:
    target = repo_root / submodule_rel
    if target.is_dir() and any(target.iterdir()):
        return
    print(f"==> Initializing submodule: {submodule_rel}")
    subprocess.run(
        ["git", "submodule", "update", "--init", "--depth=1", submodule_rel],
        cwd=str(repo_root),
        check=False,
    )


def _declared_submodule_paths(repo_root: pathlib.Path) -> list[str]:
    """Submodule paths declared in .gitmodules, longest first.

    Read from the file rather than `git config` so this works on a plain
    directory copy with no git metadata.
    """
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.is_file():
        return []
    paths = [
        line.split("=", 1)[1].strip()
        for line in gitmodules.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("path")
    ]
    return sorted(paths, key=len, reverse=True)


def _submodule_owning(repo_root: pathlib.Path, context_rel: str) -> str | None:
    """The submodule that IS, or contains, this build context.

    Previously this was a hardcoded `pmoves/integrations/*` prefix test, so a
    repo-root submodule context (PMOVES.YT) was never initialized and its paths
    read as missing.
    """
    context_rel = context_rel.strip("/")
    if not context_rel or context_rel == ".":
        return None
    for candidate in _declared_submodule_paths(repo_root):
        if context_rel == candidate or context_rel.startswith(f"{candidate}/"):
            return candidate
    return None


def check_paths(entry: dict[str, object], repo_root: pathlib.Path) -> ValidationResult:
    name = str(entry.get("name", ""))
    image_name = str(entry.get("image_name", ""))
    context_rel = str(entry.get("context", ""))
    dockerfile_rel = str(entry.get("dockerfile", ""))
    tag = f"local/{image_name}:paths-check"

    context_rel_path = pathlib.Path(context_rel)
    dockerfile_rel_path = pathlib.Path(dockerfile_rel)
    if context_rel_path.is_absolute() or dockerfile_rel_path.is_absolute():
        print(f"[FAIL] {name}: paths must be repo-relative, not absolute")
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note="paths must be repo-relative")

    repo_root_resolved = repo_root.resolve()
    owning_submodule = _submodule_owning(repo_root, context_rel)
    if owning_submodule:
        _init_submodule(repo_root, owning_submodule)

    context_path = (repo_root / context_rel_path).resolve()
    dockerfile_path = (repo_root / dockerfile_rel_path).resolve()

    if not context_path.is_relative_to(repo_root_resolved) or not dockerfile_path.is_relative_to(repo_root_resolved):
        print(f"[FAIL] {name}: path escapes repo root")
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note="path escapes repo root")

    if not context_path.exists():
        print(f"[FAIL] {name}: context path missing: {context_rel}")
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note=f"missing context: {context_rel}")
    if not dockerfile_path.exists():
        print(f"[FAIL] {name}: dockerfile missing: {dockerfile_rel}")
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note=f"missing dockerfile: {dockerfile_rel}")

    print(f"[PASS] {name}: {dockerfile_rel}")
    return ValidationResult(name=name, tag=tag, build_ok=True, trivy_ok=None, note="paths-only")


def build_and_scan(
    entry: dict[str, object],
    source_root: pathlib.Path,
    args: argparse.Namespace,
) -> ValidationResult:
    name = str(entry.get("name", ""))
    image_name = str(entry.get("image_name", ""))
    context_rel = str(entry.get("context", ""))
    dockerfile_rel = str(entry.get("dockerfile", ""))
    trivy_ignore_rel = str(entry.get("trivy_ignorefile", "") or "")
    tag_suffix = sanitize_tag_suffix(args.tag_suffix)
    tag = f"local/{image_name}:{tag_suffix}"

    context_path = (source_root / context_rel).resolve()
    dockerfile_path = (source_root / dockerfile_rel).resolve()

    if not context_path.exists():
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note="missing context")
    if not dockerfile_path.exists():
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note="missing dockerfile")

    print(f"\n==> [{name}] build ({dockerfile_rel})")
    build_cmd = [
        "docker",
        "buildx",
        "build",
        "--platform",
        args.platform,
        "-f",
        str(dockerfile_path),
        "-t",
        tag,
        str(context_path),
        "--load",
    ]
    build_ok = run(build_cmd) == 0
    if not build_ok:
        return ValidationResult(name=name, tag=tag, build_ok=False, trivy_ok=None, note="build failed")

    if args.skip_trivy:
        return ValidationResult(name=name, tag=tag, build_ok=True, trivy_ok=None, note="trivy skipped")

    print(f"==> [{name}] trivy (HIGH,CRITICAL + ignore-unfixed)")
    trivy_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
    ]

    ignorefile_args: list[str] = []
    if trivy_ignore_rel:
        ignorefile_path = (source_root / trivy_ignore_rel).resolve()
        if ignorefile_path.exists():
            trivy_cmd.extend(["-v", f"{ignorefile_path}:/tmp/trivyignore:ro"])
            ignorefile_args = ["--ignorefile", "/tmp/trivyignore"]
        else:
            print(f"[warn] {name}: trivy ignorefile not found at {ignorefile_path}")

    trivy_cmd.extend(
        [
            args.trivy_image,
            "image",
            "--timeout",
            args.trivy_timeout,
            "--no-progress",
            "--vuln-type",
            "os,library",
            "--scanners",
            "vuln",
            "--severity",
            "HIGH,CRITICAL",
            "--ignore-unfixed",
            "--format",
            "table",
            "--exit-code",
            "1",
        ]
    )
    trivy_cmd.extend(ignorefile_args)
    trivy_cmd.append(tag)

    trivy_ok = run(trivy_cmd) == 0
    return ValidationResult(
        name=name,
        tag=tag,
        build_ok=True,
        trivy_ok=trivy_ok,
        note="" if trivy_ok else "trivy gate failed",
    )


def print_summary(results: list[ValidationResult]) -> None:
    print("\n=== GHCR Local Prepublish Summary ===")
    print("name\tbuild\ttrivy\tstatus\tnote")
    for item in results:
        build = "PASS" if item.build_ok else "FAIL"
        if item.trivy_ok is None:
            trivy = "SKIP"
        else:
            trivy = "PASS" if item.trivy_ok else "FAIL"
        status = "PASS" if item.ok else "FAIL"
        note = item.note or "-"
        print(f"{item.name}\t{build}\t{trivy}\t{status}\t{note}")


def main() -> int:
    args = parse_args()
    matrix_file = args.matrix_file.resolve()
    repo_root = args.repo_root.resolve()

    if not matrix_file.exists():
        print(f"error: matrix file not found: {matrix_file}", file=sys.stderr)
        return 2
    if not repo_root.exists():
        print(f"error: repo root not found: {repo_root}", file=sys.stderr)
        return 2

    try:
        entries = load_matrix(matrix_file)
        selected = resolve_entries(entries, args.include_external, args.integration)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not selected:
        scope = "all" if args.include_external else "in-repo"
        print(f"error: no integrations selected for {scope} scope", file=sys.stderr)
        return 2

    print(
        f"Selected {len(selected)} integration(s): "
        + ", ".join(str(entry.get("name", "?")) for entry in selected)
    )

    if args.paths_only:
        results = [check_paths(entry, repo_root) for entry in selected]
        print_summary(results)
        failed = [item for item in results if not item.ok]
        if failed:
            print(f"\nFAIL: {len(failed)} integration(s) have missing paths.", file=sys.stderr)
            return 1
        print(f"\nPASS: all {len(results)} integration path(s) verified.")
        return 0

    try:
        ensure_builder(args.builder)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    clone_cache: dict[tuple[str, str], pathlib.Path] = {}
    results: list[ValidationResult] = []

    with tempfile.TemporaryDirectory(prefix="ghcr-local-prepublish-") as temp_dir:
        tmp_root = pathlib.Path(temp_dir)
        for entry in selected:
            name = str(entry.get("name", ""))
            git_url = str(entry.get("git_url", ""))
            git_ref = str(entry.get("ref", ""))

            if git_url == LOCAL_REPO_URL:
                source_root = repo_root
                # The build context may live in a submodule that this checkout
                # has only as a gitlink (e.g. pmoves-yt builds from PMOVES.YT).
                owning = _submodule_owning(repo_root, str(entry.get("context", "")))
                if owning:
                    _init_submodule(repo_root, owning)
            else:
                key = (git_url, git_ref)
                source_root = clone_cache.get(key)
                if source_root is None:
                    checkout_dir = tmp_root / f"repo-{len(clone_cache) + 1}-{name}"
                    try:
                        source_root = clone_repo(git_url, git_ref, checkout_dir)
                    except RuntimeError as exc:
                        print(f"[error] {name}: {exc}")
                        results.append(
                            ValidationResult(
                                name=name,
                                tag=f"local/{entry.get('image_name', name)}:{sanitize_tag_suffix(args.tag_suffix)}",
                                build_ok=False,
                                trivy_ok=None,
                                note="clone failed",
                            )
                        )
                        continue
                    clone_cache[key] = source_root

            result = build_and_scan(entry, source_root, args)
            results.append(result)

    print_summary(results)

    failed = [item for item in results if not item.ok]
    if failed:
        print(f"\nFAIL: {len(failed)} integration(s) did not pass local prepublish validation.")
        return 1

    print("\nPASS: all selected integrations passed local prepublish validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
