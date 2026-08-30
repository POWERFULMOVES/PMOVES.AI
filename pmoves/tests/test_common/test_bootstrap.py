import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.bootstrap import bootstrap_import_paths, ensure_import_paths


def test_bootstrap_adds_service_dir():
    """bootstrap_import_paths adds the service dir to sys.path."""
    fake_file = str(repo_root / "pmoves" / "services" / "my-svc" / "main.py")
    original_path = sys.path[:]
    try:
        bootstrap_import_paths(file_ref=fake_file)
        # The service dir (parent[0]) should be in sys.path
        service_dir = str(Path(fake_file).resolve().parent)
        assert service_dir in sys.path
        # The services dir (parent[1]) should also be in sys.path
        services_dir = str(Path(fake_file).resolve().parents[1])
        assert services_dir in sys.path
    finally:
        sys.path[:] = original_path


def test_bootstrap_with_extra_roots():
    """bootstrap_import_paths adds extra_roots to sys.path."""
    extra = Path("/tmp/fake_extra_root")
    original_path = sys.path[:]
    try:
        bootstrap_import_paths(
            file_ref=str(repo_root / "pmoves" / "services" / "svc" / "main.py"),
            extra_roots=[extra],
        )
        assert str(extra) in sys.path
    finally:
        sys.path[:] = original_path


def test_bootstrap_idempotent():
    """Calling bootstrap_import_paths twice does not duplicate entries."""
    fake_file = str(repo_root / "pmoves" / "services" / "my-svc" / "main.py")
    original_path = sys.path[:]
    try:
        bootstrap_import_paths(file_ref=fake_file)
        path_snapshot = sys.path[:]
        bootstrap_import_paths(file_ref=fake_file)
        # No duplicates added
        assert sys.path == path_snapshot
    finally:
        sys.path[:] = original_path


def test_ensure_import_paths_calls_bootstrap():
    """ensure_import_paths delegates to bootstrap_import_paths."""
    with patch("services.common.bootstrap.bootstrap_import_paths") as mock_bs:
        ensure_import_paths()
        mock_bs.assert_called_once()
