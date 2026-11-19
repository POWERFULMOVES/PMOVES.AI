"""Ratchet: the /n8n slash commands must not name a container or a python
module that does not exist.

THE DEFECT CLASS
----------------
``.claude/commands/n8n/*.md`` are slash commands an agent executes. Every one
of them used to carry a second, dead path: a ``docker exec`` into a container
named ``pmoves-n8n-agent-1`` running ``python3 -c "from app_n8n_agent import
N8nClient"``. That path could not work, for TWO independent reasons, and a
reader who fixed only one of them would still ship a broken command:

  1. THE CONTAINER DOES NOT EXIST. No compose file in this repository defines
     an ``n8n-agent`` service. The live n8n containers are ``pmoves-n8n``
     (pmoves/docker-compose.n8n.yml:21), ``pmoves-n8n-runners`` (same file:71)
     and ``pmoves-n8n-db`` (pmoves/docker-compose.n8n.postgres.yml:4).
  2. THE MODULE IS NOT IN THE IMAGE EITHER. The n8n image is built from
     ``PMOVES-n8n/compose/n8n/Dockerfile``, whose entire content is
     ``FROM n8nio/n8n:2.1.0`` -- a stock image with no PMOVES python module in
     it. Repointing the container name at ``pmoves-n8n`` would therefore move
     the failure from "no such container" to
     ``ModuleNotFoundError: No module named 'app_n8n_agent'``.

So the gate derives BOTH sets from the live configuration and holds the
command files against them:

  * the container names compose files actually create, and
  * the python modules the n8n image can actually import.

NO TAUTOLOGIES
--------------
The two sets are DERIVED, not restated. The container set comes from scanning
the compose files for ``container_name:`` keys; the module set comes from
parsing the image recipe and collecting what its ``COPY``/``ADD`` instructions
bring in. The expected values in the assertions are read out of those same
derivations, never typed in by hand from the fix.

``test_the_derived_container_set_covers_the_live_n8n_fleet`` exists because a
ratchet that derives an empty set passes everything: it asserts the derivation
still finds the fleet it is supposed to be watching.

HERMETIC: no network, no docker, no nats, no gh. It reads files in this
repository.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The slash commands under audit.
COMMAND_DIR = REPO_ROOT / ".claude" / "commands" / "n8n"

#: The MCP registry entry this lane reconciled.
N8N_AGENT_YAML = REPO_ROOT / "pmoves" / "config" / "mcp" / "n8n-agent.yaml"

#: The n8n image recipe, as tracked in THIS repository (the mirror of the
#: submodule copy the compose build actually uses).
TRACKED_N8N_RECIPE = REPO_ROOT / "pmoves" / "compose" / "n8n" / "Dockerfile"

#: The authoritative recipe: the n8n compose service builds
#: ``PMOVES-n8n/compose/n8n/Dockerfile`` (pmoves/docker-compose.n8n.yml:17-19).
SUBMODULE_N8N_RECIPE = REPO_ROOT / "PMOVES-n8n" / "compose" / "n8n" / "Dockerfile"

#: The compose globs the lane contract names explicitly. These are REQUIRED to
#: contribute to the derived set -- if they stop matching, the ratchet is
#: watching a fleet that is not the one it was written for.
REQUIRED_COMPOSE_GLOBS = (
    "pmoves/docker-compose*.yml",
    "pmoves/compose/*.yml",
)

#: Directories that hold deployable compose files outside the required globs.
#: They are included so that a container which IS real, but is declared in a
#: compose file the required globs do not cover, is not reported as a false
#: positive.
EXTRA_COMPOSE_ROOTS = ("pmoves", "deploy")

#: Directories that are never scanned for compose files.
_PRUNED_DIRS = frozenset(
    {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
)

_CONTAINER_NAME_RE = re.compile(r"^[ \t]*container_name:[ \t]*(?P<value>.+?)[ \t]*$", re.M)

#: ``${VAR:-default}`` inside a container_name value.
_ENV_DEFAULT_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}")

#: A service key: two-space indent, at the top of a service block.
_SERVICE_KEY_RE = re.compile(r"^  ([A-Za-z0-9][A-Za-z0-9_.-]*):[ \t]*(?:#.*)?$", re.M)

#: A top-level compose section: `services:`, `networks:`, `volumes:`, ...
#: The indent is what separates a service key from a NETWORK or a VOLUME
#: name, because both take the same `key:` shape.
_TOP_LEVEL_SECTION_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*):[ \t]*(?:#.*)?$", re.M
)

#: ``docker exec`` with any number of flags before the container name.
_DOCKER_EXEC_RE = re.compile(
    r"docker\s+exec\s+(?:-{1,2}[^\s]+[ \t]+)*(?P<container>[A-Za-z0-9][A-Za-z0-9_.-]*)"
)

_FROM_IMPORT_RE = re.compile(r"^[ \t]*from[ \t]+(?P<mod>[A-Za-z_][A-Za-z0-9_.]*)[ \t]+import\b", re.M)
_PLAIN_IMPORT_RE = re.compile(r"^[ \t]*import[ \t]+(?P<mod>[A-Za-z_][A-Za-z0-9_.]*)", re.M)

#: A double-quoted payload -- e.g. the program in ``python3 -c "..."``.
_QUOTED_SPAN_RE = re.compile(r'"([^"]*)"')

#: Dockerfile COPY/ADD.
_COPY_RE = re.compile(r"^[ \t]*(?:COPY|ADD)[ \t]+(?P<args>.+?)[ \t]*$", re.M | re.I)

#: The module named in the defect, kept here so the failure message can point
#: at it by name rather than only by value.
RETIRED_MODULE = "app_n8n_agent"


# ── compose discovery ───────────────────────────────────────────────────────

def _walk_compose_files() -> list[Path]:
    """Every compose file this ratchet reads.

    The two REQUIRED globs come first and are always included; the extra
    roots only ever ADD containers, so including them can make the ratchet
    more permissive but never wrong.
    """
    files: set[Path] = set()

    for pattern in REQUIRED_COMPOSE_GLOBS:
        files.update(p for p in REPO_ROOT.glob(pattern) if p.is_file())

    for root_name in EXTRA_COMPOSE_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in _walk_dirs(root):
            for name in filenames:
                if name.startswith("docker-compose") and name.endswith((".yml", ".yaml")):
                    files.add(Path(dirpath) / name)
                elif name.endswith((".yml", ".yaml")) and Path(dirpath).name.startswith(
                    "docker-compose"
                ):
                    files.add(Path(dirpath) / name)

    return sorted(files)


def _walk_dirs(root: Path):
    """os.walk with the noisy directories pruned."""
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNED_DIRS]
        yield dirpath, dirnames, filenames


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(path: Path) -> str:
    """Repo-relative path when the file is inside the repo, else the raw path."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _declared_container_names() -> set[str]:
    """Container names a compose file declares with an explicit ``container_name:``."""
    names: set[str] = set()
    for path in _walk_compose_files():
        for match in _CONTAINER_NAME_RE.finditer(_read(path)):
            raw = match.group("value").split("#", 1)[0].strip()
            raw = raw.strip('"').strip("'").strip()
            if not raw:
                continue
            names.add(raw)
            for default in _ENV_DEFAULT_RE.findall(raw):
                default = default.strip().strip('"').strip("'").strip()
                if default:
                    names.add(default)
    return names


