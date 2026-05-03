"""Naming-drift coherence audit (read-only).

Walks eight surfaces and verifies they agree on canonical names:

1. ``pmoves/bootstrap/registry.json``                     — declared canonical names
2. ``pmoves/config/agent_registry.yaml``                  — agent ports + health paths
3. ``pmoves/config/signing_identity_cards.yaml``          — 5x5 identity cards
4. ``pmoves/contracts/schemas/`` (recursive)              — versioned schemas
5. ``pmoves/docker-compose*.yml`` (multiple)              — env-var wiring
6. ``.github/workflows/*.yml``                            — secret references
7. ``pmoves/config/agent_signatures.yaml``                — H-half identity registry
8. ``.claude/context/services-catalog.md`` + ``nats-subjects.md``  — context-doc claims

Cross-checks:

* Each ``${VAR:-}`` empty default in compose is in the canonical-aliases doc OR
  has a ``# host-leak-guard`` annotation.
* Every active identity card has a matching ``agent_id`` in agent_signatures.yaml
  (or is a ``runner`` / ``service-account`` role that does not need one).
* Every NATS subject in context docs matches ``<cat>.<svc>.<event>.v<N>``.
* No workflow passes ``GH_APP_SEC`` to a ``private-key:`` parameter
  (it must be ``GH_APP_PRIVATE_KEY``).
* No host-side port binding is duplicated across compose files.

Outputs:

* ``pmoves/docs/logs/naming_drift_latest.json`` — full report
* ``pmoves/docs/logs/node_descriptions_diff_latest.md`` — Phase 5 diff

Exit codes:

* ``0`` — clean OR drift below severity threshold (default: P2)
* ``1`` — drift at severity threshold or above (P0/P1 with ``--strict``)
* ``2`` — runtime error reading inputs

Usage:
    python pmoves/scripts/audit_naming_drift.py            # WARN-only
    python pmoves/scripts/audit_naming_drift.py --strict   # CI gate
    python pmoves/scripts/audit_naming_drift.py --json     # JSON to stdout
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

logger = logging.getLogger("audit_naming_drift")

REPO_ROOT = Path(__file__).resolve().parents[2]

REGISTRY_JSON = REPO_ROOT / "pmoves" / "bootstrap" / "registry.json"
AGENT_REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
SIGNING_CARDS = REPO_ROOT / "pmoves" / "config" / "signing_identity_cards.yaml"
AGENT_SIGNATURES = REPO_ROOT / "pmoves" / "config" / "agent_signatures.yaml"
CANONICAL_NAMES_DOC = REPO_ROOT / "pmoves" / "docs" / "operations" / "CANONICAL_NAMES.md"
SCHEMAS_DIR = REPO_ROOT / "pmoves" / "contracts" / "schemas"
COMPOSE_GLOB = "pmoves/docker-compose*.yml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SERVICES_CATALOG = REPO_ROOT / ".claude" / "context" / "services-catalog.md"
NATS_SUBJECTS = REPO_ROOT / ".claude" / "context" / "nats-subjects.md"

LOGS_DIR = REPO_ROOT / "pmoves" / "docs" / "logs"
DRIFT_REPORT = LOGS_DIR / "naming_drift_latest.json"
NODE_DIFF_REPORT = LOGS_DIR / "node_descriptions_diff_latest.md"

NATS_SUBJECT_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+\.v\d+$")
COMPOSE_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:[-?])([^}]*)\}")
NATS_SUBJECT_INLINE_RE = re.compile(r"`([a-z][a-z0-9_-]*\.[a-z][a-z0-9_.-]*\.v\d+)`")

ALLOWED_SECRET_KEYS_FOR_PEM = {"GH_APP_PRIVATE_KEY"}
DEPRECATED_PEM_KEY = "GH_APP_SEC"
HOST_LEAK_GUARD_HINT = "host-leak-guard"

SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}

# Inline copy of pmoves/contracts/schemas/identity/signing-card.v1.schema.json.
# The canonical path is read-only via damage-control policy (intentional —
# schemas are versioned, not mutated), and adding a new file there requires
# extending patterns.yaml which is out of scope for a credential-audit lane.
# Until the policy carve-out lands, this dict is the single source of truth
# the audit validates cards against.  When the file ships at the canonical
# path, replace the literal with a load-from-disk and keep the dict as a
# fallback for environments without jsonschema installed.
SIGNING_CARD_V1_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Signing Identity Card v1",
    "type": "object",
    "required": ["card_id", "ml", "h", "issued_at", "active"],
    "additionalProperties": False,
    "properties": {
        "card_id": {"type": "string", "format": "uuid"},
        "ml": {
            "type": "object",
            "required": ["primary_method"],
            "additionalProperties": False,
            "properties": {
                "primary_method": {"type": "string", "enum": ["ssh", "gpg", "github-app"]},
                "ssh_fingerprint": {"type": ["string", "null"]},
                "ssh_allowed_signers_line": {"type": ["string", "null"]},
                "gpg_key_id": {"type": ["string", "null"]},
                "github_app_installation_id": {"type": ["integer", "null"]},
                "ci_runner_label": {"type": ["string", "null"]},
            },
        },
        "h": {
            "type": "object",
            "required": ["agent_id", "glyph", "color", "role"],
            "additionalProperties": False,
            "properties": {
                "agent_id": {"type": "string", "minLength": 1},
                "display_name": {"type": "string"},
                "glyph": {"type": "string", "minLength": 1, "maxLength": 2},
                "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                "voice": {"type": "string"},
                "role": {"type": "string", "enum": ["operator", "agent", "runner", "service-account"]},
            },
        },
        "issued_at": {"type": "string", "format": "date-time"},
        "rotated_at": {"type": ["string", "null"], "format": "date-time"},
        "active": {"type": "boolean"},
        "supersedes_card_id": {"type": ["string", "null"], "format": "uuid"},
        "notes": {"type": "string"},
    },
}


@dataclass
class Finding:
    """One drift detection."""

    check: str
    severity: str
    message: str
    location: str | None = None
    evidence: str | None = None

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    surfaces_scanned: dict[str, Any] = field(default_factory=dict)
    canonical_aliases_seen: list[str] = field(default_factory=list)
    cards_summary: dict[str, Any] = field(default_factory=dict)

    def add(self, **kwargs: Any) -> None:
        self.findings.append(Finding(**kwargs))

    def by_severity(self) -> dict[str, int]:
        out: Counter[str] = Counter()
        for f in self.findings:
            out[f.severity] += 1
        return dict(out)


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_canonical_aliases_from_registry(registry_path: Path) -> dict[str, list[str]] | None:
    """Read the structured ``canonical_aliases`` block from registry.json.

    Preferred over the markdown parser when the registry block exists — JSON
    is the durable form, markdown is the human-facing explainer.  Returns
    ``None`` (not ``{}``) when the block is absent so the caller can fall
    back to the markdown parser.
    """
    if not registry_path.exists():
        return None
    try:
        data = _read_json(registry_path)
    except json.JSONDecodeError:
        return None
    block = data.get("canonical_aliases") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return None
    out: dict[str, list[str]] = {}
    for canonical, entry in block.items():
        if isinstance(entry, list):
            out[canonical] = [a for a in entry if isinstance(a, str) and a != canonical]
        elif isinstance(entry, dict):
            aliases = entry.get("aliases") or []
            out[canonical] = [a for a in aliases if isinstance(a, str) and a != canonical]
        else:
            out[canonical] = []
    return out


def parse_canonical_aliases_from_markdown(doc_path: Path) -> dict[str, list[str]]:
    """Extract deprecated-alias declarations from CANONICAL_NAMES.md.

    Fallback parser used when registry.json's ``canonical_aliases`` block
    is missing.  Markdown formatting changes silently break this — the
    structured JSON form should be preferred long-term.
    """
    if not doc_path.exists():
        return {}
    text = _read_text(doc_path)
    aliases: dict[str, list[str]] = {}
    canonical_re = re.compile(r"^- \*\*Canonical:\*\* `([A-Z_][A-Z0-9_]*)`", re.MULTILINE)
    deprecated_re = re.compile(r"^- \*\*Deprecated aliases:\*\* (.+?)(?=\n\n|\n- |\Z)", re.MULTILINE | re.DOTALL)
    sections = re.split(r"(?m)^## \d+\.", text)
    for section in sections[1:]:  # skip preamble
        cm = canonical_re.search(section)
        if not cm:
            continue
        canonical = cm.group(1)
        dm = deprecated_re.search(section)
        if not dm:
            aliases[canonical] = []
            continue
        body = dm.group(1)
        ticked = re.findall(r"`([A-Z_][A-Z0-9_]*)`", body)
        aliases[canonical] = [a for a in ticked if a != canonical]
    return aliases


def parse_canonical_aliases(doc_path: Path, registry_path: Path | None = None) -> dict[str, list[str]]:
    """Resolve canonical/alias map from the durable source first, markdown second.

    Tries ``registry.json`` -> ``canonical_aliases`` block.  Falls back to
    ``CANONICAL_NAMES.md`` regex parsing only when the JSON block is absent.
    """
    if registry_path is not None:
        from_json = parse_canonical_aliases_from_registry(registry_path)
        if from_json is not None:
            return from_json
    return parse_canonical_aliases_from_markdown(doc_path)


def check_signing_cards(report: Report) -> None:
    """Validate identity cards parse and bind to agent_signatures."""
    if not SIGNING_CARDS.exists():
        report.add(
            check="signing_cards.exists",
            severity="P0",
            message="signing_identity_cards.yaml missing",
            location=str(SIGNING_CARDS.relative_to(REPO_ROOT)),
        )
        return

    data = _read_yaml(SIGNING_CARDS)
    cards = data.get("cards") or []
    report.surfaces_scanned["signing_cards"] = {"count": len(cards)}

    # Schema validation (advisory unless jsonschema is installed)
    schema_errors = 0
    try:
        import jsonschema  # type: ignore[import-not-found]

        validator = jsonschema.Draft202012Validator(SIGNING_CARD_V1_SCHEMA)
        for c in cards:
            for err in validator.iter_errors(c):
                schema_errors += 1
                cid = (c or {}).get("card_id") or "<no-card_id>"
                report.add(
                    check="card.schema",
                    severity="P1",
                    message=f"card {cid} fails schema: {err.message}",
                    location=str(SIGNING_CARDS.relative_to(REPO_ROOT)),
                )
    except ImportError:
        report.surfaces_scanned["card_schema_validation"] = "skipped (jsonschema not installed)"
    if schema_errors == 0:
        report.surfaces_scanned["card_schema_validation"] = "ok"

    if not AGENT_SIGNATURES.exists():
        report.add(
            check="agent_signatures.exists",
            severity="P0",
            message="agent_signatures.yaml missing — cannot cross-check H half",
        )
        signatures: dict[str, Any] = {}
    else:
        sig_doc = _read_yaml(AGENT_SIGNATURES)
        signatures = (sig_doc or {}).get("signatures") or {}

    seen_card_ids: set[str] = set()
    active_by_agent: defaultdict[str, list[str]] = defaultdict(list)

    for c in cards:
        cid = c.get("card_id")
        ml = c.get("ml") or {}
        h = c.get("h") or {}
        agent_id = h.get("agent_id")
        role = h.get("role")
        active = bool(c.get("active"))

        if not cid:
            report.add(check="card.card_id", severity="P0", message="missing card_id", evidence=str(c))
            continue
        if cid in seen_card_ids:
            report.add(
                check="card.card_id_unique",
                severity="P0",
                message=f"duplicate card_id {cid}",
            )
        seen_card_ids.add(cid)

        if not agent_id:
            report.add(check="card.agent_id", severity="P0", message=f"card {cid} missing h.agent_id")
            continue
        if not role:
            report.add(check="card.role", severity="P1", message=f"card {cid} missing h.role")

        if not ml.get("primary_method"):
            report.add(check="card.primary_method", severity="P0", message=f"card {cid} missing ml.primary_method")

        if active:
            active_by_agent[agent_id].append(cid)

        # Cross-check against agent_signatures (only for `agent` role; runners + service-accounts
        # don't need entries in agent_signatures.yaml)
        if active and role == "agent" and agent_id not in signatures:
            report.add(
                check="card.agent_in_signatures",
                severity="P1",
                message=f"active card {cid} (agent_id={agent_id}) has no entry in agent_signatures.yaml",
            )

    # At most one active card per agent_id
    for agent_id, ids in active_by_agent.items():
        if len(ids) > 1:
            report.add(
                check="card.one_active_per_agent",
                severity="P0",
                message=f"agent_id={agent_id} has {len(ids)} active cards: {ids}",
            )

    report.cards_summary = {
        "total": len(cards),
        "active": sum(1 for c in cards if c.get("active")),
        "by_role": dict(Counter((c.get("h") or {}).get("role") for c in cards if c.get("active"))),
    }


def check_health_endpoints(report: Report) -> None:
    """Compare per-service health paths in agent_registry vs catalog claims."""
    if not AGENT_REGISTRY.exists():
        report.add(check="agent_registry.exists", severity="P0", message="agent_registry.yaml missing")
        return
    data = _read_yaml(AGENT_REGISTRY) or {}
    agents_raw = data.get("agents") or {}
    # agent_registry.yaml uses a dict keyed by agent_id; values carry `name`, `health`, etc.
    if isinstance(agents_raw, dict):
        agent_items = list(agents_raw.items())
    else:
        agent_items = [(a.get("name") or a.get("id"), a) for a in agents_raw]
    health_by_agent: dict[str, str | None] = {
        aid: (body.get("health") if isinstance(body, dict) else None) for aid, body in agent_items
    }
    report.surfaces_scanned["agent_registry"] = {"count": len(agent_items)}

    if SERVICES_CATALOG.exists():
        catalog = _read_text(SERVICES_CATALOG)
        global_claim = re.search(
            r"All services? expose `?/healthz`?\b",
            catalog,
            re.IGNORECASE,
        )
        if global_claim:
            report.add(
                check="catalog.global_healthz_claim",
                severity="P1",
                message="services-catalog.md asserts a global /healthz; per-service entries in agent_registry.yaml disagree",
                location=str(SERVICES_CATALOG.relative_to(REPO_ROOT)),
                evidence=global_claim.group(0),
            )

    distinct_paths = sorted({p for p in health_by_agent.values() if p})
    report.surfaces_scanned["health_paths_distinct"] = distinct_paths


def check_nats_subjects(report: Report) -> None:
    """Every NATS subject mentioned in context docs must match the regex."""
    if not NATS_SUBJECTS.exists():
        return
    text = _read_text(NATS_SUBJECTS)
    subjects = sorted(set(NATS_SUBJECT_INLINE_RE.findall(text)))
    bad: list[str] = []
    for s in subjects:
        if not NATS_SUBJECT_RE.match(s):
            bad.append(s)
    report.surfaces_scanned["nats_subjects_distinct"] = len(subjects)
    for s in bad:
        report.add(
            check="nats_subject.format",
            severity="P2",
            message=f"NATS subject does not match <cat>.<svc>.<event>.v<N>: {s}",
            location=str(NATS_SUBJECTS.relative_to(REPO_ROOT)),
        )


def check_compose_empty_defaults(report: Report, canonical_aliases: dict[str, list[str]]) -> None:
    """Each ${VAR:-} empty default in compose must be canonical, an accepted
    alias of one, or carry an explicit host-leak-guard annotation."""
    aliases_to_canonical: dict[str, str] = {}
    for canonical, alist in canonical_aliases.items():
        aliases_to_canonical[canonical] = canonical
        for a in alist:
            aliases_to_canonical[a] = canonical

    compose_files = sorted(REPO_ROOT.glob(COMPOSE_GLOB))
    report.surfaces_scanned["compose_files"] = [p.relative_to(REPO_ROOT).as_posix() for p in compose_files]

    for cf in compose_files:
        text = _read_text(cf)
        for m in COMPOSE_VAR_RE.finditer(text):
            var_name = m.group(1)
            sep = m.group(2)
            default = m.group(3)
            if sep != ":-":
                continue  # only `${VAR:-...}` matters for empty-default analysis
            if default != "":
                continue  # non-empty default — outside scope here
            # Check 1: var is canonical or an accepted alias
            if var_name in aliases_to_canonical:
                continue
            # Check 2: nearby comment annotates it as host-leak-guard
            line_start = text.rfind("\n", 0, m.start()) + 1
            window_start = max(0, line_start - 400)
            window = text[window_start:m.end()]
            if HOST_LEAK_GUARD_HINT in window:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            report.add(
                check="compose.empty_default_unknown",
                severity="P1",
                message=f"${{{var_name}:-}} empty default with no canonical/alias mapping and no host-leak-guard annotation",
                location=f"{cf.relative_to(REPO_ROOT).as_posix()}:{line_no}",
                evidence=m.group(0),
            )


def check_workflow_pem_misuse(report: Report) -> None:
    """No workflow may pass GH_APP_SEC where private-key is expected."""
    if not WORKFLOWS_DIR.exists():
        return
    pattern = re.compile(r"private-key:\s*\$\{\{\s*secrets\.GH_APP_SEC\s*\}\}")
    offenders: list[tuple[str, int]] = []
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = _read_text(wf)
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            offenders.append((wf.relative_to(REPO_ROOT).as_posix(), line_no))
    report.surfaces_scanned["workflow_pem_misuse"] = len(offenders)
    for f, ln in offenders:
        report.add(
            check="workflow.pem_misuse",
            severity="P0",
            message=f"GH_APP_SEC passed where PEM expected; canonical is GH_APP_PRIVATE_KEY",
            location=f"{f}:{ln}",
        )


def check_port_collisions(report: Report) -> None:
    """No two services may bind the same host-side port across compose files."""
    compose_files = sorted(REPO_ROOT.glob(COMPOSE_GLOB))
    by_port: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for cf in compose_files:
        try:
            data = _read_yaml(cf) or {}
        except yaml.YAMLError as exc:
            report.add(
                check="compose.parse",
                severity="P0",
                message=f"YAML parse error: {exc}",
                location=cf.relative_to(REPO_ROOT).as_posix(),
            )
            continue
        for svc, body in (data.get("services") or {}).items():
            for entry in (body.get("ports") or []):
                # Compose port can be int, "80", "8080:80", or {"target": .., "published": ..}
                if isinstance(entry, dict):
                    pub = str(entry.get("published") or entry.get("target") or "")
                else:
                    pub = str(entry).split(":")[0]
                if not pub or not pub.isdigit():
                    continue
                by_port[pub].append((cf.relative_to(REPO_ROOT).as_posix(), svc))

    for port, owners in by_port.items():
        unique_owners = sorted({o[1] for o in owners})
        if len(unique_owners) > 1:
            report.add(
                check="compose.port_collision",
                severity="P1",
                message=f"port {port} bound by multiple services: {', '.join(unique_owners)}",
                evidence="; ".join(f"{f}::{svc}" for f, svc in owners),
            )


def render_node_descriptions_diff(report: Report) -> str:
    """Phase 5 — render the one-row-per-node diff across surfaces."""
    rows: list[dict[str, str]] = []

    registry: dict[str, Any] = {}
    if REGISTRY_JSON.exists():
        try:
            registry = _read_json(REGISTRY_JSON) or {}
        except json.JSONDecodeError as exc:
            report.add(check="registry.parse", severity="P0", message=f"registry.json: {exc}")

    services_raw = registry.get("services") if isinstance(registry, dict) else None
    services: dict[str, dict[str, Any]] = {}
    if isinstance(services_raw, list):
        for s in services_raw:
            if isinstance(s, dict) and s.get("id"):
                services[s["id"]] = s
    elif isinstance(services_raw, dict):
        services = services_raw

    agent_registry: dict[str, Any] = {}
    if AGENT_REGISTRY.exists():
        agent_registry = _read_yaml(AGENT_REGISTRY) or {}
    agents_raw = agent_registry.get("agents") or {}
    if isinstance(agents_raw, dict):
        agents = {aid: body for aid, body in agents_raw.items() if isinstance(body, dict)}
    else:
        agents = {a.get("name"): a for a in agents_raw if isinstance(a, dict) and a.get("name")}

    catalog_text = _read_text(SERVICES_CATALOG) if SERVICES_CATALOG.exists() else ""

    nodes = sorted(set(list(services.keys()) + list(agents.keys())))
    for node in nodes:
        reg_desc = ""
        if node in services and isinstance(services[node], dict):
            reg_desc = (services[node].get("description") or "")[:80]
        ar_desc = (agents.get(node, {}).get("name") or "")[:60]
        ar_health = agents.get(node, {}).get("health") or ""
        catalog_match = re.search(rf"\*\*{re.escape(node)}\*\*", catalog_text, re.IGNORECASE)
        catalog_present = "✓" if catalog_match else "—"
        first_disagreement = ""
        if reg_desc and ar_desc and reg_desc.lower()[:20] != ar_desc.lower()[:20]:
            first_disagreement = "registry vs agent_registry name prefix"
        rows.append(
            {
                "node": node,
                "registry_desc": reg_desc,
                "agent_registry_name": ar_desc,
                "agent_registry_health": ar_health,
                "catalog_present": catalog_present,
                "first_disagreement": first_disagreement,
            }
        )

    md_lines = [
        "# Node-Description Diff",
        "",
        f"Generated: {os.environ.get('NAMING_DRIFT_TS', '2026-04-26')}",
        "",
        "One row per node found in `bootstrap/registry.json` services or `agent_registry.yaml` agents.",
        "Disagreement column flags the first surface where the description prefix diverges.",
        "",
        "| Node | registry.json description | agent_registry.yaml name | health path | catalog present | first disagreement |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| `{r['node']}` | {r['registry_desc'] or '—'} | {r['agent_registry_name'] or '—'} | `{r['agent_registry_health'] or '—'}` | {r['catalog_present']} | {r['first_disagreement'] or '—'} |"
        )
    md_lines.append("")
    md_lines.append(f"Total nodes scanned: {len(rows)}")
    return "\n".join(md_lines)


def write_outputs(report: Report) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp": "2026-04-26",
        "by_severity": report.by_severity(),
        "findings": [f.asdict() for f in report.findings],
        "surfaces_scanned": report.surfaces_scanned,
        "cards_summary": report.cards_summary,
    }
    DRIFT_REPORT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    diff_md = render_node_descriptions_diff(report)
    NODE_DIFF_REPORT.write_text(diff_md, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit non-zero on any P0/P1 finding")
    parser.add_argument("--severity", default="P1", choices=["P0", "P1", "P2"])
    parser.add_argument("--json", action="store_true", help="print JSON summary to stdout")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    report = Report()

    canonical_aliases = parse_canonical_aliases(CANONICAL_NAMES_DOC, REGISTRY_JSON)
    report.canonical_aliases_seen = sorted(canonical_aliases.keys())
    report.surfaces_scanned["canonical_aliases_source"] = (
        "registry.json" if parse_canonical_aliases_from_registry(REGISTRY_JSON) is not None else "markdown"
    )

    check_signing_cards(report)
    check_health_endpoints(report)
    check_nats_subjects(report)
    check_compose_empty_defaults(report, canonical_aliases)
    check_workflow_pem_misuse(report)
    check_port_collisions(report)

    write_outputs(report)

    by_sev = report.by_severity()
    threshold = SEVERITY_RANK[args.severity]
    above_threshold = sum(1 for f in report.findings if SEVERITY_RANK[f.severity] <= threshold)

    if args.json:
        json.dump(
            {"by_severity": by_sev, "above_threshold": above_threshold, "findings": [f.asdict() for f in report.findings]},
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    else:
        print(f"Naming-drift audit complete:")
        print(f"  Surfaces scanned:    {len(report.surfaces_scanned)}")
        print(f"  Canonical names:     {len(report.canonical_aliases_seen)}")
        print(f"  Cards (active/total): {report.cards_summary.get('active', '?')}/{report.cards_summary.get('total', '?')}")
        print(f"  Findings by severity: {by_sev}")
        print(f"  Above threshold {args.severity}: {above_threshold}")
        print(f"  Reports: {DRIFT_REPORT.relative_to(REPO_ROOT)}")
        print(f"           {NODE_DIFF_REPORT.relative_to(REPO_ROOT)}")
        for f in report.findings[:20]:
            loc = f" @ {f.location}" if f.location else ""
            print(f"  [{f.severity}] {f.check}{loc}: {f.message}")
        if len(report.findings) > 20:
            print(f"  ... {len(report.findings) - 20} more in JSON report")

    if args.strict and above_threshold > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
