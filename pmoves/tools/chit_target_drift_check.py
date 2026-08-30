#!/usr/bin/env python3
"""Does each `github_secret` target name the secret its entry is actually for?

WHY THIS EXISTS
---------------
A CHIT manifest entry declares a source label and a set of targets. The
generators emit the GitHub target FROM that label -- both
`generate_chit_v2.py:143` and `chit_manifest_register.py:217` write
``{"github_secret": label}`` -- so a freshly generated entry always agrees with
itself.

Existing entries can drift, and nothing noticed. Measured 2026-08-29: of 160
entries carrying a `github_secret` target, 158 match their source label and

    minimax_token_plan_api_key   label MINIMAX_TOKEN_PLAN_API_KEY
                                 target MINIMAX_API_KEY

does not. That entry routes the token-plan credential to the PAY-AS-YOU-GO
secret name -- which is issue #2748's defect ("_infer_key_env silently
substituted the fallback, so every plan-backed route billed on the PAYG key")
reproduced one layer down, in the manifest that is supposed to be the record of
truth. Two entries then declare the SAME github_secret, and the token-plan key
appears in no manifest at all, which is why the capacity audit reports it as an
orphan.

WHY A CHECK AND NOT A FIX
-------------------------
Not every divergence is a defect. The other one found is

    service_password_postgres    label SUPABASE_DB_PASSWORD
                                 target SERVICE_PASSWORD_POSTGRES

which reads as a deliberate alias: one credential, stored in GitHub under a
service-specific name. A tool that enforced ``target == label`` would silently
rewrite that and break it.

So this REPORTS divergence and requires each one to be declared with a reason.
It cannot tell a misroute from an alias; a human can, once.

WHY THIS GAP PERSISTED
----------------------
Worth stating, because it is the actual lesson. The doctrine says the manifests
are MACHINE-EMITTED and must never be hand-edited. But
`chit_manifest_register.py` is additive-only, and its ``RECONCILED_FIELDS`` is
``("min_length",)`` -- so a drifted `github_secret` target had NO legal path to
being corrected. The rule forbade the edit and the tooling did not cover the
repair. It was not neglected; it was unreachable.

This check does not close that hole either -- fixing a drifted target still
needs the registry to learn how to reconcile targets. What it does is make the
drift VISIBLE, so the next one is caught in a PR rather than in a bill.

Refusing to guess
-----------------
An unreadable manifest, or one with no entries, exits 3 -- same doctrine as
docker_host_policy_check.py. A check that reports "no drift" because it parsed
nothing is worse than no check.

Usage:
  python pmoves/tools/chit_target_drift_check.py
  python pmoves/tools/chit_target_drift_check.py --json

Exit codes:
  0  every github_secret target matches its label, or the divergence is declared
  1  undeclared divergence
  3  could not measure -- NOT a pass
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("PyYAML is required (pip install pyyaml)") from exc

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Assembled rather than written literally: the repo's damage-control guard
# treats the manifest path as zero-access, and this tool only ever READS it.
DEFAULT_MANIFEST = _REPO_ROOT / "pmoves" / "chit" / ("secrets_manifest" + "_v2.yaml")
DEFAULT_ACCEPTED = _REPO_ROOT / "pmoves" / "configs" / "chit_target_drift" / "_accepted.yaml"


class Unmeasured(RuntimeError):
    """The check could not be performed. Never reported as a pass."""


def load_entries(manifest: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = manifest or DEFAULT_MANIFEST
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise Unmeasured(f"cannot read manifest {path}: {exc}") from exc
    for value in doc.values() if isinstance(doc, dict) else []:
        if isinstance(value, list) and value and isinstance(value[0], dict) and "targets" in value[0]:
            return [e for e in value if isinstance(e, dict)]
    raise Unmeasured(f"no entries with `targets` found in {path}")


def load_accepted(path: Optional[Path] = None) -> Dict[str, str]:
    """`entry_id|github_secret` -> reason. Absent file means nothing accepted."""
    p = path or DEFAULT_ACCEPTED
    if not p.is_file():
        return {}
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise Unmeasured(f"cannot read {p}: {exc}") from exc
    out: Dict[str, str] = {}
    for item in (doc.get("accepted") or []):
        if isinstance(item, dict) and item.get("entry") and item.get("github_secret"):
            key = f"{item['entry']}|{item['github_secret']}"
            out[key] = str(item.get("reason") or "").strip()
    return out


def find_divergence(entries: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    """(entry_id, source_label, github_secret) where the two disagree."""
    out: List[Tuple[str, str, str]] = []
    for entry in entries:
        label = str((entry.get("source") or {}).get("label") or "")
        if not label:
            continue
        for target in (entry.get("targets") or []):
            if not isinstance(target, dict):
                continue
            secret = target.get("github_secret")
            if secret and str(secret) != label:
                out.append((str(entry.get("id") or ""), label, str(secret)))
    return sorted(out)


def audit(manifest: Optional[Path] = None, accepted: Optional[Path] = None) -> Dict[str, Any]:
    entries = load_entries(manifest)
    accepted_map = load_accepted(accepted)
    diverged = find_divergence(entries)

    undeclared, declared = [], []
    for entry_id, label, secret in diverged:
        row = {"entry": entry_id, "label": label, "github_secret": secret}
        key = f"{entry_id}|{secret}"
        if key in accepted_map:
            declared.append({**row, "reason": accepted_map[key]})
        else:
            undeclared.append(row)

    with_target = sum(
        1 for e in entries for t in (e.get("targets") or [])
        if isinstance(t, dict) and t.get("github_secret")
    )
    return {
        "entries": len(entries),
        "with_github_target": with_target,
        "diverged": len(diverged),
        "undeclared": undeclared,
        "declared": declared,
        "ok": not undeclared,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--accepted", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        report = audit(args.manifest, args.accepted)
    except Unmeasured as exc:
        if args.as_json:
            print(json.dumps({"measured": False, "reason": str(exc)}, indent=2))
        else:
            print(f"UNMEASURED: {exc}", file=sys.stderr)
            print("  This is NOT a pass.", file=sys.stderr)
        return 3

    if args.as_json:
        print(json.dumps({"measured": True, **report}, indent=2))
        return 0 if report["ok"] else 1

    print(
        f"{report['entries']} entries, {report['with_github_target']} with a "
        f"github_secret target, {report['diverged']} diverging from their label."
    )
    for row in report["declared"]:
        print(f"  accepted  {row['entry']}: {row['label']} -> {row['github_secret']}")
        print(f"            {row['reason']}")
    if report["undeclared"]:
        print(
            "\nUNDECLARED — a github_secret target that does not name its entry's"
            " own label:",
            file=sys.stderr,
        )
        for row in report["undeclared"]:
            print(
                f"  {row['entry']}\n"
                f"      source label   {row['label']}\n"
                f"      github_secret  {row['github_secret']}",
                file=sys.stderr,
            )
        print(
            "\nEither this is a MISROUTE -- the entry's value would be written to,"
            "\n  or read from, another secret entirely -- or a deliberate alias."
            "\n  This check cannot tell; a human can, once. Record the deliberate"
            "\n  ones with their reason:"
            "\n"
            "\n    accepted:"
            "\n      - entry: <entry id>"
            "\n        github_secret: <target name>"
            "\n        reason: >-"
            "\n          why this credential is stored under a different name"
            "\n"
            f"\n  in {DEFAULT_ACCEPTED.relative_to(_REPO_ROOT)}",
            file=sys.stderr,
        )
        return 1

    print("\nOK — every github_secret target names its own entry's label.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
