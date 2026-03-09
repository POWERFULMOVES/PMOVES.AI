#!/usr/bin/env python3
"""Local build validation gate for CI runner images.

Reads images.yaml (and optionally integrations-ghcr.matrix.json), resolves
build contexts against the local repo tree, and runs single-arch
`docker build` as a validation gate before dispatching to CI runners.

Phase 2 adds pre-build validation: Dockerfile audit (--audit), BuildKit
--check (--check), and CI matrix field validation (--validate-ci).

Usage:
    python tools/build_gate.py --dry-run             # show resolved contexts
    python tools/build_gate.py --service agent-zero   # validate one service
    python tools/build_gate.py --all                  # validate all images.yaml
    python tools/build_gate.py --ci-matrix            # validate CI matrix only
    python tools/build_gate.py --ci-matrix --lint     # also run hadolint
    python tools/build_gate.py --ci-matrix --audit    # hardening compliance audit
    python tools/build_gate.py --ci-matrix --check    # BuildKit --check validation
    python tools/build_gate.py --ci-matrix --validate-ci  # CI field references
    python tools/build_gate.py --ci-matrix --audit --check --lint  # full pre-dispatch
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------------

def find_repo_root() -> Path:
    """Walk up from this script to find the repo root (contains .git)."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".git").exists():
            return parent
    sys.exit("ERROR: could not locate repo root (.git not found)")


REPO_ROOT = find_repo_root()
PMOVES_DIR = REPO_ROOT / "pmoves"
IMAGES_YAML = PMOVES_DIR / "images.yaml"
CI_MATRIX_JSON = REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.matrix.json"


# ---------------------------------------------------------------------------
# Lightweight YAML parser for images.yaml
# ---------------------------------------------------------------------------

def parse_images_yaml(path: Path) -> list[dict[str, str]]:
    """Parse images.yaml without PyYAML — handles the flat list-of-dicts format."""
    text = path.read_text(encoding="utf-8")
    images: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "images:":
            continue
        # New list item
        if stripped.startswith("- "):
            if current:
                images.append(current)
            current = {}
            stripped = stripped[2:].strip()
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            current[key.strip()] = val.strip()
    if current:
        images.append(current)
    return images


def parse_ci_matrix(path: Path) -> list[dict[str, Any]]:
    """Parse integrations-ghcr.matrix.json."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Build context resolution
# ---------------------------------------------------------------------------

class BuildTarget:
    """Resolved build target with local paths."""

    def __init__(self, name: str, dockerfile: Path, context: Path,
                 source: str, gpu: bool = False):
        self.name = name
        self.dockerfile = dockerfile
        self.context = context
        self.source = source  # "images.yaml" or "ci-matrix"
        self.gpu = gpu

    def __repr__(self) -> str:
        return f"BuildTarget({self.name}, df={self.dockerfile}, ctx={self.context})"


GPU_NAMES = {"pmoves-ultimate-tts-studio", "ultimate-tts-studio"}


def resolve_from_images_yaml(images: list[dict[str, str]]) -> list[BuildTarget]:
    """Resolve images.yaml entries to local build targets."""
    targets: list[BuildTarget] = []
    for img in images:
        name = img.get("name", "")
        repo = img.get("repo", "")
        context_rel = img.get("context", ".")
        dockerfile_rel = img.get("dockerfile", "Dockerfile")
        is_gpu = name in GPU_NAMES

        if repo:
            # Submodule-backed: context is relative to submodule root
            sub_root = REPO_ROOT / repo
            if context_rel == ".":
                context = sub_root
            else:
                context = sub_root / context_rel
            dockerfile = sub_root / dockerfile_rel
        else:
            # In-tree: context is relative to repo root
            if context_rel == "pmoves":
                context = PMOVES_DIR
            else:
                context = REPO_ROOT / context_rel
            dockerfile = context / dockerfile_rel

        targets.append(BuildTarget(
            name=name,
            dockerfile=dockerfile,
            context=context,
            source="images.yaml",
            gpu=is_gpu,
        ))
    return targets


def resolve_from_ci_matrix(matrix: list[dict[str, Any]]) -> list[BuildTarget]:
    """Resolve CI matrix entries to local build targets.

    The CI matrix uses git_url + context paths that assume a fresh clone.
    For local validation, we map these back to the local repo tree:
    - PMOVES.AI.git entries → paths relative to repo root
    - Submodule entries → local submodule checkouts
    """
    targets: list[BuildTarget] = []
    for entry in matrix:
        name = entry.get("name", "")
        image_name = entry.get("image_name", name)
        git_url = entry.get("git_url", "")
        context_rel = entry.get("context", ".")
        dockerfile_rel = entry.get("dockerfile", "Dockerfile")
        is_gpu = image_name in GPU_NAMES or name in GPU_NAMES

        if "PMOVES.AI.git" in git_url:
            # In-tree: paths are relative to repo root
            context = REPO_ROOT / context_rel
            dockerfile = REPO_ROOT / dockerfile_rel
        else:
            # Submodule: extract repo name from git URL
            repo_name = git_url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
            sub_root = REPO_ROOT / repo_name
            if context_rel == ".":
                context = sub_root
            else:
                context = sub_root / context_rel
                # dockerfile is always relative to sub_root regardless of context
            dockerfile = sub_root / dockerfile_rel

        targets.append(BuildTarget(
            name=image_name or name,
            dockerfile=dockerfile,
            context=context,
            source="ci-matrix",
            gpu=is_gpu,
        ))
    return targets


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def check_docker() -> bool:
    """Verify Docker daemon is accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_submodule_status(path: Path) -> str | None:
    """Return a warning string if submodule is dirty or missing, else None."""
    if not path.exists():
        return f"NOT CHECKED OUT at {path}"
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=path, timeout=10,
        )
        if result.stdout.strip():
            return f"DIRTY ({len(result.stdout.strip().splitlines())} changed files)"
    except Exception:
        pass
    return None