def _compose_service_keys(text: str) -> list[str]:
    """The service keys of a compose file -- the keys under ``services:``.

    SECTION CONTEXT MATTERS. A two-space-indented ``key:`` is a SERVICE only
    under ``services:``. The same shape under ``networks:`` or ``volumes:``
    names a NETWORK or a VOLUME, and ``docker exec pmoves-pmoves_api-1`` does
    not name a container. An allow-list that cannot tell the two apart
    believes the building's plumbing is a guest.

    So the scan tracks which top-level section it is inside, and a key counts
    only under ``services:``.
    """
    keys: list[str] = []
    section = ""
    for line in text.splitlines():
        top = _TOP_LEVEL_SECTION_RE.match(line)
        if top:
            section = top.group("name")
            continue
        if section != "services":
            continue
        match = _SERVICE_KEY_RE.match(line)
        if match:
            keys.append(match.group(1))
    return keys


def _compose_default_container_names() -> set[str]:
    """Compose's DEFAULT container names for services that declare no
    ``container_name:``.

    The fleet's own convention is documented in the compose files themselves --
    "No container_name: keep the compose-default ``${PROJECT}-archon-1`` name"
    (pmoves/docker-compose.agents.yml:275) -- so a ``docker exec`` naming such
    a container is legitimate and must not be reported. The project name is
    ``pmoves``, the repository's compose directory.

    Only keys that live under ``services:`` are services -- see
    ``_compose_service_keys`` for why the section context is tracked.
    """
    names: set[str] = set()
    for path in _walk_compose_files():
        for service in _compose_service_keys(_read(path)):
            names.add(f"pmoves-{service}-1")
            names.add(f"pmoves-{service}")
    return names


def _known_container_names() -> set[str]:
    """Every container name this repository can actually create."""
    return _declared_container_names() | _compose_default_container_names()


