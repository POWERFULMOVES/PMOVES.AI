#!/usr/bin/env python3
"""Deterministic submodule-first validation for PMOVES layered audits."""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import json
import py_compile
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"
DEFAULT_MANIFEST = REPO_ROOT / "pmoves" / "configs" / "submodule_layer_validation_manifest.json"
DEFAULT_REPORT_MD = REPO_ROOT / "pmoves" / "docs" / "SUBMODULE_LAYER_VALIDATION.md"
DEFAULT_REPORT_JSON = REPO_ROOT / "pmoves" / "docs" / "evidence" / "submodule_layer_validation.json"


@dataclass
class Finding:
    level: str
    code: str
    module_path: str
    message: str


@dataclass
class ModuleResult:
    name: str
    path: str
    url: str
    commit: str = ""
    status_prefix: str = "?"
    detail: str = ""
    initialized: bool = False
    remote_commit_reachable: str = "skip"
    required_files_any_ok: bool = False
    top_level_files_ok: bool = True
    nested_gitmodules_ok: bool = True
    python_compile_ok: str = "skip"
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, code: str, message: str) -> None:
        self.findings.append(Finding(level=level, code=code, module_path=self.path, message=message))

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.findings if item.level == "ERROR")

    @property
    def warn_count(self) -> int:
        return sum(1 for item in self.findings if item.level == "WARN")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--allow-uninitialized", action="store_true")
    parser.add_argument("--skip-remote-check", action="store_true")
    parser.add_argument(
        "--check-uninitialized-remote",
        action="store_true",
        help="For uninitialized modules, attempt deterministic remote commit fetch checks (slower).",
    )
    parser.add_argument("--skip-python-compile", action="store_true")
    parser.add_argument("--remote-timeout", type=float, default=20.0)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Limit validation to selected submodule name/path. Can be provided multiple times.",
    )
    return parser.parse_args()


def run_git(*args: str, cwd: Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def load_manifest(path: Path) -> dict[str, Any]:
    candidate = path
    if not candidate.exists() and not candidate.is_absolute():
        repo_relative = (REPO_ROOT / candidate).resolve()
        if repo_relative.exists():
            candidate = repo_relative
    if not candidate.exists():
        raise SystemExit(f"Manifest not found: {path}")
    data = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(data, dict):
        raise SystemExit(f"Manifest must be a JSON object: {candidate}")
    return data


def parse_gitmodules(path: Path) -> list[tuple[str, str, str]]:
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    rows: list[tuple[str, str, str]] = []
    for section in cfg.sections():
        if not section.startswith("submodule "):
            continue
        name = section[len("submodule ") :].strip().strip('"')
        module_path = cfg.get(section, "path", fallback="").strip()
        url = cfg.get(section, "url", fallback="").strip()
        if module_path:
            rows.append((name, module_path, url))
    rows.sort(key=lambda item: item[1].lower())
    return rows


def parse_submodule_status() -> dict[str, tuple[str, str, str]]:
    proc = run_git("submodule", "status")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "git submodule status failed")
    rows: dict[str, tuple[str, str, str]] = {}
    for raw in proc.stdout.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        prefix = line[0]
        payload = line[1:].strip()
        parts = payload.split(maxsplit=2)
        if len(parts) < 2:
            continue
        commit = parts[0]
        path = parts[1]
        detail = parts[2] if len(parts) > 2 else ""
        rows[path.replace("\\", "/")] = (prefix, commit, detail)
    return rows


def is_top_level(path: str) -> bool:
    return "/" not in path.replace("\\", "/")


def merged_module_policy(path: str, manifest: dict[str, Any]) -> dict[str, Any]:
    policy = {
        "required_files_any": list(manifest.get("required_files_any", [])),
        "top_level_required_files": list(manifest.get("top_level_required_files", [])),
    }
    overrides = manifest.get("overrides", {})
    if isinstance(overrides, dict):
        override = overrides.get(path)
        if isinstance(override, dict):
            for key, value in override.items():
                policy[key] = value
    return policy


