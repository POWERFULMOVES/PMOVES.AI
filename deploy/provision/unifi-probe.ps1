# unifi-probe.ps1 — Query Unifi Network Application and cross-check host NICs
# (PowerShell mirror of unifi-probe.sh)
#
# Emits a unifi_topology JSON object for appending to glances-autodetect.ps1 output.
# Called automatically by glances-autodetect.ps1 when UNIFI_CONTROLLER_URL and
# UNIFI_API_KEY are set. Can also be run standalone.
#
# USAGE:
#   .\unifi-probe.ps1 [-Json] [-Controller URL] [-ApiKey KEY] [-Site SITE]
#
# ENV VARS (used if flags omitted):
#   UNIFI_CONTROLLER_URL  e.g. https://unifi-controller or https://unifi-controller:8443
#   UNIFI_API_KEY         API key from: Unifi Network App → Settings → System → API
#   UNIFI_SITE            Site name (default: "default")
#
# OUTPUT (stdout, JSON): same schema as unifi-probe.sh
#
# SAFETY:
#   - Never exits non-zero due to controller issues (best-effort enrichment)
#   - Self-signed certs accepted
#   - No state written; read-only queries only

param(
    [switch]$Json,
    [string]$Controller = "",
    [string]$ApiKey     = "",
    [string]$Site       = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"  # "Stop" would propagate uncaught exceptions as non-zero exit

# --- Resolve from env vars if not passed ---
if (-not $Controller) { $Controller = $env:UNIFI_CONTROLLER_URL }
if (-not $ApiKey)     { $ApiKey     = $env:UNIFI_API_KEY }
if (-not $Site)       { $Site       = if ($env:UNIFI_SITE) { $env:UNIFI_SITE } else { "default" } }

# --- Safe JSON output helpers ---
function Emit-Skip([string]$Reason) {
    Write-Output "{`"skipped`":true,`"reason`":`"$Reason`"}"
    exit 0
}

function Emit-Error([string]$ErrCode) {
    $urlJson = if ($Controller) { "`"$Controller`"" } else { "null" }
    Write-Output "{`"controller_url`":$urlJson,`"topology_ok`":false,`"error`":`"$ErrCode`"}"
    exit 0
}

# --- Skip if not configured ---
if (-not $Controller) { Emit-Skip "UNIFI_CONTROLLER_URL not set" }
if (-not $ApiKey)     { Emit-Skip "UNIFI_API_KEY not set" }

# Strip trailing slash
$Controller = $Controller.TrimEnd('/')

# --- TLS: accept self-signed certs (cross-version) ---
function Disable-SslVerification {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        # PS5.1 — use ServicePointManager callback
        Add-Type -TypeDefinition @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class AcceptAllCerts : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int err) {
        return true;
    }
}
"@
        [System.Net.ServicePointManager]::CertificatePolicy = New-Object AcceptAllCerts
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    }
}

Disable-SslVerification

# Splatting helper for cross-version SkipCertificateCheck
$IrmOpts = @{ Headers = @{ "X-API-KEY" = $ApiKey; "Content-Type" = "application/json" }; TimeoutSec = 8 }
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $IrmOpts["SkipCertificateCheck"] = $true
}

# --- Normalize MAC to lowercase colon form ---
function Normalize-Mac([string]$Mac) {
    $Mac.ToLower() -replace '-', ':'
}

# --- Collect host MACs from Get-NetAdapter ---
$HostMacs = @()
$MacToNic = @{}
try {
    Get-NetAdapter | ForEach-Object {
        $mac = Normalize-Mac $_.MacAddress
        if ($mac -ne "00:00:00:00:00:00" -and $mac -ne "") {
            $HostMacs += $mac
            $MacToNic[$mac] = $_.Name
        }
    }
} catch {
    # Non-fatal — proceed with empty host MAC list
}

# --- Detect API version: try modern UDM path first, fall back to legacy ---
$ApiVersion = "unknown"
$ModernUrl  = "$Controller/proxy/network/api/s/$Site/stat/sta"
$LegacyUrl  = "$Controller/api/s/$Site/stat/sta"
$BaseUrl    = ""

