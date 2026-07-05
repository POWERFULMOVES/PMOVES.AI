# AMD R9700 Install-Day Runbook

**Intent:** Fast path for the PMOVES AMD 9850X3D + dual R9700 workstation when the target box is already on the bench and the install USB is either ready or about to be rebuilt.

**Primary source:** `deploy/runbooks/fresh-install-fleet.md`

**Helper agent:** `.claude/agents/amd-usb-installer.md`

---

## Use This Runbook When

- the target machine is the RDNA4 workstation (`pmoves-9850x3d-r9700`)
- you want the shortest operator path from USB to first-boot verification
- you need explicit stop/go checks during physical install work

## Pre-Flight

1. Confirm the target is the AMD workstation, not the Proxmox host.
2. Confirm the workstation has both intended NVMe devices installed. The shipped autoinstall expects redundant ZFS layout.
3. Disable Secure Boot in firmware before starting. ROCm DKMS will be painful otherwise.
4. Connect wired networking before first boot so the first-boot provisioner can clone PMOVES.AI.
5. Have one trusted PMOVES node available for follow-up verification and fleet enrollment.
6. If rebuilding the USB, verify the installer ISO checksum first.

## Fast Path If The USB Is Already Built

1. Insert the USB into the AMD workstation.
2. Open the UEFI boot menu and choose the USB in UEFI mode.
3. Let autoinstall run unattended.
4. Expect about 8 to 12 minutes before the first boot reaches the login prompt.
5. Watch `/var/log/pmoves-first-boot.log` after boot if anything looks stalled.

## Rebuild The USB If Needed

```bash
sudo bash deploy/provision/build-usb.sh \
  --iso=$PWD/ubuntu-24.04.2-live-server-amd64.iso \
  --autoinstall=deploy/provision/autoinstall/rdna4-workstation.yaml \
  --device=/dev/sdb \
  --hostname=pmoves-9850x3d-r9700 \
  --ssh-keys-from-github=POWERFULMOVES
```

Run `--dry-run` first if the device path is not already confirmed.

## Stop/Go Gates

- **Stop** if the installer asks unexpected storage questions. That usually means the disk layout on the box does not match the autoinstall assumptions.
- **Stop** if the machine boots in legacy BIOS mode instead of UEFI.
- **Go** once the first boot reaches a shell and `/var/log/pmoves-first-boot.log` is actively progressing.
- **Stop** if first-boot cannot reach GitHub or package mirrors. Fix network first; do not keep retrying blind.

## First-Boot Verification

On the workstation itself:

```bash
sudo systemctl status pmoves-first-boot.service --no-pager
sudo tail -50 /var/log/pmoves-first-boot.log
rocminfo | head -40
```

From a trusted PMOVES node:

```bash
ssh pmoves@pmoves-9850x3d-r9700
curl http://localhost:8090/v1/models
curl http://localhost:9835/ | head -20
```

## Fleet Enrollment

After first boot is stable:

```bash
make -C pmoves fleet-enroll ROLE=owner DEVICE=pmoves-9850x3d-r9700
```

Then complete the Tailscale join on the workstation and verify it appears in `tailscale status`.

## If Something Fails

- If autoinstall fails before reboot, inspect `/var/log/installer/autoinstall-user-data` on the target.
- If first-boot fails after login is available, rerun `/usr/local/sbin/pmoves-first-boot.sh` manually.
- If ROCm DKMS fails, verify matching kernel headers, then reboot and retry the GPU install path.