# ── the n8n image's python modules ─────────────────────────────────────────

def _n8n_image_recipes() -> list[Path]:
    """The recipes that define the n8n image.

    The submodule copy is authoritative (it is what the compose build uses);
    the tracked mirror is the always-present copy in this repository. Both are
    read when both exist.
    """
    recipes: list[Path] = []
    for candidate in (SUBMODULE_N8N_RECIPE, TRACKED_N8N_RECIPE):
        if candidate.is_file() and candidate not in recipes:
            recipes.append(candidate)
    return recipes


def _split_dockerfile_args(text: str) -> list[str]:
    """Split a Dockerfile instruction's arguments, honouring quotes."""
    args: list[str] = []
    current = ""
    quote = ""
    for char in text:
        if quote:
            if char == quote:
                quote = ""
            else:
                current += char
        elif char in ("'", '"'):
            quote = char
        elif char.isspace():
            if current:
                args.append(current)
                current = ""
        else:
            current += char
    if current:
        args.append(current)
    return args


def _local_copy_sources(recipe: Path) -> list[str]:
    """The local source paths a recipe COPYs or ADDs into the image."""
    sources: list[str] = []
    for match in _COPY_RE.finditer(_read(recipe)):
        args = _split_dockerfile_args(match.group("args"))
        if not args or args[0].startswith("--from="):
            continue
        for source in args[:-1]:  # the last argument is the destination
            if "://" in source or source.startswith("$"):
                continue
            sources.append(source)
    return sources


def _n8n_image_python_modules() -> set[str]:
    """Top-level python module names the n8n image can import.

    A python module reaches an image only through a COPY/ADD of a local
    source. The n8n recipe is ``FROM n8nio/n8n:2.1.0`` with no COPY at all, so
    this set is EMPTY -- which is exactly why importing ``app_n8n_agent``
    inside the n8n container cannot work.
    """
    modules: set[str] = set()
    for recipe in _n8n_image_recipes():
        context = recipe.parents[2] if len(recipe.parents) > 2 else recipe.parent
        for source in _local_copy_sources(recipe):
            base = (context / source).resolve()
            if base.is_dir():
                modules.add(base.name)
                modules.update(p.stem for p in base.glob("*.py"))
            elif base.is_file() and base.suffix == ".py":
                modules.add(base.stem)
    return modules


# ── the command files ───────────────────────────────────────────────────────

def _command_files() -> list[Path]:
    return sorted(COMMAND_DIR.glob("*.md")) if COMMAND_DIR.is_dir() else []


def _docker_exec_targets(text: str) -> list[str]:
    return [match.group("container") for match in _DOCKER_EXEC_RE.finditer(text)]


def _imported_modules(text: str) -> set[str]:
    """Every python module the file imports.

    Scanned twice: once over the raw text, and once over the INSIDE of every
    double-quoted payload. A command file can carry a python program as
    ``python3 -c "from x import y"`` on ONE line, where the import is not at
    the start of a line and a line-anchored scan would miss it.
    """
    modules: set[str] = set()

    def _scan(body: str) -> None:
        for match in _FROM_IMPORT_RE.finditer(body):
            modules.add(match.group("mod"))
        for match in _PLAIN_IMPORT_RE.finditer(body):
            modules.add(match.group("mod"))

    _scan(text)
    for span in _QUOTED_SPAN_RE.finditer(text):
        _scan(span.group(1))
    return modules


# ── the ratchet ─────────────────────────────────────────────────────────────

def test_no_docker_exec_target_outside_the_compose_container_set() -> None:
    """REQUIREMENT 1 and 3: every ``docker exec`` container named by an n8n
    slash command must be a container this repository can actually create.

    The defect this bites: ``docker exec pmoves-n8n-agent-1 ...`` in the
    command files. ``pmoves-n8n-agent-1`` is not a declared ``container_name:``
    and ``n8n-agent`` is not a service in any compose file, so it is in
    neither the declared set nor the compose-default set.
    """
    known = _known_container_names()
    offenders: list[str] = []
    for path in _command_files():
        text = _read(path)
        for container in _docker_exec_targets(text):
            if container not in known:
                offenders.append(f"{_rel(path)}: {container}")
    assert not offenders, (
        "an n8n slash command execs into a container no compose file creates:\n  "
        + "\n  ".join(offenders)
        + "\n\nDerive the real container names from the compose files "
        "(container_name: keys) before naming one."
    )


