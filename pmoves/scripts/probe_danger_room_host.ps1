<#
============================================================================
 Danger Room (E2B self-host) capability probe -- WINDOWS HOST side.

 RUN THIS ON THE CANDIDATE NODE (pmoves-5090). It reads local hypervisor and
 hardware state; a reading taken anywhere else is not evidence about this node.

     powershell -ExecutionPolicy Bypass -File pmoves\scripts\probe_danger_room_host.ps1

 This half answers only one question: CAN A LINUX ENVIRONMENT WITH /dev/kvm
 EXIST ON THIS HOST? It cannot answer whether that environment actually has
 the kernel features Firecracker needs, because those are Linux-side facts.

 After this passes, run the Linux half INSIDE the WSL2 distro or VM:
     wsl -d <distro> -- bash pmoves/scripts/probe_danger_room_host.sh

 Why the split: PMOVES-Danger-infra/DEV-LOCAL.md opens with "Linux is required
 for developing on bare metal", and its prerequisites -- Firecracker microVMs,
 `modprobe nbd nbds_max=64`, `sysctl -w vm.nr_hugepages=2048` -- are Linux
 kernel features with no Windows equivalent. Windows does not host the Danger
 Room; a Linux environment on Windows might.

 VERDICTS: every item prints PASS / FAIL / COULD-NOT-MEASURE.
 COULD-NOT-MEASURE IS NOT A PASS. Several checks below need an elevated shell;
 unelevated they return could-not-measure rather than guessing.

 EXIT CODES (fleet doctrine):
   0 clean | 1 findings | 3 could-not-measure
 Could-not-measure outranks findings: an incomplete reading must not be
 reported as a complete verdict.

 THIS PROBE IS READ-ONLY. It enables no Windows feature, installs no distro,
 starts no VM, edits no .wslconfig, and touches no credential. Every remedy is
 printed for an operator to run deliberately.
============================================================================
#>

# StrictMode off on purpose: several CIM/WSL surfaces are absent on some SKUs
# and we want a COULD-NOT-MEASURE, not a terminating error.
$ErrorActionPreference = 'SilentlyContinue'

# --- Requirements, from PMOVES-Danger-infra/DEV-LOCAL.md --------------------
$ReqFreeRamGB  = 32    # 9 local-infra services + 4 GiB hugepages + microVMs
$ReqFreeDiskGB = 150   # public kernels + firecrackers + template rootfs + Go cache
$ReqArch       = 'AMD64'
$ReqHugepages  = 2048

$script:PassN = 0; $script:FailN = 0; $script:CnmN = 0

function P([string]$m) { Write-Host ("  [PASS]              " + $m);              $script:PassN++ }
function F([string]$m) { Write-Host ("  [FAIL]              " + $m);              $script:FailN++ }
function C([string]$m) { Write-Host ("  [COULD-NOT-MEASURE] " + $m);              $script:CnmN++  }
function H([string]$m) { Write-Host ""; Write-Host ("== " + $m) }
function N([string]$m) { Write-Host ("  note: " + $m) }

Write-Host "=== Danger Room capability probe (Windows host side) ==="
Write-Host ("host: " + $env:COMPUTERNAME + "   date: " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))
Write-Host "requirements source: PMOVES-Danger-infra/DEV-LOCAL.md"

