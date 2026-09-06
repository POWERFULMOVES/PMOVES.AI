#!/usr/bin/env bash
# ============================================================================
# Danger Room (E2B self-host) capability probe — LINUX side.
#
# RUN THIS ON THE CANDIDATE NODE. It cannot be run remotely and it must not be
# run "on behalf of" a node from somewhere else: every item below reads local
# kernel state, and a reading taken on the wrong machine is worse than no
# reading, because it looks like evidence.
#
#   On a native Linux candidate:   bash pmoves/scripts/probe_danger_room_host.sh
#   On Windows (e.g. pmoves-5090): run probe_danger_room_host.ps1 FIRST for the
#                                  host-level answers, then run THIS inside the
#                                  WSL2 / VM Linux environment it identifies.
#
# ── Why both halves are needed ──────────────────────────────────────────────
# PMOVES-Danger-infra/DEV-LOCAL.md opens with "Linux is required for developing
# on bare metal", and the pieces it needs are Linux-kernel features:
#   * Firecracker microVMs   -> /dev/kvm
#   * `modprobe nbd nbds_max=64`
#   * `sysctl -w vm.nr_hugepages=2048`
# On a Windows host none of those exist at the host level, so the question
# splits in two: (a) can a Linux environment exist here at all, and (b) does
# THAT environment expose the kernel features. The .ps1 answers (a); this
# script answers (b).
#
# ── Verdicts ────────────────────────────────────────────────────────────────
# Every item prints exactly one of PASS / FAIL / COULD-NOT-MEASURE.
# COULD-NOT-MEASURE IS NOT A PASS. It means the probe could not obtain a
# reading — the tool was absent, permission was denied, or the interface did
# not exist. Treating it as a pass is how a node gets handed a workload it
# cannot run.
#
# Exit codes (fleet doctrine):
#   0  clean      — every item PASS
#   1  findings   — at least one FAIL, and no unresolved COULD-NOT-MEASURE
#   3  could-not-measure — at least one item could not be read
# When both a FAIL and a COULD-NOT-MEASURE occur, exit 3 wins: an incomplete
# reading cannot be reported as a complete verdict.
#
# ── This probe is READ-ONLY ─────────────────────────────────────────────────
# It never loads a module, never writes a sysctl, never provisions anything and
# never brings up a service. `modprobe` is tested with `--dry-run`, hugepages
# are read from the current sysctl value plus the writability of the knob.
# Bringing the stack up is a separate, operator-owned action — see
# pmoves/docs/operations/E2B_SELF_HOST_RUNBOOK.md.
#
# It also prints no credential values. It touches no secret at all.
# ============================================================================
set +x
# NOTE: deliberately NO `pipefail`. `lsmod | grep -q ...` makes grep exit as
# soon as it matches, lsmod then dies on SIGPIPE (141), and pipefail propagates
# THAT as the pipeline status — so a successfully-detected module reads as
# "not loaded". This probe hit exactly that on its first self-test run: kvm_amd
# was loaded and the item still printed FAIL. A probe that reports a false FAIL
# is worse than no probe.
set -u

# --- Requirements from PMOVES-Danger-infra/DEV-LOCAL.md ---------------------
REQ_HUGEPAGES=2048          # step 2: sysctl -w vm.nr_hugepages=2048
REQ_NBDS_MAX=64             # step 1: modprobe nbd nbds_max=64
# 2048 x 2 MiB hugepages = 4 GiB reserved before a single sandbox exists, and
# the stack in step 4 runs clickhouse + grafana + loki + memcached + mimir +
# otel + postgres + redis + tempo alongside the api, orchestrator and
# client-proxy. 32 GiB free RAM is the floor at which this is not a fight.
REQ_FREE_RAM_GB=32
# Kernels (step 3), firecracker builds (step 7), template rootfs images, the Go
# build cache and nine service containers.
REQ_FREE_DISK_GB=150
REQ_ARCH="x86_64"

PASS_N=0; FAIL_N=0; CNM_N=0

pass() { printf '  [PASS]              %s\n' "$*"; PASS_N=$((PASS_N+1)); }
fail() { printf '  [FAIL]              %s\n' "$*"; FAIL_N=$((FAIL_N+1)); }
cnm()  { printf '  [COULD-NOT-MEASURE] %s\n' "$*"; CNM_N=$((CNM_N+1)); }
hdr()  { printf '\n== %s\n' "$*"; }

