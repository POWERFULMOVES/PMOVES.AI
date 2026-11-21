"""Ratchet: the Services and Integrations index must agree with the EXECUTABLE configs.

THE GOVERNING RULE
------------------
Where prose and an executable config disagree, **the executable config is the
truth and the prose is corrected**. The executable configs this ratchet reads
are the ones the fleet actually runs on:

* ``.github/workflows/integrations-ghcr.matrix.json`` -- what the CI image
  workflow (``.github/workflows/integrations-ghcr.yml``) builds and pushes.
* ``pmoves/images.yaml`` -- the published-image inventory, consumed by
  ``.github/workflows/build-images.yml``.
* ``pmoves/docker-compose*.yml`` -- the runtime.
* ``pmoves/configs/dockerfiles/_known_orphans.yaml`` -- the orphan registry.
* ``pmoves/config/mcp_inventory.json`` -- the MCP server roster.
* the filesystem itself -- a ``pmoves/services/<name>`` path either exists or
  it does not.

The document under test is ``docs/PMOVES.AI Services and Integrations.md``.
It is a *human-readable index*, so every claim it makes about a path, an
image name, an MCP server name and a published Dockerfile has to be derivable
from one of the configs above.

WHY THIS EXISTS -- THE FIVE DEFECTS THIS GATES
-----------------------------------------------
This lane was opened by five MEASURED documentation-drift defects. Each one
was a prose statement that the executable config contradicted. A prose fix
that is not gated rots back, so each defect now has an assertion here:

* **F1 -- Archon.** The doc declared Archon's path as
  ``pmoves/services/archon``. MEASURED: ``pmoves/services/`` has no
  ``archon`` directory (it has 101 sibling directories, from ``agent_zero``
  to ``yt-cookie-writer``). Archon's real locations are the repo-root
  submodule ``PMOVES-Archon`` and the nested submodule
  ``pmoves/integrations/archon``.
* **F2 -- the pmoves-yt THREE-WAY CONTRADICTION.** Three files named three
  different Dockerfiles for ONE published image. The live matrix entry
  (``name: pmoves-yt``) declares ``context: PMOVES.YT`` and
  ``dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile``; the doc and the
  orphan registry both named ``pmoves/services/pmoves-yt/Dockerfile`` as the
  published source. The matrix is the truth.
* **F3 -- the jellyfin-ai triple.** ``pmoves/images.yaml`` publishes
  ``pmoves-jellyfin-ai-api-gateway``, ``pmoves-jellyfin-ai-dashboard`` and
  ``pmoves-jellyfin-ai-audio-processor``; the doc named NONE of them.
* **F4 -- pmoves-docker-gateway-sse.** An MCP server entry (NOT a published
  image) that the doc never named.
* **F5 -- the integrations inventory.** ``pmoves/integrations/`` holds EIGHT
  directories; the README listed four.

THE TWO DEFECTS THE REVIEW FOUND
--------------------------------
A second review of this lane found two more prose-vs-executable contradictions,
both of which rot back unless they are gated:

* **F6 -- the published-image inventory was incomplete.** The doc claimed
  "every image the fleet publishes is declared in ``pmoves/images.yaml``",
  which its own next paragraph contradicted: the CI image workflow is a
  SECOND publisher, driven by
  ``.github/workflows/integrations-ghcr.matrix.json``. MEASURED: the matrix
  publishes 15 images and ``pmoves/images.yaml`` declares 32, and FIVE of
  the matrix's images are in no ``pmoves/images.yaml`` entry --
  ``pmoves-archon-ui``, ``pmoves-firefly-iii``, ``pmoves-deepresearch``,
  ``pmoves-supaserch`` and ``pmoves-a2ui-renderer``. The published-image set
  is therefore the UNION of the two publishers, and the inventory table must
  carry all of it.
* **F7 -- the gateway listener's profile selection was fiction.** The doc
  claimed that an unset ``PMOVES_MCP_PROFILE_ID`` sends the listener through
  ``pmoves/tools/node_gateway_profile.py`` (pinned node profile -> hardware
  detection -> REFUSE, never a guess). MEASURED, the listener assigns the
  LITERAL fallback
  ``PROFILE_ID="${PMOVES_MCP_PROFILE_ID:-pmoves_5090_web}"`` and never calls
  the resolver; the resolver belongs to
  ``pmoves/scripts/mcp-toolkit-connect.sh``. An operator on a node that does
  not serve that profile would have believed the listener selects or refuses
  the right one.

THE SCOPE OF THE MCP ASSERTION -- AND WHY IT IS NARROWER THAN "EVERY KEY"
-------------------------------------------------------------------------
Requirement: every name in ``pmoves/config/mcp_inventory.json`` must appear
in the doc. MEASURED against the live inventory, "every key" is NOT a
defensible rule, because the inventory deliberately mixes two different
things:

1. **PMOVES-hosted servers** -- served over HTTP/SSE by a PMOVES node. These
   are SERVICES this repo operates, and this document indexes services, so
   every one of them must be named here.
2. **Client configuration** -- hosted third-party endpoints the inventory
   marks ``endpoint: external`` (Composio Connect, Titan Mail), and the
   stdio entries that spawn a client-side process (``npx`` / ``uvx`` / ``uv``
   / ``docker exec`` servers such as ``huggingface``, ``tailscale``,
   ``supabase-db``, ``jcodemunch``). These are not services in the monorepo;
   forcing them into a services index would make the document inaccurate.

So the rule is DERIVED FROM THE INVENTORY, not hard-coded: an entry is in
scope when ``transport`` is ``http`` or ``sse`` AND ``endpoint`` is ``local``
or ``fleet``. That resolves to seven keys today:
``agent-zero``, ``composio-local``, ``flute-voice``, ``flute-voice-mcp``,
``pmoves-cipher``, ``pmoves-cipher-local``, ``pmoves-docker-gateway-sse``.
The scope rule is a MODULE CONSTANT below, so a change to the inventory that
widens or narrows the hosted set is visible in the diff rather than buried
in a literal.

MUTATION-KILL
-------------
``pmoves/tests/tools/test_integration_reconciliation_ratchet_mutation_kill.py``
is the companion harness. It puts each of the SEVEN defects back into the live
tree and requires the NAMED test here to die.

Hermetic: no network, no docker, no NATS, no gh, no credentials.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

# This file lives at `<repo>/pmoves/tests/tools/<name>.py`:
#   parents[0] = tools,  parents[1] = tests,  parents[2] = pmoves
#   parents[3] = the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = REPO_ROOT / "pmoves"

#: The document under test.
DOC = REPO_ROOT / "docs" / "PMOVES.AI Services and Integrations.md"

#: What the CI image workflow builds and pushes. THE authority for F2.
CI_MATRIX = REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.matrix.json"

#: The published-image inventory.
IMAGES_YAML = PMOVES_DIR / "images.yaml"

#: The orphan-Dockerfile registry.
ORPHANS_YAML = PMOVES_DIR / "configs" / "dockerfiles" / "_known_orphans.yaml"

#: The integration overlay tree and its inventory.
INTEGRATIONS_DIR = PMOVES_DIR / "integrations"
INTEGRATIONS_README = INTEGRATIONS_DIR / "README.md"

#: The MCP server roster.
MCP_INVENTORY = PMOVES_DIR / "config" / "mcp_inventory.json"

#: The matrix entry that governs the ONE published pmoves-yt image.
YOTUBE_MATRIX_NAME = "pmoves-yt"

#: The orphan Dockerfile the F2 defect named as the published source.
YOUTUBE_ORPHAN = "pmoves/services/pmoves-yt/Dockerfile"

#: The scope rule for the MCP assertion. See the module docstring.
HOSTED_MCP_TRANSPORTS = ("http", "sse")
HOSTED_MCP_ENDPOINTS = ("local", "fleet")

#: The host-side MCP Toolkit gateway listener the doc describes. See F7.
GATEWAY_LISTEN = PMOVES_DIR / "scripts" / "mcp-toolkit-gateway-listen.sh"

#: The profile resolver. The LISTENER does not call it -- the connect script
#: does. See F7.
GATEWAY_PROFILE_RESOLVER = "node_gateway_profile.py"

#: How the scripts spell the resolver's path. Used to find its consumer.
GATEWAY_PROFILE_RESOLVER_PATH = "pmoves/tools/node_gateway_profile.py"

#: ``PROFILE_ID="${PMOVES_MCP_PROFILE_ID:-<default>}"`` -- the listener's own
#: assignment, which is the ONLY thing that decides the profile it serves.
_LISTENER_PROFILE_RE = re.compile(
    r'^PROFILE_ID="\$\{PMOVES_MCP_PROFILE_ID:-([^}]*)\}"', re.MULTILINE
)


# ── readers ─────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    """Read a text file with its line endings normalised to ``\\n``.

    The normalisation keeps the regexes below line-ending independent; the
    mutations that restore a file work on the RAW bytes, so this never
    changes what is on disk.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _doc_text() -> str:
    return _read(DOC)


