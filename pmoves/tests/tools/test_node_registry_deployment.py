"""node-registry is deployable, and its port is the one the catalogue names.

THE DEFECT THIS RATCHET EXISTS FOR
-----------------------------------
`pmoves/services/node_registry/` was a complete service -- subscriber,
storage, HTTP API, a `/healthz` route -- and it could not be run at all.
It had no Dockerfile, no compose service entry and no Make target, so the
layered bring-up never started it. That is the R8/R8a row of
`pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md`, open since
2026-08-25.

The preflight called the port an operator decision and left it there. It was
not a decision, it was a DEFECT, and the answer was already written down in
two places the code disagreed with:

  - `pmoves/tests/utils/service_catalog.py`  NODE_REGISTRY.port = 8115
  - `pmoves/docs/infrastructure/DISTRIBUTED_COMPUTE_SERVICES.md`  ":8115"

while the code said 8082 in six places. 8082 is not a free port: it is
media-audio's live host binding. So the code was claiming another service's
port, and -- worse -- the consumers that pointed at the node registry
(`pmoves/services/work_marshaling/`, `pmoves/services/vllm_orchestrator/`)
carried the SAME 8082 default. Leaving those alone would not have produced a
connection error: 8082 answers. It would have pointed them at media-audio.

HOW EACH FORMAT IS PARSED, AND WHY
----------------------------------
The rule here is that a check uses the PARSER for the format it is reading,
and a regex only where no parser exists.

  Python source  -> AST (`ast.parse`), NOT regex.
      The same lane's Windows POSIX ratchet
      (`pmoves/tests/tools/test_windows_posix_ratchet.py`) already walks the
      AST, so this is the house precedent, and it is the only way to tell
      this service's own port from the NATS port it carries as DATA. A
      regex over "port" and a nearby number cannot: it matches
      `port INTEGER DEFAULT 4222` in the storage schema and
      `payload.get("port", 4222)` in the announce handler -- both of which
      are the NATS server's port, not this service's, and both of which a
      fuzzy rule would report as violations. The AST knows the difference:
      a parameter named `port` with an `int` annotation and a literal
      default is a binding; a keyword argument whose value is a CALL is
      not.

  Compose YAML   -> pydantic models over the parsed YAML.
      The compose contract is a contract, so it is expressed as a typed,
      validated model rather than as `dict["healthcheck"]["test"]` chains
      that raise KeyError on a shape change. A malformed entry now fails
      with a pydantic validation error naming the field, instead of an
      AttributeError three frames away from the cause.

  Makefile       -> regex. Make has no parser and no schema.
  Compose's own `${VAR:-default}` interpolation -> regex. It is compose's
      own syntax, and the default has to be resolved before the host port
      can be read (the default may itself contain a colon, as `0.0.0.0`
      does, so a naive split reads the wrong field).

WHAT THIS FILE ASSERTS, AND WHAT IT DELIBERATELY DOES NOT
----------------------------------------------------------
It asserts the three obligations that were missing, and it asserts the port
AGREEMENT across all three of them -- the source defaults, the compose
binding, and the catalogue. The point is not "the number 8115 appears"; it
is "every place that names this service's port names the SAME port, and
that port is the catalogue's".

SCOPE OF THE COLLISION CHECK, AND WHY IT IS NOT WIDER
------------------------------------------------------
The collision assertion covers the DEFAULT STACK -- the compose files
`STACK_FILES` names in `pmoves/Makefile` -- because that is the set that is
actually brought up together.

It is deliberately NOT "every compose file in pmoves/". `pmoves/` holds
dozens, and `pmoves/docker-compose.yt-cookies.yml` binds
`${YT_COOKIE_REFRESHER_BIND:-127.0.0.1}:${YT_COOKIE_REFRESHER_PORT:-8126}:8115`
for `yt-cookie-refresher`
-- a SECOND claimant of the canonical node-registry port. That overlay is
not in `STACK_FILES` and the service is behind the `yt-cookies` profile, so
it is not a default-stack collision. It IS a latent one and it is reported
to the operator as a separate defect; a ratchet that is red on the day it
lands teaches the fleet to ignore it.

(That binding was `:8115:8115` until the carry-over-closure lane moved the
host port to 8126 on 2026-11-01, which is why it is no longer a second
claimant. The paragraph above records the SHAPE of the finding, not a live
collision.)

A WIDER SCOPE WOULD ALSO BE WRONG FOR A SECOND REASON: the same service
appears in BOTH `docker-compose.yml` and an overlay (model-registry, wger,
botz-gateway, pinokio_bridge, nats_event_bus, pmoves-yt). Compose MERGES an
overlay with its base, so that is ONE container, not two claimants of one
port. Counting claims per SERVICE rather than per file is what makes the
check mean what it says.

AND IT IS NOT THE EXISTING GATE
------------------------------
`pmoves/tests/smoke/test_compose_structure.py::test_cross_compose_port_conflicts`
cannot answer this question. It resolves a host port only when the
left-of-colon side is a bare number, so every `${VAR:-127.0.0.1}` binding is
SKIPPED -- and the bindings in this repo are nearly all in that form. This
ratchet resolves the default and reads the HOST field properly.

THE NEGATIVE CONTROL
--------------------
`test_the_port_assertion_detects_a_reverted_port` feeds MUTATED IN-MEMORY
text to the SAME checkers the positive tests use and requires them to report
the violation. A check that cannot be seen to fail is a check that cannot
say no.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = REPO_ROOT / "pmoves"
SERVICE_DIR = PMOVES_DIR / "services" / "node_registry"
COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"
MAKEFILE = PMOVES_DIR / "Makefile"
DOCKERFILE = SERVICE_DIR / "Dockerfile"
REQUIREMENTS = SERVICE_DIR / "requirements.txt"

SERVICE_NAME = "node-registry"

# The parameter names that name THIS SERVICE's own listening port.
_OWN_PORT_PARAMS = ("port", "api_port")

# `${VAR:-default}` -> `default`. A compose port binding is nearly always
# written in this form, so the HOST port has to be resolved before it can be
# compared with anything.
_ENV_DEFAULT = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}")

# `STACK_FILES ?= \` in pmoves/Makefile -- the compose files the default
# bring-up composes together. Make has no parser, so this is read as text.
_STACK_FILES = re.compile(r"^STACK_FILES \?= \\\n((?:\t.*\n)+)", re.MULTILINE)

# A third-party import is a module name that is not in the standard library
# and is not a relative or project import.
_IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)

# The port in a DOCSTRING: "port 8115", "port: 8115", "api_port=8115".
# The leading lookbehind keeps "report"/"export" from matching.
_DOCSTRING_PORT = re.compile(
    r"(?<![A-Za-z])(?:api_)?port\b\s*[:=]?\s*(\d{4})", re.IGNORECASE
)


# --------------------------------------------------------------------------
# the compose contract, as a validated model
# --------------------------------------------------------------------------
class _Healthcheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    test: list[str] | str | None = None
    interval: str | None = None
    timeout: str | None = None
    retries: int | None = None
    start_period: str | None = None


class _Dependency(BaseModel):
    model_config = ConfigDict(extra="allow")

    condition: str | None = None
    required: bool | None = None


class _ServiceBlock(BaseModel):
    """One compose service, validated.

    `extra="allow"` on purpose: compose files grow new keys constantly, and
    a ratchet that fails on an unknown key would be red on the day it lands
    for a reason that has nothing to do with the thing it checks.
    """

    model_config = ConfigDict(extra="allow")

    image: str | None = None
    # compose's `build:` has a SHORT form -- `build: ./services/hf-agent` --
    # as well as the long mapping form. The validated model says so
    # explicitly; a `dict`-only model rejects ~12 services in this file on
    # the day it lands, which is a ratchet that is red before it checks
    # anything.
    build: dict[str, Any] | str | None = None
    restart: str | None = None
    environment: list[str] | int | None = None
    ports: list[str | int] = Field(default_factory=list)
    # `depends_on:` has a short LIST form (`- nats`) and a long mapping form
    # (`nats: {condition: service_healthy}`). Same for `networks:`, which may
    # also be a mapping carrying per-network `aliases`. Both forms occur in
    # this repo, so the model accepts both and the checks read whichever
    # shape is present.
    depends_on: dict[str, _Dependency | None] | list[str] | None = None
    healthcheck: _Healthcheck | None = None
    profiles: list[str] = Field(default_factory=list)
    networks: list[str] | dict[str, Any] | None = None


class _ComposeFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    services: dict[str, _ServiceBlock] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _catalog_port() -> int:
    """The port the SERVICE CATALOGUE gives this service.

    Read from the catalogue rather than hardcoded, so this ratchet tracks the
    catalogue instead of carrying a second copy of the number it checks.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from pmoves.tests.utils.service_catalog import NODE_REGISTRY
    finally:
        sys.path.remove(str(REPO_ROOT))
    return NODE_REGISTRY.port