function Test-ApiEndpoint([string]$Url) {
    try {
        $resp = Invoke-WebRequest -Uri $Url @IrmOpts -Method Get -UseBasicParsing 2>$null
        return $resp.StatusCode
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code) { return $code }
        return 0
    }
}

$ModernCode = Test-ApiEndpoint $ModernUrl
if ($ModernCode -eq 200) {
    $ApiVersion = "modern"
    $BaseUrl    = "$Controller/proxy/network/api/s/$Site"
} elseif ($ModernCode -eq 401 -or $ModernCode -eq 403) {
    Emit-Error "auth_failed"
} elseif ($ModernCode -eq 0) {
    Emit-Error "unreachable"
} else {
    $LegacyCode = Test-ApiEndpoint $LegacyUrl
    if ($LegacyCode -eq 200) {
        $ApiVersion = "legacy"
        $BaseUrl    = "$Controller/api/s/$Site"
    } elseif ($LegacyCode -eq 401 -or $LegacyCode -eq 403) {
        Emit-Error "auth_failed"
    } else {
        Emit-Error "unreachable"
    }
}

# --- Fetch managed devices and clients ---
function Invoke-Api([string]$Path) {
    try {
        $resp = Invoke-RestMethod -Uri "$BaseUrl$Path" @IrmOpts
        return $resp
    } catch {
        return @{ data = @() }
    }
}

$DevicesRaw = Invoke-Api "/stat/device"
$ClientsRaw = Invoke-Api "/stat/sta"

# --- Build managed devices list ---
$ManagedDevices = [System.Collections.Generic.List[hashtable]]::new()
$SeenMacs = [System.Collections.Generic.HashSet[string]]::new()

# Infrastructure devices (switches, APs, gateways) take precedence
foreach ($d in $DevicesRaw.data) {
    $mac = Normalize-Mac ($d.mac -replace '-', ':')
    if (-not $mac) { continue }
    $type = switch ($d.type) {
        "usw" { "switch" }
        "uap" { "ap" }
        "ugw" { "gw" }
        "udm" { "gw" }
        default { if ($d.type) { $d.type } else { "device" } }
    }
    $entry = @{
        mac          = $mac
        hostname     = if ($d.name) { $d.name } elseif ($d.hostname) { $d.hostname } else { "" }
        ip           = if ($d.ip) { $d.ip } else { "" }
        vlan         = if ($null -ne $d.vlan) { [int]$d.vlan } else { 0 }
        port         = if ($d.uplink -and $d.uplink.port_idx) { [int]$d.uplink.port_idx } else { 0 }
        uplink_mbps  = if ($d.uplink -and $d.uplink.speed) { [int]$d.uplink.speed } else { 0 }
        type         = $type
    }
    $ManagedDevices.Add($entry)
    [void]$SeenMacs.Add($mac)
}

# Clients (only if MAC not already seen)
foreach ($c in $ClientsRaw.data) {
    $mac = Normalize-Mac ($c.mac -replace '-', ':')
    if (-not $mac -or $SeenMacs.Contains($mac)) { continue }
    $entry = @{
        mac         = $mac
        hostname    = if ($c.hostname) { $c.hostname } elseif ($c.name) { $c.name } else { "" }
        ip          = if ($c.ip) { $c.ip } else { "" }
        vlan        = if ($null -ne $c.vlan) { [int]$c.vlan } else { 0 }
        port        = 0
        uplink_mbps = if ($c.uplink_speed) { [int]$c.uplink_speed } else { 0 }
        type        = "client"
    }
    $ManagedDevices.Add($entry)
    [void]$SeenMacs.Add($mac)
}

$UnifiMacs = $ManagedDevices | ForEach-Object { $_.mac }

# --- Cross-check: host MACs vs Unifi ---
$HostMacMatches = foreach ($mac in $HostMacs) {
    $nic = if ($MacToNic.ContainsKey($mac)) { $MacToNic[$mac] } else { "unknown" }
    $status = if ($UnifiMacs -contains $mac) { "matched" } else { "unmanaged" }
    @{ nic = $nic; mac = $mac; status = $status }
}

