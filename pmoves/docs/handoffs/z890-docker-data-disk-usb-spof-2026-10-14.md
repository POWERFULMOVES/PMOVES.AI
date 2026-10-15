# z890 — Docker data disk on USB is a single point of failure (incident 2026-10-13/14)

**Node:** z890 (Windows 11, Docker Desktop on WSL2)
**Status:** recovered 2026-10-14; root cause (data vhdx on a USB disk) still in place
**Preflight:** `make -C pmoves docker-disk-preflight` (read-only; `pmoves/tools/docker_disk_preflight.py`)

> **RULE — NEVER restart or reset Docker Desktop after an engine hang until
> `make -C pmoves docker-disk-preflight` passes AND a read-only `e2fsck -fn` of
> the data vhdx is clean.**
>
> Docker's wsl-bootstrap cannot tell an *unreadable* data disk from a *blank*
> one. When it cannot read a filesystem it logs `detected no file system.
> Formatting` and runs the ext4 format tool against the disk. On 2026-10-14 the
> format failed only because the device returned ENXIO. On a disk that reads
> back zeros instead of erroring, the same restart wipes every volume.

---

## 1. The single point of failure

Docker Desktop's data disk does not live in its default location on z890. A
directory junction redirects it to an external USB drive:

```
%LOCALAPPDATA%\Docker\wsl\disk  ->  I:\DockerData\disk   (junction)
I:\DockerData\disk\docker_data.vhdx                       (~554 GB / 516 GiB)
```

`I:` is a USB-attached desktop HDD (`BusType=USB`; Windows disk 6 at the time of
writing — the number can change across reboots). Consequences:

- **Every Docker volume on z890 depends on one USB link.** That covers Postgres,
  the Supabase stack, NATS JetStream, Qdrant, MinIO, Neo4j, ClickHouse, and the
  observability stack (see § 4).
- **The drive is shared.** `I:` is also the operator's bulk media / backup
  drive (Jellyfin library, bundles, other operator data). Its I/O load, power
  management, and cable all reach the Docker engine. A full-drive event or a
  USB-selective-suspend stall on `I:` is a Docker outage.
- **USB storage stalls instead of failing cleanly.** The UASP stack resets the
  device and retries (events 129 / 153). Inside the VM a retried write that
  times out surfaces as ext4 I/O errors, and the engine hangs rather than
  exiting.

## 2. Provenance gap

**Nothing in the repo records who created the junction, why, or with whose
approval.** What can be measured:

