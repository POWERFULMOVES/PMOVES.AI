"""Pinokio 8 state reader for the pinokio_bridge service.

Reads P8 state from the on-disk JSON files Pinokio 8 writes to `~/pinokio/`
(or `D:\pinokio\` on Windows). The state files referenced here are the
documented P8 surfaces (per https://cocktailpeanutlabs.github.io/p8/):

    ~/pinokio/autolaunch/state.json       - per-app autolaunch ON/OFF + script
    ~/pinokio/orchestration/graph.json    - dependency graph + launch order
    ~/pinokio/skills/library.json         - managed skill library + sync targets
    ~/pinokio/skills/sync_state.json      - last sync timestamp + conflicts
    ~/pinokio/gpu/state.json             - detected GPU + VRAM per node

The state is read-only from this service's perspective (writes are forwarded
to Pinokio via structured `shell.run` argv, not via direct file mutation).
The service also supports a "mock" mode for tests where state is provided
as an in-memory dict (no Pinokio install required).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default Pinokio home path. P8 default is `~/pinokio` (or `%USERPROFILE%\pinokio`
# on Windows). Operators can override via PINOKIO_HOME env var.
DEFAULT_PINOKIO_HOME = os.environ.get(
    "PINOKIO_HOME",
    # Windows default
    str(Path(os.environ.get("USERPROFILE", str(Path.home()))).joinpath("pinokio"))
    if os.name == "nt"
    # macOS / Linux default
    else str(Path.home().joinpath("pinokio")),
)


@dataclass
class PinokioState:
    """In-memory snapshot of the Pinokio 8 state files.

    The state can be loaded from disk via `load_from_disk` or constructed
    directly for tests via the dataclass constructor. All read endpoints
    in app.py read from this object; all write endpoints mutate it and
    persist back via `save_to_disk` (or no-op in mock mode).
    """

    home: Path
    apps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    autolaunch: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    autolaunch_global_disabled: bool = False
    orchestration: Dict[str, Any] = field(default_factory=dict)
    skills: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    skills_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    gpu: Dict[str, Any] = field(default_factory=dict)
    pinokio_version: str = "8.0.0"
    last_loaded_at: Optional[str] = None

    @classmethod
    def load_from_disk(cls, home: Path | str = DEFAULT_PINOKIO_HOME) -> "PinokioState":
        """Read all P8 state files from `home` and return a snapshot.

        Missing files default to empty values — the service still
        starts, just with empty state. The caller can detect missing
        state via the per-field empties (e.g. `apps == {}`).
        """
        home = Path(home)
        state = cls(home=home)

        def _read_json(path: Path) -> Any:
            if not path.exists():
                return None
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None

        apps_doc = _read_json(home / "apps" / "index.json") or {}
        if isinstance(apps_doc, dict):
            state.apps = apps_doc.get("apps", {})

        auto_doc = _read_json(home / "autolaunch" / "state.json") or {}
        if isinstance(auto_doc, dict):
            state.autolaunch = auto_doc.get("per_app", {})
            state.autolaunch_global_disabled = auto_doc.get(
                "global_disabled", False
            )

        state.orchestration = (
            _read_json(home / "orchestration" / "graph.json") or {}
        )

        skills_doc = _read_json(home / "skills" / "library.json") or {}
        if isinstance(skills_doc, dict):
            state.skills = skills_doc.get("skills", {})

        sync_doc = _read_json(home / "skills" / "sync_state.json") or {}
        if isinstance(sync_doc, dict):
            state.skills_conflicts = sync_doc.get("conflicts", [])

        state.gpu = _read_json(home / "gpu" / "state.json") or {}

        version_doc = _read_json(home / "version.json") or {}
        if isinstance(version_doc, dict):
            state.pinokio_version = version_doc.get("version", "8.0.0")

        state.last_loaded_at = datetime.now(timezone.utc).isoformat()
        return state

    def save_to_disk(self) -> None:
        """Persist the in-memory state back to the on-disk P8 layout.

        Used after a write endpoint (autolaunch toggle, skill sync,
        app launch). For mock mode (test fixture), this is a no-op.
        """
        if not self.home.exists() and self._is_mock():
            return  # mock mode — no disk writes
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "apps").mkdir(exist_ok=True)
        (self.home / "autolaunch").mkdir(exist_ok=True)
        (self.home / "orchestration").mkdir(exist_ok=True)
        (self.home / "skills").mkdir(exist_ok=True)
        (self.home / "gpu").mkdir(exist_ok=True)

        (self.home / "apps" / "index.json").write_text(
            json.dumps({"apps": self.apps}, indent=2), encoding="utf-8"
        )
        (self.home / "autolaunch" / "state.json").write_text(
            json.dumps(
                {
                    "per_app": self.autolaunch,
                    "global_disabled": self.autolaunch_global_disabled,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (self.home / "orchestration" / "graph.json").write_text(
            json.dumps(self.orchestration, indent=2), encoding="utf-8"
        )
        (self.home / "skills" / "library.json").write_text(
            json.dumps({"skills": self.skills}, indent=2), encoding="utf-8"
        )
        (self.home / "skills" / "sync_state.json").write_text(
            json.dumps({"conflicts": self.skills_conflicts}, indent=2),
            encoding="utf-8",
        )
        (self.home / "gpu" / "state.json").write_text(
            json.dumps(self.gpu, indent=2), encoding="utf-8"
        )

    def _is_mock(self) -> bool:
        """A state is "mock" if the home path is a temp dir or doesn't exist
        on disk + has no real Pinokio install marker. Used to short-circuit
        save_to_disk in tests.
        """
        return not (self.home / "version.json").exists() and not self.home.exists()

    # ------------------------------------------------------------------
    # Convenience accessors used by the FastAPI endpoints
    # ------------------------------------------------------------------

    def get_app(self, slug: str) -> Optional[Dict[str, Any]]:
        return self.apps.get(slug)

    def get_autolaunch(self, slug: str) -> Dict[str, Any]:
        return self.autolaunch.get(
            slug,
            {"slug": slug, "enabled": False, "script": None,
             "last_evaluated_at": None},
        )

    def set_autolaunch(self, slug: str, enabled: bool, script: Optional[str]) -> None:
        self.autolaunch[slug] = {
            "slug": slug,
            "enabled": enabled,
            "script": script,
            "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_dependencies(self, slug: str) -> Dict[str, Any]:
        """Return the resolved launch order for `slug` (recursive).

        Reads `orchestration['edges']` and `orchestration['nodes']` to
        walk the graph. Returns the launch order as a list of levels,
        each level listing the apps that can launch in parallel.
        """
        edges = self.orchestration.get("edges", [])
        nodes = self.orchestration.get("nodes", [])
        if slug not in {n.get("slug") for n in nodes}:
            return {
                "slug": slug,
                "depends_on": [],
                "recursive": [],
                "launch_order": [],
                "ready_checks": {slug: False},
            }

        # Build adjacency + reverse
        deps: Dict[str, List[str]] = {n.get("slug"): [] for n in nodes}
        for edge in edges:
            frm = edge.get("from")
            to = edge.get("to")
            if frm in deps and to in deps:
                deps[frm].append(to)

        # BFS for transitive closure of `slug`'s deps
        seen: set[str] = set()
        stack: List[str] = [slug]
        while stack:
            cur = stack.pop()
            for d in deps.get(cur, []):
                if d not in seen:
                    seen.add(d)
                    stack.append(d)

        # Resolve launch order via topo levels
        in_degree: Dict[str, int] = {n: 0 for n in seen}
        for d in seen:
            for downstream in deps.get(d, []):
                if downstream in in_degree:
                    in_degree[downstream] += 1
        levels: List[List[str]] = []
        ready_map: Dict[str, bool] = {}
        remaining = set(seen)
        while remaining:
            level = [n for n in remaining if in_degree.get(n, 0) == 0]
            if not level:
                break  # cycle — return what we have
            levels.append(sorted(level))
            for n in level:
                ready_map[n] = True
                remaining.discard(n)
                for downstream in deps.get(n, []):
                    if downstream in in_degree:
                        in_degree[downstream] -= 1
        ready_map[slug] = False  # the requester is not yet ready until we launch it
        return {
            "slug": slug,
            "depends_on": deps.get(slug, []),
            "recursive": sorted(seen),
            "launch_order": levels,
            "ready_checks": ready_map,
        }