printf '=== Danger Room capability probe (Linux side) ===\n'
printf 'host: %s   date: %s\n' "$(hostname 2>/dev/null || echo '<unknown>')" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'requirements source: PMOVES-Danger-infra/DEV-LOCAL.md\n'

# ---------------------------------------------------------------------------
hdr "0. Environment kind (native Linux vs WSL2 vs VM)"
KERNEL="$(uname -r 2>/dev/null || echo '')"
IS_WSL=0
if [ -z "$KERNEL" ]; then
  cnm "kernel release: uname unavailable"
else
  printf '  kernel: %s\n' "$KERNEL"
  case "$KERNEL" in
    *microsoft*|*WSL*) IS_WSL=1 ;;
  esac
  if [ "$IS_WSL" -eq 1 ]; then
    if [ -e /proc/sys/fs/binfmt_misc/WSLInterop ] || [ -d /run/WSL ]; then
      pass "environment: WSL2 (kernel names microsoft AND a WSL2 interop marker is present)"
    else
      # WSL1 has no real Linux kernel and cannot host /dev/kvm at all.
      fail "environment: WSL, but no WSL2 interop marker — this looks like WSL1. WSL1 is a syscall translation layer with no Linux kernel; it cannot provide /dev/kvm and cannot run Firecracker. Convert with: wsl --set-version <distro> 2"
    fi
  else
    pass "environment: native Linux or a full VM (kernel does not name microsoft)"
  fi
fi

# ---------------------------------------------------------------------------
hdr "1. CPU architecture"
ARCH="$(uname -m 2>/dev/null || echo '')"
if [ -z "$ARCH" ]; then
  cnm "arch: uname -m returned nothing"
elif [ "$ARCH" = "$REQ_ARCH" ]; then
  pass "arch: $ARCH (matches the required $REQ_ARCH)"
else
  fail "arch: $ARCH — expected $REQ_ARCH. Firecracker publishes x86_64 and aarch64 builds, but 'make download-public-firecrackers' and the public kernels are the x86_64 set here."
fi
# The profile declares no arch:. Print what the CPU actually says so the
# placement decision stops resting on an inference from a model name.
if [ -r /proc/cpuinfo ]; then
  CPU_MODEL="$(grep -m1 -i '^model name' /proc/cpuinfo 2>/dev/null | sed 's/.*: *//')"
  [ -n "$CPU_MODEL" ] && printf '  cpu: %s\n' "$CPU_MODEL"
fi

# ---------------------------------------------------------------------------
hdr "2. Nested virtualization / KVM (Firecracker's hard requirement)"
# Firecracker IS a KVM userspace VMM. No /dev/kvm, no Danger Room. Full stop.
if [ -e /dev/kvm ]; then
  if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    pass "/dev/kvm: present and read-writable by $(id -un 2>/dev/null || echo "$USER")"
  else
    # Present but not usable by this user is a real, fixable finding — not an
    # unmeasurable one. We measured it; the answer is 'no, as configured'.
    fail "/dev/kvm: present but NOT read-writable by $(id -un 2>/dev/null || echo "$USER"). Firecracker will fail to open it. Fix: usermod -aG kvm \$USER, then re-login."
  fi
else
  fail "/dev/kvm: ABSENT. Firecracker is a KVM VMM and cannot run without it. On a Windows host this is the expected result inside WSL2 unless nested virtualization is enabled — see probe_danger_room_host.ps1 and the runbook."
fi

# Distinguish 'the CPU lacks virt extensions' from 'the hypervisor withholds
# them'. These are different problems with different owners.
if [ -r /proc/cpuinfo ]; then
  if grep -qE '^flags.*\b(vmx|svm)\b' /proc/cpuinfo 2>/dev/null; then
    pass "cpu virt extensions: exposed to this environment (vmx/svm visible in /proc/cpuinfo)"
  else
    fail "cpu virt extensions: NOT exposed (no vmx/svm flag). Either the CPU lacks them, they are disabled in firmware (AMD-V/SVM), or an outer hypervisor is not passing them through. On a Windows host this is the nested-virtualization switch."
  fi
  if grep -qE '^flags.*\bhypervisor\b' /proc/cpuinfo 2>/dev/null; then
    printf '  note: the hypervisor flag is set — this environment is itself a guest, so KVM here is NESTED virtualization.\n'
  fi
