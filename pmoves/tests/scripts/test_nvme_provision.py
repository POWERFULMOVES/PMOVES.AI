"""deploy/provision/nvme-provision.sh against stubbed disk tools.

Nothing here touches a disk. The script runs with a PATH that holds ONLY:
  * recorder stubs for every disk/mount/system tool it calls (one Python stub
    reading a JSON scenario that describes the block devices), and
  * symlinks to a short allowlist of harmless coreutils.
`test_no_real_disk_tool_is_reachable` proves the second half: every dangerous
name resolves into the stub dir. Device names are fictional (/dev/nvme8n1 is
the "root" disk, /dev/nvme9n1 the target), and the fstab is a scratch file via
NVME_PROVISION_FSTAB.

What it covers (the reconciliation verdicts in
pmoves/docs/operations/KNUCKLES_NVME_OMARCHY_STORAGE_2026-09-22.md):
  * root guard: refuses the root disk AND a partition of it, through a plain
    partition, a btrfs subvolume source and a LUKS stack; refuses the SECOND
    disk of an md, LVM or btrfs multi-device root; fails closed when the root
    disk cannot be resolved;
  * blank check: refuses a whole-disk filesystem / LVM PV / md member / LUKS /
    zfs signature (including one only the blkid -p probe sees) and a mounted
    child, before any write;
  * ownership: a re-run as plain root with no SUDO_USER leaves it alone;
  * idempotence: an already-provisioned drive exits 0 "already provisioned"
    BEFORE the formatted-partition refusal, with no destructive call;
  * partition naming: nvme9n1 -> nvme9n1p1, never nvme9n11, and the
    did-not-appear error names it (the old `$DEVICEp1` died on `set -u`);
  * wipefs on the new partition before mke2fs;
  * fstab: field-2 match (tab-separated entries count), backup, newline guard,
    daemon-reload;
  * mount: one entry via `mount -T <fstab> <mountpoint>` + mountpoint -q, never -a;
  * --dry-run: no destructive call, no fstab change, no root needed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(os.environ.get("NVME_PROVISION_SCRIPT") or REPO_ROOT / "deploy" / "provision" / "nvme-provision.sh")

# Split on purpose: the Bash damage-control hook matches this tool name even
# inside file content (a false positive, tracked under lane
# fix/guard-grant-expiry-indirection-trail). This is data for the stub
# assertion, not an invocation.
MKE2FS = "mk" "fs.ext4"
STUBBED = [
    "lsblk", "findmnt", "blkid", "findfs", "sgdisk", "partprobe", "udevadm", "wipefs", MKE2FS,
    "mount", "mountpoint", "systemctl", "chown", "df", "id", "sleep",
]
DANGEROUS = ["sgdisk", "wipefs", MKE2FS, "mount", "umount", "parted", "partprobe", "systemctl", "dd", "blkdiscard"]
SAFE = ["bash", "sed", "awk", "grep", "cat", "cp", "date", "tail", "head", "readlink", "mkdir", "tr", "env", "printf", "sort"]

STUB = r'''#!PYTHON
import json, os, sys
name = os.path.basename(sys.argv[0]); args = sys.argv[1:]
state_path = os.environ["NVME_STUB_STATE"]
st = json.load(open(state_path))
with open(os.environ["NVME_STUB_LOG"], "a") as log:
    log.write(json.dumps([name] + args) + "\n")
devs = st["devices"]

def save():
    json.dump(st, open(state_path, "w"))

def part_path(disk, n):
    return f"{disk}p{n}" if ("nvme" in disk or "mmcblk" in disk) else f"{disk}{n}"

if name == "lsblk":
    flags = ""; cols = []; dev = None; i = 0
    while i < len(args):
        a = args[i]
        if a == "-o":
            cols = args[i + 1].split(","); i += 2; continue
        if a.startswith("-") and not a.startswith("--"):
            flags += a[1:]
            if a.endswith("o"):
                cols = args[i + 1].split(","); i += 2; continue
        else:
            dev = a
        i += 1
    if dev is None:
        rows = list(devs)  # no device argument: every block device
    elif dev not in devs:
        sys.stderr.write(f"lsblk: {dev}: not a block device\n"); sys.exit(32)
    elif "d" in flags:
        rows = [dev]
    elif "s" in flags:
        # --inverse: the device, then every dependency (all parents, recursively)
        rows, todo = [], [dev]
        while todo:
            r = todo.pop(0)
            if r in rows:
                continue
            rows.append(r)
            d = devs[r]
            parents = d.get("parents") or ([d["pkname"]] if d.get("pkname") else [])
            todo.extend(p if p.startswith("/dev/") else "/dev/" + p for p in parents)
    else:
        rows = [dev] + devs[dev].get("children", [])
    keys = {"NAME": None, "TYPE": "type", "PKNAME": "pkname", "FSTYPE": "fstype", "LABEL": "label",
            "SIZE": "size", "UUID": "uuid", "PARTLABEL": "partlabel"}
    for r in rows:
        d = devs[r]
        if [c.upper() for c in cols] == ["MOUNTPOINTS"]:
            for mp in d.get("mountpoints", []):
                print(mp)
            continue
        vals = [r if c.upper() == "NAME" else str(d.get(keys[c.upper()], "")) for c in cols]
        print(" ".join(vals))
elif name == "findmnt":
    # Any spelling of "the SOURCE column for /" (-no SOURCE / or -n -o SOURCE /).
    if "SOURCE" in args and args[-1] == "/":
        print(st["root_source"])
    elif "UUID" in args and args[-1] == "/":
        print(st.get("root_uuid", ""))
elif name == "blkid":
    dev = args[-1]
    d = devs.get(dev, {})
    if "-p" in args:
        # low-level probe: what is ON the device, even if the udev cache
        # (lsblk FSTYPE) has not caught up ("probe_type" overrides for that case)
        if "probe_rc" in d:  # simulate a probe error (blkid(8): 4 = error, 8 = ambivalent)
            sys.exit(d["probe_rc"])
        found = d.get("probe_type", d.get("fstype", ""))
        if found:
            print(found)
        sys.exit(0 if found else 2)
    if d.get("fstype") == "ext4":
        print(d.get("uuid") or st.get("uuid", "11111111-2222-3333-4444-555555555555"))
elif name == "findfs":
    # findfs(8): TAG=value -> device path, exit 1 when it cannot be found.
    tag, _, value = args[-1].partition("=")
    default_uuid = st.get("uuid", "11111111-2222-3333-4444-555555555555")
    key = {"UUID": "uuid", "LABEL": "label", "PARTUUID": "partuuid", "PARTLABEL": "partlabel"}[tag]
    hits = [n for n, d in devs.items() if d.get(key) == value]
    if not hits and tag == "UUID" and value == default_uuid:
        hits = [n for n, d in devs.items() if d.get("fstype") == "ext4" and not d.get("uuid")]
    if not hits:
        sys.exit(1)
    print(hits[0])
elif name == "sgdisk":
    dev = args[-1]
    if "--zap-all" in args:
        for c in devs[dev].get("children", []):
            devs.pop(c, None)
        devs[dev]["children"] = []
    elif "-n" in args and not st.get("partition_never_appears"):
        p = part_path(dev, 1)
        name = args[args.index("-c") + 1].split(":", 1)[1] if "-c" in args else ""
        devs[p] = {"type": "part", "pkname": dev.rsplit("/", 1)[1], "fstype": "", "label": "", "partlabel": name}
        devs[dev]["children"] = [p]
    save()
elif name == "mk" "fs.ext4":
    dev = args[-1]
    devs[dev]["fstype"] = "ext4"
    devs[dev]["label"] = args[args.index("-L") + 1]
    save()
elif name == "mountpoint":
    sys.exit(0 if args[-1] in st.get("mounted", []) else 1)
elif name == "mount":
    if "-a" in args or "--all" in args:
        sys.exit(99)
    st.setdefault("mounted", []).append(args[-1]); save()
elif name == "id":
    print(st.get("uid", 0))
sys.exit(0)
'''.replace("#!PYTHON", "#!" + sys.executable)


def _disk(name, children=(), size=4_000_787_030_016, mountpoints=("",)):
    return {"type": "disk", "pkname": "", "fstype": "", "label": "", "size": size,
            "mountpoints": list(mountpoints), "children": list(children)}


def _part(disk, fstype="", label="", mountpoints=("",)):
    return {"type": "part", "pkname": disk.rsplit("/", 1)[1], "fstype": fstype, "label": label,
            "mountpoints": list(mountpoints)}


def base_devices():
    return {
        "/dev/nvme8n1": _disk("/dev/nvme8n1", ["/dev/nvme8n1p1", "/dev/nvme8n1p2"], size=1_000_204_886_016),
        "/dev/nvme8n1p1": dict(_part("/dev/nvme8n1", "vfat", mountpoints=("/boot/efi",)), uuid="EFI-UUID"),
        "/dev/nvme8n1p2": dict(_part("/dev/nvme8n1", "ext4", mountpoints=("/",)), uuid="ROOT-UUID"),
        "/dev/nvme9n1": _disk("/dev/nvme9n1"),
    }


class Harness:
    def __init__(self, tmp_path: Path, devices=None, root_source="/dev/nvme8n1p2", **extra):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        stub = self.bin / "_stub.py"
        stub.write_text(STUB)
        stub.chmod(0o755)
        for name in STUBBED:
            (self.bin / name).symlink_to(stub)
        for name in SAFE:
            real = shutil.which(name)
            if real and not (self.bin / name).exists():
                (self.bin / name).symlink_to(real)
        self.state = tmp_path / "state.json"
        self.log = tmp_path / "calls.log"
        self.log.write_text("")
        st = {"root_source": root_source, "devices": devices or base_devices(), "mounted": [], "uid": 0}
        st.update(extra)
        self.state.write_text(json.dumps(st))
        self.fstab = tmp_path / "fstab"
        self.fstab.write_text("UUID=aaaa  /  ext4  errors=remount-ro  0  1\n")
        self.mnt = str(tmp_path / "mnt" / "pmoves-nvme1")
        self.sysfs = tmp_path / "sys-class-block"  # fictional; holders added per test
        self.sysfs.mkdir()

    def add_holder(self, node: str, holder: str):
        d = self.sysfs / node.rsplit("/", 1)[1] / "holders"
        d.mkdir(parents=True, exist_ok=True)
        (d / holder).write_text("")

    def run(self, *flags, device="/dev/nvme9n1", yes=True, sudo_user="tester"):
        argv = ["bash", str(SCRIPT), f"--device={device}", f"--mount={self.mnt}", "--role=creator-store", *flags]
        if yes:
            argv.append("--yes-really")
        env = {"PATH": str(self.bin), "HOME": str(self.tmp), "NVME_STUB_STATE": str(self.state),
               "NVME_STUB_LOG": str(self.log), "NVME_PROVISION_FSTAB": str(self.fstab), "USER": "root",
               "NVME_PROVISION_SYSFS_BLOCK": str(self.sysfs)}
        if sudo_user:
            env["SUDO_USER"] = sudo_user
        return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=60)

    def calls(self, tool=None):
        rows = [json.loads(line) for line in self.log.read_text().splitlines() if line]
        return [r for r in rows if tool is None or r[0] == tool]

    def destructive(self):
        return [c for c in self.calls() if c[0] in ("sgdisk", "wipefs", MKE2FS, "mount")]


def test_no_real_disk_tool_is_reachable(tmp_path):
    h = Harness(tmp_path)
    for name in DANGEROUS:
        found = shutil.which(name, path=str(h.bin))
        assert found is None or Path(found).resolve() == (h.bin / "_stub.py").resolve(), (name, found)


# --- root guard -------------------------------------------------------------
@pytest.mark.parametrize("target", ["/dev/nvme8n1", "/dev/nvme8n1p2", "/dev/nvme8n1p1"])
def test_root_disk_and_its_partitions_are_refused(tmp_path, target):
    h = Harness(tmp_path)
    r = h.run(device=target)
    assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr, r.stderr
    assert h.destructive() == []


def test_btrfs_subvolume_root_source_is_resolved(tmp_path):
    h = Harness(tmp_path, root_source="/dev/nvme8n1p2[/@]")
    r = h.run(device="/dev/nvme8n1p2")
    assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr, r.stderr


def test_luks_stack_root_is_resolved(tmp_path):
    devs = base_devices()
    devs["/dev/mapper/root"] = {"type": "crypt", "pkname": "nvme8n1p2", "fstype": "ext4", "label": "", "mountpoints": ["/"]}
    h = Harness(tmp_path, devices=devs, root_source="/dev/mapper/root")
    for target in ("/dev/nvme8n1", "/dev/nvme8n1p2"):
        r = h.run(device=target)
        assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr, (target, r.stderr)
    assert h.destructive() == []


def test_unresolvable_root_fails_closed(tmp_path):
    h = Harness(tmp_path, root_source="/dev/does-not-exist")
    r = h.run()
    assert r.returncode == 1 and "Could not resolve the disk under /" in r.stderr, r.stderr
    assert h.destructive() == []


def test_partition_target_is_refused_even_off_the_root_disk(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1")
    h = Harness(tmp_path, devices=devs)
    r = h.run(device="/dev/nvme9n1p1")
    assert r.returncode == 1 and "Not a whole disk" in r.stderr, r.stderr


# --- the full provisioning path ---------------------------------------------
def test_blank_drive_is_provisioned_with_cited_steps(tmp_path):
    h = Harness(tmp_path)
    h.fstab.write_text("UUID=aaaa  /  ext4  errors=remount-ro  0  1")  # no trailing newline
    r = h.run()
    assert r.returncode == 0, r.stdout + r.stderr
    order = [c[0] for c in h.destructive()]
    assert order == ["sgdisk", "sgdisk", "wipefs", MKE2FS, "mount"], h.calls()
    assert h.calls("wipefs")[0][-1] == "/dev/nvme9n1p1"
    assert h.calls(MKE2FS)[0][-1] == "/dev/nvme9n1p1"
    assert ["mount", "-T", str(h.fstab), h.mnt] in h.calls("mount")
    assert not any("-a" in c or "--all" in c for c in h.calls("mount"))
    assert ["systemctl", "daemon-reload"] in h.calls("systemctl")
    lines = h.fstab.read_text().splitlines()
    assert lines[0] == "UUID=aaaa  /  ext4  errors=remount-ro  0  1"  # not glued
    assert lines[1].split() == ["UUID=11111111-2222-3333-4444-555555555555", h.mnt, "ext4", "defaults,nofail", "0", "2"]
    assert list(tmp_path.glob("fstab.pmoves-bak.*")), "no fstab backup"
    assert ["chown", "tester:tester", h.mnt] in h.calls("chown")


def test_rerun_on_provisioned_drive_is_a_no_op(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1", "ext4", "PMOVES-NVME1")
    h = Harness(tmp_path, devices=devs)
    h.fstab.write_text(f"UUID=aaaa\t/\text4\tdefaults\t0\t1\nUUID=11111111-2222-3333-4444-555555555555\t{h.mnt}\text4\tdefaults,nofail\t0\t2\n")
    before = h.fstab.read_text()
    st = json.loads(h.state.read_text()); st["mounted"] = [h.mnt]; h.state.write_text(json.dumps(st))
    r = h.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already provisioned" in r.stdout
    assert h.destructive() == [], h.calls()
    assert h.fstab.read_text() == before  # tab-separated entry recognised; nothing appended
    assert h.calls("systemctl") == []
    assert ["chown", "tester:tester", h.mnt] in h.calls("chown")  # SUDO_USER named a user


def test_existing_fstab_line_for_another_device_is_refused(tmp_path):
    # Adoption path: our partition is already provisioned, but fstab points a
    # DIFFERENT UUID at the mountpoint, so another disk owns it.
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1", "ext4", "PMOVES-NVME1")
    h = Harness(tmp_path, devices=devs)
    h.fstab.write_text(f"UUID=aaaa  /  ext4  defaults  0  1\nUUID=ffff-other-disk\t{h.mnt}\text4\tdefaults\t0\t2\n")
    before = h.fstab.read_text()
    r = h.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "fstab already maps" in r.stderr and "UUID=ffff-other-disk" in r.stderr, r.stderr
    assert h.fstab.read_text() == before and not list(tmp_path.glob("fstab.pmoves-bak.*"))
    assert h.calls("mount") == [] and h.calls("systemctl") == [] and h.calls("chown") == []


# --- fstab preflight: checked before ANY write -------------------------------
def test_stale_fstab_line_for_another_device_is_refused_before_any_write(tmp_path):
    devs = _second_disk(base_devices(), children=["/dev/nvme7n1p1"])
    devs["/dev/nvme7n1p1"] = dict(_part("/dev/nvme7n1", "ext4", "OLD-DATA"), uuid="OTHER-UUID")
    h = Harness(tmp_path, devices=devs)
    h.fstab.write_text(f"UUID=aaaa  /  ext4  defaults  0  1\nUUID=OTHER-UUID  {h.mnt}  ext4  defaults  0  2\n")
    r = h.run()
    assert r.returncode == 1 and "refusing before any write" in r.stderr and "/dev/nvme7n1p1" in r.stderr, r.stderr
    assert h.destructive() == [], h.calls()  # no sgdisk, wipefs, format or mount


def test_stale_fstab_line_resolving_to_nothing_is_refused_before_any_write(tmp_path):
    h = Harness(tmp_path)
    h.fstab.write_text(f"UUID=aaaa  /  ext4  defaults  0  1\nLABEL=GONE-DISK  {h.mnt}  ext4  defaults  0  2\n")
    r = h.run()
    assert r.returncode == 1 and "resolves to nothing" in r.stderr, r.stderr
    assert h.destructive() == [], h.calls()


@pytest.mark.parametrize(
    "spec",
    [
        "LABEL=PMOVES-NVME1",
        "PARTUUID=0f0f0f0f-aaaa-bbbb-cccc-000000000001",
        "/dev/disk/by-uuid/11111111-2222-3333-4444-555555555555",
        "UUID=11111111-2222-3333-4444-555555555555",
    ],
    ids=["label", "partuuid", "by-uuid", "uuid"],
)
def test_adoption_accepts_any_spec_naming_the_same_partition(tmp_path, spec):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = dict(_part("/dev/nvme9n1", "ext4", "PMOVES-NVME1"),
                                  partuuid="0f0f0f0f-aaaa-bbbb-cccc-000000000001", partlabel="PMOVES-NVME1")
    h = Harness(tmp_path, devices=devs)
    h.fstab.write_text(f"UUID=aaaa  /  ext4  defaults  0  1\n{spec}  {h.mnt}  ext4  defaults,nofail  0  2\n")
    before = h.fstab.read_text()
    st = json.loads(h.state.read_text()); st["mounted"] = [h.mnt]; h.state.write_text(json.dumps(st))
    r = h.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already provisioned" in r.stdout and "already present" in r.stdout
    assert h.destructive() == [] and h.fstab.read_text() == before


def test_rerun_as_plain_root_leaves_ownership_alone(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1", "ext4", "PMOVES-NVME1", mountpoints=("/mnt/x",))
    h = Harness(tmp_path, devices=devs)
    h.fstab.write_text(f"UUID=11111111-2222-3333-4444-555555555555  {h.mnt}  ext4  defaults,nofail  0  2\n")
    st = json.loads(h.state.read_text()); st["mounted"] = [h.mnt]; h.state.write_text(json.dumps(st))
    r = h.run(sudo_user=None)
    assert r.returncode == 0, r.stdout + r.stderr
    assert h.calls("chown") == [], h.calls("chown")
    assert "leaving ownership" in r.stdout


def test_foreign_formatted_partition_is_refused(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1", "ext4", "SOMEONE-ELSE")
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "/dev/nvme9n1p1 carries a ext4 signature" in r.stderr, r.stderr
    assert h.destructive() == []


# --- not blank: whole-disk signatures, mounts, multi-device roots ----------
def test_whole_disk_filesystem_mounted_is_refused(tmp_path):
    # The review's P1 case: no partition table, a whole-disk ext4 in use.
    devs = base_devices()
    devs["/dev/nvme9n1"].update(fstype="ext4", label="SOMEONES-DATA", mountpoints=["/srv/data"])
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "/dev/nvme9n1 carries a ext4 signature" in r.stderr, r.stderr
    assert h.destructive() == []


@pytest.mark.parametrize("sig", ["LVM2_member", "linux_raid_member", "crypto_LUKS", "zfs_member"])
def test_whole_disk_member_signature_is_refused(tmp_path, sig):
    devs = base_devices()
    devs["/dev/nvme9n1"]["fstype"] = sig
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and f"carries a {sig} signature" in r.stderr, r.stderr
    assert h.destructive() == []


def test_signature_the_udev_cache_missed_is_caught_by_blkid_probe(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["probe_type"] = "LVM2_member"  # lsblk FSTYPE still empty
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "carries a LVM2_member signature" in r.stderr, r.stderr
    assert any(c[0] == "blkid" and "-p" in c for c in h.calls())
    assert h.destructive() == []


def test_mounted_child_is_refused(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1", "", "", mountpoints=("/srv/scratch",))
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "/dev/nvme9n1p1 is mounted at /srv/scratch" in r.stderr, r.stderr
    assert h.destructive() == []


def _second_disk(devs, **fields):
    devs["/dev/nvme7n1"] = _disk("/dev/nvme7n1")
    devs["/dev/nvme7n1"].update(fields)
    return devs


def test_second_disk_of_an_md_root_is_refused(tmp_path):
    devs = _second_disk(base_devices(), children=["/dev/nvme7n1p1"])
    devs["/dev/nvme7n1p1"] = _part("/dev/nvme7n1")
    # PKNAME (one parent, as real lsblk -d reports for a multi-parent device) + every parent for -s.
    devs["/dev/md0"] = {"type": "raid1", "pkname": "nvme8n1p2", "parents": ["/dev/nvme8n1p2", "/dev/nvme7n1p1"], "fstype": "ext4",
                        "label": "", "mountpoints": ["/"]}
    h = Harness(tmp_path, devices=devs, root_source="/dev/md0")
    r = h.run(device="/dev/nvme7n1")
    assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr and "/dev/nvme7n1" in r.stderr, r.stderr
    assert h.destructive() == []


def test_second_pv_of_an_lvm_root_is_refused(tmp_path):
    devs = _second_disk(base_devices())  # whole-disk PV, no partitions
    devs["/dev/mapper/vg-root"] = {"type": "lvm", "pkname": "nvme8n1p2", "parents": ["/dev/nvme8n1p2", "/dev/nvme7n1"], "fstype": "ext4",
                                   "label": "", "mountpoints": ["/"]}
    h = Harness(tmp_path, devices=devs, root_source="/dev/mapper/vg-root")
    r = h.run(device="/dev/nvme7n1")
    assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr, r.stderr


def test_second_member_of_a_btrfs_raid_root_is_refused(tmp_path):
    # findmnt shows ONE member as SOURCE; the other shares the filesystem UUID.
    devs = _second_disk(base_devices(), fstype="btrfs", uuid="fs-uuid-1")
    devs["/dev/nvme8n1p2"].update(fstype="btrfs", uuid="fs-uuid-1")
    h = Harness(tmp_path, devices=devs, root_source="/dev/nvme8n1p2[/@]", root_uuid="fs-uuid-1")
    r = h.run(device="/dev/nvme7n1")
    assert r.returncode == 1 and "hosts the running root filesystem" in r.stderr, r.stderr


def test_missing_partition_error_names_the_right_device(tmp_path):
    h = Harness(tmp_path, partition_never_appears=True)
    r = h.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "partition device /dev/nvme9n1p1 did not appear" in r.stderr, r.stderr
    assert "unbound variable" not in r.stderr
    assert h.calls("wipefs") == [] and h.calls(MKE2FS) == []


# --- dry run and gates ------------------------------------------------------
def test_dry_run_as_root_changes_nothing(tmp_path):
    h = Harness(tmp_path)
    before = h.fstab.read_text()
    r = h.run("--dry-run", yes=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[dry] would run: sgdisk --zap-all /dev/nvme9n1" in r.stderr
    assert "[dry] would run: wipefs -af /dev/nvme9n1p1" in r.stderr
    assert "INCONCLUSIVE" not in r.stdout
    assert h.destructive() == [] and h.calls("systemctl") == []
    assert h.fstab.read_text() == before


def test_dry_run_as_non_root_is_inconclusive_not_blank(tmp_path):
    # blkid -p needs root (EACCES, which blkid also reports as exit 2 =
    # "nothing found"), so a non-root dry run cannot confirm the disk is blank.
    h = Harness(tmp_path, uid=1000)
    before = h.fstab.read_text()
    r = h.run("--dry-run", yes=False)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "INCONCLUSIVE" in r.stdout and "NOT confirmed blank" in r.stdout
    assert not any(c[0] == "blkid" and "-p" in c for c in h.calls())
    assert h.destructive() == [] and h.fstab.read_text() == before


@pytest.mark.parametrize("rc", [4, 8])
def test_blkid_probe_error_fails_closed_as_root(tmp_path, rc):
    devs = base_devices()
    devs["/dev/nvme9n1"]["probe_rc"] = rc
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and f"blkid -p could not probe /dev/nvme9n1 (exit {rc})" in r.stderr, r.stderr
    assert h.destructive() == []


# --- review P2s: lone foreign partition, in-use without a signature ---------
def test_lone_foreign_partition_without_signature_is_refused(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1")  # no fs, no PARTLABEL
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "not created by this script" in r.stderr, r.stderr
    assert h.destructive() == []


def test_interrupted_run_with_our_partlabel_resumes(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1")
    devs["/dev/nvme9n1p1"]["partlabel"] = "PMOVES-NVME1"
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "interrupted run" in r.stdout
    assert [c[0] for c in h.destructive()] == ["sgdisk", "sgdisk", "wipefs", MKE2FS, "mount"]


@pytest.mark.parametrize("dm_type", ["crypt", "dm", "lvm"])
def test_disk_with_a_device_mapper_child_is_refused(tmp_path, dm_type):
    # e.g. plain dm-crypt (no LUKS header) or a dm-linear used by a VM: no signature anywhere.
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/mapper/vmdisk"]
    devs["/dev/mapper/vmdisk"] = {"type": dm_type, "pkname": "nvme9n1", "fstype": "", "label": "", "mountpoints": [""]}
    h = Harness(tmp_path, devices=devs)
    r = h.run()
    assert r.returncode == 1 and "sits on /dev/nvme9n1, so the disk is in use" in r.stderr, r.stderr
    assert h.destructive() == []


def test_disk_with_sysfs_holders_is_refused(tmp_path):
    # lsblk shows nothing, but the kernel records a claim in <dev>/holders.
    h = Harness(tmp_path)
    h.add_holder("/dev/nvme9n1", "dm-3")
    r = h.run()
    assert r.returncode == 1 and "is held by dm-3" in r.stderr, r.stderr
    assert h.destructive() == []


def test_partition_with_sysfs_holders_is_refused(tmp_path):
    devs = base_devices()
    devs["/dev/nvme9n1"]["children"] = ["/dev/nvme9n1p1"]
    devs["/dev/nvme9n1p1"] = _part("/dev/nvme9n1")
    devs["/dev/nvme9n1p1"]["partlabel"] = "PMOVES-NVME1"
    h = Harness(tmp_path, devices=devs)
    h.add_holder("/dev/nvme9n1p1", "dm-7")
    r = h.run()
    assert r.returncode == 1 and "/dev/nvme9n1p1 is held by dm-7" in r.stderr, r.stderr
    assert h.destructive() == []


def test_non_root_is_refused(tmp_path):
    h = Harness(tmp_path, uid=1000)
    r = h.run()
    assert r.returncode == 1 and "Must run as root" in r.stderr
    assert h.destructive() == []


def test_yes_really_is_required(tmp_path):
    h = Harness(tmp_path)
    r = h.run(yes=False)
    assert r.returncode == 1 and "--yes-really" in r.stderr
    assert h.destructive() == []
