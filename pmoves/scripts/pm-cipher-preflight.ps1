# pm-cipher-preflight.ps1 -- the Windows half of the cipher_preflight block in
# pmoves/scripts/claude-pmoves.sh.
#
# WHY THIS FILE EXISTS. claude-pmoves.sh runs pmoves/tools/cipher_preflight.py
# on every launch and tells the session, in its prompt, whether persistent
# memory is usable -- and, when it is not, WHICH failure it is, so the model
# neither reports a refused credential as an outage nor asks for a re-mint on a
# 503. claude-pmoves.ps1 never ran it (measured 2026-11-04: no reference to
# cipher_preflight anywhere in the file), so a Windows session was told nothing
# and had to rediscover cipher's state by trial.
#
# CONTRACT (mirrors the .sh case on the tool's exit code; never fails the launch):
#   $cp = Invoke-PmCipherPreflight -Root <repo root> -Py <python argv prefix>
#                  [-Roster <the roster claude is handed>]   -- probe what the
#                  session will actually get, not the working tree's default
#                  (Codex #3454 P2: a branch that changes the cipher entries
#                  would otherwise be judged against servers it does not load)
#   $cp.Verdict  up | unauthorized | unusable | down | skipped
#   $cp.Line     one line for the caller to print
#   $cp.Prompt   the sentence for the session prompt ('' when skipped)
#   $cp.Output   the tool's stdout, for the caller to echo on a non-up verdict
#
# Exit codes (cipher_preflight.py): 0 a usable endpoint; 1 something answered,
# not usably -- 'cipher UNAUTHORIZED' on stdout narrows it; anything else
# (3, a crash, python absent) is DOWN, the only case where "no memory" is true.
#
# Prompt texts are the .sh's, word for word: the model reads the same
# sentence whichever shell launched it. Keep them in step.

function Invoke-PmCipherPreflight {
    param(
        [string]$Root,
        [string[]]$Py = @(),
        [string]$Roster = ''
    )
    $tool = Join-Path (Join-Path (Join-Path $Root 'pmoves') 'tools') 'cipher_preflight.py'
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf) -or $Py.Count -eq 0) {
        return [pscustomobject]@{ Verdict = 'skipped'; Line = "cipher=unchecked (no $tool or no python)"; Prompt = ''; Output = '' }
    }
    $since = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $recovery = 'Recovery: pmoves/docs/operations/MCP_TOOLKIT.md.'

    # stdout AND stderr, as the .sh's 2>&1: only the `cipher OK` row rides
    # stdout; `cipher UNAUTHORIZED` and every other non-OK row go to STDERR
    # (cipher_preflight.py), so a stdout-only capture turned a real 401 into
    # 'unusable' -- telling the model NOT to suspect a credential that was
    # refused (Kilo #3454). Under Windows PowerShell 5.1 a 2>&1 on a native
    # command makes each stderr line an ErrorRecord, terminating ONLY under
    # EAP=Stop -- hence Continue for this call, and the records turned back
    # into their text.
    $out = ''
    $rc = 3
    $eap = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $pyArgs = @(if ($Py.Count -gt 1) { $Py[1..($Py.Count - 1)] }) + @($tool)
        if ($Roster) { $pyArgs += @('--roster', $Roster) }
        $out = (& $Py[0] @pyArgs 2>&1 | ForEach-Object {
                if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
            } | Out-String)
        $rc = $LASTEXITCODE
    } catch {
        $out = "cipher_preflight did not run: $($_.Exception.Message)"
        $rc = 3
    } finally {
        $ErrorActionPreference = $eap
    }
    if ($null -eq $rc) { $rc = 3 }

    if ($rc -eq 0) {
        $which = 'unknown'
        foreach ($l in ($out -split "`r?`n")) {
            $f = @($l.Trim() -split '\s+')
            if ($f.Count -ge 3 -and $f[0] -ceq 'cipher' -and $f[1] -ceq 'OK') { $which = $f[2]; break }
        }
        return [pscustomobject]@{
            Verdict = 'up'; Output = $out
            Line    = "cipher=up ($which)"
            Prompt  = "Persistent memory IS available this session via the Cipher MCP server '" + $which + "'. Use it for recall and for writes; do not fall back to the auto-memory directory while it is up."
        }
    }
    if ($rc -eq 1 -and $out -clike '*cipher UNAUTHORIZED*') {
        return [pscustomobject]@{
            Verdict = 'unauthorized'; Output = $out
            Line    = 'cipher=UNAUTHORIZED (exit 1) -- service is UP, credential not accepted'
            Prompt  = 'Cipher ANSWERED this session but refused the credential (preflight exit 1, verdict unauthorized), so persistent memory is not usable right now. The service is UP -- this is an access problem, not an outage, so do NOT report Cipher as down. A 401 is NOT proof the token is revoked: a Cipher shim older than the lookup-failure fix also answers 401 when its OWN Supabase service key is missing or refused or its lookup times out, and every agent on the node then fails at once. Before asking for a re-mint, check `docker logs --since ' + $since + ' pmoves-cipher-api-1 2>&1 | grep pmoves-auth` -- any hit means the token was never judged and the fix is the backend, not the token. Use the file-based auto-memory directory meanwhile and say which of the two it is. Remedy when the token itself is wrong: bind CIPHER_API_TOKEN into the roster. ' + $recovery
        }
    }
    if ($rc -eq 1) {
        return [pscustomobject]@{
            Verdict = 'unusable'; Output = $out
            Line    = 'cipher=ANSWERED-UNUSABLE (exit 1) -- something is listening; see the status below'
            Prompt  = 'Cipher ANSWERED this session but not usably (preflight exit 1, and NOT a 401/403 -- read the status printed above, e.g. an HTTP error or a refused redirect), so persistent memory is not usable right now. Something IS listening on that endpoint, so do NOT report Cipher as simply down, and do NOT assume the credential is at fault -- the preflight would have said unauthorized if it were. An HTTP 503 in particular means the token was not judged (a proxy, Kong, startup, or after the fork fix a lookup backend failure), so do not ask for a re-mint. Use the file-based auto-memory directory meanwhile and say which of the two it is. ' + $recovery
        }
    }
    return [pscustomobject]@{
        Verdict = 'down'; Output = $out
        Line    = "cipher=DOWN (exit $rc) -- session has no persistent memory"
        Prompt  = "Cipher is NOT reachable this session (preflight exit $rc), so you have NO persistent memory. Say so at session start rather than recalling nothing silently, and use the file-based auto-memory directory instead. $recovery"
    }
}