# --- Ghost devices: Unifi sees them but host doesn't claim them ---
$GhostDevices = foreach ($umac in $UnifiMacs) {
    if ($HostMacs -notcontains $umac) {
        $hostname = ($ManagedDevices | Where-Object { $_.mac -eq $umac } | Select-Object -First 1).hostname
        @{ mac = $umac; hostname = $hostname; note = "seen by Unifi, not on this host" }
    }
}

# --- VLAN mismatches ---
$VlanMismatches = foreach ($mac in $HostMacs) {
    $nic = if ($MacToNic.ContainsKey($mac)) { $MacToNic[$mac] } else { "unknown" }
    $device = $ManagedDevices | Where-Object { $_.mac -eq $mac } | Select-Object -First 1
    if ($device -and $device.vlan -gt 0) {
        # Check if host has a VLAN-tagged adapter (name like "Ethernet.10")
        $taggedName = "$nic.$($device.vlan)"
        $hasTagged = Get-NetAdapter -Name $taggedName -ErrorAction SilentlyContinue
        if (-not $hasTagged) {
            @{ nic = $nic; host_vlan = 0; unifi_vlan = $device.vlan }
        }
    }
}

# --- topology_ok ---
$GhostCount = @($GhostDevices).Count
$MatchCount = @($HostMacMatches | Where-Object { $_.status -eq "matched" }).Count
$TopologyOk = ($GhostCount -eq 0 -and $MatchCount -gt 0)

# --- Helpers to render JSON arrays without ConvertTo-Json depth issues ---
function To-JsonArray($items, [scriptblock]$itemRenderer) {
    if (-not $items -or @($items).Count -eq 0) { return "[]" }
    $parts = @($items) | ForEach-Object { & $itemRenderer $_ }
    return "[" + ($parts -join ",") + "]"
}

function Escape-Json([string]$s) {
    $s -replace '\\', '\\' -replace '"', '\"' `
       -replace "`n", '\n' -replace "`r", '\r' -replace "`t", '\t'
}

$ManagedDevicesJson = To-JsonArray $ManagedDevices {
    param($d)
    "{`"mac`":`"$(Escape-Json $d.mac)`",`"hostname`":`"$(Escape-Json $d.hostname)`",`"ip`":`"$(Escape-Json $d.ip)`",`"vlan`":$($d.vlan),`"port`":$($d.port),`"uplink_mbps`":$($d.uplink_mbps),`"type`":`"$(Escape-Json $d.type)`"}"
}

$HostMacMatchesJson = To-JsonArray $HostMacMatches {
    param($m)
    "{`"nic`":`"$(Escape-Json $m.nic)`",`"mac`":`"$(Escape-Json $m.mac)`",`"status`":`"$(Escape-Json $m.status)`"}"
}

$GhostDevicesJson = To-JsonArray $GhostDevices {
    param($g)
    "{`"mac`":`"$(Escape-Json $g.mac)`",`"hostname`":`"$(Escape-Json $g.hostname)`",`"note`":`"seen by Unifi, not on this host`"}"
}

$VlanMismatchesJson = To-JsonArray $VlanMismatches {
    param($v)
    "{`"nic`":`"$(Escape-Json $v.nic)`",`"host_vlan`":$($v.host_vlan),`"unifi_vlan`":$($v.unifi_vlan)}"
}

$TopologyOkJson = if ($TopologyOk) { "true" } else { "false" }

# --- Emit final JSON ---
Write-Output @"
{
  "controller_url": "$(Escape-Json $Controller)",
  "site": "$(Escape-Json $Site)",
  "api_version": "$ApiVersion",
  "managed_devices": $ManagedDevicesJson,
  "host_mac_matches": $HostMacMatchesJson,
  "ghost_devices": $GhostDevicesJson,
  "vlan_mismatches": $VlanMismatchesJson,
  "topology_ok": $TopologyOkJson,
  "error": null
}
"@
