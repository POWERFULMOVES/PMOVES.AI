'''Behavior tests for the register-citation checker (incident: PR #3408).'''
import pathlib
import subprocess
import sys

TOOL = pathlib.Path(__file__).resolve().parents[1] / 'tools' / 'verify_register_citations.py'
ROW = '- `2026-10-14T17:13:47Z` CLAIM `Z890-A0` branch: `erp/demo` | scope text\n'


def run(tmp_path, register, doc_text):
    reg = tmp_path / 'AGNOTE4482PHI.t1.md'
    reg.write_text(register)
    doc = tmp_path / 'doc.md'
    doc.write_text(doc_text)
    return subprocess.run(
        [sys.executable, str(TOOL), '--register', str(reg), str(doc)],
        capture_output=True, text=True,
    )


def test_resolvable_token_passes(tmp_path):
    r = run(tmp_path, ROW, 'See AGNOTE4482[Z890-A0@erp/demo @2026-10-14T17:13:47Z].\n')
    assert r.returncode == 0, r.stdout + r.stderr


def test_wrong_branch_token_fails(tmp_path):
    r = run(tmp_path, ROW, 'See AGNOTE4482[Z890-A0@erp/other @2026-10-14T17:13:47Z].\n')
    assert r.returncode == 1 and 'unresolvable' in r.stdout


def test_wrong_ts_token_fails(tmp_path):
    r = run(tmp_path, ROW, 'See AGNOTE4482[Z890-A0@erp/demo @2026-10-15T00:00:00Z].\n')
    assert r.returncode == 1


def test_bare_line_citation_fails(tmp_path):
    r = run(tmp_path, ROW, 'As recorded at AGNOTE4482PHI.t1.md:3410 for the claim.\n')
    assert r.returncode == 1 and 'bare line citation' in r.stdout