def _ci_matrix() -> list[dict[str, Any]]:
    return json.loads(_read(CI_MATRIX))


def _matrix_entry(name: str) -> dict[str, Any]:
    """The live matrix entry for ``name`` -- or a loud failure."""
    for entry in _ci_matrix():
        if entry.get("name") == name:
            return entry
    raise AssertionError(
        f"the CI matrix has no {name!r} entry -- the ratchet cannot derive "
        f"the published Dockerfile"
    )


def _pmoves_yt_block() -> str:
    """The doc's PMOVES.YT paragraph.

    Scoped to the paragraph so that the ``dockerfile:`` tokens harvested from
    it are the ones the paragraph makes a CLAIM about, not every token in
    the whole document.
    """
    for block in _doc_text().split("\n\n"):
        if block.startswith("**PMOVES.YT**"):
            return block
    raise AssertionError("the doc has no PMOVES.YT section")


#: A ``dockerfile: <path>`` claim. The path stops at whitespace or a
#: backtick, so a prose mention inside backticks is captured without its
#: closing backtick.
_DOCKERFILE_CLAIM_RE = re.compile(r"dockerfile:\s*([^\s`]+)")

#: A ``pmoves/services/<...>`` path mention.
_SERVICES_PATH_RE = re.compile(r"pmoves/services/[A-Za-z0-9_.\-/]*")


