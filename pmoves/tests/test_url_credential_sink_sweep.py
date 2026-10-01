"""The URL-credential dataflow sweep: clean on the repo, and it FLAGS known leak shapes.

Probe trees are built under tmp_path/pmoves so allowlist keys (which are relative to
the scanned root's parent) line up with the real repo's. All credentials synthetic.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

PMOVES = pathlib.Path(__file__).resolve().parents[1]
TOOL = PMOVES / "tools" / "url_credential_sink_sweep.py"
sys.path.insert(0, str(PMOVES / "tools"))
import url_credential_sink_sweep as sweep_mod  # noqa: E402


def test_sweep_reports_no_unredacted_sinks():
    proc = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout
    summary = proc.stdout.splitlines()[0]
    # Guard against a vacuous pass (the sweep once scanned zero files from a dotted path).
    assert int(summary.split("files=")[1].split()[0]) > 500, summary


def _probe_tree(tmp_path, files: dict[str, str]) -> pathlib.Path:
    root = tmp_path / "pmoves"
    common = root / "services" / "common"
    common.mkdir(parents=True)
    shutil.copy(PMOVES / "services" / "common" / "redact.py", common / "redact.py")
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src))
    return root


def _flagged_lines(root, rel):
    _files, _t, sinks = sweep_mod.sweep(root)
    findings, _problems = sweep_mod.evaluate(sinks)
    return {line for path, line, *_ in findings if path == f"pmoves/{rel}"}


def test_allowlisted_multiline_sink_does_not_hide_a_new_one(tmp_path):
    """Round-2 review probe: a new multi-line logger.debug with slug + an env-read NATS URL,
    in the same file and with the same identifiers as an allowlisted row, must be reported."""
    rel = "services/common/nats_service_listener.py"
    original = (PMOVES / rel).read_text()
    probe = original + textwrap.dedent('''

        def _probe_announce(slug):
            url = os.environ.get("NATS_URL", "")
            logger.debug(
                f"Service announcement received: {slug} "
                f"at {url}"
            )
        ''')
    root = _probe_tree(tmp_path, {rel: probe})
    probe_line = len(original.splitlines()) + 5
    assert probe_line in _flagged_lines(root, rel)


SHAPES = {
    "settings_whole": '''
        import logging, os
        from pydantic_settings import BaseSettings
        logger = logging.getLogger(__name__)
        class Settings(BaseSettings):
            nats_url: str = "nats://nats:4222"
            port: int = 8080
        settings = Settings()
        logger.info("config %s", settings)                     # FLAG
        logger.info(f"config {settings}")                      # FLAG
        logger.info("config %s", settings.model_dump())        # FLAG
        logger.info("port %s", settings.port)                  # ok
    ''',
    "dict_literal": '''
        import logging, os
        logger = logging.getLogger(__name__)
        cfg = {"bus": os.getenv("NATS_URL"), "port": 1}
        logger.info("cfg=%s", cfg)                             # FLAG
    ''',
    "exception_object": '''
        import logging, os
        logger = logging.getLogger(__name__)
        def connect():
            err = ConnectionError("cannot reach " + os.environ["DATABASE_URL"])
            logger.error("failed: %s", err)                    # FLAG
    ''',
    "environ_dump": '''
        import logging, os
        logger = logging.getLogger(__name__)
        logger.debug("env=%s", dict(os.environ))               # FLAG
    ''',
    "more_keys": '''
        import os
        print(os.getenv("MONGODB_URI"))                        # FLAG
        print(os.getenv("RABBITMQ_URL"))                       # FLAG
        print(os.getenv("NATS_EVENT_BUS_URL"))                 # FLAG
        print(os.getenv("TENSORZERO_CLICKHOUSE_URL"))          # FLAG
        print(os.getenv("GOOGLE_REDIRECT_URI"))                # ok (redirect URIs carry no userinfo)
    ''',
    "nats_publish": '''
        import json, os
        async def announce(nc):
            payload = {"bus": os.getenv("NATS_URL")}
            await nc.publish("svc.up", json.dumps(payload).encode())  # FLAG
    ''',
    "non_canonical_redactor": '''
        import logging, os
        logger = logging.getLogger(__name__)
        from services.common.redact import redact_url
        def _scrub(url):
            return url.split("@")[-1]
        URL = os.getenv("NATS_URL")
        logger.info("bus %s", _scrub(URL))                     # FLAG (private redactor does not clean)
        logger.info("bus %s", redact_url(URL))                 # ok (canonical)
    ''',
}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_sweep_flags_leak_shape(tmp_path, name):
    rel = f"services/probe_{name}/main.py"
    src = textwrap.dedent(SHAPES[name])
    root = _probe_tree(tmp_path, {rel: src})
    want = {i for i, line in enumerate(src.splitlines(), 1) if line.rstrip().endswith("# FLAG") or "# FLAG (" in line}
    clean = {i for i, line in enumerate(src.splitlines(), 1) if "# ok" in line}
    got = _flagged_lines(root, rel)
    assert want <= got, f"missed lines {sorted(want - got)}"
    assert not (clean & got), f"false positives on lines {sorted(clean & got)}"


def test_allowlist_row_matching_two_sinks_fails():
    key = ("pmoves/x.py", "log", "url", "logger.info(url)")
    sinks = [("pmoves/x.py", 1, "log", "url", "logger.info(url)"),
             ("pmoves/x.py", 9, "log", "url", "logger.info(url)")]
    _findings, problems = sweep_mod.evaluate(sinks, {key: "test"})
    assert problems == [(2, key)]
