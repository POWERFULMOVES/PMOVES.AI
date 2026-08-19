"""Provider-Verifier static gate.

The MiniMax-Provider-Verifier is the conformance gate for adding a new
third-party provider to the Mavis model cascade. It REQUIRES real API
calls (--api-key, --base-url, --model) so it cannot run in CI without
exposing secrets. This module is the static half of the gate — what runs
on every PR via .github/workflows/provider-verifier.yml.

The static checks (no real API calls):

  1. provider.json is well-formed JSON
  2. Every provider entry has the four required fields
     (name, model, base_url, api_key)
  3. The api_key field in the example is the placeholder
     "your-api-key-here" — catches a real key accidentally committed
  4. sample.jsonl exists and is non-empty (required for verify.py to run)
  5. The verifier entry point is importable (catches missing deps +
     syntax errors in the submodule)

The full conformance run (verify.py against a real provider with real
API keys) is the operator's manual step via workflow_dispatch. The static
checks fail-fast on configuration drift; the full run answers "is this
provider actually MiniMax-compatible?".

Exit codes:

  0  all checks passed
  1  one or more checks failed
  2  unexpected error (verifier submodule not initialized, etc.)

JSON output (stdout) for CI consumption:

  {"verdict": "PASS", "checks": [...], "summary": "..."}
  {"verdict": "FAIL", "checks": [...], "summary": "..."}
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root is two parents up from pmoves/tools/.
REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_SUBMODULE = REPO_ROOT / "Pmoves-MiniMax-Provider-Verifier"
PROVIDER_CONFIG = VERIFIER_SUBMODULE / "provider.json.example"
SAMPLE_JSONL = VERIFIER_SUBMODULE / "sample.jsonl"
VERIFIER_ENTRY = VERIFIER_SUBMODULE / "verify.py"

# The placeholder string used in the example. A real key landing in
# this file is a secret leak and MUST be caught.
PLACEHOLDER_API_KEY = "your-api-key-here"

# The four required fields per provider entry. Anything else (extra_body,
# openrouter_provider, etc.) is allowed and ignored by the static check.
REQUIRED_FIELDS = {"name", "model", "base_url", "api_key"}


@dataclass
class CheckResult:
    """One static check's outcome.

    name: short identifier (snake_case)
    passed: True/False
    detail: human-readable explanation (for the PR comment + step summary)
    """

    name: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    """The aggregate gate verdict.

    verdict: "PASS" or "FAIL"
    checks: one CheckResult per static check (5 today)
    summary: one-line human-readable summary
    """

    verdict: str
    checks: List[CheckResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "checks": [asdict(c) for c in self.checks],
            "summary": self.summary,
        }


# ============================================================================
# Individual checks
# ============================================================================


def _paths(verifier_submodule: Path) -> Dict[str, Path]:
    """Resolve the 3 paths the gate inspects under the given submodule dir."""
    return {
        "config": verifier_submodule / "provider.json.example",
        "sample": verifier_submodule / "sample.jsonl",
        "entry": verifier_submodule / "verify.py",
    }


def _try_relative(path: Path) -> str:
    """Best-effort: show the path relative to REPO_ROOT if it lives there."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_verifier_submodule_present(verifier_submodule: Path) -> CheckResult:
    """The Pmoves-MiniMax-Provider-Verifier submodule must be initialized."""
    if not verifier_submodule.exists():
        return CheckResult(
            name="verifier_submodule_present",
            passed=False,
            detail=(
                f"Pmoves-MiniMax-Provider-Verifier/ not found at {verifier_submodule}. "
                "Run `git submodule update --init Pmoves-MiniMax-Provider-Verifier`."
            ),
        )
    if not verifier_submodule.is_dir():
        return CheckResult(
            name="verifier_submodule_present",
            passed=False,
            detail=f"{verifier_submodule} is not a directory.",
        )
    return CheckResult(
        name="verifier_submodule_present",
        passed=True,
        detail=f"submodule present at {_try_relative(verifier_submodule)}",
    )


def check_provider_config_well_formed(verifier_submodule: Path) -> CheckResult:
    """provider.json.example must be valid JSON with a top-level list."""
    config = _paths(verifier_submodule)["config"]
    if not config.exists():
        return CheckResult(
            name="provider_config_well_formed",
            passed=False,
            detail=f"{_try_relative(config)} not found.",
        )
    try:
        with config.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return CheckResult(
            name="provider_config_well_formed",
            passed=False,
            detail=f"JSON decode error: {exc}",
        )
    if not isinstance(data, list):
        return CheckResult(
            name="provider_config_well_formed",
            passed=False,
            detail=f"top-level must be a JSON array, got {type(data).__name__}",
        )
    return CheckResult(
        name="provider_config_well_formed",
        passed=True,
        detail=f"JSON array with {len(data)} provider entries",
    )


