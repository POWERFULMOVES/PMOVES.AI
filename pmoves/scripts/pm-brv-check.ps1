# pm-brv-check.ps1 -- the Windows half of pm-brv-check.sh.
#
# The POSIX launcher tells the session when the ByteRover CLI (brv) is absent,
# so the model says "no context-tree memory this session" instead of reporting
# an empty tree. claude-pmoves.ps1 never checked, so a Windows session could
# not tell "nothing curated yet" from "the tool is not installed".
#
# CONTRACT (mirrors pm_brv_check; never fails the launch):
#   $r = Invoke-PmBrvCheck
#   $r.Ok      $true when brv resolves on PATH (npm's brv.cmd/brv.ps1 count)
#   $r.Line    one line for the caller to print
#   $r.Prompt  '' or a sentence to append to the session's system prompt

$script:PmBrvInstallHint = 'npm install -g byterover-cli'

function Invoke-PmBrvCheck {
    $cmd = Get-Command brv -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) {
        return [pscustomobject]@{ Ok = $true; Line = "brv=present ($($cmd.Source))"; Prompt = '' }
    }
    return [pscustomobject]@{
        Ok     = $false
        Line   = "WARN: brv=MISSING -- ByteRover CLI not on PATH, so this session has NO context-tree memory (brv-query/brv-curate). Install (user-level, no admin): $script:PmBrvInstallHint  then: make -C pmoves cli-check"
        Prompt = "The ByteRover CLI (brv) is NOT installed on this node, so context-tree memory (brv-query / brv-curate) is unavailable this session. Say so at session start rather than reporting an empty tree. Install route: $script:PmBrvInstallHint (user-level npm global, no admin)."
    }
}