else
  cnm "cpu virt extensions: /proc/cpuinfo not readable"
fi

# kvm modules loaded. Capture lsmod ONCE into a variable rather than piping it
# into grep -q; see the pipefail note at the top of this file.
if command -v lsmod >/dev/null 2>&1; then
  LSMOD_OUT="$(lsmod 2>/dev/null)"
  if [ -z "$LSMOD_OUT" ]; then
    cnm "kvm kernel modules: lsmod produced no output — cannot tell whether kvm is loaded or built into the kernel"
  else
    KVM_MODS="$(printf '%s\n' "$LSMOD_OUT" | awk '/^kvm/{printf "%s ",$1}')"
    if [ -n "$KVM_MODS" ]; then
      pass "kvm kernel modules: loaded ($KVM_MODS)"
    elif [ -e /dev/kvm ]; then
      # /dev/kvm without a kvm module means KVM is compiled in (CONFIG_KVM=y).
      # That is a PASS, not a FAIL — the capability is what matters, not how it
      # was delivered.
      pass "kvm kernel modules: none listed, but /dev/kvm exists — KVM is built into this kernel (CONFIG_KVM=y) rather than loaded as a module"
    else
      fail "kvm kernel modules: not loaded and /dev/kvm absent. Try: sudo modprobe kvm_amd (AMD) or kvm_intel."
    fi
  fi
else
  cnm "kvm kernel modules: lsmod unavailable"
fi

# ---------------------------------------------------------------------------
hdr "3. nbd module — DEV-LOCAL.md step 1 (modprobe nbd nbds_max=$REQ_NBDS_MAX)"
# READ-ONLY: --dry-run resolves the module and its dependencies WITHOUT
# inserting it. A probe that loaded the module would be provisioning.
if ! command -v modprobe >/dev/null 2>&1; then
  cnm "nbd: modprobe not on PATH (kmod not installed, or a container without module tooling)"
elif printf '%s\n' "$(lsmod 2>/dev/null)" | grep -qE '^nbd[[:space:]]'; then
  CUR_NBDS="$(cat /sys/module/nbd/parameters/nbds_max 2>/dev/null || echo '?')"
  if [ "$CUR_NBDS" = "?" ]; then
    pass "nbd: already loaded (nbds_max not readable, but the module is in)"
  elif [ "$CUR_NBDS" -ge "$REQ_NBDS_MAX" ] 2>/dev/null; then
    pass "nbd: loaded with nbds_max=$CUR_NBDS (>= required $REQ_NBDS_MAX)"
  else
    fail "nbd: loaded but nbds_max=$CUR_NBDS < required $REQ_NBDS_MAX. nbds_max is set at INSERT time only — it needs: sudo rmmod nbd && sudo modprobe nbd nbds_max=$REQ_NBDS_MAX"
  fi
elif modprobe --dry-run nbd >/dev/null 2>&1; then
  pass "nbd: available to load (modprobe --dry-run resolved it; not loaded yet — nothing was inserted by this probe)"
else
  # Positive control for the dry-run: prove the mechanism can succeed, so an
  # 'nbd missing' verdict is not really 'modprobe --dry-run never works here'.
  if modprobe --dry-run loop >/dev/null 2>&1; then
    fail "nbd: NOT available in this kernel (modprobe --dry-run nbd failed, while the same dry-run SUCCEEDS for 'loop' — so the mechanism works and nbd is genuinely absent). WSL2's default kernel ships without it; a custom kernel or a full VM is required."
  else
    cnm "nbd: modprobe --dry-run failed for BOTH nbd and the 'loop' control, so this reading says nothing about nbd — the dry-run mechanism itself is unavailable here (no /lib/modules for the running kernel is the usual cause)."
  fi
fi

# ---------------------------------------------------------------------------
hdr "4. Huge pages — DEV-LOCAL.md step 2 (vm.nr_hugepages=$REQ_HUGEPAGES)"
HP_KNOB=/proc/sys/vm/nr_hugepages
if [ ! -e "$HP_KNOB" ]; then
  fail "hugepages: $HP_KNOB does not exist — this kernel has no hugepage support exposed."