def _named_dockerfiles(text: str) -> list[str]:
    """Every Dockerfile path the text CLAIMS via a ``dockerfile:`` token."""
    return _DOCKERFILE_CLAIM_RE.findall(text)


def _services_paths(text: str) -> list[str]:
    """Every ``pmoves/services/<...>`` path the text mentions."""
    out: set[str] = set()
    for raw in _SERVICES_PATH_RE.findall(text):
        cleaned = raw.rstrip("/")
        if cleaned.endswith("."):
            cleaned = cleaned[:-1]
        if cleaned:
            out.add(cleaned)
    return sorted(out)


def _mentions_token(text: str, token: str) -> bool:
    """Does the text name ``token`` as a WHOLE token?

    Word-boundary style, with ``-`` counted as part of a token, so
    ``pmoves-cipher`` does NOT satisfy a demand for ``pmoves-cipher-local``
    and ``pmoves-jellyfin`` does NOT satisfy a demand for
    ``pmoves-jellyfin-ai-dashboard``.
    """
    pattern = re.compile(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])")
    return bool(pattern.search(text))


def _images_yaml_image_names() -> list[str]:
    """Every image name ``pmoves/images.yaml`` declares."""
    data = yaml.safe_load(_read(IMAGES_YAML))
    images = data.get("images", []) if isinstance(data, dict) else []
    return [str(image["name"]) for image in images]


def _ci_matrix_image_names() -> list[str]:
    """Every image name the CI image workflow's matrix publishes.

    The matrix is the SECOND publisher. See F6.
    """
    return [
        str(entry["image_name"])
        for entry in _ci_matrix()
        if entry.get("image_name")
    ]


def _published_image_names() -> list[str]:
    """Every image the fleet publishes -- the UNION of BOTH publishers.

    MEASURED: ``pmoves/images.yaml`` declares 32 images and the CI matrix
    publishes 15, and five of the matrix's are in no ``images.yaml`` entry.
    An inventory derived from either file ALONE is incomplete, so the
    published-image set is derived from both. See F6.
    """
    return sorted(set(_images_yaml_image_names()) | set(_ci_matrix_image_names()))


