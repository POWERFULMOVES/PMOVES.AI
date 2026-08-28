"""Shared import-path bootstrap for PMOVES services.

Ensures PMOVES package roots are importable in container/runtime variants.
Consolidates the duplicated ``_bootstrap_import_paths()`` previously found
in agent-zero and archon entry-points.

Usage::

    from services.common.bootstrap import bootstrap_import_paths

    bootstrap_import_paths()

Or, for automatic bootstrapping on import::

    from services.common.bootstrap import ensure_import_paths  # calls immediately
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence


def bootstrap_import_paths(
    *,
    extra_roots: Sequence[Path] | None = None,
    file_ref: str | None = None,
) -> None:
    """Ensure PMOVES package roots are on ``sys.path``.

    By default, this inspects the calling module's ``__file__`` and adds
    sensible parent directories (the service dir, the services dir, and
    the project root).  Callers may pass *file_ref* to override the
    reference file used for path calculation.

    Args:
        extra_roots: Additional directories to prepend to ``sys.path``.
        file_ref: Absolute path to use as reference for parent calculation.
                  Defaults to the caller's ``__file__``.
    """
    try:
        if file_ref is not None:
            here = Path(file_ref).resolve()
        else:
            import inspect
            frame = inspect.stack()[1]
            here = Path(frame.filename).resolve()

        # Standard PMOVES service layout:
        #   /app/pmoves/services/<service-name>/main.py
        #   parents[0] -> service dir   (<service-name>/)
        #   parents[1] -> services dir  (services/)
        #   parents[2] -> project root  (pmoves/ or /app)
        candidates: list[Path] = []
        if here.parents:
            candidates = [
                here.parents[2],  # project root / /app
                here.parents[1],  # services/
                here.parent,      # <service-name>/
            ]

        if extra_roots:
            candidates = list(extra_roots) + candidates

        for path in candidates:
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
    except Exception:
        # Keep startup resilient; downstream imports will raise explicit errors
        # if unresolved.
        pass


def ensure_import_paths(**kwargs: object) -> None:
    """Convenience wrapper that calls :func:`bootstrap_import_paths` immediately."""
    bootstrap_import_paths()


__all__ = ["bootstrap_import_paths", "ensure_import_paths"]
