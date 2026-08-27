"""Guard the AMD/ROCm compose overlay's reachability through a Known Road.

The defect
----------
`pmoves/docker-compose.amd.yml` landed on main (6a7499dfc, direct push) with a
header comment telling operators to invoke it as::

    docker compose ... -f docker-compose.yml -f docker-compose.amd.yml ...

No Make target referenced it. That is not a cosmetic gap: this repo's convention
is that services come up through Make targets ("Known Roads", .claude/PATTERNS.md),
and `.claude/hooks/governance/known-roads-enforcer.py` exists specifically to push
raw `docker compose up` back onto them. An overlay reachable only by the
discouraged path is, in practice, not reachable on the node class it exists for.

The precedent it should have matched was already in the tree: `up-voice-amd`
(Makefile) is the `-amd` sibling of `up-voice` and appends
`docker-compose.amd-voice.yml` to the same file chain. `up-ffmpeg-whisper` had no
such sibling.

What is asserted
----------------
1. Every target whose recipe starts `ffmpeg-whisper` through compose passes
   `$(WHISPER_NODE_OVERLAY)`, the injection slot the `-amd` siblings set.
2. Each of those targets has an `-amd` sibling that recurses into it with
   `WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"`.
3. `AMD_OVERLAY` names a compose file that exists and actually resets the
   reservation for ffmpeg-whisper.
4. The base compose file still declares an `nvidia` reservation for
   ffmpeg-whisper -- without this the overlay would be a no-op and assertions
   1-3 would be guarding nothing.

Deliberately static: no `docker` binary and no tier env files are required, so
this runs in CI. The merged-config behaviour it stands in for was verified
directly on B850 (base -> driver "nvidia"; +overlay -> reservations {} and
WHISPER_DEVICE=cpu).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"

TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._/-]*)\s*:(?!=)")
COMPOSE_INVOCATION_RE = re.compile(r"docker compose|\$\((?:DC|COOKIES_DC)\)")
UP_D_RE = re.compile(r"\bup -d\b")
# Whole-word, so `ffmpeg-whisper-smoke`'s curl line is not mistaken for a bring-up.
WHISPER_ARG_RE = re.compile(r"(?<![\w./-])ffmpeg-whisper(?![\w./-])")

OVERLAY_SLOT = "$(WHISPER_NODE_OVERLAY)"
OVERLAY_SET = 'WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"'
AMD_OVERLAY_ASSIGN_RE = re.compile(r"^AMD_OVERLAY\s*:?=\s*-f\s+(\S+)\s*$", re.MULTILINE)


class _TolerantLoader(yaml.SafeLoader):
    """Compose's `!reset` / `!override` tags are not types SafeLoader knows.

    Preserve the tag rather than dropping it -- assertion 3 needs to see that the
    devices list is *reset*, not merely that it is empty. `[]` and `!reset []`
    are very different claims: the first is an empty override that Compose MERGES
    into the base list (leaving the nvidia reservation in place), the second
    replaces it.

    Registered per-tag rather than via add_multi_constructor because
    pmoves/tests/conftest.py installs an exact-tag `!reset` constructor on
    yaml.SafeLoader that discards the tag, and in PyYAML an exact-tag constructor
    outranks a multi-constructor. Subclass entries shadow the inherited ones, so
    these win here without disturbing that shim for other tests.
    """


def _tagged(tag: str):
    def construct(loader, node):  # noqa: ANN001 - yaml constructor signature
        if isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node)
        elif isinstance(node, yaml.MappingNode):
            value = loader.construct_mapping(node)
        else:
            value = loader.construct_scalar(node)
        return {"__tag__": tag, "value": value}

    return construct


for _tag in ("reset", "override"):
    _TolerantLoader.add_constructor(f"!{_tag}", _tagged(_tag))


def makefiles() -> list[Path]:
    return sorted(list((PMOVES / "mk").glob("*.mk")) + [PMOVES / "Makefile"])


def _recipes() -> dict[str, list[str]]:
    """-> {target: [recipe lines]}. A target may be declared in several files."""
    recipes: dict[str, list[str]] = {}
    for path in makefiles():
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("\t"):
                match = TARGET_RE.match(line)
                current = match.group(1) if match else None
                continue
            if current:
                recipes.setdefault(current, []).append(line)
    return recipes


def _whisper_starters() -> dict[str, list[str]]:
    """Targets whose recipe brings ffmpeg-whisper up through compose."""
    found: dict[str, list[str]] = {}
    for target, lines in _recipes().items():
        hits = [
            line
            for line in lines
            if COMPOSE_INVOCATION_RE.search(line)
            and UP_D_RE.search(line)
            and WHISPER_ARG_RE.search(line)
        ]
        if hits:
            found[target] = hits
    return found


def _amd_overlay_path() -> Path:
    text = (PMOVES / "Makefile").read_text(encoding="utf-8")
    match = AMD_OVERLAY_ASSIGN_RE.search(text)
    assert match, "AMD_OVERLAY is not assigned as `-f <file>` in pmoves/Makefile"
    return PMOVES / match.group(1)


def _whisper_service(*compose_files: Path) -> dict:
    """Shallow merge of the ffmpeg-whisper service across compose files, in order."""
    merged: dict = {}
    for path in compose_files:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_TolerantLoader) or {}
        service = (doc.get("services") or {}).get("ffmpeg-whisper")
        if service:
            merged.update(service)
    return merged


def test_scanner_finds_whisper_bringup_targets():
    """If discovery breaks, every assertion below passes vacuously."""
    starters = _whisper_starters()
    assert len(makefiles()) > 5
    # up-yt, up-yt-published, up-yt-hardened, up-ffmpeg-whisper at time of writing.
    assert len(starters) >= 4, (
        f"expected >=4 ffmpeg-whisper bring-up targets, found {sorted(starters)}"
    )


def test_base_compose_really_reserves_an_nvidia_device():
    """Non-vacuity guard for the whole file: if the base stopped requesting an
    NVIDIA device, the overlay would be pointless and every wiring assertion
    below would be protecting a no-op."""
    base = _whisper_service(PMOVES / "docker-compose.yml")
    reservations = base.get("deploy", {}).get("resources", {}).get("reservations", {})
    devices = reservations.get("devices")
    assert devices, "docker-compose.yml no longer reserves a device for ffmpeg-whisper"
    assert any(d.get("driver") == "nvidia" for d in devices), (
        f"expected an nvidia device reservation, got {devices}"
    )


def test_amd_overlay_file_exists_and_resets_the_reservation():
    overlay = _amd_overlay_path()
    assert overlay.is_file(), f"AMD_OVERLAY points at a missing file: {overlay}"
    service = _whisper_service(overlay)
    reservations = service.get("deploy", {}).get("resources", {}).get("reservations", {})
    devices = reservations.get("devices")
    assert isinstance(devices, dict) and devices.get("__tag__") == "reset", (
        "the overlay must reset the devices reservation with `devices: !reset []`; "
        f"got {devices!r}"
    )
    assert devices.get("value") == [], f"expected an empty reset list, got {devices!r}"


def test_every_whisper_bringup_target_accepts_the_overlay():
    """The exact regression: an overlay no Known Road can reach."""
    starters = _whisper_starters()
    offenders = [
        target
        for target, lines in starters.items()
        if not any(OVERLAY_SLOT in line for line in lines)
    ]
    assert not offenders, (
        f"these targets start ffmpeg-whisper without passing {OVERLAY_SLOT}, so "
        "AMD/ROCm nodes cannot reach docker-compose.amd.yml through them: "
        f"{sorted(offenders)}"
    )


def test_every_whisper_bringup_target_has_an_amd_sibling():
    """Accepting the slot is not enough -- something has to SET it, or the only
    way in is still a raw `docker compose` chain typed by hand."""
    starters = _whisper_starters()
    recipes = _recipes()
    missing = []
    for target in starters:
        sibling = f"{target}-amd"
        lines = recipes.get(sibling)
        if not lines or not any(OVERLAY_SET in line and target in line for line in lines):
            missing.append(sibling)
    assert not missing, (
        f"missing `-amd` sibling target(s) that recurse with {OVERLAY_SET}: "
        f"{sorted(missing)}. Precedent: up-voice / up-voice-amd."
    )


def test_amd_siblings_are_phony():
    """A non-.PHONY target silently no-ops if a file of that name ever appears."""
    declared = set()
    for path in makefiles():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(".PHONY:"):
                declared.update(line.split(":", 1)[1].split())
    siblings = {f"{t}-amd" for t in _whisper_starters()}
    assert siblings <= declared, f"not declared .PHONY: {sorted(siblings - declared)}"