def _doc_section(heading: str) -> str:
    """The doc's section under ``heading`` -- up to the next H2.

    H3 subsections stay INSIDE the section: the published-image inventory
    carries two tables, and both belong to it.
    """
    lines = _doc_text().split("\n")
    start: int | None = None
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        if start is None:
            if line[3:].strip() == heading:
                start = index + 1
        else:
            return "\n".join(lines[start:index])
    if start is None:
        raise AssertionError(f"the doc has no {heading!r} section")
    return "\n".join(lines[start:])


def _inventory_table_image_names() -> list[str]:
    """The image names the doc's published-image inventory TABLES list.

    A table row is recognised by its FIRST cell being a single backticked
    token. The header row and the ``|---|`` separator are not.
    """
    names: list[str] = []
    for line in _doc_section("Published image inventory").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first.startswith("`") and first.endswith("`") and first.count("`") == 2:
            names.append(first[1:-1])
    return names


def _doc_block(prefix: str) -> str:
    """The doc's paragraph that starts with ``prefix``."""
    for block in _doc_text().split("\n\n"):
        if block.startswith(prefix):
            return block
    raise AssertionError(f"the doc has no block starting with {prefix!r}")


def _sentences(text: str) -> list[str]:
    """Split prose into sentences.

    A period that is followed by whitespace ends a sentence. A period INSIDE
    a backticked token (``node_gateway_profile.py``) is followed by a
    backtick, so it does not.
    """
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _gateway_mcp_key() -> str:
    """The hosted MCP inventory key for the Docker MCP Toolkit gateway.

    Derived from the live inventory rather than hard-coded, so a rename in
    the inventory is visible in the diff.
    """
    keys = [key for key in _pmoves_hosted_mcp_keys() if "docker-gateway" in key]
    assert len(keys) == 1, (
        "expected exactly one hosted MCP inventory key for the Docker MCP "
        f"Toolkit gateway, found {keys!r} -- update the ratchet"
    )
    return keys[0]


def _listener_profile_default() -> str:
    """The literal profile the listener falls back to.

    Read out of the listener's OWN assignment, so the doc's claim is
    checked against the script rather than against a literal in this file.
    See F7.
    """
    match = _LISTENER_PROFILE_RE.search(_read(GATEWAY_LISTEN))
    assert match, (
        "could not parse the listener's PROFILE_ID assignment -- the script "
        "changed shape and the ratchet must be updated"
    )
    return match.group(1)


def _resolver_consumers() -> list[str]:
    """The scripts under ``pmoves/scripts/`` that reference the resolver.

    Derived from the live tree: the resolver is named by exactly one
    script, and the doc must name THAT one. See F7.
    """
    scripts = PMOVES_DIR / "scripts"
    return sorted(
        path.name
        for path in scripts.glob("*.sh")
        if GATEWAY_PROFILE_RESOLVER_PATH in _read(path)
    )


def _integration_dirs() -> list[str]:
    """Every directory actually present under ``pmoves/integrations/``."""
    return sorted(
        path.name for path in INTEGRATIONS_DIR.iterdir() if path.is_dir()
    )


def _pmoves_hosted_mcp_keys() -> list[str]:
    """The MCP inventory keys that are PMOVES-HOSTED SERVICES.

    Derived from the live inventory by the scope rule in the module
    docstring -- never a hard-coded list -- so the inventory can grow
    without this list going stale.
    """
    inventory = json.loads(_read(MCP_INVENTORY))
    keys: list[str] = []
    for group in inventory.get("groups", {}).values():
        for server in group.get("servers", []):
            if (
                server.get("transport") in HOSTED_MCP_TRANSPORTS
                and server.get("endpoint") in HOSTED_MCP_ENDPOINTS
            ):
                keys.append(str(server["key"]))
    return sorted(keys)