# Elevation governs what several checks can see. Report it up front so a reader
# knows whether a COULD-NOT-MEASURE means "absent" or "not visible from here".
$IsAdmin = $false
try {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $IsAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
              [Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { }
Write-Host ("elevated: " + $IsAdmin + "   (several items below require an elevated shell)")

# ---------------------------------------------------------------------------
H "1. OS and CPU architecture"
$os = Get-CimInstance Win32_OperatingSystem
if ($null -eq $os) {
  C "OS: Win32_OperatingSystem unavailable"
} else {
  Write-Host ("  OS: " + $os.Caption + " build " + $os.BuildNumber)
  P ("OS identified: " + $os.Caption)
}
$arch = $env:PROCESSOR_ARCHITECTURE
if ([string]::IsNullOrEmpty($arch)) {
  C "arch: PROCESSOR_ARCHITECTURE not set"
} elseif ($arch -eq $ReqArch) {
  P ("arch: " + $arch + " (x86_64 -- matches what the public kernels and firecracker builds target)")
} else {
  F ("arch: " + $arch + " -- expected " + $ReqArch + ". The node profile declares no arch: field, so this reading is the only ground truth.")
}
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
if ($cpu) { Write-Host ("  cpu: " + $cpu.Name.Trim() + "  cores=" + $cpu.NumberOfCores + " threads=" + $cpu.NumberOfLogicalProcessors) }

# ---------------------------------------------------------------------------
H "2. Hypervisor / virtualization firmware"
$ci = Get-ComputerInfo -Property HyperVisorPresent,HyperVRequirementVirtualizationFirmwareEnabled,HyperVRequirementVMMonitorModeExtensions,HyperVRequirementSecondLevelAddressTranslation
if ($null -eq $ci) {
  C "Get-ComputerInfo returned nothing -- hypervisor state unknown"
} else {
  if ($ci.HyperVisorPresent -eq $true) {
    P "hypervisor: RUNNING on this host (Hyper-V / VBS active). WSL2 and Hyper-V VMs can use it."
  } elseif ($ci.HyperVRequirementVirtualizationFirmwareEnabled -eq $true) {
    F "hypervisor: NOT running, but the firmware virtualization switch (AMD-V/SVM) IS enabled. Enable the platform: Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All  (or VirtualMachinePlatform for WSL2 only), then reboot."
  } elseif ($ci.HyperVRequirementVirtualizationFirmwareEnabled -eq $false) {
    F "hypervisor: NOT running AND firmware virtualization is DISABLED. Enable SVM Mode in UEFI setup first -- nothing below can be fixed in Windows until that is on."
  } else {
    C "hypervisor: Get-ComputerInfo did not report HyperVisorPresent / firmware state (this is normal when the hypervisor is already running, which suppresses the HyperVRequirement* fields)."
  }
  if ($ci.HyperVRequirementSecondLevelAddressTranslation -eq $false) {
    F "SLAT: not reported -- Hyper-V and WSL2 both require Second Level Address Translation."
  }
}

# ---------------------------------------------------------------------------
H "3. Windows optional features (Hyper-V, VirtualMachinePlatform, WSL)"
# Get-WindowsOptionalFeature needs elevation. Unelevated it returns nothing,
# which is a COULD-NOT-MEASURE and emphatically not "the feature is absent".
$featNames = @('Microsoft-Hyper-V-All','VirtualMachinePlatform','Microsoft-Windows-Subsystem-Linux')
foreach ($fn in $featNames) {
  $f = Get-WindowsOptionalFeature -Online -FeatureName $fn
  if ($null -eq $f) {
    if (-not $IsAdmin) {
      C ($fn + ": not readable from an UNELEVATED shell. Re-run this probe as Administrator. This is not evidence the feature is absent.")
    } else {
      C ($fn + ": Get-WindowsOptionalFeature returned nothing even elevated -- feature may not exist on this SKU (Home has no Hyper-V).")
    }
  } elseif ($f.State -eq 'Enabled') {
    P ($fn + ": Enabled")
  } else {
    # VirtualMachinePlatform is the one WSL2 actually requires; Hyper-V-All is
    # only needed for full Hyper-V VMs, so its absence is not fatal if WSL2 is
    # the chosen path. Say so rather than emitting an undifferentiated FAIL.
    if ($fn -eq 'Microsoft-Hyper-V-All') {
      F ($fn + ": " + $f.State + ". Needed only if the Linux environment is a full Hyper-V VM. If WSL2 is the chosen path, VirtualMachinePlatform below is the one that matters.")
    } else {
      F ($fn + ": " + $f.State + " -- required for WSL2. Enable-WindowsOptionalFeature -Online -FeatureName " + $fn + " -All, then reboot.")
    }
  }
}

# ---------------------------------------------------------------------------
H "4. WSL presence and version"
$wslExe = Get-Command wsl.exe
if ($null -eq $wslExe) {
  F "wsl.exe: not on PATH -- WSL is not installed. Install with: wsl --install"
} else {
  P ("wsl.exe: present (" + $wslExe.Source + ")")
  # WSL writes UTF-16LE to a redirected pipe; decode explicitly or every string
  # comparison below silently fails against NUL-interleaved text.
  $prevEnc = [Console]::OutputEncoding
  try { [Console]::OutputEncoding = [System.Text.Encoding]::Unicode } catch { }
  $wslList = (& wsl.exe --list --verbose 2>&1 | Out-String)
  $wslStat = (& wsl.exe --status        2>&1 | Out-String)
  try { [Console]::OutputEncoding = $prevEnc } catch { }
  $wslList = $wslList -replace "`0", ""
  $wslStat = $wslStat -replace "`0", ""

  if ([string]::IsNullOrWhiteSpace($wslList)) {
    C "wsl --list --verbose: no output -- cannot tell which distros exist or what version they run."
  } else {
    Write-Host "  --- wsl --list --verbose ---"
    foreach ($ln in ($wslList -split "`r?`n")) { if ($ln.Trim().Length -gt 0) { Write-Host ("    " + $ln.TrimEnd()) } }
    if ($wslList -match 'no installed distributions|has no installed distributions') {
      F "WSL distros: NONE installed. Firecracker needs a real Linux environment. Install one: wsl --install -d Ubuntu"
    } elseif ($wslList -match '(?m)\s2\s*$') {
      P "WSL distro version: at least one distro runs WSL **2** (a real Linux kernel -- the only version that can expose /dev/kvm)."
    } elseif ($wslList -match '(?m)\s1\s*$') {
      F "WSL distro version: distros found but all run WSL **1**. WSL1 is a syscall translation layer with NO Linux kernel: no /dev/kvm, no Firecracker, ever. Convert: wsl --set-version <distro> 2"
    } else {
      C "WSL distro version: could not parse the VERSION column out of wsl --list --verbose."
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($wslStat)) {
    Write-Host "  --- wsl --status ---"
    foreach ($ln in ($wslStat -split "`r?`n")) { if ($ln.Trim().Length -gt 0) { Write-Host ("    " + $ln.TrimEnd()) } }
  }
}

# ---------------------------------------------------------------------------
H "5. Nested virtualization (Firecracker needs /dev/kvm INSIDE the guest)"
# This is the decisive item and it is only PARTIALLY answerable from Windows.
# The authoritative test is `ls -l /dev/kvm` inside the guest, which is what the
# Linux half of this probe does. Everything here is the necessary condition.
N "Firecracker is a KVM userspace VMM. It needs /dev/kvm inside the Linux guest, which means the outer hypervisor must expose virtualization extensions to that guest. That is nested virtualization."
$wslCfg = Join-Path $env:USERPROFILE ".wslconfig"
if (Test-Path $wslCfg) {
  P (".wslconfig: present at " + $wslCfg)
  $cfg = Get-Content $wslCfg -Raw
  if ($cfg -match '(?im)^\s*nestedVirtualization\s*=\s*true') {
    P ".wslconfig: nestedVirtualization=true is set explicitly."
  } elseif ($cfg -match '(?im)^\s*nestedVirtualization\s*=\s*false') {
    F ".wslconfig: nestedVirtualization=FALSE is set explicitly -- this actively blocks /dev/kvm in the guest. Set it to true under [wsl2] and run: wsl --shutdown"
  } else {
    C ".wslconfig: present but does not mention nestedVirtualization. The default differs by Windows build and CPU vendor, so this file does not settle the question -- only the Linux-side /dev/kvm check does."
  }
  if ($cfg -match '(?im)^\s*memory\s*=\s*(\S+)') {
    N (".wslconfig caps guest memory at '" + $Matches[1] + "'. The host's installed RAM is NOT what the guest gets -- check the Linux half's MemTotal against the " + $ReqFreeRamGB + " GiB requirement.")
  } else {
    N "No explicit memory= in .wslconfig: WSL2 defaults to a fraction of host RAM. Confirm the guest's actual MemTotal in the Linux half."
  }
} else {
  C (".wslconfig: absent (" + $wslCfg + "). Not a failure -- defaults apply -- but nested virtualization is then unstated, so the guest-side /dev/kvm check is the only answer.")
}
foreach ($vm in (Get-VM)) {
  $vp = Get-VMProcessor -VMName $vm.Name
  if ($vp) {
    if ($vp.ExposeVirtualizationExtensions -eq $true) {
      P ("Hyper-V VM '" + $vm.Name + "': nested virtualization EXPOSED")
    } else {
      F ("Hyper-V VM '" + $vm.Name + "': nested virtualization NOT exposed. Fix (VM must be off): Set-VMProcessor -VMName '" + $vm.Name + "' -ExposeVirtualizationExtensions `$true")
    }
  }
}
C "nested virtualization, decisive check: NOT ANSWERABLE from Windows. Run the Linux half inside the guest and read its '/dev/kvm' item:  wsl -d <distro> -- bash pmoves/scripts/probe_danger_room_host.sh"

# ---------------------------------------------------------------------------
H ("6. Free RAM (host, need >= " + $ReqFreeRamGB + " GiB for the guest to have headroom)")
if ($null -eq $os) {
  C "RAM: Win32_OperatingSystem unavailable"
} else {
  $freeGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 1)   # KB -> GiB
  $totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
  Write-Host ("  total=" + $totalGB + " GiB  free=" + $freeGB + " GiB")
  if ($freeGB -ge $ReqFreeRamGB) {
    P ("RAM: " + $freeGB + " GiB free on the host (>= " + $ReqFreeRamGB + " GiB)")
  } else {
    F ("RAM: only " + $freeGB + " GiB free on the host, need >= " + $ReqFreeRamGB + " GiB.")
  }
  N ("host free RAM is a CEILING, not the answer: the WSL2 guest gets what .wslconfig allows, and " + $ReqHugepages + " hugepages reserve 4 GiB inside the guest before a single microVM starts.")
}

# ---------------------------------------------------------------------------
H ("7. Free disk (need >= " + $ReqFreeDiskGB + " GiB)")
$vols = Get-Volume | Where-Object { $_.DriveLetter -and $_.SizeRemaining -gt 0 }
if ($null -eq $vols) {
  C "disk: Get-Volume returned nothing"
} else {
  $best = 0
  foreach ($v in $vols) {
    $gb = [math]::Round($v.SizeRemaining / 1GB, 1)
    Write-Host ("  " + $v.DriveLetter + ": free=" + $gb + " GiB  fs=" + $v.FileSystemType)
    if ($gb -gt $best) { $best = $gb }
  }
  if ($best -ge $ReqFreeDiskGB) {
    P ("disk: largest free volume has " + $best + " GiB (>= " + $ReqFreeDiskGB + " GiB)")
  } else {
    F ("disk: largest free volume has only " + $best + " GiB, need >= " + $ReqFreeDiskGB + " GiB.")
  }
  N "The WSL2 ext4.vhdx grows on demand from the volume holding it (usually C:). Free space THERE is what constrains kernels, firecracker builds and rootfs images -- and the checkout must live on the guest's ext4, never on /mnt/c."
}

# ---------------------------------------------------------------------------
H "8. Host port collisions (DEV-LOCAL.md 'Services')"
# WSL2 forwards listeners to the host via localhost relay, so a HOST process on
# :3000 is a real conflict for the guest's e2b api. :3000 has already bitten
# this fleet once -- a host npx hf-mcp-server took it and PostgREST moved to 3001.
$ports = @(@(3000,'e2b api'), @(3002,'e2b client-proxy'), @(5008,'e2b orchestrator'),
           @(5432,'postgres'), @(8123,'clickhouse http'), @(6379,'redis'), @(53000,'grafana'))
$anyPortRead = $false
foreach ($pp in $ports) {
  $pn = $pp[0]; $what = $pp[1]
  $conn = Get-NetTCPConnection -State Listen -LocalPort $pn
  if ($null -ne $conn) {
    $anyPortRead = $true
    $owner = ""
    $pr = Get-Process -Id ($conn | Select-Object -First 1).OwningProcess
    if ($pr) { $owner = " (held by " + $pr.ProcessName + ", pid " + $pr.Id + ")" }
    F ("port " + $pn + " (" + $what + "): ALREADY IN USE on the host" + $owner)
  } else {
    P ("port " + $pn + " (" + $what + "): free on the host")
    $anyPortRead = $true
  }
}
if (-not $anyPortRead) { C "ports: Get-NetTCPConnection unavailable -- no port reading was obtained" }

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== verdict ==="
Write-Host ("  PASS=" + $script:PassN + "  FAIL=" + $script:FailN + "  COULD-NOT-MEASURE=" + $script:CnmN)
if ($script:CnmN -gt 0) {
  Write-Host "  OVERALL: COULD-NOT-MEASURE (exit 3)"
  Write-Host ("  " + $script:CnmN + " item(s) could not be read. This is NOT a pass. The nested-virtualization item is ALWAYS could-not-measure from Windows by construction -- run the Linux half inside the guest to settle it.")
  exit 3
}
if ($script:FailN -gt 0) {
  Write-Host "  OVERALL: FINDINGS (exit 1)"
  Write-Host "  Each FAIL above names its remedy. Nothing here was changed by this probe."
  exit 1
}
Write-Host "  OVERALL: CLEAN (exit 0)"
Write-Host "  A Linux environment can exist on this host. That is a NECESSARY, not sufficient, condition -- now run the Linux half inside it:"
Write-Host "    wsl -d <distro> -- bash pmoves/scripts/probe_danger_room_host.sh"
exit 0