| Fact | Value | Source |
|---|---|---|
| Robocopy of the vhdx from the default `%LOCALAPPDATA%` location to `D:\DockerData\disk\` started | 2026-08-01 11:56 local | `D:\DockerData\rc.log` (log ends at 22.3% copied) |
| `D:\DockerData\disk\docker_data.vhdx` last written | 2026-08-02 17:24 UTC (553,197,240,320 bytes) | file mtime |
| `I:\DockerData` created | 2026-08-02 17:24 UTC | filesystem creation time |
| Junction `%LOCALAPPDATA%\Docker\wsl\disk` created | 2026-08-02 14:34 local (18:34 UTC) | filesystem creation time |
| Docker Desktop's own disk-location setting | none set. Docker believes the disk is at its default path, so the redirect is invisible to it | `%APPDATA%\Docker\settings-store.json` |
| Repo docs, register rows, PRs, or handoffs recording the move | none found | repo search |

Operator memory notes **earlier failed attempts to relocate the disk image to
`D:` through the Docker Desktop GUI**. The filesystem evidence fits that: a
manual robocopy to `D:` (2026-08-01), then a copy to `I:` and a hand-made
junction (2026-08-02). None of this was written down. No later agent or
operator knew the engine depended on a USB disk until the incident exposed it.
(The 2026-08-16 Firefly handoff says `D:` "hosts the repo **and** `DockerData`".
That was true of the *stale copy*, not the live disk.)

**There is still a ~553 GB copy of the vhdx on `D:`**
(`D:\DockerData\disk\docker_data.vhdx`), frozen since 2026-08-02. It is **not**
a backup of current data: it is about 2.5 months stale. It is also the main
reason `D:` is short of space (§ 7). Deleting it is a destructive action (§ 6)
and needs the operator's decision. Do not mistake it for the live disk during a
recovery: the live one is behind the junction on `I:`.

Action owed (operator): record who made the change and why, or confirm it is
unknown, so the gap can be closed rather than re-discovered.

## 3. Incident timeline (UTC)

Times come from the Windows System log and the Docker Desktop host backend log.
VM-side lines in the backend log carry the **VM clock**, which was skewed (the
format line is stamped `07:02:10Z` but was reported by the host at `11:39:24Z`).
The host clock is authoritative.

| Time (UTC) | Event | Source |
|---|---|---|
| 2026-10-13 17:01:52 | Event 129 `UASPStor`: reset issued to the USB storage device | System log |
| 2026-10-13 17:02:02 – 17:02:28 | 85 × event 153 `disk`: IO operation retried, **disk 6 (`I:`)** | System log |
| 2026-10-13 ~17:05 | Last Prometheus write. The obs stack shares the failing disk (§ 4) | obs audit |
| 2026-10-13 → 10-14 | Engine hung for ~17h. ext4 I/O errors inside the VM | operator account |
| 2026-10-14 before 11:39 | Operator runs `docker desktop restart` | operator account |
| 2026-10-14 11:39:24 | Host records the engine start failure. wsl-bootstrap had logged `detected no file system. Formatting`, and the format tool exited with *No such device or address* (ENXIO) on the data block device | backend log |
| 2026-10-14 (between) | Manual recovery (§ 5): bare mount, read-only fsck, operator-approved repair, clean re-check | operator session |
| 2026-10-14 12:23:08 → 12:23:42 | WSL engine `starting` → `running` | backend log |
| 2026-10-14 ~12:30 | Prometheus resumes writing | obs audit |
| 2026-10-14 +~8 min | Postgres crash recovery completes. Slow because WAL replay ran over USB | operator session |

## 4. Observability gap

The obs audit finished on 2026-10-15. **Nothing alerted, because nothing could
have.** Measured findings:

1. **No Alertmanager is deployed on z890.** `prometheus.yml` has `rule_files`
   but no `alerting:` block, and `/api/v1/alertmanagers` is empty. The pieces
   exist but are not wired: the overlay `pmoves/docker-compose.alertmanager.yml`
   and `pmoves/config/alertmanager/alertmanager.yml` (4 Discord receivers) are
   in the repo, and `z890-coordinator.yaml:67` and `docker_matrix.yaml:41`
   declare `alertmanager:9093`. No make target brings it up.
2. **19 of 47 Prometheus targets are permanently down.** `ServiceDown` has been
   firing since at least 2026-10-13 12:00. With that baseline of noise, a real
   failure looks the same as normal.
3. **Nothing watches the host disk.** The `HostFilesystem*` rules depend on
   cadvisor, which is defined (monitoring compose `:98`) but not running. z890
   has no node-exporter. Nothing observes `I:`, the vhdx, or Windows disk events
   153 / 129 / 7 / 51.
4. **The whole obs stack shares the fault domain.** Prometheus, Grafana, Loki,
   promtail and blackbox run in the same Docker VM, on the same `I:` disk. There
   is no off-node watcher: the VPS nodes are scraped *by* z890, not the other
   way round. Prometheus wrote until 2026-10-13 17:05, then had a gap until
   2026-10-14 12:30.
5. **Grafana alerting has no configuration.** The alerting and notifier
   provisioning directories are empty.

Ranked follow-ups (each a separate PR, **not** part of this one):

1. Off-node dead-man's switch for z890: a Watchdog rule plus an external check
   that alerts when z890 goes silent.
2. A Windows-native disk-event probe: export events 7/51/129/153 and the
   `docker-disk-preflight` result as metrics, on the host and outside the VM.
3. Deploy Alertmanager and the Prometheus `alerting:` block through a make
   target.
4. Alert hygiene: bring the down-target baseline to zero, restore cadvisor, and
   add a z890 host-disk target.
5. Rules for the data tier (Postgres, JetStream, Qdrant).

## 5. Safe recovery runbook (engine hang on z890)

Each step is read-only unless marked **[OPERATOR CONFIRM]**. Run from an
elevated Windows terminal unless noted.

1. **Do not restart Docker Desktop.** Do not click "Restart" or "Reset", and do
   not run `docker desktop restart`.
2. **Check the disk first:** `make -C pmoves docker-disk-preflight`.
   - `FAIL` (exit 2): the disk is actively erroring. Fix the physical layer
     first (cable, port, power, USB selective suspend), then re-run.
   - `WARN` (exit 1): read the evidence. USB placement and *old* event-153
     bursts are expected on z890 until the follow-up in § 7 lands. *Recent*
     events are not.
3. **Stop the VM cleanly:** `wsl --shutdown`.
4. **Attach the vhdx without mounting it:**
   `wsl --mount --vhd "I:\DockerData\disk\docker_data.vhdx" --bare`
5. **Locate the block device by filesystem UUID, not by letter.** Device names
   like `/dev/sdX` move between attaches. From a regular WSL distro (for example
   Ubuntu-24.04):
   `lsblk -o NAME,SIZE,FSTYPE,UUID` and `sudo blkid`. Pick the ext4 device
   whose size matches the vhdx's virtual size. Record its UUID here at the first
   healthy check so later recoveries can match it exactly:
   `<docker-data-fs-uuid: TODO record>`.
6. **Run a read-only check:** `sudo e2fsck -fn /dev/<dev>`. `-n` answers "no"
   to every question and writes nothing. Save the output.
7. **[OPERATOR CONFIRM] Repair only if step 6 reported errors and the operator
   has approved it:** `sudo e2fsck -fy /dev/<dev>`. This writes to the
   filesystem. Snapshot or copy the vhdx first if space allows.
8. **Re-check read-only:** `sudo e2fsck -fn /dev/<dev>` must come back clean.
   If it does not, stop and escalate. Do not start Docker.
9. **Detach:** `wsl --unmount "I:\DockerData\disk\docker_data.vhdx"`.
10. **Re-run the preflight:** `make -C pmoves docker-disk-preflight`.
11. **Start, don't reset:** `docker desktop start`.
12. **Wait for the data tier.** Postgres crash recovery took ~8 min over USB on
    2026-10-14. Do not restart containers while WAL replay is running. Watch the
    container logs and health endpoints instead.

## 6. Destructive actions — operator confirmation required

None of these may be run by an agent on its own judgement, and none are part of
the runbook above unless explicitly marked:

- Docker Desktop **Reset to factory defaults**, **Clean / Purge data**, or
  **Uninstall**.
- `wsl --unregister docker-desktop` (or any `docker-desktop*` distro). This
  deletes the distro and its disk.
- Removing or pruning Docker volumes. Use the Known Roads
  `make -C pmoves volume-reset SERVICE=...` only with operator approval, and
  never `prune` with volumes during a disk incident.
- Repair-mode fsck (`e2fsck -y`, `-p`, or anything without `-n`).
- Moving, renaming, copying-over, compacting (`Optimize-VHD`, `diskpart
  compact`) or deleting the vhdx, or re-pointing / removing the junction.
- Re-running Docker's first-boot provisioning against the existing disk.

## 7. Follow-up — move Docker data to internal NVMe

Target: an internal NVMe volume. `D:` (WD_BLACK SN850X, NVMe) is the obvious
candidate, but **space is too tight today**: ~559 GiB free against a ~516 GiB
(554 GB) vhdx. That is too little headroom for the copy and for growth.

Most of the shortfall is the **stale 2026-08-02 vhdx copy already on `D:`**
(~515 GiB, § 2). If the operator decides to delete it, `D:` free space roughly
doubles. That is a destructive action (§ 6): it needs an explicit operator
decision and a check that nothing references the copy.

Order of operations (each step its own PR or operator session):

1. Operator decision on the stale `D:\DockerData` copy.
2. Prune, through the Known Roads only: `make -C pmoves docker-prune`, then
   (with approval) `docker-prune-all`. Measure the reclaimable build cache and
   buildx volumes (`make -C pmoves docker-host-policy-check` surfaces orphaned
   buildx state). Compacting the vhdx afterwards is a destructive action (§ 6).
3. Record the decision and the approver in this doc. That closes the
   provenance gap for the *new* location.
4. Relocate through Docker Desktop's supported "Disk image location" setting, or
   through a documented, reversible procedure, with Docker stopped and a
   verified copy kept until the new location has run clean.
5. Re-run `make -C pmoves docker-disk-preflight`. `data-disk-location` should
   now PASS.

## 8. What `docker-disk-preflight` checks

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| `data-disk-location` | vhdx on an internal bus | USB / removable bus, or unknown bus | disk directory missing / link target unreachable |
| `vhdx-header` | first 8 bytes are `vhdxfile` | file locked by another process | missing, unreadable, or wrong signature |
| `disk-events` | no 7/51/129/153 events on the Docker disk in the window (default 72h) | events on the Docker disk older than `--fail-hours` (default 1h), or events that can't be attributed to a disk | any 7/51 on the Docker disk, or any event on it within `--fail-hours` |
| `physical-disk-health` | `Healthy` / `OK` | other non-fatal state | `Unhealthy`, `Lost Communication`, offline, etc. |
| `vm-init-log` | newest init logs clean | generic `I/O error` | `Buffer I/O error`, `EXT4-fs error`, `detected no file system` |

Exit codes: `0` pass, `1` warn, `2` fail, `3` could not measure (non-Windows,
or checks skipped). Exit 3 is **not** a pass. Through `make`, every non-zero
becomes make's own exit 2 (`Error 1` in the message), so read the `RESULT:` line
or the `--json` `exit_code` for the real verdict. `ARGS='--json'` gives
machine-readable output. The tool never mounts, repairs, restarts, or writes.