def _orphan_entry_block(key: str) -> str:
    """The comment block above ``key:`` in the orphan registry, plus the line.

    The comment block is part of the claim: the F2 defect lived in the
    explanatory comment as well as in the reason line, so the ratchet reads
    both.
    """
    lines = _read(ORPHANS_YAML).splitlines()
    for index, line in enumerate(lines):
        if line.startswith(key + ":"):
            start = index
            while start > 0 and lines[start - 1].lstrip().startswith("#"):
                start -= 1
            return "\n".join(lines[start : index + 1])
    raise AssertionError(f"the orphan registry has no {key!r} entry")


def _compose_dockerfile_claims() -> list[str]:
    """Every ``dockerfile:`` value declared by a compose ``build:`` stanza."""
    values: list[str] = []
    for compose in sorted(PMOVES_DIR.glob("docker-compose*.yml")):
        for match in re.finditer(
            r"^\s*dockerfile:\s*(.+?)\s*$", _read(compose), re.MULTILINE
        ):
            values.append(match.group(1).strip().strip("'\""))
    return values


# ── F1: every pmoves/services path the doc claims exists on disk ────────────

def test_every_services_path_the_doc_claims_exists_on_disk() -> None:
    """F1. A path the doc names must exist.

    The defect this gates: the doc declared Archon's path as
    ``pmoves/services/archon``, and there is NO such directory. A reader who
    followed that path found nothing, and a wrapper that was never built
    could not be fixed by editing the file the doc pointed at.
    """
    paths = _services_paths(_doc_text())
    assert paths, (
        "no pmoves/services path was parsed out of the doc -- the ratchet "
        "would pass vacuously"
    )
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]
    assert not missing, (
        "the doc names pmoves/services paths that do not exist on disk: "
        + ", ".join(missing)
        + " -- correct the doc to the real path (or add the directory); the "
        "executable tree is the truth"
    )


# ── F2: the pmoves-yt published Dockerfile is the matrix's ──────────────────

def test_the_docs_pmoves_yt_published_dockerfile_is_the_one_ci_builds() -> None:
    """F2, doc half.

    The doc's PMOVES.YT paragraph must NAME the Dockerfile the CI image
    workflow builds, and every ``dockerfile:`` claim it makes must be the
    matrix's value.

    Two failure modes are caught:
      * naming no Dockerfile at all (the pre-fix prose said "the CI image
        workflows build that one" and never named a file); and
      * naming the ORPHAN ``pmoves/services/pmoves-yt/Dockerfile`` as the
        published source, which is the three-way contradiction.
    """
    matrix_dockerfile = str(_matrix_entry(YOTUBE_MATRIX_NAME)["dockerfile"])
    claims = _named_dockerfiles(_pmoves_yt_block())
    assert claims, (
        "the doc's PMOVES.YT section does not name the Dockerfile the CI "
        "image workflow builds -- it must name "
        f"{matrix_dockerfile!r} explicitly"
    )
    wrong = [claim for claim in claims if claim != matrix_dockerfile]
    assert not wrong, (
        "the doc's PMOVES.YT section names a Dockerfile that is not the one "
        f"CI builds. The matrix entry {YOTUBE_MATRIX_NAME!r} declares "
        f"dockerfile={matrix_dockerfile!r}; the doc claims "
        + ", ".join(repr(claim) for claim in wrong)
        + ". The executable config is the truth -- correct the doc."
    )


def test_the_known_orphans_pmoves_yt_reason_names_the_ci_published_dockerfile() -> None:
    """F2, orphan-registry half.

    The registry's reason line for ``pmoves/services/pmoves-yt/Dockerfile``
    (and the comment block above it) must name the matrix's Dockerfile as
    the published source. The pre-fix text claimed that
    ``integrations-ghcr.yml`` builds and PUSHES THIS file, which is false.
    """
    matrix_dockerfile = str(_matrix_entry(YOTUBE_MATRIX_NAME)["dockerfile"])
    block = _orphan_entry_block(YOUTUBE_ORPHAN)
    claims = _named_dockerfiles(block)
    assert claims, (
        "the orphan registry's pmoves-yt entry does not name the Dockerfile "
        f"CI builds -- it must name {matrix_dockerfile!r} explicitly"
    )
    wrong = [claim for claim in claims if claim != matrix_dockerfile]
    assert not wrong, (
        "the orphan registry's pmoves-yt entry names a Dockerfile that is "
        f"not the one CI builds. The matrix entry {YOTUBE_MATRIX_NAME!r} "
        f"declares dockerfile={matrix_dockerfile!r}; the registry claims "
        + ", ".join(repr(claim) for claim in wrong)
        + ". The executable config is the truth -- correct the registry."
    )