def _service_sources() -> dict[str, str]:
    """Every module of the service, as text, keyed by file name."""
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(SERVICE_DIR.glob("*.py"))
    }


def _int_literal(node: ast.AST) -> int | None:
    """The value of a plain integer literal, or None.

    "Plain" is the point: a keyword argument whose value is a CALL
    (`port=int(payload.get("port", 4222) or 4222)`) is not this service's
    own port, and neither is a subscript. Only a literal counts.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _own_port_sites(text: str) -> list[tuple[str, int]]:
    """Every place this source names THIS SERVICE's own port.

    Returns (site description, port). The AST decides what counts:

      - a FUNCTION PARAMETER named `port`/`api_port` with an `int`
        annotation and a literal default -- that is a binding;
      - a KEYWORD ARGUMENT named `port`/`api_port` whose value is a plain
        integer literal -- that is a binding;
      - `os.getenv("NODE_REGISTRY_PORT", "<digits>")` -- the env default;
      - a DOCSTRING that names the port -- the usage example.

    What it does NOT count, structurally rather than by luck: the NATS port
    this service carries as data (`port INTEGER DEFAULT 4222` in the
    storage schema, `payload.get("port", 4222)` in the announce handler).
    A keyword argument whose value is a CALL is not a binding.
    """
    tree = ast.parse(text)
    sites: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            defaults = args.defaults
            for arg_node, default in zip(args.args[-len(defaults):], defaults):
                if arg_node.arg not in _OWN_PORT_PARAMS:
                    continue
                annotation = (
                    ast.unparse(arg_node.annotation) if arg_node.annotation else None
                )
                if annotation not in ("int", "int | None"):
                    continue
                value = _int_literal(default)
                if value is not None:
                    sites.append((f"{node.name}(): parameter {arg_node.arg}", value))

        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg not in _OWN_PORT_PARAMS:
                    continue
                value = _int_literal(keyword.value)
                if value is not None:
                    sites.append((f"call keyword {keyword.arg}", value))
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "getenv"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "NODE_REGISTRY_PORT"
                and len(node.args) > 1
            ):
                default = node.args[1]
                if (
                    isinstance(default, ast.Constant)
                    and isinstance(default.value, str)
                    and default.value.isdigit()
                ):
                    sites.append((
                        'os.getenv("NODE_REGISTRY_PORT", ...)',
                        int(default.value),
                    ))

        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                owner = getattr(node, "name", "<module>")
                for match in _DOCSTRING_PORT.finditer(docstring):
                    sites.append((f"{owner}(): docstring", int(match.group(1))))

    return sites


def _source_port_violations(text: str, catalog_port: int) -> list[str]:
    """The ways this text names a port other than the catalogue's.

    Returns a list of violations -- an empty list is the PASS, and the
    caller asserts on its length, so the check can say no.
    """
    violations: list[str] = []
    for site, value in _own_port_sites(text):
        if value != catalog_port:
            violations.append(
                f"{site} names port {value}, but the catalogue says {catalog_port}"
            )
    return violations


def _resolve_env_defaults(text: str) -> str:
    """`${VAR:-default}` -> `default`."""
    return _ENV_DEFAULT.sub(lambda m: m.group(1), str(text))


def _host_port(entry: object) -> int | None:
    """The HOST port a compose `ports:` entry publishes, or None.

    Handles the three shapes that occur here:
      "8115"                 -> container only, no host port
      "8115:8115"            -> host 8115
      "0.0.0.0:8115:8115"    -> host 8115
    The `${VAR:-default}` prefix is resolved FIRST, because the default may
    itself contain a colon (`0.0.0.0`) and a naive split would then read the
    wrong field.
    """
    text = _resolve_env_defaults(entry).strip().strip('"').strip("'")
    parts = text.split(":")
    if len(parts) == 1:
        return None
    candidate = parts[0] if len(parts) == 2 else parts[1]
    return int(candidate) if candidate.isdigit() else None


def _compose_file(compose_text: str) -> _ComposeFile:
    """The compose file, parsed and VALIDATED."""
    import yaml

    return _ComposeFile.model_validate(yaml.safe_load(compose_text) or {})


def _depends_on_names(block: _ServiceBlock) -> list[str]:
    """The services this block depends on, from either legal `depends_on` form."""
    depends = block.depends_on
    if isinstance(depends, dict):
        return list(depends)
    if isinstance(depends, list):
        return list(depends)
    return []


def _dependency_condition(block: _ServiceBlock, name: str) -> str | None:
    """The `condition:` of a dependency, or None when it has none.

    The short list form (`- nats`) carries no condition at all -- there is
    no condition to read, and saying so is different from saying the
    condition is something else.
    """
    depends = block.depends_on
    if not isinstance(depends, dict):
        return None
    dependency = depends.get(name)
    if dependency is None:
        return None
    return dependency.condition


def _compose_service(compose_text: str, service_name: str) -> _ServiceBlock | None:
    """One service's validated block out of a compose file's text."""
    return _compose_file(compose_text).services.get(service_name)


def _compose_port_violations(
    compose_text: str, service_name: str, catalog_port: int
) -> list[str]:
    """The ways this compose file names a port other than the catalogue's."""
    violations: list[str] = []
    block = _compose_service(compose_text, service_name)
    if block is None:
        violations.append(f"the compose file declares no `{service_name}` service")
        return violations
    if not block.ports:
        violations.append(f"`{service_name}` publishes no host port at all")
        return violations
    for entry in block.ports:
        host = _host_port(entry)
        if host is None:
            violations.append(
                f"`{service_name}` publishes {entry!r}, whose host port could "
                f"not be resolved -- an unresolvable binding is not a pass"
            )
        elif host != catalog_port:
            violations.append(
                f"`{service_name}` publishes host port {host}, but the "
                f"catalogue says {catalog_port}"
            )
    return violations