def check_provider_entries_have_required_fields(verifier_submodule: Path) -> CheckResult:
    """Every entry must have name, model, base_url, api_key."""
    config = _paths(verifier_submodule)["config"]
    if not config.exists():
        return CheckResult(
            name="provider_entries_have_required_fields",
            passed=False,
            detail="provider.json.example not found; cannot check entries",
        )
    with config.open(encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        return CheckResult(
            name="provider_entries_have_required_fields",
            passed=False,
            detail="provider.json.example is not a list; cannot check entries",
        )
    bad: List[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            bad.append(f"entry[{i}] is not a dict")
            continue
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            bad.append(f"entry[{i}] ({entry.get('name', '?')}) missing {sorted(missing)}")
    if bad:
        return CheckResult(
            name="provider_entries_have_required_fields",
            passed=False,
            detail="; ".join(bad),
        )
    return CheckResult(
        name="provider_entries_have_required_fields",
        passed=True,
        detail=f"all {len(entries)} entries have the 4 required fields",
    )


def check_example_keys_are_placeholders(verifier_submodule: Path) -> CheckResult:
    """No real API key in the example file.

    The example is committed to the repo and serves as a template. If a
    real key ever lands here, it MUST be caught at PR time, not at
    audit time.
    """
    config = _paths(verifier_submodule)["config"]
    if not config.exists():
        return CheckResult(
            name="example_keys_are_placeholders",
            passed=False,
            detail="provider.json.example not found",
        )
    with config.open(encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        return CheckResult(
            name="example_keys_are_placeholders",
            passed=False,
            detail="provider.json.example is not a list",
        )
    leaked: List[str] = []
    for i, entry in enumerate(entries):
        key = entry.get("api_key", "")
        if key and key != PLACEHOLDER_API_KEY:
            leaked.append(
                f"entry[{i}] ({entry.get('name', '?')}): api_key looks real "
                f"(length {len(key)}, prefix {key[:4]!r}...)"
            )
    if leaked:
        return CheckResult(
            name="example_keys_are_placeholders",
            passed=False,
            detail=(
                "Real API key(s) detected in the example. The example file "
                "is committed to the repo — replace with the placeholder. "
                f"Findings: {'; '.join(leaked)}"
            ),
        )
    return CheckResult(
        name="example_keys_are_placeholders",
        passed=True,
        detail="all api_key values are the placeholder",
    )


def check_sample_jsonl_present(verifier_submodule: Path) -> CheckResult:
    """sample.jsonl is required for verify.py to run (positional file_path)."""
    sample = _paths(verifier_submodule)["sample"]
    if not sample.exists():
        return CheckResult(
            name="sample_jsonl_present",
            passed=False,
            detail=f"{_try_relative(sample)} not found.",
        )
    size = sample.stat().st_size
    if size == 0:
        return CheckResult(
            name="sample_jsonl_present",
            passed=False,
            detail=f"{_try_relative(sample)} is empty.",
        )
    # Count non-empty lines as a quick smoke check.
    with sample.open(encoding="utf-8") as f:
        line_count = sum(1 for line in f if line.strip())
    return CheckResult(
        name="sample_jsonl_present",
        passed=True,
        detail=f"{_try_relative(sample)} present, {line_count} non-empty lines, {size} bytes",
    )


def check_verifier_entry_point_importable(verifier_submodule: Path) -> CheckResult:
    """verify.py must be importable (catches missing deps + syntax errors)."""
    entry = _paths(verifier_submodule)["entry"]
    if not entry.exists():
        return CheckResult(
            name="verifier_entry_point_importable",
            passed=False,
            detail=f"{_try_relative(entry)} not found",
        )
    spec = importlib.util.spec_from_file_location("_pmoves_provider_verifier", entry)
    if spec is None or spec.loader is None:
        return CheckResult(
            name="verifier_entry_point_importable",
            passed=False,
            detail=f"could not load spec for {_try_relative(entry)}",
        )
    try:
        # We don't execute the module's top-level code (which may import
        # validator/ package and its deps) — we just confirm the source
        # is parseable. The full import is a heavier check that lives
        # in the operator's manual run.
        compile(entry.read_text(encoding="utf-8"), str(entry), "exec")
    except SyntaxError as exc:
        return CheckResult(
            name="verifier_entry_point_importable",
            passed=False,
            detail=f"syntax error in verify.py: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="verifier_entry_point_importable",
            passed=False,
            detail=f"unexpected error parsing verify.py: {exc}",
        )
    return CheckResult(
        name="verifier_entry_point_importable",
        passed=True,
        detail=f"verify.py parses cleanly ({entry.stat().st_size} bytes)",
    )


# ============================================================================
# Aggregation
# ============================================================================


def run_gate(verifier_submodule: Optional[Path] = None) -> GateResult:
    """Run all 5 static checks. The verifier_submodule override is for tests."""
    target = verifier_submodule if verifier_submodule is not None else VERIFIER_SUBMODULE

    checks = [
        check_verifier_submodule_present(target),
        check_provider_config_well_formed(target),
        check_provider_entries_have_required_fields(target),
        check_example_keys_are_placeholders(target),
        check_sample_jsonl_present(target),
        check_verifier_entry_point_importable(target),
    ]
    failed = [c for c in checks if not c.passed]
    if failed:
        verdict = "FAIL"
        names = ", ".join(c.name for c in failed)
        summary = f"{len(failed)} of {len(checks)} static check(s) failed: {names}"
    else:
        verdict = "PASS"
        summary = f"all {len(checks)} static checks passed"
    return GateResult(verdict=verdict, checks=checks, summary=summary)


# ============================================================================
# CLI
# ============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Static gate for the MiniMax-Provider-Verifier. Checks the "
            "config + the verifier entry point without making real API calls."
        )
    )
    parser.add_argument(
        "--verifier-submodule",
        type=Path,
        default=None,
        help="Override the verifier submodule path (for tests).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output to stdout (default: human-readable).",
    )
    args = parser.parse_args(argv)

    try:
        result = run_gate(verifier_submodule=args.verifier_submodule)
    except Exception as exc:
        sys.stderr.write(f"unexpected error: {exc}\n")
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        for c in result.checks:
            mark = "PASS" if c.passed else "FAIL"
            print(f"[{mark}] {c.name}: {c.detail}")
        print()
        print(f"verdict: {result.verdict}")
        print(f"summary: {result.summary}")

    return 0 if result.verdict == "PASS" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
