#!/usr/bin/env python3
"""Assert the hardened compose overlay keeps its hardening, as a ratchet.

Why this exists
---------------
`pmoves/scripts/validate-hardening.sh` used to be 103 lines of `grep -A 10`
against `pmoves/docker-compose.hardened.yml`. Measured on 2026-09-20 it printed

    Summary: 112 passed, 43 warnings, 0 errors

and exited 0. Five defects, each enough on its own to make the check
meaningless (see `pmoves/docs/audit/HARDENING_VENDOR_RECONCILE_2026-09-20.md`,
findings H2 and M5):

  1. Every property Docker's own hardening guidance calls a requirement --
     `user`, `read_only`, `cap_drop: ALL`, `no-new-privileges`, resource
     limits -- incremented `warnings`. The ONLY path to `errors` was a
     `user:` that both matched `^[0-9]+:[0-9]+$` AND had uid 0. The only way
     to fail the gate was to write the literal string `user: "0:0"`.

  2. A `user:` that exists but is NOT `uid:gid` (`user: nginx`) fell through
     the regex with no `else`. Nothing incremented -- not passed, not
     warnings, not errors. That service vanished from all three counters, so
     the `Summary:` line under-reported its own denominator and a reader
     could not tell "all subjects evaluated" from "some fell through". Latent
     on 2026-09-20 (all 28 services carried numeric users), not fixed.

  3. Service discovery stripped the top-level KEYS `services`, `secrets`,
     `networks` and `volumes` by name, but not their children. It validated
     31 subjects against a file declaring 28 services; the extra three were
     the entries under top-level `secrets:` -- `supabase_service_role_key`,
     `supabase_jwt_secret`, `p7_control_token` -- each scored for a missing
     `user` and `read_only`. 10% of the denominator was not a container.

  4. `grep -A 10 "^  service:"` reads a fixed ten-line window, so a directive
     on line 11 of a service block is invisible and one belonging to the NEXT
     service is attributed to this one.

  5. Nothing could regress. 43 warnings on a run that exits 0 is the same
     output whether the number is 43 or 430.

What is asserted
----------------
For every service in the overlay, five properties, each landing in exactly one
bucket -- there is no fall-through:

  NO_USER              no `user:` at all; the container runs as the image
                       default (root unless the image says otherwise).
  ROOT_USER            `user:` resolves to uid 0.
  USER_NOT_NUMERIC     `user:` is a name, not `uid[:gid]`. NOT scored as a
                       pass: whether that name is root cannot be decided from
                       compose, only from the image's /etc/passwd. Recorded as
                       a finding so it is visible rather than silent.
  NO_READ_ONLY         `read_only:` absent or not true.
  NO_CAP_DROP_ALL      `cap_drop` does not contain ALL.
  NO_NO_NEW_PRIVILEGES `security_opt` lacks `no-new-privileges:true`.
  NO_RESOURCE_LIMITS   `deploy.resources.limits` absent.

Vendor anchors: https://docs.docker.com/engine/security/#linux-kernel-capabilities
("remove all capabilities except those explicitly required"),
https://docs.docker.com/reference/compose-file/services/#read_only ,
https://docs.docker.com/reference/compose-file/services/#cap_drop ,
https://docs.docker.com/reference/cli/docker/container/run/#security-opt .

The file is parsed as YAML, not grepped. It carries Compose's `!override` and
`!reset` tags, which `yaml.safe_load` refuses outright, so unknown tags are
passed through rather than ignored -- see `_loader`.

Ratchet semantics -- identical to pmoves/tools/hardening_ratchet.py:

  new findings    not in the baseline                     -> fail
  stale entries   in the baseline, now compliant, and the
                  service IS declared in this overlay     -> fail
  not-in-file     in the baseline, service not declared
                  here                                    -> report, do not fail

Stale entries fail on purpose: without that a baseline rots into a permanent
allowlist. The list may shrink and must never quietly grow.

THIS TOOL IS NOT A REQUIRED STATUS CHECK. It runs in
`.github/workflows/hardening-validation.yml`, which contributes no context to
`pmoves/configs/branch_protection/pmoves_standard.json`. Promoting it is a
policy decision for the operator, and must not be taken merely because the
tool is now able to fail -- being able to fail is what makes that decision
possible, not a substitute for it.

Run:   python pmoves/tools/compose_hardening_ratchet.py
       python pmoves/tools/compose_hardening_ratchet.py flute-gateway
       python pmoves/tools/compose_hardening_ratchet.py --json
       python pmoves/tools/compose_hardening_ratchet.py --write-baseline

Exit:  0 = clean
       1 = new finding(s) and/or stale baseline entry(ies)
       3 = COULD NOT MEASURE (no YAML parser, file missing/unparseable, or the
           per-service verdict count did not reconcile). Never conflate with 0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
COMPOSE = PMOVES / "docker-compose.hardened.yml"
BASELINE = PMOVES / "configs" / "hardening_ratchet" / "_compose_known_gaps.yaml"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_CANNOT_MEASURE = 3

# Every property evaluated per service. The count is asserted against the
# verdicts actually produced, so a future branch that forgets to emit one is a
# reconcile failure (exit 3) rather than a quietly smaller denominator.
PROPERTIES = ("user", "read_only", "cap_drop", "no_new_privileges", "resource_limits")

DEFAULT_KIND = "debt"
_NUMERIC_USER = re.compile(r"^(\d+)(?::(\d+))?$")


class CouldNotMeasure(RuntimeError):
    """Raised where a wrong answer would be worse than no answer."""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _loader():
    """A SafeLoader that passes unknown tags through instead of refusing them.

    `docker-compose.hardened.yml` uses Compose's merge tags (`!override`,
    `!reset`, https://docs.docker.com/reference/compose-file/merge/ ). PyYAML's
    SafeLoader raises ConstructorError on the first one, so a naive
    `yaml.safe_load` of this exact file fails outright -- which is one reason
    the original check reached for grep. Passing the tag through preserves the
    node's value, which is all this tool reads.
    """
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise CouldNotMeasure(
            "PyYAML is not importable, so the overlay cannot be parsed. "
            "A grep fallback is deliberately NOT provided: the grep is the "
            "defect this tool replaces."
        ) from exc

    class _TagTolerantLoader(yaml.SafeLoader):
        pass

    def _passthrough(loader, tag_suffix, node):  # noqa: ANN001 - PyYAML API
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node, deep=True)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        return loader.construct_scalar(node)

    _TagTolerantLoader.add_multi_constructor("", _passthrough)
    return _TagTolerantLoader


def load_services(path: Path = COMPOSE) -> Dict[str, dict]:
    """Return the overlay's `services:` mapping, and nothing else.

    Top-level `secrets:`, `networks:` and `volumes:` are excluded STRUCTURALLY
    rather than filtered by name, which is what let three secret NAMES be
    validated as if they were containers.
    """
    if not path.is_file():
        raise CouldNotMeasure(f"compose overlay not found: {path}")
    loader = _loader()
    import yaml

    try:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
    except yaml.YAMLError as exc:
        raise CouldNotMeasure(f"{path} is not parseable as YAML: {exc}") from exc
    if not isinstance(doc, dict):
        raise CouldNotMeasure(f"{path} did not parse to a mapping")
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        raise CouldNotMeasure(f"{path} declares a non-mapping `services:`")
    return {name: (body or {}) for name, body in services.items()}


# ---------------------------------------------------------------------------
# Per-property verdicts. Each returns (finding_kind, detail); an empty
# finding_kind means PASS. There is no third outcome, by construction.
# ---------------------------------------------------------------------------


def _verdict_user(body: dict) -> Tuple[str, str]:
    if "user" not in body:
        return "NO_USER", "no user: directive"
    raw = str(body["user"]).strip().strip('"').strip("'")
    m = _NUMERIC_USER.match(raw)
    if not m:
        return (
            "USER_NOT_NUMERIC",
            f"user: {raw} (a name; root-ness undecidable from compose)",
        )
    if m.group(1) == "0":
        return "ROOT_USER", f"user: {raw}"
    return "", f"user: {raw}"


def _verdict_read_only(body: dict) -> Tuple[str, str]:
    if body.get("read_only") is True:
        return "", "read_only: true"
    if "read_only" not in body:
        return "NO_READ_ONLY", "no read_only: directive"
    return "NO_READ_ONLY", f"read_only: {body['read_only']!r}"


def _verdict_cap_drop(body: dict) -> Tuple[str, str]:
    caps = body.get("cap_drop") or []
    if isinstance(caps, str):
        caps = [caps]
    if any(str(c).strip().upper() == "ALL" for c in caps):
        return "", "cap_drop: [ALL]"
    return "NO_CAP_DROP_ALL", f"cap_drop: {caps!r}"


def _verdict_no_new_privileges(body: dict) -> Tuple[str, str]:
    opts = body.get("security_opt") or []
    if isinstance(opts, str):
        opts = [opts]
    for opt in opts:
        text = str(opt).replace(" ", "")
        if text.startswith("no-new-privileges:") and text.split(":", 1)[1].lower() == "true":
            return "", "security_opt: no-new-privileges:true"
    return "NO_NO_NEW_PRIVILEGES", f"security_opt: {opts!r}"


def _verdict_resource_limits(body: dict) -> Tuple[str, str]:
    limits = ((body.get("deploy") or {}).get("resources") or {}).get("limits")
    if limits:
        return "", f"deploy.resources.limits: {sorted(limits)}"
    return "NO_RESOURCE_LIMITS", "no deploy.resources.limits"


_VERDICTS = {
    "user": _verdict_user,
    "read_only": _verdict_read_only,
    "cap_drop": _verdict_cap_drop,
    "no_new_privileges": _verdict_no_new_privileges,
    "resource_limits": _verdict_resource_limits,
}


def evaluate(services: Dict[str, dict]) -> List[dict]:
    """One record per (service, property). Never fewer, never more.

    Emitting a record for a PASS as well as for a finding is the point: the
    original script's counters could not distinguish an evaluated pass from a
    subject that fell through a branch, because a fall-through incremented
    nothing at all.
    """
    records: List[dict] = []
    for name in sorted(services):
        body = services[name]
        if not isinstance(body, dict):
            body = {}
        for prop in PROPERTIES:
            kind, detail = _VERDICTS[prop](body)
            records.append(
                {
                    "service": name,
                    "property": prop,
                    "kind": kind or "PASS",
                    "ident": f"{kind}|{name}" if kind else "",
                    "detail": detail,
                }
            )
    return records


def reconcile(services: Dict[str, dict], records: List[dict]) -> None:
    """The direct test for the silent fall-through.

    passed + findings MUST equal len(services) * len(PROPERTIES). If it does
    not, the tool did not evaluate what it says it evaluated, and printing a
    tidy summary would be the original defect wearing a new counter.
    """
    expected = len(services) * len(PROPERTIES)
    if len(records) != expected:
        raise CouldNotMeasure(
            f"verdict count {len(records)} != {len(services)} services x "
            f"{len(PROPERTIES)} properties = {expected}"
        )
    seen = {(r["service"], r["property"]) for r in records}
    if len(seen) != expected:
        raise CouldNotMeasure(
            f"{expected - len(seen)} (service, property) pair(s) were evaluated "
            "more than once or not at all"
        )


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def _parse_baseline(path: Path = BASELINE) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ({ident: reason}, {ident: kind}).

    Entries are either a bare `"KIND|service"` string or a mapping with
    `entry` / `kind` / `reason`, matching `_known_gaps.yaml` so the two
    baselines read the same way.
    """
    if not path.is_file():
        return {}, {}
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = doc.get("known_gaps") or []
    reasons: Dict[str, str] = {}
    kinds: Dict[str, str] = {}
    for item in entries:
        if isinstance(item, str):
            reasons[item] = ""
            kinds[item] = DEFAULT_KIND
        elif isinstance(item, dict) and item.get("entry"):
            ident = str(item["entry"])
            reasons[ident] = str(item.get("reason") or "")
            kinds[ident] = str(item.get("kind") or DEFAULT_KIND)
        else:
            raise CouldNotMeasure(f"unreadable baseline entry: {item!r}")
    return reasons, kinds


