# PMOVES.AI Glances-Based System Autodetection - Windows Companion
#
# Samples system specs (CPU, RAM, GPU, disk, NIC speed, OS, platform hints)
# using WMI/CIM, Get-PhysicalDisk, Get-NetAdapter, and registry queries,
# then emits a suggested `hostinger-kvm-setup.sh --node-type` value.
#
# Designed to be run on UNKNOWN WINDOWS SYSTEMS during PMOVES.AI onboarding:
#   - Fresh hardware with unknown configuration
#   - Community node-operator machines (Windows 10/11 x64 or ARM64)
#   - 4090/5090 workstations awaiting classification
#
# USAGE:
#   # Must be run in PowerShell (any version >=5.1). No elevation required.
#   .\glances-autodetect.ps1                    # interactive report + suggestion
#   .\glances-autodetect.ps1 -Json              # structured JSON to stdout
#   .\glances-autodetect.ps1 -JsonFile PATH     # write JSON to file
#   .\glances-autodetect.ps1 -Suggest           # print ONLY the suggested node-type
#   .\glances-autodetect.ps1 -Help              # usage
#
# JSON SCHEMA (matches glances-autodetect.sh - stable):
#   {
#     "os":              { "distro": "windows", "version": "11 Pro", "kernel": "10.0.26200" },
#     "arch":            "x86_64" | "aarch64",
#     "cpu":             { "model": "...", "cores_physical": 8, "cores_logical": 16 },
#     "ram_gb":          32,
#     "gpus":            [ { "vendor": "nvidia|amd|intel", "model": "...", "vram_gb": 24, "pci_id": "" } ],
#     "disks":           [ { "name": "NVMe ...", "size_gb": 1000, "rotational": false } ],
#     "nics":            [ { "name": "Ethernet", "speed_mbps": 10000 } ],
#     "nic_collisions":  [ { "primary": "<adapter> (<ip>) [Up]", "ghost": "<adapter> (<ip>) [Disconnected]", "subnet": "<cidr>" } ],
#     "platform_hints":  { "is_pve": false, "is_dgx_os": false, "has_tailscale": false,
#                          "has_docker": false, "has_wsl2": false, "has_hyper_v": false },
#     "suggested_node_type":   "gpu-4090",
#     "suggestion_confidence": "high" | "medium" | "low",
#     "suggestion_rationale":  "Detected NVIDIA RTX 4090 + Core i9-14900HX + 64 GB RAM"
#   }
#
# NODE-TYPE MAPPING (matches glances-autodetect.sh):
#   gpu-5090           x86_64 + NVIDIA RTX 5090 + >=64 GB RAM
#   gpu-4090           x86_64 + NVIDIA RTX 4090 (any RAM)
#   rdna4-workstation  AMD Ryzen + 2x AMD Radeon (gfx1201/R9700/RDNA4)
#   dgx-spark          ARM64 + NVIDIA (would be DGX OS; rare on bare Windows)
#   pve-member-fresh   >=10 GbE NIC + >=2 NVMe + >=64 GB RAM (candidate new PVE host)
#   desktop-workstation  x86_64 + discrete GPU + >=32 GB RAM (unclassified)
#   unknown            Manual selection required
#
# SAFETY:
#   - No elevation required; some NIC speed fields require admin for accuracy.
#   - Idempotent: no state writes unless --json-file given.
#   - System is NOT modified by this script.