def _default_stack_files() -> list[str]:
    """The compose files the default bring-up composes together."""
    match = _STACK_FILES.search(MAKEFILE.read_text(encoding="utf-8"))
    assert match, "pmoves/Makefile does not declare STACK_FILES"
    return re.findall(r"-f (\S+)", match.group(1))


def _stack_port_claimants() -> dict[int, set[str]]:
    """host port -> the DISTINCT SERVICES claiming it in the default stack.

    Keyed by service name, not by file: compose MERGES an overlay with its
    base, so a service named in both is one container, not two claimants.
    """
    claimants: dict[int, set[str]] = {}
    for name in _default_stack_files():
        path = PMOVES_DIR / name
        if not path.exists():
            continue
        compose = _compose_file(path.read_text(encoding="utf-8"))
        for service, block in compose.services.items():
            for entry in block.ports:
                host = _host_port(entry)
                if host is not None:
                    claimants.setdefault(host, set()).add(service)
    return claimants


def _docker_guard():
    """The session's docker-guard module.

    `pmoves/tests/conftest.py` loads it under this module name and installs it
    process-wide, so this returns the SAME module the guard is enforcing with.
    """
    name = "pmoves_tests_destructive_docker_guard"
    if name in sys.modules:
        return sys.modules[name]
    import importlib.util

    guard_file = Path(__file__).resolve().parents[1] / "_destructive_docker_guard.py"
    spec = importlib.util.spec_from_file_location(name, guard_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _make_plan_env(stub_dir: Path) -> dict[str, str]:
    """A PATH the docker guard accepts for a `make` spawn.

    THE SANCTIONED HELPER IS `build_stub_env`, NOT A HAND-ROLLED STUB DIR.

    The guard's `is_stub_dir()` requires each recorder to be EXECUTABLE --
    `_is_recorder()` tests `os.access(path, os.X_OK)`. A file Python wrote is
    0644, and `os.access(..., X_OK)` reports that as executable on WINDOWS
    (where `X_OK` is a no-op on a regular file) and as NOT executable on
    LINUX. So a hand-rolled stub dir passed on the operator's platform and
    was REFUSED on CI, where the guard raised `DestructiveDockerCallBlocked`
    and this test failed for a reason that had nothing to do with
    node-registry. `build_stub_env` chmods 0o755, which is correct on both.

    `stub_make=False` is required, and the reason is the opposite one: the
    REAL make must run, because `make -n` printing the recipe IS the
    assertion. docker/docker-compose/supabase still resolve to recorders, and
    the node-registry recipe carries no `$(MAKE)`, so `-n` runs nothing.
    """
    return dict(_docker_guard().build_stub_env(stub_dir, stub_make=False))


# --------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------
def test_node_registry_code_default_and_compose_binding_match_catalog_port() -> None:
    """The source default, the compose binding and the catalogue all AGREE.

    This is the test the lane's mutation-kill harness targets: it reverts the
    compose host binding to 8082 and separately reverts `api.py`'s default to
    8082, and REQUIRES this test to fail either time. A revert that this
    test does not catch is a revert the fleet would ship.

    Three things are asserted, and they are the three places the port is
    named:
      - every own-port site in the service's source equals the catalogue's
        port;
      - the service's compose binding publishes the catalogue's port;
      - the sweep is NOT vacuous -- it found the six sites measured when
        this was written, and it must keep finding them.
    """
    catalog_port = _catalog_port()

    sources = _service_sources()
    assert sources, f"no source files found under {SERVICE_DIR}"

    found_total = 0
    for name, text in sources.items():
        violations = _source_port_violations(text, catalog_port)
        assert not violations, (
            f"{name} names a port other than the catalogue's {catalog_port}: "
            + "; ".join(violations)
        )
        found_total += len(_own_port_sites(text))

    # The sweep must not have silently stopped matching. At the time of
    # writing the service named its own port in six places; the count may
    # GROW, but if it SHRINKS the port configuration surface changed and
    # that has to be re-measured rather than accepted silently.
    assert found_total >= 6, (
        f"the port sweep found {found_total} own-port sites in "
        f"{SERVICE_DIR.name}/, expected at least 6 -- either the service "
        f"stopped naming its port, or the sweep stopped matching. Both "
        f"need re-measuring; neither may pass unnoticed."
    )

    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    violations = _compose_port_violations(compose_text, SERVICE_NAME, catalog_port)
    assert not violations, (
        "the compose entry for "
        f"{SERVICE_NAME} does not publish the catalogue's port {catalog_port}: "
        + "; ".join(violations)
    )


def test_node_registry_dockerfile_carries_the_packages_the_service_imports() -> None:
    """The image can actually start the service.

    Two separate obligations, and the second is the one that bites: the
    image must run the service's entry point AND carry everything the service
    imports at import time -- `..resource_detector.models` /
    `..resource_detector.hardware`, and `pmoves.services.common`, which
    `pmoves/services/__init__.py` imports eagerly. An image carrying only
    the service's own files imports cleanly on the host and dies in the
    container.
    """
    catalog_port = _catalog_port()
    assert DOCKERFILE.exists(), f"{DOCKERFILE} does not exist"
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "pmoves.services.node_registry.main" in text, (
        "the Dockerfile does not run the service's entry point"
    )
    assert f"EXPOSE {catalog_port}" in text, (
        f"the Dockerfile does not EXPOSE the catalogue's port {catalog_port}"
    )
    assert f"http://localhost:{catalog_port}/healthz" in text, (
        f"the Dockerfile's healthcheck does not probe the catalogue's port "
        f"{catalog_port}"
    )
    for required in ("services/resource_detector", "services/common"):
        assert required in text, (
            f"the Dockerfile does not copy {required} -- the service imports "
            f"it, so the image would fail at import time"
        )

    # Every third-party module the service imports must be DECLARED. The
    # import set is read from the source rather than hardcoded, so a new
    # third-party import cannot slip in undeclared.
    assert REQUIREMENTS.exists(), f"{REQUIREMENTS} does not exist"
    requirements = REQUIREMENTS.read_text(encoding="utf-8").lower()
    declared = {
        "nats": "nats-py",
        "supabase": "supabase",
    }
    for source_text in _service_sources().values():
        for match in _IMPORT.finditer(source_text):
            module = match.group(1)
            if module in sys.stdlib_module_names or module.startswith("_"):
                continue
            if module in {"pmoves", "services"}:
                continue
            package = declared.get(module, module)
            assert package in requirements, (
                f"the service imports {module!r} but {package!r} is not in "
                f"{REQUIREMENTS.name}"
            )


def test_node_registry_compose_service_declares_health_and_nats_dependency() -> None:
    """The compose entry is a complete entry, not a stub.

    Health is declared against the CONTAINER port (the catalogue's port) and
    the service waits for NATS, which the catalogue lists as a dependency and
    which the node registry subscribes through.
    """
    catalog_port = _catalog_port()
    block = _compose_service(
        COMPOSE_FILE.read_text(encoding="utf-8"), SERVICE_NAME
    )
    assert block is not None, (
        f"{COMPOSE_FILE.name} declares no `{SERVICE_NAME}` service"
    )

    health = block.healthcheck
    assert health is not None, f"`{SERVICE_NAME}` declares no healthcheck"
    test_command = health.test
    if isinstance(test_command, list):
        test_command = " ".join(str(part) for part in test_command)
    test_command = str(test_command or "")
    assert "/healthz" in test_command, (
        f"`{SERVICE_NAME}` has no /healthz healthcheck: {test_command!r}"
    )
    assert f":{catalog_port}" in test_command, (
        f"`{SERVICE_NAME}`'s healthcheck does not probe the catalogue's port "
        f"{catalog_port}: {test_command!r}"
    )

    assert "nats" in _depends_on_names(block), (
        f"`{SERVICE_NAME}` does not depend on nats, which the catalogue "
        f"lists and which the node registry subscribes through"
    )
    condition = _dependency_condition(block, "nats")
    assert condition == "service_healthy", (
        f"`{SERVICE_NAME}` does not wait for nats to be healthy: "
        f"condition={condition!r}"
    )


def test_node_registry_make_target_is_reachable() -> None:
    """The service is reachable from a Make target, and the target is in the
    bring-up path.

    `make -n` is a dry run: it prints the recipe and runs nothing, so the
    target's reachability can be asserted without touching Docker. The
    target must also be attached to the layered bring-up -- a service with a
    Make target nobody's bring-up calls is the same defect the lane started
    from, one layer in.
    """
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    assert "include mk/node-registry.mk" in makefile_text, (
        "pmoves/Makefile does not include mk/node-registry.mk"
    )
    mk_text = (PMOVES_DIR / "mk" / "node-registry.mk").read_text(encoding="utf-8")
    assert "up-node-registry:" in mk_text, (
        "mk/node-registry.mk declares no up-node-registry target"
    )
    assert "up-model-management:" in mk_text, (
        "mk/node-registry.mk does not attach node-registry to the layered "
        "bring-up, so `make up-model-management` still would not start it"
    )

    stub_dir = Path(tempfile.gettempdir()) / "pmoves-node-registry-stub"
    env = _make_plan_env(stub_dir)
    try:
        proc = subprocess.run(
            ["make", "-C", str(PMOVES_DIR), "-n", "up-node-registry"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        shutil.rmtree(stub_dir, ignore_errors=True)
    assert proc.returncode == 0, (
        f"`make -C pmoves -n up-node-registry` failed:\n{proc.stdout}\n{proc.stderr}"
    )
    assert SERVICE_NAME in proc.stdout, (
        f"the dry run did not mention {SERVICE_NAME}:\n{proc.stdout}"
    )


def test_node_registry_port_is_not_double_bound_in_the_default_stack() -> None:
    """In the stack that is actually brought up together, this port is ours.

    The check counts DISTINCT SERVICES, because compose merges an overlay
    with its base and a service named in both is one container.

    The scope is the default stack (`STACK_FILES`), not every compose file in
    `pmoves/`: `pmoves/docker-compose.yt-cookies.yml` binds 8115 for
    `yt-cookie-refresher`, but that overlay is not in `STACK_FILES` and the
    service sits behind the `yt-cookies` profile, so it is not a
    default-stack collision. It is a latent second claimant of the canonical
    node-registry port and is reported separately; a ratchet that is red on
    the day it lands teaches the fleet to ignore it.
    """
    catalog_port = _catalog_port()
    claimants = _stack_port_claimants()

    assert claimants.get(catalog_port) == {SERVICE_NAME}, (
        f"host port {catalog_port} in the default stack is claimed by "
        f"{sorted(claimants.get(catalog_port, set()))} -- it must be claimed "
        f"by {SERVICE_NAME} alone"
    )

    # The collider stays with its owner. 8082 is media-audio's live binding;
    # a node-registry claiming it could not bind alongside media-audio.
    assert SERVICE_NAME not in claimants.get(8082, set()), (
        f"{SERVICE_NAME} claims host port 8082, which belongs to media-audio"
    )
    assert "media-audio" in claimants.get(8082, set()), (
        "media-audio no longer holds host port 8082 -- the collider this "
        "lane moved node-registry off of has changed, and the decision "
        "should be re-measured rather than assumed"
    )


def test_the_port_assertion_detects_a_reverted_port() -> None:
    """The negative control: the same checkers, fed a reverted port.

    Both checkers are pure functions over TEXT, so the mutation is applied
    in memory and the disk is never touched. Each mutated input MUST be
    reported -- a checker that cannot be seen to fail is a checker that
    cannot say no.
    """
    catalog_port = _catalog_port()

    source_text = _service_sources()["api.py"]
    assert str(catalog_port) in source_text, (
        "the api.py source no longer names the catalogue's port, so the "
        "reverted variant below would not be a mutation at all"
    )
    reverted = source_text.replace(
        f"port: int = {catalog_port},", "port: int = 8082,"
    )
    assert reverted != source_text, "the source mutation was a no-op"
    violations = _source_port_violations(reverted, catalog_port)
    assert violations, (
        "the source port checker accepted a source that names 8082 -- the "
        "check cannot see the defect it exists to catch"
    )
    assert any("8082" in v for v in violations), (
        f"the source port checker did not NAME the offending port: {violations}"
    )

    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    # MEASURED 2026-11-01: the binding is PARAMETERISED now --
    # `"${NODE_REGISTRY_BIND:-0.0.0.0}:${NODE_REGISTRY_PORT:-8115}:8115"` --
    # so the old `":8115:8115"` anchor no longer exists and the mutation
    # below rewrote NOTHING. A negative control that mutates nothing proves
    # nothing, so the mutation now moves the HOST port's default: the
    # middle segment is the host port, and the container port stays put.
    #
    # `:-<port>}:` is unique in this file (MEASURED), so the replacement
    # touches this one binding and no other.
    reverted_compose = compose_text.replace(
        f":-{catalog_port}}}:", f":-8082}}:"
    )
    assert reverted_compose != compose_text, "the compose mutation was a no-op"
    violations = _compose_port_violations(
        reverted_compose, SERVICE_NAME, catalog_port
    )
    assert violations, (
        "the compose port checker accepted a compose entry that publishes "
        "8082 -- the check cannot see the defect it exists to catch"
    )
    assert any("8082" in v for v in violations), (
        f"the compose port checker did not NAME the offending port: {violations}"
    )