def test_the_orphan_pmoves_yt_dockerfile_is_named_by_no_compose_build() -> None:
    """F2, the doc's "no compose build stanza names it" claim.

    The doc asserts that the orphan is a non-deployed copy. That is a claim
    about the runtime, so it is gated against the compose files rather than
    asserted.
    """
    claims = _compose_dockerfile_claims()
    assert claims, (
        "no compose `dockerfile:` claim was parsed -- the ratchet would pass "
        "vacuously"
    )
    offenders = [
        value
        for value in claims
        if value.endswith(YOUTUBE_ORPHAN)
        or value.endswith(YOUTUBE_ORPHAN.split("pmoves/", 1)[1])
    ]
    assert not offenders, (
        "a compose build stanza names the pmoves-yt orphan Dockerfile "
        f"({YOUTUBE_ORPHAN}): " + ", ".join(offenders) + " -- the doc's "
        "description of it as a non-deployed copy is now wrong"
    )


# ── F3: every published image name is named in the doc ──────────────────────

def test_every_published_image_name_is_named_in_the_services_doc() -> None:
    """F3, F6 and the whole image inventory.

    ``pmoves/images.yaml`` declares 32 published images. Before this lane
    the doc named FOUR of them, and none of the three jellyfin-ai images --
    so the doc described the Jellyfin-AI stack without naming a single image
    it actually publishes.

    The scope is the UNION of the TWO publishers (F6): the CI image
    workflow's matrix publishes five images that no ``pmoves/images.yaml``
    entry declares, and a published image the doc never names is the same
    defect whichever publisher ships it.
    """
    names = _published_image_names()
    assert names, "pmoves/images.yaml declares no images -- the ratchet is vacuous"
    doc = _doc_text()
    missing = [name for name in names if not _mentions_token(doc, name)]
    assert not missing, (
        "the Services and Integrations doc does not name these published "
        "images: " + ", ".join(missing) + " -- add them to the doc"
    )


def test_every_published_image_is_listed_in_the_inventory_table() -> None:
    """F6: the published-image inventory must be COMPLETE.

    The defect this gates: the doc's inventory table carried the 32
    ``pmoves/images.yaml`` entries and the doc CLAIMED that every published
    image is declared there -- a claim its own next paragraph contradicted,
    because the CI image workflow's matrix is a second publisher. MEASURED:
    five published images (``pmoves-archon-ui``, ``pmoves-firefly-iii``,
    ``pmoves-deepresearch``, ``pmoves-supaserch``, ``pmoves-a2ui-renderer``)
    are in no ``pmoves/images.yaml`` entry, so the table was missing five
    rows of the fleet's published images.

    Naming an image somewhere in the prose is not enough: the inventory
    table is what an operator reads to learn what the fleet publishes, so
    every published image needs a ROW.
    """
    names = _published_image_names()
    assert names, (
        "neither pmoves/images.yaml nor the CI matrix declares an image -- "
        "the ratchet is vacuous"
    )
    rows = _inventory_table_image_names()
    assert rows, (
        "the doc's published-image inventory table lists no images -- the "
        "ratchet would pass vacuously"
    )
    missing = [name for name in names if name not in rows]
    assert not missing, (
        "the Services and Integrations doc's published-image inventory table "
        "does not list these published images: "
        + ", ".join(missing)
        + " -- add a row for each (the union of pmoves/images.yaml and the "
        "CI image workflow's matrix)"
    )