# Support both PowerShell (-Param) and Linux-style (--param) flags for parity
# with the Bash companion.  We parse $args manually first, then set the
# declared params so the rest of the script stays unchanged.
param(
    [switch]$Json,
    [string]$JsonFile,
    [switch]$Suggest,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$i = 0
while ($i -lt $args.Count) {
    switch ($args[$i]) {
        '--json'      { $Json = $true }
        '--json-file' { if ($i + 1 -lt $args.Count) { $JsonFile = $args[++$i] } else { throw '--json-file requires a path argument' } }
        '--suggest'   { $Suggest = $true }
        '--help'      { $Help = $true }
        default       { Write-Warn "Unknown argument: $($args[$i])" }
    }
    $i++
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Info  { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Sect  { param($msg) Write-Host "[====] $msg" -ForegroundColor Cyan }

if ($Help) {
    Get-Content -Path $MyInvocation.MyCommand.Path | Select-String -Pattern '^#' |
        ForEach-Object { $_.Line -replace '^# ?','' }
    exit 0
}

# ---------------------------------------------------------------------------
# OS detection
# ---------------------------------------------------------------------------
function Get-OsInfo {
    $os = Get-CimInstance Win32_OperatingSystem
    $caption = $os.Caption -replace 'Microsoft Windows ',''
    $version = $os.Version
    $arch = if ([System.Environment]::Is64BitOperatingSystem) {
        if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
    } else { 'x86' }
    @{
        distro  = 'windows'
        version = $caption.Trim()
        kernel  = $version
        arch    = $arch
    }
}

# ---------------------------------------------------------------------------
# CPU detection
# ---------------------------------------------------------------------------
function Get-CpuInfo {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $logical = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    @{
        model         = $cpu.Name.Trim()
        cores_physical = [int]$cpu.NumberOfCores
        cores_logical  = [int]$logical
    }
}

# ---------------------------------------------------------------------------
# RAM detection
# ---------------------------------------------------------------------------
function Get-RamGb {
    $cs = Get-CimInstance Win32_ComputerSystem
    [int][Math]::Round($cs.TotalPhysicalMemory / 1GB)
}

# ---------------------------------------------------------------------------
# GPU detection - VRAM via registry (WMI AdapterRAM capped at 4 GB)
# ---------------------------------------------------------------------------
function Get-GpuVramMbFromRegistry {
    param([string]$DeviceId)
    # VideoController DeviceID is like PCI\VEN_10DE&DEV_... - match via driver key
    $regBase = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
    $found = 0
    Get-ChildItem -Path $regBase -ErrorAction SilentlyContinue | ForEach-Object {
        $mem = (Get-ItemProperty -Path $_.PSPath -Name 'HardwareInformation.MemorySize' -ErrorAction SilentlyContinue).'HardwareInformation.MemorySize'
        if ($null -ne $mem -and $mem -gt 0) {
            $match = (Get-ItemProperty -Path $_.PSPath -Name 'MatchingDeviceId' -ErrorAction SilentlyContinue).MatchingDeviceId
            if ($match -and $DeviceId -and $DeviceId.ToLower().Contains(($match -replace '\*','').ToLower())) {
                $found = [int]($mem / 1MB)
            }
        }
    }
    $found
}

function Get-GpuInfo {
    $gpus = @()
    # Exclude virtual/software adapters and display-only devices
    $skipPattern = 'Microsoft Basic|Virtual|Parsec|SudoMaker|USB Mobile|Meta Virtual|Citrix|TeamViewer|Remote Desktop'
    $controllers = Get-CimInstance Win32_VideoController |
        Where-Object { $_.Name -notmatch $skipPattern -and $_.PNPDeviceID -match '^PCI\\' }
    foreach ($g in $controllers) {
        $name = $g.Name.Trim()
        $vendor = switch -Regex ($name) {
            'NVIDIA|GeForce|Quadro|Tesla' { 'nvidia' }
            'AMD|Radeon|FirePro'          { 'amd' }
            'Intel'                       { 'intel' }
            default                       { 'unknown' }
        }
        # Registry query for VRAM — more accurate than WMI (which caps at 4 GB)
        $vramMb = Get-GpuVramMbFromRegistry -DeviceId ($g.PNPDeviceID)
        if ($vramMb -le 0) {
            # WMI fallback (capped at 4 GB on older drivers; last resort)
            $vramMb = [int]($g.AdapterRAM / 1MB)
        }
        $vramGb = [Math]::Round($vramMb / 1024, 1)
        $gpus += @{
            vendor  = $vendor
            model   = $name
            vram_gb = $vramGb
            pci_id  = ''
        }
    }
    $gpus
}

# ---------------------------------------------------------------------------
# Disk detection
# ---------------------------------------------------------------------------
function Get-DiskInfo {
    $disks = @()
    try {
        $physDisks = Get-PhysicalDisk | Where-Object { $_.Size -gt 0 }
        foreach ($d in $physDisks) {
            $sizeGb = [int][Math]::Round($d.Size / 1GB)
            $rotational = ($d.MediaType -eq 'HDD')
            $disks += @{
                name       = $d.FriendlyName
                size_gb    = $sizeGb
                rotational = $rotational
                bus_type   = [string]$d.BusType
            }
        }
    } catch {
        # Fallback: WMI
        Get-CimInstance Win32_DiskDrive | ForEach-Object {
            $busType = if ($_.Model -match 'NVMe') { 'NVMe' } else { 'Unknown' }
            $disks += @{
                name       = $_.Model
                size_gb    = [int][Math]::Round($_.Size / 1GB)
                rotational = ($_.MediaType -notmatch 'SSD|NVMe|Solid')
                bus_type   = $busType
            }
        }
    }
    $disks
}

# ---------------------------------------------------------------------------
# NIC detection
# ---------------------------------------------------------------------------
function Get-NicInfo {
    $nics = @()
    $adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceType -ne 24 }
    foreach ($a in $adapters) {
        $speedMbps = if ($a.LinkSpeed -match '(\d+\.?\d*)\s*(Gbps|Mbps)') {
            if ($Matches[2] -eq 'Gbps') { [int]([double]$Matches[1] * 1000) } else { [int]$Matches[1] }
        } else { 0 }
        $nics += @{
            name       = $a.Name
            speed_mbps = $speedMbps
        }
    }
    $nics
}

# ---------------------------------------------------------------------------
# Same-subnet ghost detector
# See: pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md
#
# Returns an array of collision objects. Empty on healthy hosts.
# Output field: nic_collisions: [{primary, ghost, subnet}]
#
# A "ghost" is a disconnected/inactive adapter whose IP falls inside the
# same /24 as an active adapter. Docker Desktop's port-forwarder silently
# no-ops binds when a ghost claims the routing table entry first.
# ---------------------------------------------------------------------------
function Get-NicCollisions {
    $collisions = @()
    $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '169.254.*' -and
                       $_.IPAddress -ne '127.0.0.1' -and
                       $_.IPAddress -notlike '10.255.*' }    # exclude Docker internal

    # Group by subnet prefix using TRUE CIDR mask (bitwise), not octet truncation.
    # The earlier octet-floor approach mis-grouped /23, /20, /25, etc. — leading to
    # missed real collisions on non-/24 networks and false ones on partial-octet masks.
    $bySubnet = @{}
    foreach ($addr in $addrs) {
        $ip = [System.Net.IPAddress]::Parse($addr.IPAddress)
        $pl = [int]$addr.PrefixLength
        if ($pl -lt 1 -or $pl -gt 32) { continue }

        # Build true network mask from PrefixLength (bitwise AND on each byte)
        $bytes = $ip.GetAddressBytes()
        $netBytes = New-Object byte[] 4
        for ($i = 0; $i -lt 4; $i++) {
            $bitsRemaining = $pl - ($i * 8)
            if ($bitsRemaining -le 0) {
                $maskByte = 0
            } elseif ($bitsRemaining -ge 8) {
                $maskByte = 255
            } else {
                # Partial-octet mask: top $bitsRemaining bits set, rest cleared
                $maskByte = [byte]((0xFF -shl (8 - $bitsRemaining)) -band 0xFF)
            }
            $netBytes[$i] = [byte]($bytes[$i] -band $maskByte)
        }
        $netKey = "$($netBytes[0]).$($netBytes[1]).$($netBytes[2]).$($netBytes[3])/$pl"

        if (-not $bySubnet.ContainsKey($netKey)) { $bySubnet[$netKey] = @() }
        $bySubnet[$netKey] += $addr
    }

    foreach ($subnet in $bySubnet.Keys) {
        $members = $bySubnet[$subnet]
        if ($members.Count -lt 2) { continue }

        # Classify: primary = Up, ghost = everything else
        $primaries = @($members | Where-Object {
            (Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).Status -eq 'Up'
        })
        $ghosts = @($members | Where-Object {
            $s = (Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).Status
            $s -ne 'Up'
        })

        foreach ($ghost in $ghosts) {
            $primary = if ($primaries.Count -gt 0) { $primaries[0] } else { $members[0] }
            $primaryAdapter = Get-NetAdapter -InterfaceIndex $primary.InterfaceIndex -ErrorAction SilentlyContinue
            $ghostAdapter   = Get-NetAdapter -InterfaceIndex $ghost.InterfaceIndex   -ErrorAction SilentlyContinue
            $collisions += @{
                primary = "$($primaryAdapter.Name) ($($primary.IPAddress)) [$($primaryAdapter.Status)]"
                ghost   = "$($ghostAdapter.Name) ($($ghost.IPAddress)) [$($ghostAdapter.Status)]"
                subnet  = $subnet
            }
        }

        # Two-Up collision (both active): flag as warning
        if ($ghosts.Count -eq 0 -and $primaries.Count -ge 2) {
            $collisions += @{
                primary = "$((Get-NetAdapter -InterfaceIndex $primaries[0].InterfaceIndex -ErrorAction SilentlyContinue).Name) ($($primaries[0].IPAddress)) [Up]"
                ghost   = "$((Get-NetAdapter -InterfaceIndex $primaries[1].InterfaceIndex -ErrorAction SilentlyContinue).Name) ($($primaries[1].IPAddress)) [Up - both active]"
                subnet  = $subnet
            }
        }
    }
    $collisions
}

# ---------------------------------------------------------------------------
# Platform hints
# ---------------------------------------------------------------------------
function Get-PlatformHints {
    $hasTailscale = $null -ne (Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue) -or
                   (Test-Path 'C:\Program Files\Tailscale\tailscale.exe')
    $hasDocker    = $null -ne (Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue) -or
                   (Test-Path 'C:\Program Files\Docker\Docker\Docker Desktop.exe')
    $vmmsSvc = Get-Service -Name 'vmms' -ErrorAction SilentlyContinue
    $hasHyperV    = ($null -ne $vmmsSvc) -and ($vmmsSvc.Status -eq 'Running')
    $hasWsl2      = $null -ne (Get-Command 'wsl' -ErrorAction SilentlyContinue) -and
                   ((wsl --list --quiet 2>$null) -ne $null)
    @{
        is_pve       = $false
        is_dgx_os    = $false
        has_tailscale = $hasTailscale
        has_docker   = $hasDocker
        has_wsl2     = $hasWsl2
        has_hyper_v  = $hasHyperV
    }
}

# ---------------------------------------------------------------------------
# Node-type classification
# ---------------------------------------------------------------------------
function Get-NodeSuggestion {
    param($CpuInfo, $RamGb, $Gpus, $Disks, $Nics, $OsArch)

    $nvidiaGpus = @($Gpus | Where-Object { $_.vendor -eq 'nvidia' })
    $amdGpus    = @($Gpus | Where-Object { $_.vendor -eq 'amd' -and $_.model -notmatch 'Radeon.*Graphics' })
    $nvmeCount  = @($Disks | Where-Object { $_.bus_type -match '^NVMe$' }).Count
    $maxNicGbps = ($Nics | ForEach-Object { $_.speed_mbps } | Measure-Object -Maximum).Maximum / 1000

    # DGX Spark: ARM64 + NVIDIA (would be rare on bare Windows, but handle it)
    if ($OsArch -eq 'aarch64' -and $nvidiaGpus.Count -gt 0) {
        return @{ type='dgx-spark'; confidence='medium'; rationale="ARM64 + NVIDIA GPU detected - likely DGX/Jetson class" }
    }

    # RTX 5090
    if (($nvidiaGpus | Where-Object { $_.model -match '5090' }) -and $RamGb -ge 64) {
        return @{ type='gpu-5090'; confidence='high'; rationale="Detected NVIDIA RTX 5090 + $($CpuInfo.model) + $RamGb GB RAM (>=64 GB required)" }
    }

    # RTX 4090
    if ($nvidiaGpus | Where-Object { $_.model -match '4090' }) {
        return @{ type='gpu-4090'; confidence='high'; rationale="Detected NVIDIA RTX 4090 + $($CpuInfo.model) + $RamGb GB RAM" }
    }

    # RDNA4 workstation: AMD Ryzen + >=2 AMD Radeon (gfx1201/R9700/RDNA4)
    $rdna4Match = @($amdGpus | Where-Object { $_.model -match 'R9700|Navi 48|Radeon AI Pro|gfx1201|RDNA.?4' })
    if ($CpuInfo.model -match 'Ryzen' -and $rdna4Match.Count -ge 2) {
        return @{ type='rdna4-workstation'; confidence='high'; rationale="Detected $($rdna4Match[0].model) (x$($rdna4Match.Count)) + Ryzen $($CpuInfo.model) + $RamGb GB RAM" }
    }

    # PVE-member-fresh candidate: >=10 GbE + >=2 NVMe + >=64 GB RAM
    if ($maxNicGbps -ge 10 -and $nvmeCount -ge 2 -and $RamGb -ge 64) {
        return @{ type='pve-member-fresh'; confidence='medium'; rationale=">=${maxNicGbps} Gbps NIC + $nvmeCount NVMe + $RamGb GB RAM - PVE candidate" }
    }

    # Generic discrete GPU workstation
    if (($nvidiaGpus.Count + $amdGpus.Count) -gt 0 -and $RamGb -ge 32) {
        $gpuName = if ($nvidiaGpus.Count -gt 0) { $nvidiaGpus[0].model } else { $amdGpus[0].model }
        return @{ type='desktop-workstation'; confidence='medium'; rationale="Detected $gpuName + $($CpuInfo.model) + $RamGb GB RAM" }
    }

    return @{ type='unknown'; confidence='low'; rationale="No matching profile - manual node-type selection required" }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if (-not $Json -and -not $JsonFile -and -not $Suggest) {
    Write-Sect "PMOVES.AI Windows Hardware Probe"
}

$osRaw  = Get-OsInfo
$cpu    = Get-CpuInfo
$ramGb  = Get-RamGb
$gpus   = Get-GpuInfo
$disks  = Get-DiskInfo
$nics   = Get-NicInfo
$hints         = Get-PlatformHints
$nicCollisions = Get-NicCollisions
$suggestion    = Get-NodeSuggestion -CpuInfo $cpu -RamGb $ramGb -Gpus $gpus -Disks $disks -Nics $nics -OsArch $osRaw.arch

$result = [ordered]@{
    os = [ordered]@{
        distro  = $osRaw.distro
        version = $osRaw.version
        kernel  = $osRaw.kernel
    }
    arch   = $osRaw.arch
    cpu    = [ordered]@{
        model          = $cpu.model
        cores_physical = $cpu.cores_physical
        cores_logical  = $cpu.cores_logical
    }
    ram_gb = $ramGb
    gpus   = @($gpus | ForEach-Object {
        [ordered]@{ vendor=$_.vendor; model=$_.model; vram_gb=$_.vram_gb; pci_id=$_.pci_id }
    })
    disks = @($disks | ForEach-Object {
        [ordered]@{ name=$_.name; size_gb=$_.size_gb; rotational=$_.rotational; bus_type=$_.bus_type }
    })
    nics = @($nics | ForEach-Object {
        [ordered]@{ name=$_.name; speed_mbps=$_.speed_mbps }
    })
    nic_collisions = @($nicCollisions | ForEach-Object {
        [ordered]@{ primary=$_.primary; ghost=$_.ghost; subnet=$_.subnet }
    })
    platform_hints = [ordered]@{
        is_pve        = $hints.is_pve
        is_dgx_os     = $hints.is_dgx_os
        has_tailscale = $hints.has_tailscale
        has_docker    = $hints.has_docker
        has_wsl2      = $hints.has_wsl2
        has_hyper_v   = $hints.has_hyper_v
    }
    suggested_node_type   = $suggestion.type
    suggestion_confidence = $suggestion.confidence
    suggestion_rationale  = $suggestion.rationale
}

if ($Suggest) {
    Write-Output $suggestion.type
    exit 0
}

$jsonStr = $result | ConvertTo-Json -Depth 5

if ($JsonFile) {
    $jsonStr | Out-File -FilePath $JsonFile -Encoding utf8
    Write-Info "JSON written to: $JsonFile"
    exit 0
}

if ($Json) {
    Write-Output $jsonStr
    exit 0
}

# ---------------------------------------------------------------------------
# Interactive report
# ---------------------------------------------------------------------------
Write-Sect "OS"
Write-Host "  Windows $($osRaw.version) ($($osRaw.arch)) - kernel $($osRaw.kernel)"

Write-Sect "CPU"
Write-Host "  $($cpu.model)"
Write-Host "  Cores: $($cpu.cores_physical) physical / $($cpu.cores_logical) logical"

Write-Sect "RAM"
Write-Host "  $ramGb GB"

Write-Sect "GPUs"
if ($gpus.Count -eq 0) {
    Write-Host "  (none detected)"
} else {
    foreach ($g in $gpus) {
        Write-Host "  [$($g.vendor.ToUpper())] $($g.model)  VRAM: $($g.vram_gb) GB"
    }
}

Write-Sect "Disks"
foreach ($d in $disks) {
    $type = if ($d.rotational) { 'HDD' } else { 'SSD/NVMe' }
    Write-Host "  $($d.name)  $($d.size_gb) GB  $type"
}

Write-Sect "NICs (Up)"
foreach ($n in $nics) {
    Write-Host "  $($n.name)  $($n.speed_mbps) Mbps"
}

Write-Sect "NIC Collision Check"
if ($nicCollisions.Count -eq 0) {
    Write-Host "  No same-subnet ghost adapters detected" -ForegroundColor Green
} else {
    foreach ($col in $nicCollisions) {
        Write-Warn "Same-subnet collision on $($col.subnet)"
        Write-Host "    Primary : $($col.primary)"
        Write-Host "    Ghost   : $($col.ghost)"
    }
    Write-Host ""
    Write-Warn "Docker Desktop may silently fail port binds on this host."
    Write-Host "  See: pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md"
    Write-Host "  Fix: re-IP ghost adapter to a dedicated CIDR, then restart Docker stack."
}

Write-Sect "Platform Hints"
Write-Host "  Tailscale:  $($hints.has_tailscale)"
Write-Host "  Docker:     $($hints.has_docker)"
Write-Host "  WSL2:       $($hints.has_wsl2)"
Write-Host "  Hyper-V:    $($hints.has_hyper_v)"

Write-Host ""
$confColor = switch ($suggestion.confidence) {
    'high'   { 'Green' }
    'medium' { 'Yellow' }
    default  { 'Red' }
}
Write-Host "SUGGESTED NODE TYPE: " -NoNewline
Write-Host $suggestion.type -ForegroundColor $confColor
Write-Host "Confidence:          $($suggestion.confidence)"
Write-Host "Rationale:           $($suggestion.rationale)"
Write-Host ""
Write-Host 'To apply:'
$applyCmd = "  bash deploy/provision/hostinger-kvm-setup.sh --node-type " + $suggestion.type
Write-Host $applyCmd