def run_hadolint(dockerfile: Path) -> tuple[bool, str]:
    """Run hadolint on a Dockerfile. Returns (passed, output)."""
    try:
        result = subprocess.run(
            ["hadolint", str(dockerfile)],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return True, "(hadolint not installed — skipped)"
    except subprocess.TimeoutExpired:
        return False, "(hadolint timed out)"


def run_docker_build(target: BuildTarget, *, use_buildx: bool = False) -> tuple[bool, str]:
    """Run a local single-arch docker build (no push).

    When use_buildx=True, uses `docker buildx build` instead of legacy
    `docker build`. Falls back to legacy with a warning if buildx is
    unavailable.
    """
    if use_buildx:
        bx_ok, _ = detect_buildx()
        if not bx_ok:
            print("  WARN  buildx not available, falling back to legacy docker build")
            use_buildx = False

    if use_buildx:
        cmd = [
            "docker", "buildx", "build",
            "--load",
            "-f", str(target.dockerfile),
            "-t", f"build-gate/{target.name}:local-test",
            str(target.context),
        ]
    else:
        cmd = [
            "docker", "build",
            "-f", str(target.dockerfile),
            "-t", f"build-gate/{target.name}:local-test",
            str(target.context),
        ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            return True, "BUILD OK"
        # Trim output to last 40 lines for readability
        stderr_lines = result.stderr.strip().splitlines()
        tail = "\n".join(stderr_lines[-40:])
        return False, f"BUILD FAILED (exit {result.returncode}):\n{tail}"
    except subprocess.TimeoutExpired:
        return False, "BUILD TIMEOUT (>10 min)"


# ---------------------------------------------------------------------------
# Buildx detection
# ---------------------------------------------------------------------------

def detect_buildx() -> tuple[bool, str]:
    """Check if docker buildx is available and return (available, version)."""
    try:
        result = subprocess.run(
            ["docker", "buildx", "version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return False, ""
        # Parse version from output like "github.com/docker/buildx v0.17.1 ..."
        match = re.search(r"v?(\d+\.\d+\.\d+)", result.stdout)
        version = match.group(1) if match else "unknown"
        return True, version
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def buildx_version_gte(version: str, minimum: str) -> bool:
    """Check if a semver version string is >= minimum."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))
    try:
        return parse(version) >= parse(minimum)
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# BuildKit --check mode
# ---------------------------------------------------------------------------

def run_buildx_check(target: BuildTarget) -> tuple[bool, str]:
    """Run `docker buildx build --check` on a Dockerfile (no actual build).

    Requires buildx >= 0.15.0. Returns (passed, output).
    """
    cmd = [
        "docker", "buildx", "build",
        "--check",
        "-f", str(target.dockerfile),
        str(target.context),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=60,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output if output else "CHECK OK"
    except FileNotFoundError:
        return False, "docker buildx not found"
    except subprocess.TimeoutExpired:
        return False, "CHECK TIMEOUT (>60s)"


# ---------------------------------------------------------------------------
# Dockerfile audit (pure regex, no Docker needed)
# ---------------------------------------------------------------------------

@dataclass
class AuditFinding:
    """A single audit finding for a Dockerfile."""
    rule: str
    severity: str  # "FAIL" | "WARN" | "INFO"
    message: str
    line: int | None = None


def audit_dockerfile(dockerfile: Path, context: Path | None = None) -> list[AuditFinding]:
    """Audit a Dockerfile for hardening compliance.

    Pure text/regex analysis — no Docker daemon required. Returns a list
    of findings sorted by severity (FAIL > WARN > INFO).
    """
    findings: list[AuditFinding] = []
    try:
        text = dockerfile.read_text(encoding="utf-8")
    except OSError as exc:
        return [AuditFinding("IO-001", "FAIL", f"Cannot read Dockerfile: {exc}")]

    lines = text.splitlines()

    # --- USER-001 / USER-002: Non-root USER directive ---
    # Dockerfile instructions are case-insensitive per spec
    user_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        stripped_upper = stripped.upper()
        if stripped_upper.startswith("USER ") and not stripped.startswith("#"):
            user_lines.append((i, stripped))

    if not user_lines:
        findings.append(AuditFinding(
            "USER-001", "FAIL",
            "No USER directive — container runs as root",
        ))
    else:
        last_lineno, last_user = user_lines[-1]
        # Extract the username after USER
        user_val = last_user.split(None, 1)[1].strip() if len(last_user.split(None, 1)) > 1 else ""
        if user_val.lower() in ("root", "0"):
            findings.append(AuditFinding(
                "USER-002", "FAIL",
                f"Final USER is root (line {last_lineno}): {last_user}",
                line=last_lineno,
            ))

    # --- HEALTHCHECK-001: HEALTHCHECK directive ---
    has_healthcheck = any(
        line.strip().upper().startswith("HEALTHCHECK ")
        and not line.strip().startswith("#")
        for line in lines
    )
    if not has_healthcheck:
        findings.append(AuditFinding(
            "HEALTHCHECK-001", "WARN",
            "No HEALTHCHECK directive in Dockerfile",
        ))

    # --- SHA-001 / SHA-002: Base image SHA pinning ---
    # Collect all FROM lines and local stage names.
    # Must be uppercase FROM at start of line (Dockerfile instruction),
    # not Python `from` inside RUN heredocs.
    from_lines: list[tuple[int, str]] = []
    local_stages: set[str] = set()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.upper().startswith("FROM ") and not stripped.startswith("#"):
            from_lines.append((i, stripped))
            # Track local stage alias: FROM ... AS <name>
            as_match = re.search(r"\bAS\s+(\S+)", stripped, re.IGNORECASE)
            if as_match:
                local_stages.add(as_match.group(1).lower())

    for lineno, from_line in from_lines:
        # Parse the image reference (after FROM, before AS)
        parts = from_line.split()
        if len(parts) < 2:
            continue
        image_ref = parts[1]

        # Skip scratch and local stage references
        if image_ref.lower() == "scratch":
            continue
        if image_ref.lower() in local_stages:
            continue

        # ARG-interpolated FROM — can't statically pin
        if "${" in image_ref or "$(" in image_ref:
            findings.append(AuditFinding(
                "SHA-002", "INFO",
                f"ARG-interpolated FROM (cannot statically SHA-pin): {image_ref}",
                line=lineno,
            ))
            continue

        # Check for SHA pin
        if "@sha256:" not in image_ref:
            findings.append(AuditFinding(
                "SHA-001", "WARN",
                f"Base image not SHA-pinned: {image_ref}",
                line=lineno,
            ))

    # --- MULTISTAGE-001: Multi-stage detection ---
    if len(from_lines) > 1:
        findings.append(AuditFinding(
            "MULTISTAGE-001", "INFO",
            f"Multi-stage build ({len(from_lines)} stages)",
        ))
    elif len(from_lines) == 1:
        findings.append(AuditFinding(
            "MULTISTAGE-001", "INFO",
            "Single-stage build (consider multi-stage for smaller images)",
        ))

    # --- Accumulate logical RUN blocks for APT-001 and PIPE-001 ---
    # Each entry: (start_line, joined_text_after_RUN)
    run_blocks: list[tuple[int, str]] = []
    in_run = False
    run_start = 0
    run_buf: list[str] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.upper().startswith("RUN "):
            # Start a new RUN block
            in_run = True
            run_start = i
            content = stripped[4:]  # text after "RUN " (4 chars regardless of case)
            if content.endswith("\\"):
                run_buf = [content[:-1]]
            else:
                # Single-line RUN — complete immediately
                run_blocks.append((run_start, content))
                in_run = False
                run_buf = []
            continue
        if in_run:
            if stripped.endswith("\\"):
                run_buf.append(stripped[:-1])
            else:
                run_buf.append(stripped)
                run_blocks.append((run_start, " ".join(run_buf)))
                in_run = False
                run_buf = []
    # Post-loop flush: if last RUN ends with \, flush what we have
    if in_run and run_buf:
        run_blocks.append((run_start, " ".join(run_buf)))

    # --- APT-001: --no-install-recommends ---
    for start_line, run_text in run_blocks:
        if "apt-get install" in run_text and "--no-install-recommends" not in run_text:
            findings.append(AuditFinding(
                "APT-001", "WARN",
                "apt-get install without --no-install-recommends",
                line=start_line,
            ))

    # --- PIPE-001: set -o pipefail before pipes ---
    for start_line, run_text in run_blocks:
        if "|" in run_text and "pipefail" not in run_text:
            findings.append(AuditFinding(
                "PIPE-001", "WARN",
                "RUN with pipe but no 'set -o pipefail'",
                line=start_line,
            ))

    # --- DIGNORE-001: .dockerignore exists ---
    if context and context.exists():
        dockerignore = context / ".dockerignore"
        if not dockerignore.exists():
            # Only warn if context has many files (>50 indicates a real project)
            try:
                file_count = sum(1 for _ in context.iterdir())
            except OSError:
                file_count = 0
            if file_count > 50:
                findings.append(AuditFinding(
                    "DIGNORE-001", "WARN",
                    f".dockerignore missing (context has {file_count}+ entries)",
                ))

    # Sort: FAIL first, then WARN, then INFO
    severity_order = {"FAIL": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 3))
    return findings


# ---------------------------------------------------------------------------
# CI matrix field validation
# ---------------------------------------------------------------------------

def validate_ci_fields(matrix: list[dict[str, Any]], repo_root: Path) -> list[str]:
    """Validate CI matrix field references against the local repo tree.

    Checks:
    - trivy_ignorefile paths exist
    - PIP_CONSTRAINT paths in build_args exist relative to context
    - platforms advisory (amd64-only flagged as INFO)

    Returns list of error/warning strings.
    """
    issues: list[str] = []
    for entry in matrix:
        name = entry.get("image_name", entry.get("name", "unknown"))

        # trivy_ignorefile
        trivy_path = entry.get("trivy_ignorefile", "")
        if trivy_path:
            full = repo_root / trivy_path
            if not full.exists():
                issues.append(f"[{name}] trivy_ignorefile not found: {trivy_path}")

        # build_args — look for PIP_CONSTRAINT=<path>
        build_args = entry.get("build_args", "")
        if not isinstance(build_args, str):
            build_args = " ".join(str(a) for a in (build_args if build_args else []))
        if "PIP_CONSTRAINT=" in build_args:
            for part in build_args.split():
                if part.startswith("PIP_CONSTRAINT="):
                    constraint_rel = part.split("=", 1)[1]
                    # Resolve relative to the build context
                    git_url = entry.get("git_url", "")
                    context_rel = entry.get("context", ".")
                    if "PMOVES.AI.git" in git_url:
                        ctx = repo_root / context_rel
                    else:
                        repo_name = git_url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
                        sub_root = repo_root / repo_name
                        ctx = sub_root if context_rel == "." else sub_root / context_rel
                    constraint_full = ctx / constraint_rel
                    if not constraint_full.exists():
                        issues.append(
                            f"[{name}] PIP_CONSTRAINT file not found: "
                            f"{constraint_rel} (resolved: {constraint_full})"
                        )

        # platforms advisory
        platforms = entry.get("platforms", "")
        if platforms and "arm64" not in platforms and "aarch64" not in platforms:
            issues.append(f"[{name}] INFO: amd64-only ({platforms})")

    return issues


# ---------------------------------------------------------------------------
# Main gate logic
# ---------------------------------------------------------------------------

def print_header(msg: str) -> None:
    """Print a visually distinct section header to stdout."""
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def run_gate(targets: list[BuildTarget], *, lint: bool = False,
             dry_run: bool = False, include_gpu: bool = False,
             audit: bool = False, check: bool = False,
             use_buildx: bool = False) -> int:
    """Run the build gate on the given targets. Returns exit code.

    Execution order:
    1. --dry-run: print resolved contexts and exit
    2. Per target: prerequisites → --audit → --lint → --check → build
    3. If any of --audit, --check, or --dry-run is set: no build happens
    """
    # Filter GPU unless opted in
    if not include_gpu:
        skipped_gpu = [t for t in targets if t.gpu]
        targets = [t for t in targets if not t.gpu]
        for t in skipped_gpu:
            print(f"  SKIP (GPU)  {t.name}")

    if not targets:
        print("No targets to validate.")
        return 0

    if dry_run:
        print_header("DRY RUN — Resolved build targets")
        for t in targets:
            status_parts = []
            if not t.dockerfile.exists():
                status_parts.append("MISSING DOCKERFILE")
            if not t.context.exists():
                status_parts.append("MISSING CONTEXT")
            status = " | ".join(status_parts) if status_parts else "OK"
            print(f"\n  {t.name} [{t.source}]")
            print(f"    Dockerfile: {t.dockerfile}")
            print(f"    Context:    {t.context}")
            print(f"    Status:     {status}")
        print(f"\nTotal: {len(targets)} targets")
        return 0

    # Determine if this is validation-only (no build)
    validation_only = audit or check or lint

    # Pre-flight: Docker needed for --check and actual builds
    needs_docker = check or (not validation_only)
    if needs_docker and not check_docker():
        if check:
            print("ERROR: Docker daemon required for --check. Start Docker and retry.")
            return 1
        if not validation_only:
            print("ERROR: Docker daemon is not accessible. Start Docker and retry.")
            return 1

    # Buildx pre-flight for --check
    if check:
        bx_ok, bx_ver = detect_buildx()
        if not bx_ok:
            print("ERROR: --check requires docker buildx (>= 0.15.0)")
            return 1
        if not buildx_version_gte(bx_ver, "0.15.0"):
            print(f"ERROR: --check requires buildx >= 0.15.0 (found {bx_ver})")
            return 1
        print(f"  buildx {bx_ver} detected")

    # Describe what we're running
    modes = []
    if audit:
        modes.append("audit")
    if lint:
        modes.append("lint")
    if check:
        modes.append("check")
    if not validation_only:
        modes.append("build" + (" (buildx)" if use_buildx else ""))
    mode_str = " + ".join(modes) if modes else "build"
    print_header(f"Build Gate [{mode_str}] — {len(targets)} targets")

    results: list[tuple[str, bool, str]] = []
    has_failures = False

    for i, target in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {target.name}")

        # Check prerequisites
        if not target.dockerfile.exists():
            msg = f"Dockerfile not found: {target.dockerfile}"
            print(f"  FAIL  {msg}")
            results.append((target.name, False, msg))
            has_failures = True
            continue

        if not target.context.exists():
            msg = f"Build context not found: {target.context}"
            print(f"  FAIL  {msg}")
            results.append((target.name, False, msg))
            has_failures = True
            continue

        # Submodule status warning
        sub_warn = check_submodule_status(target.context)
        if sub_warn:
            print(f"  WARN  Submodule {sub_warn}")

        target_ok = True

        # Audit phase
        if audit:
            findings = audit_dockerfile(target.dockerfile, target.context)
            fail_count = sum(1 for f in findings if f.severity == "FAIL")
            warn_count = sum(1 for f in findings if f.severity == "WARN")
            info_count = sum(1 for f in findings if f.severity == "INFO")
            for f in findings:
                loc = f" (line {f.line})" if f.line else ""
                print(f"  {f.severity:4s}  [{f.rule}] {f.message}{loc}")
            if fail_count:
                print(f"  AUDIT FAIL  {fail_count} FAIL, {warn_count} WARN, {info_count} INFO")
                target_ok = False
            else:
                print(f"  AUDIT OK  {warn_count} WARN, {info_count} INFO")

        # Lint phase
        if lint:
            lint_ok, lint_out = run_hadolint(target.dockerfile)
            if not lint_ok:
                print(f"  LINT FAIL\n{lint_out}")
                target_ok = False
            elif "skipped" not in lint_out:
                print(f"  LINT  OK")

        # BuildKit --check phase
        if check:
            check_ok, check_out = run_buildx_check(target)
            if not check_ok:
                print(f"  CHECK FAIL\n  {check_out}")
                target_ok = False
            else:
                print(f"  CHECK OK")

        # Build phase (only if no validation-only flags)
        if not validation_only:
            print(f"  Building {target.name}...")
            ok, msg = run_docker_build(target, use_buildx=use_buildx)
            if ok:
                print(f"  PASS  {msg}")
            else:
                print(f"  FAIL  {msg}")
                target_ok = False

        if not target_ok:
            has_failures = True
        status_msg = "PASS" if target_ok else "FAIL"
        results.append((target.name, target_ok, status_msg))

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print_header(f"Build Gate Summary [{mode_str}]")
    for name, ok, msg in results:
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}")
    print(f"\n  {passed} passed, {failed} failed, {len(targets)} total")

    return 0 if failed == 0 else 1


def main() -> None:
    """CLI entry point — parse args and dispatch to the build gate."""
    parser = argparse.ArgumentParser(
        description="Local build validation gate for CI runner images",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--service", metavar="NAME",
                       help="Validate a single service by name")
    group.add_argument("--all", action="store_true",
                       help="Validate all images in images.yaml")
    group.add_argument("--ci-matrix", action="store_true",
                       help="Validate only CI matrix images")

    parser.add_argument("--lint", action="store_true",
                        help="Also run hadolint on each Dockerfile")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print resolved contexts without building")
    parser.add_argument("--include-gpu", action="store_true",
                        help="Include GPU-heavy images (skipped by default)")
    parser.add_argument("--check", action="store_true",
                        help="Run BuildKit --check validation (requires buildx >= 0.15.0)")
    parser.add_argument("--audit", action="store_true",
                        help="Audit Dockerfiles for hardening compliance")
    parser.add_argument("--validate-ci", action="store_true",
                        help="Validate CI matrix field references (trivy, build_args)")
    parser.add_argument("--buildx", action="store_true",
                        help="Use docker buildx build instead of legacy docker build")

    args = parser.parse_args()

    # Load targets and optionally the raw matrix for --validate-ci
    raw_matrix: list[dict[str, Any]] | None = None
    if args.ci_matrix:
        if not CI_MATRIX_JSON.exists():
            sys.exit(f"ERROR: CI matrix not found: {CI_MATRIX_JSON}")
        raw_matrix = parse_ci_matrix(CI_MATRIX_JSON)
        targets = resolve_from_ci_matrix(raw_matrix)
    else:
        if not IMAGES_YAML.exists():
            sys.exit(f"ERROR: images.yaml not found: {IMAGES_YAML}")
        images = parse_images_yaml(IMAGES_YAML)
        targets = resolve_from_images_yaml(images)

    # Filter to single service if requested
    if args.service:
        name = args.service.strip()
        # Match against name with or without pmoves- prefix
        matches = [t for t in targets
                    if t.name == name
                    or t.name == f"pmoves-{name}"
                    or t.name.removeprefix("pmoves-") == name]
        if not matches:
            available = ", ".join(sorted(t.name for t in targets))
            sys.exit(f"ERROR: service '{name}' not found.\nAvailable: {available}")
        targets = matches

    # --validate-ci runs once at matrix level (before per-target loop)
    ci_exit = 0
    if args.validate_ci:
        if raw_matrix is None:
            sys.exit("ERROR: --validate-ci requires --ci-matrix")
        print_header("CI Matrix Field Validation")
        issues = validate_ci_fields(raw_matrix, REPO_ROOT)
        errors = [i for i in issues if "INFO:" not in i]
        infos = [i for i in issues if "INFO:" in i]
        for issue in errors:
            print(f"  FAIL  {issue}")
        for issue in infos:
            print(f"  INFO  {issue}")
        if errors:
            print(f"\n  {len(errors)} errors, {len(infos)} advisories")
            ci_exit = 1
        else:
            print(f"\n  OK  {len(infos)} advisories, 0 errors")

        # If --validate-ci is the only validation mode, exit early
        if not (args.audit or args.check or args.lint or args.dry_run):
            sys.exit(ci_exit)

    gate_exit = run_gate(
        targets,
        lint=args.lint,
        dry_run=args.dry_run,
        include_gpu=args.include_gpu,
        audit=args.audit,
        check=args.check,
        use_buildx=args.buildx,
    )

    # Combined exit: fail if either --validate-ci or per-target gate failed
    sys.exit(max(ci_exit, gate_exit))


if __name__ == "__main__":
    main()
