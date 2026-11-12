# pm-ca-bundle.ps1 -- the Windows half of pm-ca-bundle.sh.
#
# WHY THIS FILE EXISTS. deploy/provision/claude-pmoves.sh normalizes host TLS
# before any python MCP server starts; claude-pmoves.ps1 never did. Measured on
# Z890 2026-11-02: SSL_CERT_FILE pointed at a miniconda path that no longer
# exists, the PowerShell launcher said nothing, and every python TLS client in
# the session (httpx/requests under the MCP servers) inherits a CA file it
# cannot open.
#
# CONTRACT (mirrors pm_ca_bundle_normalize):
#   $line = Invoke-PmCaBundleNormalize      # '' or one line to print
# Rules carried over unchanged:
#   * a CONFIGURED value is the operator's and is KEPT -- a broken one is
#     WARNED about by name, never silently replaced;
#   * nothing configured -> nothing exported, except as below.
#
# DELIBERATE DIFFERENCES from the POSIX twin, each because Windows differs:
#   1. No "clear the set-but-empty var" pass. A Windows process environment
#      cannot hold an empty value: assigning '' deletes the variable, so the
#      state that pass repairs cannot occur here.
#   2. Nothing configured -> NO bundle is exported. On Linux python's compiled
#      default may point at a path the distro does not have, so the twin hunts
#      for a bundle. On Windows python's ssl module and Node both load the OS
#      certificate store when no override is set; exporting a PEM file (e.g.
#      Git's mingw bundle) would REPLACE that store and drop any enterprise
#      root installed in it. Unset is the correct state here.

function Invoke-PmCaBundleNormalize {
    $vars = @('SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS')
    $configured = @($vars | Where-Object { [Environment]::GetEnvironmentVariable($_, 'Process') })
    if ($configured.Count -eq 0) {
        return ''
    }

    # Test-Path throws on characters illegal in a path ('<', '|', ...), and the
    # launcher runs with ErrorActionPreference=Stop. A value that cannot even be
    # probed is not a readable path: report it, never fail the launch.
    $isPath = {
        param($p, $type)
        try { return [bool](Test-Path -LiteralPath $p -PathType $type -ErrorAction Stop) } catch { return $false }
    }
    $broken = @()
    foreach ($v in @('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS')) {
        $p = [Environment]::GetEnvironmentVariable($v, 'Process')
        if ($p -and -not (& $isPath $p 'Leaf')) { $broken += "$v=$p" }
    }
    $d = $env:SSL_CERT_DIR
    if ($d -and -not (& $isPath $d 'Container')) { $broken += "SSL_CERT_DIR=$d" }

    if ($broken.Count -eq 0) { return '' }

    # Name the scope the value came from, so the remedy is one the operator can
    # act on: a User/Machine-scope variable survives every new terminal.
    $origin = @()
    foreach ($b in $broken) {
        $name = $b.Substring(0, $b.IndexOf('='))
        $scope = if ([Environment]::GetEnvironmentVariable($name, 'User')) { 'User' }
                 elseif ([Environment]::GetEnvironmentVariable($name, 'Machine')) { 'Machine' }
                 else { 'this shell' }
        $origin += "$name ($scope scope)"
    }
    return ("ca-bundle: WARN kept as configured but NOT a readable path: $($broken -join '; ') " +
            "-- python/Node TLS in this session will fail. Set from: $($origin -join ', '). " +
            "Remove it to use the Windows certificate store, e.g. " +
            "[Environment]::SetEnvironmentVariable('SSL_CERT_FILE', `$null, 'User'), then open a new terminal.")
}