else
  CUR_HP="$(cat "$HP_KNOB" 2>/dev/null || echo '?')"
  HP_SIZE_KB="$(awk '/^Hugepagesize:/{print $2}' /proc/meminfo 2>/dev/null || echo '')"
  printf '  current vm.nr_hugepages=%s   Hugepagesize=%s kB\n' "$CUR_HP" "${HP_SIZE_KB:-?}"
  if [ "$CUR_HP" != "?" ] && [ "$CUR_HP" -ge "$REQ_HUGEPAGES" ] 2>/dev/null; then
    pass "hugepages: already at $CUR_HP (>= required $REQ_HUGEPAGES)"
  elif [ -w "$HP_KNOB" ] || [ "$(id -u 2>/dev/null)" = "0" ]; then
    pass "hugepages: at $CUR_HP, and the knob is writable — 'sudo sysctl -w vm.nr_hugepages=$REQ_HUGEPAGES' can set it (this probe did NOT set it)"
  elif command -v sudo >/dev/null 2>&1; then
    cnm "hugepages: at $CUR_HP and the knob is not writable as $(id -un 2>/dev/null). sudo exists but this probe will not invoke a privileged write to find out — re-run as root to convert this to PASS/FAIL."
  else
    fail "hugepages: at $CUR_HP, knob not writable, and no sudo available — the required $REQ_HUGEPAGES cannot be set by this account."
  fi
  if [ -n "$HP_SIZE_KB" ] && [ "$HP_SIZE_KB" -gt 0 ] 2>/dev/null; then
    printf '  note: %s pages x %s kB = %s MiB would be reserved and unavailable to normal allocations.\n' \
      "$REQ_HUGEPAGES" "$HP_SIZE_KB" "$(( REQ_HUGEPAGES * HP_SIZE_KB / 1024 ))"
  fi
fi

# ---------------------------------------------------------------------------
hdr "5. Free RAM (need >= ${REQ_FREE_RAM_GB} GiB available)"
if [ -r /proc/meminfo ]; then
  MEM_TOTAL_KB="$(awk '/^MemTotal:/{print $2}' /proc/meminfo)"
  MEM_AVAIL_KB="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)"
  if [ -z "$MEM_AVAIL_KB" ]; then
    cnm "RAM: MemAvailable absent from /proc/meminfo (very old kernel) — MemTotal=$(( ${MEM_TOTAL_KB:-0} / 1024 / 1024 )) GiB"
  else
    MEM_TOTAL_GB=$(( MEM_TOTAL_KB / 1024 / 1024 ))
    MEM_AVAIL_GB=$(( MEM_AVAIL_KB / 1024 / 1024 ))
    printf '  MemTotal=%s GiB  MemAvailable=%s GiB\n' "$MEM_TOTAL_GB" "$MEM_AVAIL_GB"
    if [ "$MEM_AVAIL_GB" -ge "$REQ_FREE_RAM_GB" ]; then
      pass "RAM: ${MEM_AVAIL_GB} GiB available (>= ${REQ_FREE_RAM_GB} GiB)"
    else
      fail "RAM: only ${MEM_AVAIL_GB} GiB available, need >= ${REQ_FREE_RAM_GB} GiB for the nine local-infra services + hugepage reservation + microVMs."
    fi
    # A WSL2 guest is capped by .wslconfig, NOT by the host's installed RAM.
    # The 5090's 192 GB says nothing about what the guest gets.
    if [ "$IS_WSL" -eq 1 ]; then
      printf '  note: this is WSL2 — MemTotal above is the GUEST cap from .wslconfig, not the 192 GB installed in the host. Raise it in %%USERPROFILE%%\\.wslconfig if it is short.\n'
    fi
  fi
else
  cnm "RAM: /proc/meminfo not readable"
fi

