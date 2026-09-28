"""glances-autodetect.sh must emit JSON on a real host, not exit 1 in silence.

THE DEFECT
----------
The script runs under `set -euo pipefail`. `detect_ram` ended with

    [ "$RAM_GB" -lt 1 ] && RAM_GB=0

An AND-list is exempt from errexit only while it is NOT the last command. As
the final statement of a function it becomes the function's return status, so
on every host with at least 1 GB of RAM the test is false, `detect_ram` returns
1, the call in `main` trips errexit, and the script exits rc=1 with EMPTY stdout
and stderr. `detect_platform_hints` had the same shape on its last line
(`command -v docker ... && HINT_HAS_DOCKER=true`), which kills the run on any
host without docker even once the RAM line is fixed.

The node-survey Known Road, `hostinger-kvm-setup.sh --node-type auto` and the
node-4090-probe skill all consume this JSON, so none of them could ever get it.

HOW THIS RUNS WITHOUT ROOT OR REAL HARDWARE TOOLS
-------------------------------------------------
The script is copied into a temp dir (so the sibling unifi-probe.sh is absent
and nothing touches the network) and run under a PATH that holds ONLY:
  * symlinks to the real text utilities it needs (awk, sed, grep, python3 ...);
  * stubs for the hardware tools (lscpu, lspci, lsblk, ip, glances, hostname);
  * a stub `id` answering 0, which satisfies `require_root` -- the guard calls
    `id -u` through PATH, so no env override was added to the script.
docker / tailscale / nvidia-smi are present or absent per case, which is what
selects the `detect_platform_hints` path. /proc/meminfo is the host's own: any
machine running this suite has >= 1 GB, which is exactly the failing condition.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "provision" / "glances-autodetect.sh"

# Real utilities the script shells out to. Resolved from the ambient PATH and
# symlinked into the hermetic bin dir.
REAL_TOOLS = (
    "bash", "awk", "sed", "grep", "cat", "mktemp", "rm", "basename", "dirname",
    "readlink", "uname", "tr", "head", "tail", "timeout", "sleep",
)

STUBS = {
    "id": "#!/bin/sh\necho 0\n",
    "hostname": "#!/bin/sh\necho test-node\n",
    "lscpu": (
        "#!/bin/sh\n"
        "cat <<'OUT'\n"
        "Architecture:            x86_64\n"
        "CPU(s):                  4\n"
        "Model name:              AMD EPYC 9354P 32-Core Processor\n"
        "Core(s) per socket:      4\n"
        "Socket(s):               1\n"
        "OUT\n"
    ),
    # No display device: see test_vga_compatible_is_not_amd for why a VGA line
    # cannot be used here yet.
    "lspci": (
        "#!/bin/sh\n"
        "echo '00:03.0 Ethernet controller [0200]: "
        "Red Hat, Inc. Virtio network device [1af4:1000]'\n"
    ),
    "lsblk": (
        "#!/bin/sh\n"
        "echo '{\"blockdevices\":[{\"name\":\"sda\",\"size\":214748364800,"
        "\"rota\":true,\"type\":\"disk\"}]}'\n"
    ),
    "ip": (
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *addr*) echo '2: eth0    inet 203.0.113.10/24 brd 203.0.113.255 "
        "scope global eth0\\       valid_lft forever' ;;\n"
        "  *link*) echo '2: eth0: <BROADCAST,UP> mtu 1500 qdisc fq state UP' ;;\n"
        "esac\n"
    ),
    # glances --export-json-file <file> --stop-after 1 --quiet
    "glances": (
        "#!/bin/sh\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = --export-json-file ]; then echo '{}' > \"$2\"; fi\n"
        "  shift\n"
        "done\n"
    ),
}
PRESENCE_STUB = "#!/bin/sh\nexit 0\n"

# Top-level keys from the JSON SCHEMA block in the script header (lines 21-38).
SCHEMA_KEYS = {
    "os", "arch", "cpu", "ram_gb", "gpus", "disks", "nics", "nic_collisions",
    "platform_hints", "suggested_node_type", "suggestion_confidence",
    "suggestion_rationale", "unifi_topology",
}


def _host_ram_gb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            kb = int(line.split()[1])
            return (kb + 524288) // 1048576
    raise AssertionError("no MemTotal in /proc/meminfo")


def _hermetic_run(tmp_path: Path, *, with_docker: bool, args=("--json",), lspci=None):
    if not Path("/proc/meminfo").is_file():
        pytest.skip("needs Linux /proc/meminfo")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in REAL_TOOLS:
        real = shutil.which(tool)
        if real is None:
            pytest.skip(f"host lacks {tool}")
        (bindir / tool).symlink_to(real)
    (bindir / "python3").symlink_to(sys.executable)
    stubs = dict(STUBS)
    if lspci is not None:
        stubs["lspci"] = f"#!/bin/sh\necho '{lspci}'\n"
    if with_docker:
        stubs["docker"] = PRESENCE_STUB
        stubs["tailscale"] = PRESENCE_STUB
    for name, body in stubs.items():
        p = bindir / name
        p.write_text(body)
        p.chmod(0o755)

    script = tmp_path / "glances-autodetect.sh"
    shutil.copy(SCRIPT, script)
    env = {"PATH": str(bindir), "HOME": str(tmp_path), "LC_ALL": "C"}
    return subprocess.run(
        [str(bindir / "bash"), str(script), *args],
        env=env, capture_output=True, text=True, timeout=60,
    )


@pytest.mark.parametrize("with_docker", [True, False], ids=["docker", "no-docker"])
def test_json_mode_exits_zero_with_schema(tmp_path, with_docker):
    assert _host_ram_gb() >= 1, "precondition: the defect needs RAM >= 1 GB"
    r = _hermetic_run(tmp_path, with_docker=with_docker)
    assert r.returncode == 0, (
        f"rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r} -- an rc=1 "
        "with empty output is the errexit-on-function-tail signature"
    )
    data = json.loads(r.stdout)
    assert set(data) == SCHEMA_KEYS
    assert data["ram_gb"] == _host_ram_gb()
    assert data["cpu"]["cores_logical"] == 4
    assert data["disks"] == [{"name": "sda", "size_gb": 200, "rotational": True}]
    assert data["gpus"] == []
    assert data["unifi_topology"] is None
    assert data["platform_hints"]["has_docker"] is with_docker
    assert data["platform_hints"]["has_tailscale"] is with_docker


def test_suggest_mode_exits_zero(tmp_path):
    r = _hermetic_run(tmp_path, with_docker=False, args=("--suggest",))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr!r}"
    assert r.stdout.strip()


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN, out of scope for the errexit fix: the AMD filter "
    "`vga.*(amd|radeon|ati)` matches the 'ati' inside 'compATIble', so every "
    "'VGA compatible controller' line -- a KVM's Cirrus/bochs adapter, an Intel "
    "iGPU, an NVIDIA card without nvidia-smi -- is also counted as an AMD GPU."
))
def test_vga_compatible_is_not_amd(tmp_path):
    r = _hermetic_run(
        tmp_path, with_docker=True,
        lspci="00:02.0 VGA compatible controller [0300]: "
              "Cirrus Logic GD 5446 [1013:00b8]",
    )
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr!r}"
    vendors = [g["vendor"] for g in json.loads(r.stdout)["gpus"]]
    assert "amd" not in vendors, vendors