def test_the_doc_describes_the_gateway_listeners_actual_profile_selection() -> None:
    """F7: the doc must describe the profile selection the LISTENER performs.

    The defect this gates: the doc claimed that an unset
    ``PMOVES_MCP_PROFILE_ID`` sends the LISTENER through
    ``pmoves/tools/node_gateway_profile.py`` (pinned node profile -> hardware
    detection -> REFUSE, never a guess). MEASURED, the listener assigns the
    LITERAL fallback
    ``PROFILE_ID="${PMOVES_MCP_PROFILE_ID:-pmoves_5090_web}"`` and never
    calls the resolver -- the resolver belongs to
    ``pmoves/scripts/mcp-toolkit-connect.sh``. An operator on another node
    would have believed the listener selects, or refuses to serve, the
    right profile when it actually serves the 5090 one.

    The rules below are derived from the live script, not from a literal
    copied into this file:

    * the doc must name the env var the listener reads;
    * the sentence that names it must also name the literal fallback the
      listener actually assigns;
    * no sentence that names the env var may name the resolver, because
      the listener never calls it;
    * a sentence that names the resolver must name the script that DOES
      call it.
    """
    script = _read(GATEWAY_LISTEN)
    default = _listener_profile_default()
    assert default, "the listener's PROFILE_ID fallback is empty"

    key = _gateway_mcp_key()
    block = _doc_block(f"**{key}**")
    sentences = _sentences(block)

    named = [s for s in sentences if "PMOVES_MCP_PROFILE_ID" in s]
    assert named, (
        f"the doc's {key} entry does not mention PMOVES_MCP_PROFILE_ID -- it "
        "must describe how the listener picks its profile"
    )
    assert any(default in s for s in named), (
        "the doc's profile-selection sentence does not name the literal "
        f"fallback the listener actually uses ({default!r}) -- the listener "
        f"assigns PROFILE_ID=\"${{PMOVES_MCP_PROFILE_ID:-{default}}}\""
    )

    consumers = _resolver_consumers()
    assert consumers, (
        "no script under pmoves/scripts/ references the profile resolver -- "
        "the ratchet cannot derive the resolver's consumer"
    )

    if GATEWAY_PROFILE_RESOLVER not in script:
        for sentence in named:
            assert GATEWAY_PROFILE_RESOLVER not in sentence, (
                "the doc's profile-selection sentence attributes profile "
                f"resolution to the listener, but {GATEWAY_LISTEN.name} never "
                f"calls {GATEWAY_PROFILE_RESOLVER} -- the resolver belongs to "
                + ", ".join(consumers)
            )

    for sentence in sentences:
        if GATEWAY_PROFILE_RESOLVER in sentence:
            assert any(consumer in sentence for consumer in consumers), (
                f"the doc's {key} entry mentions {GATEWAY_PROFILE_RESOLVER} "
                "without naming the script that actually calls it: "
                + ", ".join(consumers)
            )


# ── F4: the MCP roster the doc must carry ───────────────────────────────────

def test_every_pmoves_hosted_mcp_server_is_named_in_the_services_doc() -> None:
    """F4 and the scoped MCP roster.

    The defect this gates: ``pmoves-docker-gateway-sse`` is in the inventory
    (and in ``kilo.json`` and two bootstrap scripts) and appeared ZERO times
    in the doc.
    """
    keys = _pmoves_hosted_mcp_keys()
    assert keys, (
        "no PMOVES-hosted MCP server was derived from the inventory -- the "
        "ratchet would pass vacuously"
    )
    doc = _doc_text()
    missing = [key for key in keys if not _mentions_token(doc, key)]
    assert not missing, (
        "the Services and Integrations doc does not name these PMOVES-hosted "
        "MCP servers: " + ", ".join(missing) + " -- add them to the doc"
    )


# ── F5: the integrations inventory ──────────────────────────────────────────

def test_every_integration_directory_is_named_in_the_integrations_readme() -> None:
    """F5.

    ``pmoves/integrations/`` holds EIGHT directories; the README listed four.
    ``agent0-plugins/``, ``github-runners/`` and ``tools/`` were unlisted, and
    ``_template/`` was described only in prose.
    """
    dirs = _integration_dirs()
    assert dirs, "pmoves/integrations/ holds no directories -- the ratchet is vacuous"
    readme = _read(INTEGRATIONS_README)
    missing = [name for name in dirs if f"`{name}/`" not in readme]
    assert not missing, (
        "pmoves/integrations/README.md does not list these on-disk "
        "directories: " + ", ".join(missing) + " -- list every directory that "
        "is actually present"
    )
