# mavis_sdk_env.ps1 - Mavis SDK env-strip helper, sourced by every PMOVES
# PowerShell launcher (claude-pmoves.ps1 and any generated *.ps1 wrapper).
#
# ===========================================================================
# WHY THIS FILE EXISTS (PowerShell twin of pmoves/scripts/mavis_sdk_env.sh)
# ===========================================================================
#
# The Mavis SDK puts env vars in the process environment via the `env`
# block of ~/.claude/settings.json (ANTHROPIC_BASE_URL,
# ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, MCP_TIMEOUT, API_TIMEOUT_MS,
# CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC, ...).  Every PMOVES launcher
# inherits those vars from the parent process.  Without this scrub, every
# downstream CLI (claude, kilo, codex, kimi, hermes, pmoves-mini) starts
# with Mavis's provider config baked in - claude-pmoves talks to
# api.minimax.io instead of the operator's intended Anthropic endpoint,
# kilo-pmoves gets an ANTHROPIC_BASE_URL it does not understand, etc.
#
# The operator's framing ("claude-pmoves to load the claude-code settings")
# is the load-bearing requirement.  The check is a NEED check against the
# SDK: for each Mavis SDK var in the shell env, ask "does this CLI
# consume it?".  If yes, leave it.  If no, preserve its value under
# `PMOVES_MAVIS_SDK_<NAME>` and unset it, then WARN the operator what was
# caught.
#
# ===========================================================================
# WHY A REGISTRY, NOT A BLANKET BLOCKLIST
# ===========================================================================
#
# Same rationale as the bash twin (pmoves/scripts/mavis_sdk_env.sh).
# Per-CLI needs list is the registry that makes "consider every CLI when
# adding a new var" a single-place change.
#
# ===========================================================================
# WHY THE TWO TWINS MUST STAY IN STEP
# ===========================================================================
#
# The bash + PowerShell twins MUST encode the same registry.  Drift here
# was the bug the bash blocklist `CLAUDE_CODE_` (literal, anchored)
# vs the PowerShell blocklist `CLAUDE_CODE_*` (regex match) had been
# shipping - one platform stripped vars the other did not.  Same fix in
# both places: a NEEDS list keyed by `pmoves/configs/cli_tools.yaml` CLI
# name, with `["*"]` for the wildcard (pmoves-mini consumes everything).
#
# Tests:
#   bash:    pmoves/tests/test_mavis_sdk_env.sh  (34 assertions)
#   python:  pmoves/tests/test_mavis_sdk_env.py  (subprocess wrapper)
#   ps1:     pmoves/tests/test_mavis_sdk_env.ps1 (TODO; mirror)
#
# ===========================================================================
# USAGE
# ===========================================================================
#
#   . pmoves/scripts/mavis_sdk_env.ps1
#   Strip-MavisSdkEnvFor -CliName "claude"
#   # ... downstream CLI inherits the scrubbed env.
#
# After the call:
#   $env:PMOVES_MAVIS_SDK_STRIPPED       - newline-separated stripped names
#   $env:PMOVES_MAVIS_SDK_CLI            - the CLI name passed in
#   $env:PMOVES_MAVIS_SDK_<NAME>         - preserved value of every stripped var

# ---------------------------------------------------------------------------
# Registry: Mavis SDK env vars (the env block of ~/.claude/settings.json).
# Add a NEW Mavis SDK env var HERE, then verify every entry in the per-CLI
# needs list explicitly handles it (either listed or omitted).  Leaving
# the per-CLI decision implicit means a new var silently passes through
# to every CLI - the exact leak this file exists to prevent.
# ---------------------------------------------------------------------------
$script:MAVIS_SDK_ENV_NAMES = @(
    # Billing / provider routing (force a specific API host + token)
    'ANTHROPIC_API_KEY'
    'ANTHROPIC_AUTH_TOKEN'
    'ANTHROPIC_BASE_URL'
    # Model picker forcing (forces claude --model to a specific variant)
    'ANTHROPIC_MODEL'
    'ANTHROPIC_DEFAULT_SONNET_MODEL'
    'ANTHROPIC_DEFAULT_OPUS_MODEL'
    'ANTHROPIC_DEFAULT_HAIKU_MODEL'
    # PMOVES-internal runtime config (not part of Claude Code or kilo)
    'API_TIMEOUT_MS'
    'MCP_TIMEOUT'
    # Claude Code session / telemetry (NOT consumed by kilo/codex/kimi/hermes)
    'CLAUDECODE'
    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'
    'CLAUDE_CODE_AUTO_COMPACT_WINDOW'
    # Glob patterns - matched via -like against the live env
    'CLAUDE_CODE_*'
    'CLAUDE_SESSION_*'
)

