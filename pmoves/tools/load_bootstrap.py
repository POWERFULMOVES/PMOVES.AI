"""load_bootstrap.py - load a pmoves.bootstrap/v1 CGP into a Mavis session.

The PMOVES.AI side of the harness's CGP bootstrap. Reads a CGP produced
by the Mavis harness loader (or by hand), validates it against
pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json, and returns
a Bootstrap object that the rest of the harness (orchestrator.py,
bpm_cron.py) can consume.

Why a wrapper:

- The schema is JSON Schema (Draft 2020-12); we want a typed Python
  view (dataclasses) for the harness code so consumers don't
  repeatedly parse `cgp.get("identity", {}).get("agent", "minimax")`.
- The CGP may live on disk (file path), in an env var
  (PMOVES_BOOTSTRAP_CGP), or as a raw string (test fixtures). One
  load function, three sources.
- The harness wants to know what the constraints are so it can
  enforce them in the orchestrator (e.g. no-override-existing-config
  means the orchestrator doesn't replace tools the consumer fork
  already has; no-chit-bypass means state-changing actions still
  go through pmoves-chit-sign).
- The CGP's tagged services (Tailscale/RustDesk/Hostinger/Cloudflare)
  need to land in the right env vars for the rest of the session
  to pick up. load_bootstrap handles the env-var export as a side
  effect so the harness can be unaware of the CGP shape.

Usage:

    from pmoves.tools.load_bootstrap import load_bootstrap

    bs = load_bootstrap()  # reads PMOVES_BOOTSTRAP_CGP env var
    print(bs.identity.agent)  # "minimax"
    print(bs.identity.role)  # "implementer"
    print(bs.tools)  # ["mavis__agent__create", "comfyui_client", ...]
    print(bs.services.tailscale.host)  # "powerfullmoves.tail.ts.net"

CLI:

    python -m pmoves.tools.load_bootstrap [path]
    python -m pmoves.tools.load_bootstrap --env  # reads PMOVES_BOOTSTRAP_CGP
    python -m pmoves.tools.load_bootstrap --validate  # just validate, don't export

The CGP can also be loaded as a Python dict (no schema validation)
via load_bootstrap_raw() - used by the tests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# The schema lives in pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json.
# We import jsonschema lazily so the module is importable even in environments
# without jsonschema installed (the harness will warn at runtime if the
# validator is missing).
try:
    import jsonschema
    _JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JSONSCHEMA_AVAILABLE = False

DEFAULT_CGP_PATH = "pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml"
ENV_VAR_CGP = "PMOVES_BOOTSTRAP_CGP"
ENV_VAR_CGP_PATH = "PMOVES_BOOTSTRAP_CGP_PATH"

SCHEMA_PATH = "pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json"


class BootstrapError(RuntimeError):
    """Raised when a CGP is malformed, fails schema validation, or can't be loaded.

    Distinct from a generic exception so the orchestrator can catch
    and decide whether to retry, fall back to a default CGP, or
    refuse to start the session.
    """


# ---- Typed Bootstrap objects --------------------------------------------------


@dataclass
class Identity:
    agent: str
    role: str
    skin: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Identity":
        if "agent" not in data or "role" not in data:
            raise BootstrapError(f"identity block missing required fields: {data}")
        return cls(agent=data["agent"], role=data["role"], skin=data.get("skin", ""))


@dataclass
class Services:
    """Tagged infrastructure services. All fields are optional (advisory)."""

    tailscale: dict[str, Any] = field(default_factory=dict)
    rustdesk: dict[str, Any] = field(default_factory=dict)
    hostinger: dict[str, Any] = field(default_factory=dict)
    cloudflare: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Services":
        return cls(
            tailscale=data.get("tailscale", {}) or {},
            rustdesk=data.get("rustdesk", {}) or {},
            hostinger=data.get("hostinger", {}) or {},
            cloudflare=data.get("cloudflare", {}) or {},
        )


@dataclass
class Routing:
    """Peer-agent routing table. Each peer is optional (the wire is set up
    even if the peer isn't subscribed yet)."""

    kiloclaw: dict[str, Any] = field(default_factory=dict)
    hermes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Routing":
        return cls(
            kiloclaw=data.get("kiloclaw", {}) or {},
            hermes=data.get("hermes", {}) or {},
        )


@dataclass
class Bootstrap:
    """The loaded + validated CGP for a Mavis session.

    Accessor pattern: the harness code reads `bs.identity.agent`,
    `bs.tools`, `bs.services.tailscale.host` etc. instead of poking
    at the raw dict.
    """

    raw: dict[str, Any]
    spec: str
    meta: dict[str, Any]
    identity: Identity
    tools: list[str]
    mcps: list[str]
    services: Services
    routing: Routing
    constraints: list[str]
    sig: dict[str, Any] = field(default_factory=dict)

    @property
    def has_constraint(self) -> "callable":  # type: ignore[type-arg]
        """Returns a predicate that checks if a constraint is set.

        Usage: bs.has_constraint("no-chit-bypass") -> True/False
        """
        return lambda c: c in self.constraints

    def export_env(self, prefix: str = "PMOVES_BOOTSTRAP_") -> dict[str, str]:
        """Export the CGP as env vars (for the rest of the session to consume).

        Returns the dict of vars that were exported (so the caller can
        log them or pipe them into a subprocess).
        """
        env: dict[str, str] = {}
        env[f"{prefix}AGENT"] = self.identity.agent
        env[f"{prefix}ROLE"] = self.identity.role
        if self.identity.skin:
            env[f"{prefix}SKIN"] = self.identity.skin
        env[f"{prefix}TOOLS"] = ",".join(self.tools)
        env[f"{prefix}MCPS"] = ",".join(self.mcps)
        env[f"{prefix}CONSTRAINTS"] = ",".join(self.constraints)
        if self.services.tailscale.get("host"):
            env[f"{prefix}TAILSCALE_HOST"] = str(self.services.tailscale["host"])
        if self.services.tailscale.get("ip"):
            env[f"{prefix}TAILSCALE_IP"] = str(self.services.tailscale["ip"])
        if self.services.rustdesk.get("devices"):
            env[f"{prefix}RUSTDESK_DEVICES"] = ",".join(self.services.rustdesk["devices"])
        if self.services.hostinger.get("site"):
            env[f"{prefix}HOSTINGER_SITE"] = str(self.services.hostinger["site"])
        if self.services.cloudflare.get("account"):
            env[f"{prefix}CLOUDFLARE_ACCOUNT"] = str(self.services.cloudflare["account"])
        if self.routing.kiloclaw.get("target"):
            env[f"{prefix}TARGET_KILOCLAW"] = str(self.routing.kiloclaw["target"])
        if self.routing.hermes.get("target"):
            env[f"{prefix}TARGET_HERMES"] = str(self.routing.hermes["target"])
        for k, v in env.items():
            os.environ[k] = v
        return env


# ---- Loading + validation ---------------------------------------------------


def _read_cgp(path: str | Path) -> dict[str, Any]:
    """Read a CGP from a .yaml or .json file."""
    path = Path(path)
    if not path.exists():
        raise BootstrapError(f"CGP file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _parse_cgp(text: str) -> dict[str, Any]:
    """Parse a CGP from a raw string (auto-detect YAML vs JSON)."""
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return yaml.safe_load(stripped) or {}


def _load_schema() -> dict[str, Any]:
    """Load the v1 schema from the contracts dir."""
    schema_path = Path(SCHEMA_PATH)
    if not schema_path.exists():
        raise BootstrapError(
            f"pmoves.bootstrap schema not found at {schema_path} - "
            f"is the worktree correct?"
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _validate(cgp: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate a CGP against the v1 schema. Raises BootstrapError on failure."""
    if not _JSONSCHEMA_AVAILABLE:
        # Fallback structural check: the schema's required top-level
        # fields must all be present, and spec must be the literal
        # pmoves.bootstrap/v1. This is a thin safety net for envs
        # without jsonschema; the schema should still be the source
        # of truth (this just catches the most common typos).
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in cgp:
                raise BootstrapError(
                    f"CGP missing required field: {field_name} "
                    f"(present: {sorted(cgp.keys())})"
                )
        if cgp.get("spec") != schema.get("properties", {}).get("spec", {}).get("const"):
            raise BootstrapError(
                f"CGP spec must be {schema.get('properties', {}).get('spec', {}).get('const')!r}, "
                f"got {cgp.get('spec')!r}"
            )
        return
    try:
        jsonschema.validate(instance=cgp, schema=schema)
    except jsonschema.ValidationError as exc:
        raise BootstrapError(f"CGP failed schema validation: {exc.message}") from exc


def _coerce(cgp: dict[str, Any]) -> Bootstrap:
    """Translate a raw CGP dict into a typed Bootstrap object."""
    return Bootstrap(
        raw=cgp,
        spec=cgp.get("spec", ""),
        meta=cgp.get("meta", {}) or {},
        identity=Identity.from_dict(cgp.get("identity", {}) or {}),
        tools=list(cgp.get("tools", []) or []),
        mcps=list(cgp.get("mcps", []) or []),
        services=Services.from_dict(cgp.get("services", {}) or {}),
        routing=Routing.from_dict(cgp.get("routing", {}) or {}),
        constraints=list(cgp.get("constraints", []) or []),
        sig=cgp.get("sig", {}) or {},
    )


def load_bootstrap(
    path: str | Path | None = None,
    *,
    source: str | None = None,
    export_env: bool = True,
) -> Bootstrap:
    """Load a CGP from a path, an env var, a raw string, or the default example.

    Resolution order:
    1. `path` argument if given
    2. `source` argument (raw YAML/JSON string) if given
    3. PMOVES_BOOTSTRAP_CGP env var (raw string)
    4. PMOVES_BOOTSTRAP_CGP_PATH env var (file path)
    5. DEFAULT_CGP_PATH (the example in the repo)

    Always validates against the v1 schema. By default, also exports
    the bootstrap as PMOVES_BOOTSTRAP_* env vars so the rest of the
    session can consume it.
    """
    schema = _load_schema()
    if path is not None:
        cgp = _read_cgp(path)
    elif source is not None:
        cgp = _parse_cgp(source)
    elif ENV_VAR_CGP in os.environ:
        cgp = _parse_cgp(os.environ[ENV_VAR_CGP])
    elif ENV_VAR_CGP_PATH in os.environ:
        cgp = _read_cgp(os.environ[ENV_VAR_CGP_PATH])
    else:
        cgp = _read_cgp(DEFAULT_CGP_PATH)
    _validate(cgp, schema)
    bs = _coerce(cgp)
    if export_env:
        bs.export_env()
    return bs


def load_bootstrap_raw(cgp: dict[str, Any], *, export_env: bool = True) -> Bootstrap:
    """Load a CGP from an in-memory dict, skipping file I/O.

    Used by the tests to feed fixtures directly. Always validates.
    """
    schema = _load_schema()
    _validate(cgp, schema)
    bs = _coerce(cgp)
    if export_env:
        bs.export_env()
    return bs


# ---- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="load_bootstrap", description=__doc__)
    p.add_argument("path", nargs="?", help="path to a .yaml or .json CGP")
    p.add_argument("--env", action="store_true", help="read PMOVES_BOOTSTRAP_CGP env var (raw string)")
    p.add_argument("--validate", action="store_true", help="validate only, don't export env vars")
    p.add_argument("--print", action="store_true", help="print the loaded Bootstrap as JSON and exit")
    args = p.parse_args(argv)

    try:
        if args.env:
            bs = load_bootstrap(source=os.environ.get(ENV_VAR_CGP), export_env=not args.validate)
        else:
            bs = load_bootstrap(path=args.path, export_env=not args.validate)
    except BootstrapError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.print:
        # Print a compact view: identity, tools count, services keys
        print(json.dumps({
            "spec": bs.spec,
            "identity": {
                "agent": bs.identity.agent,
                "role": bs.identity.role,
                "skin": bs.identity.skin,
            },
            "tools": bs.tools,
            "mcps": bs.mcps,
            "services": {
                "tailscale": bs.services.tailscale,
                "rustdesk": bs.services.rustdesk,
                "hostinger": bs.services.hostinger,
                "cloudflare": bs.services.cloudflare,
            },
            "routing": {
                "kiloclaw": bs.routing.kiloclaw,
                "hermes": bs.routing.hermes,
            },
            "constraints": bs.constraints,
        }, indent=2))
        return 0

    print(f"loaded CGP: spec={bs.spec!r} agent={bs.identity.agent!r} role={bs.identity.role!r}")
    print(f"  tools: {len(bs.tools)} ({', '.join(bs.tools[:3])}{'...' if len(bs.tools) > 3 else ''})")
    print(f"  mcps: {len(bs.mcps)} ({', '.join(bs.mcps[:3])}{'...' if len(bs.mcps) > 3 else ''})")
    print(f"  services: tailscale={bool(bs.services.tailscale)} rustdesk={bool(bs.services.rustdesk)} hostinger={bool(bs.services.hostinger)} cloudflare={bool(bs.services.cloudflare)}")
    print(f"  routing: kiloclaw={bs.routing.kiloclaw.get('target', 'unset')} hermes={bs.routing.hermes.get('target', 'unset')}")
    print(f"  constraints: {len(bs.constraints)} ({', '.join(bs.constraints[:3])}{'...' if len(bs.constraints) > 3 else ''})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
