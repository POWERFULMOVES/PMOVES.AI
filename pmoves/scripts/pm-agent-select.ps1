# pm-agent-select.ps1 -- agent selection for claude-pmoves.ps1, the Windows half
# of the block in pmoves/scripts/claude-pmoves.sh that reads $1 and
# PMOVES_DEFAULT_AGENT.
#
# WHY THIS FILE EXISTS. Until 2026-11-04 this rule lived in the installed shim,
# pmoves/scripts/windows/claude-pmoves.bat, which ALSO resolved the node
# identity and composed its own identity prompt before calling
# claude-pmoves.cmd -> claude-pmoves.ps1, which did both again. Measured on Z890
# with a stub claude: identity resolved twice, and claude received TWO
# --append-system-prompt blocks, only one of which carried the cipher carry.
# The shim is now a pure delegate; the one rule it owned moved here.
#
# CONTRACT (mirrors claude-pmoves.sh; never fails the launch):
#   $sel = Resolve-PmAgentArgs -Root <repo root> -Argv <launcher args> [-Positional]
#   $sel.Argv   args for claude: '--agent <name>' + the rest, or the rest alone
#   $sel.Role   the agent name, or $null for the default no-agent session
#   $sel.Lines  zero or more lines for the caller to Write-Warning
#
# RULES, in the .sh's order:
#   1. PMOVES_DEFAULT_AGENT naming no .claude/agents/<name>.md -> no default, loudly.
#   2. -Positional only: a leading NON-flag arg is an agent name. Defined ->
#      `--agent <name>`. Undefined -> DROPPED (not forwarded), loudly, and the
#      session runs with NO agent -- not the default; the .sh sets AGENT="" here.
#      ONLY the claude-pmoves shim promises that shorthand, so only the shim
#      asks for it (PMOVES_AGENT_POSITIONAL=1). Direct entry points -- the .ps1,
#      claude-pmoves.cmd, the per-node claude-pmoves-<node>.cmd wrappers -- have
#      always forwarded a leading positional as claude's PROMPT; treating
#      `"fix X"` as an agent name there would silently drop it (Codex #3454 P1).
#   3. Otherwise the default applies -- unless the caller already passed
#      --agent, which the .sh never sees because its shim cannot be bypassed.
#      Two --agent flags would be a claude error. A dangling `--agent` with no
#      value is the caller's malformed flag: forwarded untouched, no default
#      added (Kilo #3454).
#
# A name is only looked up if it is a plain file stem. `..\..\x` or a name with
# characters illegal in a path is treated as undefined, never probed.

function Test-PmAgentDefined {
    param([string]$Root, [string]$Name)
    if ("$Name" -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { return $false }
    $md = Join-Path (Join-Path (Join-Path $Root '.claude') 'agents') "$Name.md"
    try { return [bool](Test-Path -LiteralPath $md -PathType Leaf -ErrorAction Stop) } catch { return $false }
}

function Resolve-PmAgentArgs {
    param(
        [string]$Root,
        [string[]]$Argv = @(),
        [switch]$Positional
    )
    $lines = @()
    $argvIn = @($Argv | Where-Object { $null -ne $_ })

    $default = "$env:PMOVES_DEFAULT_AGENT"
    if ($default -and -not (Test-PmAgentDefined -Root $Root -Name $default)) {
        $lines += "[claude-pmoves] PMOVES_DEFAULT_AGENT='$default' has no .claude/agents/$default.md -- launching as the node identity with no --agent"
        $default = ''
    }

    if ($Positional -and $argvIn.Count -gt 0 -and -not "$($argvIn[0])".StartsWith('-')) {
        $name = "$($argvIn[0])"
        $rest = @(if ($argvIn.Count -gt 1) { $argvIn[1..($argvIn.Count - 1)] })
        if (Test-PmAgentDefined -Root $Root -Name $name) {
            return [pscustomobject]@{ Argv = @('--agent', $name) + $rest; Role = $name; Lines = $lines }
        }
        $lines += "[claude-pmoves] agent '$name' has no .claude/agents/$name.md -- dropped; launching as the node identity with no --agent"
        return [pscustomobject]@{ Argv = $rest; Role = $null; Lines = $lines }
    }

    # An explicit --agent from the caller is theirs; read it back for the prompt.
    # Scan through the LAST element: a trailing `--agent` is still the caller's.
    for ($i = 0; $i -lt $argvIn.Count; $i++) {
        if ($argvIn[$i] -ceq '--agent') {
            $val = if ($i + 1 -lt $argvIn.Count) { "$($argvIn[$i + 1])" } else { '' }
            $role = if ($val -and -not $val.StartsWith('-')) { $val } else { $null }
            return [pscustomobject]@{ Argv = $argvIn; Role = $role; Lines = $lines }
        }
    }
    if ($default) {
        return [pscustomobject]@{ Argv = @('--agent', $default) + $argvIn; Role = $default; Lines = $lines }
    }
    return [pscustomobject]@{ Argv = $argvIn; Role = $null; Lines = $lines }
}