def remote_commit_reachable(url: str, commit: str, timeout: float) -> tuple[bool, str]:
    if not url or not commit:
        return False, "missing-url-or-commit"
    try:
        proc = run_git("ls-remote", url, commit, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if proc.returncode != 0:
        return False, proc.stderr.strip() or "ls-remote-failed"
    matched = any(commit in line for line in proc.stdout.splitlines())
    if matched:
        return True, "ok"
    return False, "commit-not-found-in-remote"


def fetch_commit_exists(url: str, commit: str, timeout: float) -> tuple[bool, str]:
    if not url or not commit:
        return False, "missing-url-or-commit"
    with tempfile.TemporaryDirectory(prefix="pmoves-submodule-check-") as temp_dir:
        temp_path = Path(temp_dir)
        init = run_git("init", "-q", cwd=temp_path, timeout=timeout)
        if init.returncode != 0:
            return False, init.stderr.strip() or "git-init-failed"
        try:
            fetch = run_git("fetch", "--depth", "1", url, commit, cwd=temp_path, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        if fetch.returncode == 0:
            return True, "ok"
        return False, fetch.stderr.strip() or "fetch-failed"


def nested_gitmodules_health(module_root: Path, known_path_typos: list[str]) -> tuple[bool, list[str]]:
    nested = module_root / ".gitmodules"
    if not nested.exists():
        return True, []

    cfg = configparser.ConfigParser()
    cfg.read(nested, encoding="utf-8")
    issues: list[str] = []
    for section in cfg.sections():
        if not section.startswith("submodule "):
            continue
        path_value = cfg.get(section, "path", fallback="").strip()
        url_value = cfg.get(section, "url", fallback="").strip()
        if not path_value:
            issues.append(f"{section}: missing nested path")
        if path_value and not url_value:
            issues.append(f"{section}: missing nested url for path '{path_value}'")
        lower_path = path_value.lower()
        for typo in known_path_typos:
            if typo.lower() in lower_path:
                issues.append(f"{section}: suspicious nested path '{path_value}' (matches typo marker '{typo}')")
    return len(issues) == 0, issues


def python_compile_check(module_root: Path, max_files: int) -> tuple[str, str]:
    py_files: list[Path] = []
    skip_parts = {".git", ".venv", "node_modules", "__pycache__"}
    for path in sorted(module_root.rglob("*.py")):
        if any(part in skip_parts for part in path.parts):
            continue
        py_files.append(path)
    if not py_files:
        return "skip", "no-python-files"
    if len(py_files) > max_files:
        return "warn", f"python-file-count={len(py_files)} exceeds max={max_files}"
    try:
        for path in py_files:
            py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        return "fail", str(exc)
    return "pass", f"compiled-files={len(py_files)}"


def render_markdown(
    results: list[ModuleResult],
    findings: list[Finding],
    generated_at: str,
    manifest_path: Path,
) -> str:
    error_count = sum(1 for item in findings if item.level == "ERROR")
    warn_count = sum(1 for item in findings if item.level == "WARN")
    top_level_total = sum(1 for row in results if is_top_level(row.path))
    initialized_total = sum(1 for row in results if row.initialized)
    lines: list[str] = [
        "# Submodule Layer Validation",
        f"_Generated: {generated_at}_",
        "",
        "## Summary",
        f"- Manifest: `{manifest_path.relative_to(REPO_ROOT).as_posix()}`",
        f"- Submodules declared: **{len(results)}**",
        f"- Initialized: **{initialized_total}/{len(results)}**",
        f"- Top-level modules: **{top_level_total}**",
        f"- Findings: **{error_count} error(s)**, **{warn_count} warning(s)**",
        "",
        "## Matrix",
        "| Submodule | Initialized | Status | Remote Commit | Docs(any) | Top-level Dossier | Nested .gitmodules | Python Compile |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            f"| `{row.path}` | {'yes' if row.initialized else 'no'} | `{row.status_prefix}` | "
            f"`{row.remote_commit_reachable}` | {'yes' if row.required_files_any_ok else 'no'} | "
            f"{'yes' if row.top_level_files_ok else 'no'} | {'ok' if row.nested_gitmodules_ok else 'fail'} | "
            f"`{row.python_compile_ok}` |"
        )

    lines.extend(["", "## Findings"])
    if not findings:
        lines.append("- No findings.")
    else:
        for item in findings:
            lines.append(f"- [{item.level}] `{item.code}` `{item.module_path}`: {item.message}")
    lines.extend(
        [
            "",
            "## Layering Guidance",
            "1. Run `make -C pmoves submodule-layer-validate-strict` until this report is clean.",
            "2. Then run `make -C pmoves audit-layers-static` for root/static gates.",
            "3. Finally run `make -C pmoves audit-layers-runtime` once services are up.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)

    try:
        modules = parse_gitmodules(GITMODULES)
        status_map = parse_submodule_status()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"ERROR: {exc}")
        return 2

    allow_uninitialized = set(manifest.get("allow_uninitialized_paths", []))
    only_filters = {str(item).strip().lower() for item in args.only if str(item).strip()}
    known_typos = [str(item) for item in manifest.get("known_path_typos", [])]

    py_cfg = manifest.get("python_compile", {})
    py_enabled = bool(py_cfg.get("enabled", False)) and not args.skip_python_compile
    py_max_files = int(py_cfg.get("max_files", 400))
    py_include = set(py_cfg.get("include_paths", []))

    results: list[ModuleResult] = []
    findings: list[Finding] = []

    for name, module_path, url in modules:
        if only_filters:
            key_name = name.strip().lower()
            key_path = module_path.replace("\\", "/").strip().lower()
            if key_name not in only_filters and key_path not in only_filters:
                continue
        row = ModuleResult(name=name, path=module_path, url=url)
        key = module_path.replace("\\", "/")
        if key in status_map:
            row.status_prefix, row.commit, row.detail = status_map[key]
            row.initialized = row.status_prefix != "-"
        else:
            row.add("ERROR", "STATUS_MISSING", "Submodule not present in `git submodule status` output.")
        if not row.initialized:
            if module_path not in allow_uninitialized and not args.allow_uninitialized:
                row.add("ERROR", "UNINITIALIZED", "Submodule is not initialized.")
            else:
                row.add("WARN", "UNINITIALIZED_ALLOWED", "Submodule is not initialized (allowed by policy/flag).")

        policy = merged_module_policy(module_path, manifest)
        module_root = REPO_ROOT / module_path
        if row.initialized and module_root.exists():
            actual_head = run_git("-C", str(module_root), "rev-parse", "HEAD")
            if actual_head.returncode == 0:
                current = actual_head.stdout.strip()
                if row.commit and current != row.commit:
                    row.add(
                        "ERROR",
                        "INITIALIZED_DRIFT",
                        f"Initialized submodule head {current} does not match gitlink {row.commit}.",
                    )
            else:
                row.add("ERROR", "INITIALIZED_HEAD_UNKNOWN", actual_head.stderr.strip() or "rev-parse failed")
            row.remote_commit_reachable = "local"

            required_any = [str(item) for item in policy.get("required_files_any", [])]
            if required_any:
                row.required_files_any_ok = any((module_root / rel).exists() for rel in required_any)
                if not row.required_files_any_ok:
                    row.add(
                        "ERROR",
                        "REQUIRED_FILES_ANY_MISSING",
                        f"None of required files found: {required_any}",
                    )
            else:
                row.required_files_any_ok = True

            if is_top_level(module_path):
                top_required = [str(item) for item in policy.get("top_level_required_files", [])]
                if top_required:
                    row.top_level_files_ok = all((module_root / rel).exists() for rel in top_required)
                    if not row.top_level_files_ok:
                        row.add(
                            "ERROR",
                            "TOP_LEVEL_DOSSIER_MISSING",
                            f"Missing top-level required files: {top_required}",
                        )

            nested_ok, nested_issues = nested_gitmodules_health(module_root, known_path_typos=known_typos)
            row.nested_gitmodules_ok = nested_ok
            for issue in nested_issues:
                row.add("ERROR", "NESTED_GITMODULES_INVALID", issue)

            module_selected_for_py = bool(py_include) and (module_path in py_include or name in py_include)
            if py_enabled and (not py_include or module_selected_for_py):
                lint_status, detail = python_compile_check(module_root, py_max_files)
                row.python_compile_ok = lint_status
                if lint_status == "fail":
                    row.add("ERROR", "PYTHON_COMPILE_FAIL", detail)
                elif lint_status == "warn":
                    row.add("WARN", "PYTHON_COMPILE_SKIPPED", detail)
            else:
                row.python_compile_ok = "skip"
        else:
            if args.check_uninitialized_remote and not args.skip_remote_check and row.commit:
                ok, detail = fetch_commit_exists(url=url, commit=row.commit, timeout=args.remote_timeout)
                row.remote_commit_reachable = "ok" if ok else "fail"
                if not ok:
                    row.add("ERROR", "REMOTE_COMMIT_UNREACHABLE", detail)
            else:
                row.remote_commit_reachable = "skip-uninitialized"
            row.required_files_any_ok = False
            if is_top_level(module_path):
                row.top_level_files_ok = False

        findings.extend(row.findings)
        results.append(row)

    if only_filters and not results:
        print(f"ERROR: no submodules matched --only filters: {sorted(only_filters)}")
        return 2

    generated_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    md = render_markdown(
        results=results,
        findings=findings,
        generated_at=generated_at,
        manifest_path=args.manifest.resolve(),
    )
    output_md = args.output_md.resolve()
    output_json = args.output_json.resolve()
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(md + "\n", encoding="utf-8")

    data = {
        "generated_at": generated_at,
        "manifest": str(args.manifest.resolve()),
        "summary": {
            "submodules": len(results),
            "errors": sum(1 for item in findings if item.level == "ERROR"),
            "warnings": sum(1 for item in findings if item.level == "WARN"),
        },
        "results": [
            {
                "name": row.name,
                "path": row.path,
                "url": row.url,
                "status_prefix": row.status_prefix,
                "commit": row.commit,
                "initialized": row.initialized,
                "remote_commit_reachable": row.remote_commit_reachable,
                "required_files_any_ok": row.required_files_any_ok,
                "top_level_files_ok": row.top_level_files_ok,
                "nested_gitmodules_ok": row.nested_gitmodules_ok,
                "python_compile_ok": row.python_compile_ok,
                "findings": [
                    {
                        "level": item.level,
                        "code": item.code,
                        "message": item.message,
                    }
                    for item in row.findings
                ],
            }
            for row in results
        ],
    }
    output_json.write_text(json.dumps(data, indent=2), encoding="utf-8")

    rel_md = output_md.relative_to(REPO_ROOT).as_posix()
    rel_json = output_json.relative_to(REPO_ROOT).as_posix()
    err_count = sum(1 for item in findings if item.level == "ERROR")
    warn_count = sum(1 for item in findings if item.level == "WARN")
    print(f"Wrote {rel_md}")
    print(f"Wrote {rel_json}")
    print(f"Summary: errors={err_count} warnings={warn_count} submodules={len(results)}")

    if err_count > 0:
        return 1
    if args.strict and warn_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