def test_no_command_file_imports_a_module_absent_from_the_n8n_image() -> None:
    """REQUIREMENT 2: no n8n slash command may import a python module the n8n
    image does not carry.

    A module is acceptable if it is in the standard library or is copied into
    the n8n image by its recipe. ``app_n8n_agent`` is neither: the n8n image
    is ``FROM n8nio/n8n:2.1.0`` with no COPY, and ``app_n8n_agent.py`` lives
    in the PMOVES-BoTZ submodule, not in the n8n image.
    """
    image_modules = _n8n_image_python_modules()
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    offenders: list[str] = []
    for path in _command_files():
        text = _read(path)
        for module in sorted(_imported_modules(text)):
            root = module.split(".")[0]
            if root in stdlib or root in image_modules:
                continue
            offenders.append(
                f"{_rel(path)}: {module} "
                f"(not stdlib, not in the n8n image)"
            )
    assert not offenders, (
        "an n8n slash command imports a module the n8n image does not carry:\n  "
        + "\n  ".join(offenders)
        + f"\n\nThe n8n image carries these PMOVES modules: "
        f"{sorted(image_modules) or 'NONE'}. "
        f"'{RETIRED_MODULE}' is not one of them."
    )


def test_the_n8n_image_recipe_brings_in_no_pmoves_python_module() -> None:
    """The BASIS of the import check: the n8n image is a stock n8n image.

    If this ever fails, the n8n image carries a PMOVES python module, and the
    import check above must be re-derived against that module set rather than
    against the stock one.
    """
    recipes = _n8n_image_recipes()
    assert recipes, (
        "no n8n image recipe found: neither "
        f"{_rel(SUBMODULE_N8N_RECIPE)} nor "
        f"{_rel(TRACKED_N8N_RECIPE)} exists"
    )
    for recipe in recipes:
        sources = _local_copy_sources(recipe)
        assert not any(source.endswith((".py", ".whl", ".tar.gz")) for source in sources), (
            f"{_rel(recipe)} now copies python "
            f"sources into the n8n image: {sources}. The import check in this "
            f"file must be re-derived against the new module set."
        )
    assert _n8n_image_python_modules() == set(), (
        "the n8n image now carries PMOVES python modules; re-derive the import "
        "check in this file against the new set"
    )


def test_the_derived_container_set_covers_the_live_n8n_fleet() -> None:
    """ANTI-VACUITY: the derivation must still find the fleet it watches.

    A ratchet whose derivation returns an empty set asserts nothing, and
    would pass on a repository where every compose file had been renamed.
    """
    declared = _declared_container_names()
    for expected in ("pmoves-n8n", "pmoves-n8n-runners", "pmoves-n8n-db"):
        assert expected in declared, (
            f"{expected} is not among the container names derived from the "
            f"compose files; the derivation has drifted"
        )

    required = [
        path
        for pattern in REQUIRED_COMPOSE_GLOBS
        for path in REPO_ROOT.glob(pattern)
        if path.is_file()
    ]
    assert required, (
        "none of the required compose globs matched a file: "
        + ", ".join(REQUIRED_COMPOSE_GLOBS)
    )
    assert len(declared) > 20, (
        f"only {len(declared)} container names were derived from the compose "
        f"files -- the derivation has drifted"
    )


def test_the_n8n_agent_registry_entry_keeps_its_id_and_declares_no_dead_stdio_server() -> None:
    """The MCP registry entry is reconciled, not deleted, and not left lying.

    The loader (pmoves/tools/mcp_utils.py:load_mcp_tools) reads ``id``,
    ``name``, ``required_commands``, ``setup_instructions`` and
    ``health_check``. The dead stdio server -- ``command: docker`` with
    ``args: [exec, -i, <retired container>, python, app_n8n_agent.py]`` -- is
    NOT one of those fields, so it must not be active here: it names a
    container no compose file creates and a module the image does not carry.
    The ``id`` is kept because the gateway-agent tool catalogue references it.
    """
    text = _read(N8N_AGENT_YAML)
    assert "id: n8n-agent" in text, (
        "the n8n-agent registry entry lost its id; the gateway-agent tool "
        "catalogue references that id"
    )

    active_keys = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1] not in (" ", "\t") and ":" in stripped:
            active_keys.add(stripped.split(":", 1)[0])
    assert "command" not in active_keys, (
        "the n8n-agent entry declares an active `command:` again; the stdio "
        "server it names cannot start"
    )
    assert "args" not in active_keys, (
        "the n8n-agent entry declares active `args:` again; they point at a "
        "container no compose file creates"
    )

    known = _known_container_names()
    for container in _docker_exec_targets(text):
        assert container in known, (
            f"the n8n-agent health check execs into {container}, which no "
            f"compose file creates"
        )