# ---------------------------------------------------------------------------
# Per-CLI needs registry.
# Keys MUST match pmoves/configs/cli_tools.yaml CLI names.  A new CLI in
# cli_tools.yaml that is absent from this dict falls through the "no
# entry" branch, which behaves as needs=[] (strip everything).  That is
# the SAFE default for a new CLI - the alternative (silently inherit
# Mavis config) is the bug this file exists to prevent.
# Special value @('*') means "consume every Mavis SDK var" - reserved for
# PMOVES-internal CLIs that ARE the Mavis agent (pmoves-mini).
# ---------------------------------------------------------------------------
$script:MAVIS_SDK_NEEDS_BY_TOOL = @{
    claude      = @('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY')
    kilo        = @()
    codex       = @()
    kimi        = @()
    hermes      = @()
    crush       = @()
    'pmoves-mini' = @('*')
}

# ---------------------------------------------------------------------------
# Get-MavisSdkNeedsFor <cli_name>
# Returns the needs list for a CLI as a string[] (each element on its own).
# Returns @() for an unknown CLI (which behaves as needs=[], stripping
# everything - the safe default).
# ---------------------------------------------------------------------------
function Get-MavisSdkNeedsFor {
    param([Parameter(Mandatory)][string]$CliName)
    if ($script:MAVIS_SDK_NEEDS_BY_TOOL.ContainsKey($CliName)) {
        return , $script:MAVIS_SDK_NEEDS_BY_TOOL[$CliName]
    }
    return , @()
}

# ---------------------------------------------------------------------------
# Strip-MavisSdkEnvFor -CliName <name>
#
# The load-bearing call.  For each Mavis SDK var in the SHELL env:
#   - if the var's value matches a NEED for this CLI, leave it
#   - else preserve it under PMOVES_MAVIS_SDK_<NAME> and unset the original
#   - record the stripped names in $env:PMOVES_MAVIS_SDK_STRIPPED
#   - emit ONE WARN line summarizing what was caught, on the error stream
#
# Glob patterns in MAVIS_SDK_ENV_NAMES (e.g. CLAUDE_CODE_*) are matched via
# -like against every env var name.  A match under a glob pattern uses the
# same preserve+unset path.
#
# Special case: needs=@('*') (used by pmoves-mini) means strip NOTHING.
# This is the Mavis agent itself - it consumes the full Mavis SDK env by
# design.
# ---------------------------------------------------------------------------
function Strip-MavisSdkEnvFor {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$CliName
    )

    $needs = Get-MavisSdkNeedsFor -CliName $CliName
    $allPass = ($needs.Count -eq 1 -and $needs[0] -eq '*')

    $stripped = New-Object System.Collections.Generic.List[string]
    $preservedNames = New-Object System.Collections.Generic.List[string]

    # Snapshot of every env var name at call time.  We cannot enumerate
    # PowerShell env vars via the public surface, so we read the live
    # registry through Environment.GetEnvironmentVariables() which gives us
    # a Hashtable of name -> value.
    $liveEnv = [System.Environment]::GetEnvironmentVariables()
    foreach ($name in @($liveEnv.Keys)) {
        $matched = $false
        foreach ($pat in $script:MAVIS_SDK_ENV_NAMES) {
            if ($pat -like '*\**') {
                # Glob pattern; -like uses * as wildcard, matches $name.
                if ($name -like $pat) { $matched = $true; break }
            } else {
                if ($name -ceq $pat) { $matched = $true; break }
            }
        }
        if (-not $matched) { continue }
        if ($allPass) { continue }   # pmoves-mini: consume everything

        $needed = $false
        foreach ($n in $needs) {
            if ($name -ceq $n) { $needed = $true; break }
        }
        if ($needed) { continue }

        # Preserve + unset.
        $value = [System.Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrEmpty($value)) {
            [System.Environment]::SetEnvironmentVariable(
                "PMOVES_MAVIS_SDK_$name", $value)
        }
        [System.Environment]::SetEnvironmentVariable($name, $null)
        $stripped.Add($name)
        if (-not [string]::IsNullOrEmpty($value)) { $preservedNames.Add($name) }
    }

    # Export the stripped list for downstream introspection.
    if ($stripped.Count -gt 0) {
        [System.Environment]::SetEnvironmentVariable(
            'PMOVES_MAVIS_SDK_STRIPPED',
            ($stripped -join "`n"))
        Write-Warning ("[mavis-sdk] stripped {0} Mavis SDK vars from {1} env: {2}" -f $stripped.Count, $CliName, ($stripped -join ' '))
        Write-Warning "[mavis-sdk]   preserved under PMOVES_MAVIS_SDK_<NAME>; original vars unset."
    } else {
        [System.Environment]::SetEnvironmentVariable('PMOVES_MAVIS_SDK_STRIPPED', $null)
    }
    [System.Environment]::SetEnvironmentVariable('PMOVES_MAVIS_SDK_CLI', $CliName)
}