# ---------------------------------------------------------------------------
hdr "6. Free disk (need >= ${REQ_FREE_DISK_GB} GiB on the build/work filesystem)"
PROBE_DISK_PATH="${PROBE_DISK_PATH:-$PWD}"
if command -v df >/dev/null 2>&1; then
  DF_LINE="$(df -Pk "$PROBE_DISK_PATH" 2>/dev/null | awk 'NR==2')"
  if [ -z "$DF_LINE" ]; then
    cnm "disk: df returned nothing for $PROBE_DISK_PATH"
  else
    AVAIL_KB="$(printf '%s\n' "$DF_LINE" | awk '{print $4}')"
    MOUNT="$(printf '%s\n' "$DF_LINE" | awk '{print $6}')"
    FSNAME="$(printf '%s\n' "$DF_LINE" | awk '{print $1}')"
    AVAIL_GB=$(( AVAIL_KB / 1024 / 1024 ))
    printf '  path=%s  fs=%s  mount=%s  avail=%s GiB\n' "$PROBE_DISK_PATH" "$FSNAME" "$MOUNT" "$AVAIL_GB"
    if [ "$AVAIL_GB" -ge "$REQ_FREE_DISK_GB" ]; then
      pass "disk: ${AVAIL_GB} GiB free on $MOUNT (>= ${REQ_FREE_DISK_GB} GiB)"
    else
      fail "disk: only ${AVAIL_GB} GiB free on $MOUNT, need >= ${REQ_FREE_DISK_GB} GiB (public kernels + firecracker builds + template rootfs + Go cache + 9 service containers)."
    fi
    # Building on a Windows drive through the 9p/drvfs bridge is pathologically
    # slow and cannot host Linux file modes correctly.
    case "$FSNAME:$MOUNT" in
      drvfs:*|*:/mnt/[a-z]) printf '  note: this path is a Windows drive mounted into Linux (drvfs/9p). Do NOT build or store rootfs images here — put the checkout on the ext4 root instead.\n' ;;
    esac
  fi
else
  cnm "disk: df unavailable"
fi

# ---------------------------------------------------------------------------
hdr "7. Toolchain for the DEV-LOCAL.md steps"
# Go (steps 6, 8, 9, 10, 11 are all `go run` / Go makefiles).
if command -v go >/dev/null 2>&1; then
  pass "go: $(go version 2>/dev/null)"
else
  fail "go: MISSING — DEV-LOCAL.md steps 6 and 8-11 are Go builds (envd, seed-local-database, api, orchestrator, client-proxy)."
fi
for tool in docker make git; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "$tool: present ($(command -v "$tool"))"
  else
    fail "$tool: MISSING — required by DEV-LOCAL.md step 4 (make local-infra brings up nine containers)."
  fi
done
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    pass "docker daemon: reachable"
  else
    fail "docker daemon: NOT reachable (client present, daemon not answering or the user is not in the docker group)."
  fi
fi

# ---------------------------------------------------------------------------
hdr "8. Port availability (DEV-LOCAL.md 'Services')"
# :3000 is the loud one. On this fleet a host npx hf-mcp-server has already
# collided with :3000 once, and PostgREST was moved to 3001 because of it.
check_port() {
  set +x
  local port="$1" what="$2"
  if command -v ss >/dev/null 2>&1;  then LISTEN="$(ss -ltn 2>/dev/null | awk -v p=":$port$" '$4 ~ p {print $4}')"
  elif command -v netstat >/dev/null 2>&1; then LISTEN="$(netstat -ltn 2>/dev/null | awk -v p=":$port$" '$4 ~ p {print $4}')"
  else cnm "port $port ($what): neither ss nor netstat available"; return; fi
  if [ -n "$LISTEN" ]; then
    fail "port $port ($what): ALREADY IN USE — the E2B stack will not bind it."
  else
    pass "port $port ($what): free"
  fi
}
check_port 3000 "e2b api"
check_port 3002 "e2b client-proxy"
check_port 5008 "e2b orchestrator"
check_port 5432 "postgres"
check_port 8123 "clickhouse http"
check_port 6379 "redis"
check_port 53000 "grafana"

# ---------------------------------------------------------------------------
printf '\n=== verdict ===\n'
printf '  PASS=%s  FAIL=%s  COULD-NOT-MEASURE=%s\n' "$PASS_N" "$FAIL_N" "$CNM_N"
if [ "$CNM_N" -gt 0 ]; then
  printf '  OVERALL: COULD-NOT-MEASURE (exit 3)\n'
  printf '  %s item(s) could not be read. This is NOT a pass. Resolve them (usually: run as root, install the missing tool, or run inside the Linux environment rather than the Windows host) and re-run before any placement decision.\n' "$CNM_N"
  exit 3
fi
if [ "$FAIL_N" -gt 0 ]; then
  printf '  OVERALL: FINDINGS (exit 1)\n'
  printf '  This node cannot host the Danger Room as currently configured. Each FAIL above names its fix.\n'
  exit 1
fi
printf '  OVERALL: CLEAN (exit 0)\n'
printf '  This environment satisfies the DEV-LOCAL.md prerequisites. Bring-up is still a separate operator action — see pmoves/docs/operations/E2B_SELF_HOST_RUNBOOK.md.\n'
exit 0
