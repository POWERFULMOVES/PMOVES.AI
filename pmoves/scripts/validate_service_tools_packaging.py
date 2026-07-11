#!/usr/bin/env python3
"""Audit that every PMOVES service image packages the tools it imports.

This script catches the regression class fixed by #2067:
* a service imports ``pmoves.tools.<module>`` (or ``tools.<module>``)
* but its Dockerfile does not COPY the required files into the image
* leading to ``ModuleNotFoundError`` at container runtime.

It is intentionally dependency-light so it can run in CI before images are built.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]  # pmoves/scripts -> pmoves -> repo root
PMOVES_DIR = REPO_ROOT / "pmoves"
SERVICES_DIR = PMOVES_DIR / "services"
COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"

TOOL_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(pmoves\.)?tools\.([a-zA-Z_][a-zA-Z0-9_]*)"
    r"(?:\s+import\s+.*)?$",
    re.MULTILINE,
)

# Services that are shared libraries / not independently containerised.
SHARED_LIB_SERVICES = {"common"}

# Modules that are runtime scripts / CLI helpers and not imported as libraries.
IGNORED_MODULES = {"mini_cli"}


def _parse_compose_build() -> Dict[str, Dict[str, str]]:
    """Extract service -> {context, dockerfile} from docker-compose.yml.

    Uses regex rather than yaml to avoid a dependency on pyyaml/ruamel.yaml.
    The compose file is large but the build blocks are simple key/value pairs.
    """
    if not COMPOSE_FILE.exists():
        return {}

    text = COMPOSE_FILE.read_text()
    # Split into top-level service blocks.  A service starts at column 0 with
    # ``name:`` and continues until the next top-level key or end of file.
    blocks: Dict[str, str] = {}
    current_name: str | None = None
    current_lines: List[str] = []
    for line in text.splitlines(keepends=True):
        if not line.strip() or line.startswith("#"):
            if current_name is not None:
                current_lines.append(line)
            continue
        if not line[:1].isspace():
            if current_name is not None:
                blocks[current_name] = "".join(current_lines)
            current_name = line.split(":", 1)[0].strip()
            current_lines = [line]
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        blocks[current_name] = "".join(current_lines)

    builds: Dict[str, Dict[str, str]] = {}
    for svc, block in blocks.items():
        ctx = re.search(r"^\s+context:\s*(\S+)", block, re.MULTILINE)
        df = re.search(r"^\s+dockerfile:\s*(\S+)", block, re.MULTILINE)
        if ctx and df:
            builds[svc] = {"context": ctx.group(1).strip(), "dockerfile": df.group(1).strip()}
    return builds


def _service_from_path(path: Path) -> str:
    rel = path.relative_to(SERVICES_DIR)
    return rel.parts[0]


def _find_tool_imports() -> Dict[str, Set[Tuple[bool, str]]]:
    """Return service -> set of (uses_pmoves_prefix, module) imported by code."""
    imports: Dict[str, Set[Tuple[bool, str]]] = {}
    for py_file in SERVICES_DIR.rglob("*.py"):
        if "tests" in py_file.parts or "venv" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8")
        for prefix, mod in TOOL_IMPORT_RE.findall(text):
            if mod in IGNORED_MODULES:
                continue
            svc = _service_from_path(py_file)
            imports.setdefault(svc, set()).add((bool(prefix), mod))
    return imports


def _find_dockerfiles() -> Dict[str, List[Path]]:
    """Return service -> list of Dockerfile paths in that service directory."""
    result: Dict[str, List[Path]] = {}
    for svc_dir in SERVICES_DIR.iterdir():
        if not svc_dir.is_dir():
            continue
        dockerfiles = sorted(svc_dir.glob("Dockerfile*"))
        if dockerfiles:
            result[svc_dir.name] = dockerfiles
    return result


def _tool_files_copied(dockerfile: Path) -> Set[str]:
    """Return basenames of files copied from ``tools/`` in a Dockerfile."""
    copied: Set[str] = set()
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line.upper().startswith("COPY"):
            continue
        for token in line.split():
            if token.startswith("tools/"):
                copied.add(Path(token).name)
    return copied


def _has_pmoves_namespace_init(dockerfile: Path) -> bool:
    """Check whether the Dockerfile creates /app/pmoves/__init__.py somehow."""
    text = dockerfile.read_text(encoding="utf-8")
    if re.search(r"pmoves/__init__\.py", text):
        return True
    if re.search(r"mkdir\s+-p\s+.*pmoves", text) and re.search(
        r"printf\s+['\"].*?__init__|['\"].*?>/app/pmoves/__init__\.py", text
    ):
        return True
    return False


def _service_for_compose_entry(dockerfile: str) -> str | None:
    """Map a compose dockerfile path like ``services/foo/Dockerfile`` -> ``foo``."""
    parts = Path(dockerfile).parts
    if len(parts) >= 2 and parts[0] == "services":
        return parts[1]
    return None


def main() -> int:
    imports = _find_tool_imports()
    dockerfiles = _find_dockerfiles()
    compose_builds = _parse_compose_build()
    compose_by_service: Dict[str, Tuple[str, str]] = {}
    for svc_name, info in compose_builds.items():
        dir_svc = _service_for_compose_entry(info["dockerfile"])
        if dir_svc:
            compose_by_service[dir_svc] = (info["context"], info["dockerfile"])

    failures: List[str] = []
    warnings_: List[str] = []

    for svc, modules in sorted(imports.items()):
        if svc in SHARED_LIB_SERVICES:
            continue

        dfs = dockerfiles.get(svc, [])
        if not dfs:
            warnings_.append(
                f"{svc}: imports tools but has no Dockerfile (skipped — not a containerised service)"
            )
            continue

        ctx, compose_df = compose_by_service.get(svc, (None, None))
        imports_pmoves = any(prefix for prefix, _ in modules)

        for df in dfs:
            copied = _tool_files_copied(df)
            df_rel = df.relative_to(REPO_ROOT)

            # If this Dockerfile is the one referenced in compose, the build context
            # must be the repo root ("."), otherwise COPY tools/... is impossible.
            if compose_df and df.name == Path(compose_df).name and ctx != ".":
                failures.append(
                    f"{svc}: compose build context is '{ctx}', must be '.' so "
                    f"{df_rel} can COPY tools/"
                )

            if not copied:
                failures.append(
                    f"{svc}: {df_rel} imports tools but copies nothing from tools/"
                )
                continue

            if "__init__.py" not in copied:
                failures.append(
                    f"{svc}: {df_rel} imports tools but does not COPY tools/__init__.py"
                )

            if imports_pmoves and not _has_pmoves_namespace_init(df):
                failures.append(
                    f"{svc}: {df_rel} imports pmoves.tools.* but does not create "
                    f"/app/pmoves/__init__.py"
                )

            for prefix, mod in sorted(modules):
                expected = f"{mod}.py"
                if expected not in copied:
                    prefix_label = "pmoves.tools" if prefix else "tools"
                    failures.append(
                        f"{svc}: imports {prefix_label}.{mod} but {df_rel} does not "
                        f"COPY tools/{expected}"
                    )

    if warnings_:
        print("Service tools packaging audit WARNINGS")
        for item in warnings_:
            print(f"  - {item}")

    if failures:
        print("Service tools packaging audit FAILED", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    count = sum(len(m) for m in imports.values())
    print(
        f"Service tools packaging audit PASSED "
        f"({len(imports) - len(SHARED_LIB_SERVICES)} services checked, "
        f"{count} tool import sites)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
