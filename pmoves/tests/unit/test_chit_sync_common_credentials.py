"""sync_common_credentials' os.environ fallback.

`pmoves/chit/__init__.py` never imported `os`, so the fallback branch -- taken
whenever the caller passes no common_creds, which is also what
apply_manifest_v2 does when the decoded secrets hold none of the common keys --
raised NameError before reading a single variable. Every value here is
synthetic and every file lives under tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pmoves.chit import sync_common_credentials  # noqa: E402

_KEYS = [
    "POSTGRES_PASSWORD", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
    "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "MINIO_USER",
    "MINIO_PASSWORD", "NEO4J_AUTH", "NEO4J_PASSWORD", "PGRST_DB_URI",
]


def test_the_environ_fallback_reads_the_environment(tmp_path, monkeypatch):
    for key in _KEYS:
        monkeypatch.setenv(key, f"synthetic-{key.lower()}")
    tier = tmp_path / "env.tier-data"
    tier.write_text("EXISTING=1\n", encoding="utf-8")

    results = sync_common_credentials(tmp_path)  # no common_creds -> os.environ

    written = tier.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=synthetic-postgres_password" in written
    assert str(tier) in results and len(results[str(tier)]) == len(_KEYS)
