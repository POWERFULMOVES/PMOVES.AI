# pm-cipher-token-bind.ps1 -- the Windows half of pm-cipher-token-bind.sh.
#
# WHY THIS FILE EXISTS. Windows enters claude-pmoves through
# deploy/provision/claude-pmoves.cmd -> claude-pmoves.ps1, which never reaches
# the bash fragment. Measured on Z890 2026-11-02 (stub-claude dry run of the
# real Windows path): the launcher resolved node=z890 identity=claude_z890 and
# then reported
#     cipher carry: mode=bootstrap card=yes writes-land-as=bootstrap
# because the session carried the node bootstrap bearer from env.shared, while
# the bash path on the same node bound the minted z890-claude token. Same node,
# same token store, different memory owner depending on which shell launched.
#
# It is a SIBLING of pm-cipher-token-bind.sh, as pm-python.ps1 is of
# pm-python.sh: the CONTRACT is mirrored, not the code. Read the bash header
# for the why of every rule; the rules are restated here only where PowerShell
# makes them easy to get wrong.
#
# THE CONTRACT
#   $r = Invoke-PmCipherTokenBind -Root <repo_root> -Agent <cipher agent_id>
#   $r.Ok    $true when the session now carries a cipher_ token
#   $r.Line  one line for the caller to print -- ALWAYS set, ALWAYS printed
# On success $env:CIPHER_API_TOKEN holds the per-agent bearer.
#
# TOKEN STORE: pmoves/.env.local, key CIPHER_TOKEN_<AGENT upper, '-' -> '_'>.
# A TARGETED read of exactly one key: never dot-sourced, never expanded.
#
# CASE-SENSITIVE on purpose. PowerShell's -match/-like ignore case and the
# bash `case` globs do not; `CIPHER_...` or `Cipher_` is not a minted bearer.
# Every comparison below is -c*.
#
# NEVER prints the bearer or any part of it past the `cipher_` prefix.

function Invoke-PmCipherTokenBind {
    param(
        [string]$Root,
        [string]$Agent
    )

    if (-not $Agent) {
        return [pscustomobject]@{ Ok = $false; Line = 'cipher token=unbound -- no declared cipher agentId for this harness on this node (nothing to bind; add an agentId to node-vocabulary.yaml and mint: make -C pmoves cipher-mint-token)' }
    }

    # Explicit operator/env token wins -- reported, not silently kept.
    if ("$env:CIPHER_API_TOKEN" -clike 'cipher_*') {
        return [pscustomobject]@{ Ok = $true; Line = 'cipher token=already per-agent (explicit CIPHER_API_TOKEN in env respected)' }
    }

    $key = 'CIPHER_TOKEN_' + $Agent.ToUpperInvariant().Replace('-', '_')
    $envf = Join-Path $Root 'pmoves\.env.local'
    if (-not (Test-Path -LiteralPath $envf -PathType Leaf)) {
        return [pscustomobject]@{ Ok = $false; Line = "cipher token=unbound -- $envf absent; create it and add $key=cipher_... (mint: make -C pmoves cipher-mint-token AGENT=$Agent)" }
    }

    # First line whose name (text before the first '=') is EXACTLY $key --
    # awk -F= '$1 == k' in the twin. Fixed-string compare, no regex.
    # A .NET exception is terminating whatever ErrorActionPreference says, so a
    # locked or unreadable file is caught here and degrades to the loud
    # 'unbound' line -- the twin's `awk ... 2>/dev/null || line=""`.
    try {
        $lines = [System.IO.File]::ReadAllLines($envf)
    } catch {
        return [pscustomobject]@{ Ok = $false; Line = "cipher token=unbound -- $envf unreadable ($($_.Exception.GetType().Name)); session keeps the bootstrap bearer" }
    }
    $tok = $null
    foreach ($line in $lines) {
        $eq = $line.IndexOf('=')
        if ($eq -lt 0) { continue }
        if ($line.Substring(0, $eq) -cne $key) { continue }
        $tok = $line.Substring($eq + 1)
        break
    }
    if ($null -ne $tok) {
        # Drop a trailing ` # comment` (whitespace THEN '#'; a bare '#' stays,
        # as compose reads it), trim, strip one layer of each quote kind, trim.
        $tok = [regex]::Replace($tok, '\s#.*$', '')
        $tok = $tok.Trim()
        if ($tok.StartsWith('"')) { $tok = $tok.Substring(1) }
        if ($tok.EndsWith('"'))   { $tok = $tok.Substring(0, $tok.Length - 1) }
        if ($tok.StartsWith("'")) { $tok = $tok.Substring(1) }
        if ($tok.EndsWith("'"))   { $tok = $tok.Substring(0, $tok.Length - 1) }
        $tok = $tok.Trim()
    }

    if (-not $tok) {
        return [pscustomobject]@{ Ok = $false; Line = "cipher token=unbound -- $key not in $envf (mint: make -C pmoves cipher-mint-token AGENT=$Agent)" }
    }
    # Shape: minted bearers are cipher_<uuid4 hex> (mint_cipher_token.py).
    if ($tok -cnotlike 'cipher_*') {
        return [pscustomobject]@{ Ok = $false; Line = "cipher token=unbound -- $key in $envf is not a cipher_-prefixed token (refusing to bind it)" }
    }
    if ($tok -cnotmatch '^cipher_[0-9A-Za-z-]+$') {
        return [pscustomobject]@{ Ok = $false; Line = "cipher token=unbound -- $key in $envf is not a well-formed cipher_<hex> token (refusing to bind it)" }
    }

    $env:CIPHER_API_TOKEN = $tok
    return [pscustomobject]@{ Ok = $true; Line = "cipher token=bound for $Agent ($key from pmoves/.env.local)" }
}