def write_baseline(idents: List[str], path: Path = BASELINE) -> None:
    reasons, kinds = _parse_baseline(path)
    lines = [
        "# Baselined compose-hardening gaps - compose_hardening_ratchet.py",
        "#",
        "# Each entry is a (property, service) pair in",
        "# pmoves/docker-compose.hardened.yml that does not meet the hardening",
        "# property named. They are recorded so the check can be ENFORCED today",
        "# without turning the workflow red in a single step. They are NOT",
        "# approved, and none of them is 'expected'.",
        "#",
        "# The list may shrink and must never silently grow. A service that is",
        "# fixed but still listed here fails the gate as a STALE entry, so the",
        "# count only goes down.",
        "#",
        "# Regenerate: python pmoves/tools/compose_hardening_ratchet.py --write-baseline",
        "known_gaps:",
    ]
    for ident in sorted(idents):
        reason = reasons.get(ident)
        kind = kinds.get(ident, DEFAULT_KIND)
        if reason:
            lines.append(f'  - entry: "{ident}"')
            lines.append(f"    kind: {kind}")
            lines.append("    reason: >-")
            lines.append(f"      {reason}")
        else:
            lines.append(f'  - "{ident}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compose hardening ratchet.")
    ap.add_argument("service", nargs="?", help="evaluate a single service only")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--file", default=str(COMPOSE), help="compose overlay to read")
    ap.add_argument("--baseline", default=str(BASELINE), help="baseline file to read/write")
    ap.add_argument(
        "--write-baseline",
        action="store_true",
        help="record the current findings as the baseline",
    )
    args = ap.parse_args(argv)

    compose_path = Path(args.file)
    baseline_path = Path(args.baseline)

    try:
        all_services = load_services(compose_path)
        services = all_services
        if args.service:
            if args.service not in all_services:
                raise CouldNotMeasure(
                    f"service {args.service!r} is not declared in {compose_path}"
                )
            services = {args.service: all_services[args.service]}
        records = evaluate(services)
        reconcile(services, records)
        reasons, kinds = _parse_baseline(baseline_path)
    except CouldNotMeasure as exc:
        print(f"COULD NOT MEASURE: {exc}", file=sys.stderr)
        return EXIT_CANNOT_MEASURE

    found = {r["ident"] for r in records if r["ident"]}
    baseline = set(reasons)
    new = sorted(found - baseline)

    # A baselined ident can be absent from `found` for THREE unrelated
    # reasons, and collapsing them is how a ratchet either rots into an
    # allowlist or screams about services it was never asked to look at:
    #
    #   evaluated here and now compliant -> STALE -> fail. Without this the
    #       baseline becomes permanent and the count never goes down.
    #   declared in the overlay but outside a targeted run -> out of scope.
    #       Saying "not in this file" about a service that IS in the file
    #       would be the same wrong-subject defect this tool exists to fix.
    #   not declared in the overlay at all -> report, do not fail. A baseline
    #       shared across branches must survive a tree that dropped a service.
    declared = set(all_services)
    evaluated = set(services)
    absent = sorted(baseline - found)
    stale = [i for i in absent if i.split("|", 1)[-1] in evaluated]
    out_of_scope = [
        i
        for i in absent
        if i.split("|", 1)[-1] in declared and i.split("|", 1)[-1] not in evaluated
    ]
    not_in_file = [i for i in absent if i.split("|", 1)[-1] not in declared]

    passed = [r for r in records if not r["ident"]]
    baselined = sorted(found & baseline)

    if args.write_baseline:
        write_baseline(sorted(found), baseline_path)
        print(f"Baseline written: {baseline_path} ({len(found)} entries)")
        return EXIT_CLEAN

    if args.json:
        print(
            json.dumps(
                {
                    "compose": str(compose_path),
                    "services": len(services),
                    "properties": len(PROPERTIES),
                    "evaluated": len(records),
                    "passed": len(passed),
                    "findings": len(found),
                    "baselined": len(baselined),
                    "new": new,
                    "stale": stale,
                    "out_of_scope": out_of_scope,
                    "not_in_file": not_in_file,
                    "records": records,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_FINDINGS if (new or stale) else EXIT_CLEAN

    print("PMOVES.AI compose hardening ratchet")
    print("===================================")
    print(f"[INFO] Checking: {compose_path}")
    print("")
    for name in sorted(services):
        print(f"[INFO] Validating: {name}")
        for r in (x for x in records if x["service"] == name):
            if not r["ident"]:
                print(f"  [PASS] {r['property']}: {r['detail']}")
            elif r["ident"] in baseline:
                print(f"  [BASELINED] {r['kind']}: {r['detail']}")
            else:
                print(f"  [FAIL] {r['kind']}: {r['detail']}")
        print("")

    print("===================================")
    # Printed as an equation, not three loose numbers, because the equation IS
    # the assertion: anything that fell through a branch would break it.
    print(
        f"Summary: {len(services)} services x {len(PROPERTIES)} properties = "
        f"{len(records)} evaluated; {len(passed)} passed + {len(found)} findings "
        f"= {len(passed) + len(found)}"
    )
    print(f"Findings: {len(found)} ({len(baselined)} baselined, {len(new)} new)")
    if new:
        print("")
        print("NEW (not in the baseline):")
        for ident in new:
            print(f"  - {ident}")
    if stale:
        print("")
        print("STALE (baselined, now compliant - remove from the baseline):")
        for ident in stale:
            print(f"  - {ident}")
    if out_of_scope:
        print("")
        print(
            f"OUT OF SCOPE ({len(out_of_scope)} baselined entr(ies) for services "
            "this targeted run did not evaluate)"
        )
    if not_in_file:
        print("")
        print(f"NOT IN THIS FILE ({len(not_in_file)}, reported, not failing):")
        for ident in not_in_file:
            print(f"  - {ident}")

    if new or stale:
        print("")
        print(
            "::error::compose hardening regressed. Fix the service, or record it "
            "in pmoves/configs/hardening_ratchet/_compose_known_gaps.yaml with a "
            "reason."
        )
        return EXIT_FINDINGS
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
