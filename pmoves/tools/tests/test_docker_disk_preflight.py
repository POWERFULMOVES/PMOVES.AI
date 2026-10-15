# pmoves/tools/tests/test_docker_disk_preflight.py
"""Unit tests for the read-only Docker Desktop data-disk preflight.

Everything here runs on Linux CI: the pure pieces (header check, event
parsing/evaluation, init.log scanning, exit aggregation) take temp files and
canned PowerShell output. Only the junction-resolution test needs a real
Windows host and is skipped elsewhere. No test touches the real Docker disk.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import docker_disk_preflight as ddp  # noqa: E402

NOW = dt.datetime(2026, 10, 14, 12, 0, 0, tzinfo=dt.timezone.utc)


def _r(status: str) -> ddp.CheckResult:
    return ddp.CheckResult("x", status, "s")


# ------------------------------------------------------ exit aggregation ----


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ([ddp.PASS, ddp.PASS], ddp.EXIT_PASS),
        ([ddp.PASS, ddp.WARN], ddp.EXIT_WARN),
        ([ddp.WARN, ddp.FAIL, ddp.PASS], ddp.EXIT_FAIL),
        ([ddp.SKIP, ddp.FAIL], ddp.EXIT_FAIL),
        ([ddp.SKIP, ddp.WARN], ddp.EXIT_WARN),
        ([ddp.PASS, ddp.SKIP], ddp.EXIT_UNMEASURED),
        ([], ddp.EXIT_UNMEASURED),
    ],
)
def test_aggregate_exit(statuses, expected):
    assert ddp.aggregate_exit([_r(s) for s in statuses]) == expected


def test_overall_label():
    assert ddp.overall_label(ddp.EXIT_UNMEASURED) == "COULD-NOT-MEASURE"
    assert ddp.overall_label(ddp.EXIT_FAIL) == ddp.FAIL


# ------------------------------------------------------- vhdx header --------


def test_vhdx_header_ok(tmp_path):
    f = tmp_path / "docker_data.vhdx"
    f.write_bytes(b"vhdxfile" + b"\0" * 64)
    res = ddp.check_vhdx_header(str(f))
    assert res.status == ddp.PASS


def test_vhdx_header_wrong_magic(tmp_path):
    f = tmp_path / "docker_data.vhdx"
    f.write_bytes(b"\0" * 64)
    res = ddp.check_vhdx_header(str(f))
    assert res.status == ddp.FAIL
    assert "signature" in res.summary


def test_vhdx_header_short_file(tmp_path):
    f = tmp_path / "docker_data.vhdx"
    f.write_bytes(b"vhd")
    assert ddp.check_vhdx_header(str(f)).status == ddp.FAIL


def test_vhdx_header_missing():
    assert ddp.check_vhdx_header(None).status == ddp.FAIL


def test_vhdx_header_io_error_is_fail(tmp_path):
    f = tmp_path / "docker_data.vhdx"
    f.write_bytes(b"vhdxfile")
    with mock.patch("builtins.open", side_effect=OSError(5, "Input/output error")):
        res = ddp.check_vhdx_header(str(f))
    assert res.status == ddp.FAIL


def test_vhdx_header_sharing_violation_is_warn(tmp_path):
    f = tmp_path / "docker_data.vhdx"
    f.write_bytes(b"vhdxfile")
    exc = PermissionError(13, "in use")
    exc.winerror = 32
    with mock.patch("builtins.open", side_effect=exc):
        res = ddp.check_vhdx_header(str(f))
    assert res.status == ddp.WARN


def test_find_vhdx_prefers_current_layout(tmp_path):
    (tmp_path / "disk").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ext4.vhdx").write_bytes(b"vhdxfile")
    assert ddp.find_vhdx(str(tmp_path)).endswith("ext4.vhdx")
    (tmp_path / "disk" / "docker_data.vhdx").write_bytes(b"vhdxfile")
    assert ddp.find_vhdx(str(tmp_path)).endswith("docker_data.vhdx")


# ------------------------------------------------------ event parsing -------

EVENT_153 = {
    "time": "2026-10-13T17:02:28Z",
    "id": 153,
    "provider": "disk",
    "message": "The IO operation at logical block address 0x349c72db8 for Disk 6 "
    "(PDO name: \\Device\\00000082) was retried.",
}
EVENT_129 = {
    "time": "2026-10-13T17:01:52Z",
    "id": 129,
    "provider": "UASPStor",
    "message": "Reset to device, \\Device\\RaidPort4, was issued.",
}
EVENT_7 = {
    "time": "2026-10-13T17:03:00Z",
    "id": 7,
    "provider": "disk",
    "message": "The device, \\Device\\Harddisk6\\DR6, has a bad block.",
}


def test_parse_events_array_object_and_empty():
    assert ddp.parse_events("") == []
    assert ddp.parse_events("null") == []
    single = ddp.parse_events(json.dumps(EVENT_153))
    assert len(single) == 1 and single[0]["disk"] == 6
    many = ddp.parse_events(json.dumps([EVENT_153, EVENT_129, EVENT_7]))
    assert [e["disk"] for e in many] == [6, None, 6]


def test_parse_events_skips_malformed_rows():
    rows = [EVENT_153, {"id": "not-a-number"}, "junk"]
    assert len(ddp.parse_events(json.dumps(rows))) == 1


def test_event_disk_number_forms():
    assert ddp.event_disk_number("for Disk 12 (PDO") == 12
    assert ddp.event_disk_number("\\Device\\Harddisk3\\DR3") == 3
    assert ddp.event_disk_number("Reset to device, \\Device\\RaidPort4") is None


def _eval(rows, docker_disk=6, hours=72, fail_hours=1.0):
    return ddp.evaluate_events(ddp.parse_events(json.dumps(rows)), docker_disk,
                               hours, fail_hours, now=NOW)


def test_events_none_is_pass():
    assert _eval([]).status == ddp.PASS


def test_events_old_retries_on_docker_disk_warn():
    # The 2026-10-13 signature, evaluated ~19h later: WARN, not FAIL.
    res = _eval([EVENT_153] * 85 + [EVENT_129])
    assert res.status == ddp.WARN
    assert res.data["ours"] == 85
    assert res.data["unattributed"] == 1


def test_events_recent_retries_on_docker_disk_fail():
    recent = dict(EVENT_153, time="2026-10-14T11:45:00Z")
    assert _eval([recent]).status == ddp.FAIL


def test_events_bad_block_on_docker_disk_fail_even_if_old():
    assert _eval([EVENT_7]).status == ddp.FAIL


def test_events_other_disk_only_pass():
    other = dict(EVENT_153, message=EVENT_153["message"].replace("Disk 6", "Disk 2"))
    res = _eval([other])
    assert res.status == ddp.PASS
    assert res.data["other"] == 1


def test_events_unattributed_only_warn():
    assert _eval([EVENT_129]).status == ddp.WARN


def test_events_unknown_docker_disk_treats_all_as_unattributed():
    res = _eval([EVENT_153], docker_disk=None)
    assert res.status == ddp.WARN
    assert res.data["unattributed"] == 1


# -------------------------------------------------- physical disk health ----


def _disk(**kw):
    base = {"disk_number": 6, "friendly_name": "X", "bus_type": "NVMe",
            "disk_health": "Healthy", "disk_operational": "Online", "pd_found": True,
            "pd_health": "Healthy", "pd_operational": "OK", "pd_media_type": "SSD"}
    base.update(kw)
    return base


def test_physical_health_states():
    assert ddp.check_physical_health(_disk(), None).status == ddp.PASS
    assert ddp.check_physical_health(_disk(pd_health="Warning"), None).status == ddp.WARN
    assert ddp.check_physical_health(_disk(pd_health="Unhealthy"), None).status == ddp.FAIL
    assert ddp.check_physical_health(
        _disk(pd_operational="Lost Communication"), None).status == ddp.FAIL
    assert ddp.check_physical_health(None, "boom").status == ddp.SKIP


def test_location_usb_warn_and_internal_pass(tmp_path):
    link = {"configured": str(tmp_path), "exists": True, "is_link": True,
            "link_target": "I:\\DockerData\\disk", "resolved": "I:\\DockerData\\disk"}
    assert ddp.check_location(link, _disk(bus_type="USB"), None).status == ddp.WARN
    assert ddp.check_location(link, _disk(bus_type="NVMe"), None).status == ddp.PASS
    assert ddp.check_location(link, None, "no powershell").status == ddp.SKIP
    gone = dict(link, exists=False)
    assert ddp.check_location(gone, None, None).status == ddp.FAIL


# ------------------------------------------------------ init.log scan -------


def test_scan_init_log_text_levels():
    clean = ddp.scan_init_log_text("boot ok\nmounted /dev/sdd\n")
    assert clean["severity"] == ddp.PASS and clean["hits"] == {}
    warn = ddp.scan_init_log_text("virtiofs: I/O error on share\n")
    assert warn["severity"] == ddp.WARN
    fail = ddp.scan_init_log_text(
        "[ 12.3] Buffer I/O error on dev sdd, logical block 0\n"
        "[ 12.4] EXT4-fs error (device sdd): ext4_find_entry\n"
        "wsl-bootstrap: detected no file system. Formatting\n")
    assert fail["severity"] == ddp.FAIL
    assert fail["hits"] == {"buffer-io-error": 1, "ext4-error": 1,
                            "detected-no-filesystem": 1}
    # A FAIL line is not double-counted as a generic I/O error.
    assert "io-error" not in fail["hits"]
    assert len(fail["samples"]) == 3


def test_check_init_logs_newest_files(tmp_path):
    old = tmp_path / "init.log.20261013-000000.000"
    old.write_text("EXT4-fs error (device sdd)\n")
    os.utime(old, (1_000, 1_000))
    mid = tmp_path / "init.log.20261014-000000.000"
    mid.write_text("all fine\n")
    os.utime(mid, (2_000, 2_000))
    cur = tmp_path / "init.log"
    cur.write_text("")
    os.utime(cur, (3_000, 3_000))
    (tmp_path / "unrelated.log").write_text("EXT4-fs error\n")

    # Only the 2 newest are scanned -> the old EXT4 error is out of scope.
    res = ddp.check_init_logs(str(tmp_path), 2)
    assert res.status == ddp.PASS
    assert [f["file"] for f in res.data["files"]] == ["init.log", mid.name]

    res3 = ddp.check_init_logs(str(tmp_path), 3)
    assert res3.status == ddp.FAIL
    assert res3.data["totals"] == {"ext4-error": 1}


def test_check_init_logs_missing_dir_skip(tmp_path):
    assert ddp.check_init_logs(str(tmp_path / "nope"), 3).status == ddp.SKIP


# ------------------------------------------------------- helpers / main -----


def test_display_path_hides_profile():
    env = {"LOCALAPPDATA": "C:\\Users\\someone\\AppData\\Local",
           "USERPROFILE": "C:\\Users\\someone"}
    assert ddp.display_path("C:\\Users\\someone\\AppData\\Local\\Docker\\wsl\\disk",
                            env) == "%LOCALAPPDATA%\\Docker\\wsl\\disk"
    assert ddp.display_path("c:\\users\\someone\\x", env) == "%USERPROFILE%\\x"
    assert ddp.display_path("I:\\DockerData\\disk", env) == "I:\\DockerData\\disk"


def test_strip_extended_prefix():
    assert ddp.strip_extended_prefix("\\\\?\\I:\\DockerData\\disk") == "I:\\DockerData\\disk"
    assert ddp.strip_extended_prefix("\\\\?\\UNC\\srv\\share") == "\\\\srv\\share"
    assert ddp.strip_extended_prefix("I:\\x") == "I:\\x"


def test_run_powershell_nonzero_raises():
    fake = mock.Mock(returncode=1, stdout=b"", stderr=b"Get-Partition : No MSFT_Partition\n")
    with mock.patch.object(ddp, "_find_powershell", return_value="powershell.exe"), \
            mock.patch.object(ddp.subprocess, "run", return_value=fake):
        with pytest.raises(RuntimeError, match="No MSFT_Partition"):
            ddp.run_powershell("Get-Partition")


def test_run_powershell_missing_raises():
    with mock.patch.object(ddp, "_find_powershell", return_value=None):
        with pytest.raises(RuntimeError, match="not found"):
            ddp.run_powershell("x")


def test_query_disk_info_rejects_non_letter():
    with pytest.raises(RuntimeError):
        ddp.query_disk_info("I:; Remove-Item x")


def test_query_disk_info_parses(monkeypatch):
    monkeypatch.setattr(ddp, "run_powershell", lambda s: json.dumps(_disk(bus_type="USB")))
    assert ddp.query_disk_info("I:")["bus_type"] == "USB"


def test_main_non_windows_is_unmeasured(monkeypatch, capsys):
    monkeypatch.setattr(ddp.sys, "platform", "linux")
    assert ddp.main([]) == ddp.EXIT_UNMEASURED
    assert "Windows-only" in capsys.readouterr().out
    assert ddp.main(["--json"]) == ddp.EXIT_UNMEASURED
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "COULD-NOT-MEASURE"


def test_main_usage_error():
    assert ddp.main(["--hours", "0"]) == ddp.EXIT_USAGE
    assert ddp.main(["--bogus"]) == ddp.EXIT_USAGE


def test_main_end_to_end_mocked(monkeypatch, tmp_path, capsys):
    """Full run against a fake %LOCALAPPDATA% tree with canned PowerShell output."""
    lad = tmp_path / "Local"
    disk_dir = lad / "Docker" / "wsl" / "disk"
    disk_dir.mkdir(parents=True)
    (disk_dir / "docker_data.vhdx").write_bytes(b"vhdxfile" + b"\0" * 8)
    logs = lad / "Docker" / "log" / "vm"
    logs.mkdir(parents=True)
    (logs / "init.log").write_text("boot ok\n")

    def fake_ps(script):
        if "Get-WinEvent" in script:
            return json.dumps([EVENT_153, EVENT_129])
        return json.dumps(_disk(bus_type="USB"))

    monkeypatch.setattr(ddp.sys, "platform", "win32")
    monkeypatch.setattr(ddp, "run_powershell", fake_ps)
    # Pretend the tmp tree lives on drive I: so the drive-letter mapping works
    # on Linux too.
    monkeypatch.setattr(ddp, "drive_of", lambda p: "I:")
    monkeypatch.setenv("LOCALAPPDATA", str(lad))

    code = ddp.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    by_name = {c["name"]: c["status"] for c in payload["checks"]}
    assert by_name == {
        "data-disk-location": ddp.WARN,
        "vhdx-header": ddp.PASS,
        "disk-events": ddp.WARN,
        "physical-disk-health": ddp.PASS,
        "vm-init-log": ddp.PASS,
    }
    assert code == ddp.EXIT_WARN == payload["exit_code"]
    # The operator's profile path must not leak into --json output.
    link = payload["checks"][0]["data"]["link"]
    assert link["configured"].startswith("%LOCALAPPDATA%")
    assert str(lad) not in json.dumps(link)


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows-only")
def test_resolve_disk_dir_follows_junction(tmp_path):
    import subprocess

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                          capture_output=True)
    if proc.returncode != 0:
        pytest.skip("could not create a junction in the temp dir")
    info = ddp.resolve_disk_dir(str(link))
    assert info["is_link"] is True
    assert os.path.normcase(info["link_target"]) == os.path.normcase(str(target))
    assert info["exists"] is True
