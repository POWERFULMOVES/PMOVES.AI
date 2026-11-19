# pm-python.ps1 -- the ONE python discovery on Windows, sourced by every
# GENERATED PMOVES launcher that needs an interpreter.
#
# WHY THIS FILE EXISTS. pmoves/scripts/pm-python.sh is the POSIX half of the
# single python-discovery convention. It had no Windows counterpart: the only
# working Windows implementation lived INSIDE the hand-written
# deploy/provision/claude-pmoves.ps1, so a GENERATED launcher had no way to
# discover an interpreter without re-implementing the ladder -- which is
# exactly the "three conventions for the same question" disease that
# pm-python.sh's own header documents as the reason it exists.
#
# It is a SIBLING of pm-python.sh, not a replacement:
#   * pm-python.sh   -- POSIX half: `pm_pick_python [probe]` sets PM_PY
#   * pm-python.ps1  -- Windows half: `Get-PmovesPythonArgv -Root <r> [-Probe <mod>]`
# The rung SET is identical (operator pin -> canonical venv -> platform
# launchers). The ORDER of the last two differs on purpose and follows the
# order claude-pmoves.ps1 established: `py -3` before `python3`, because on
# Windows `python3` is the Microsoft Store app-execution alias while `py` is
# the real launcher that ships with every python.org install. Both are
# PROBED, so the order changes noise, not the outcome.
#
# PRESENCE IS NOT RUNNABILITY. On a stock Windows 10/11 node BOTH `python` and
# `python3` resolve to the Store alias in %LOCALAPPDATA%\Microsoft\WindowsApps.
# Get-Command SUCCEEDS on that alias, so a discovery that only asks "does the
# command exist?" accepts a stub that answers "Python was not found; run
# without arguments to install from the Microsoft Store" and exits non-zero.
# Every candidate here is RUN before it is accepted -- exactly as
# pm-python.sh does.
#
# THE CONTRACT: a non-null return means the argv vector holds something the
# caller can RUN. Not "PMOVES_PYTHON was non-empty", not "a candidate
# existed" -- runnable. It is the same sentence pm-python.sh's pm_pick_python
# owes its callers, and the same sentence claude-pmoves.ps1's copy owes.
#
# Usage:
#   . pmoves/scripts/pm-python.ps1
#   $py = Get-PmovesPythonArgv -Root $root
#   if ($py) {
#       $pre = @(if ($py.Count -gt 1) { $py[1..($py.Count - 1)] })
#       & $py[0] @pre script.py
#   }
#   # require PyYAML (mcp_config_generator.py reads the MiniMax YAML profile):
#   $py = Get-PmovesPythonArgv -Root $root -Probe 'yaml'
#
# PMOVES_PYTHON (space-separated override) always wins, for operator pinning.
#
# Windows PowerShell 5.1 compatible: no ternary operators, no `??`, no
# `-ErrorAction` on a native call that 5.1 cannot honour.

function Test-PmovesPythonRuns {
    <#
      Runs `<argv> -c 'pass'` -- a no-op for any real interpreter, non-zero for
      anything that is not one. This is what rejects the Microsoft Store stub.

      pm-python.sh probes with `-c ''`. An EMPTY argument is not safely
      passable to a native command from Windows PowerShell 5.1 (it can be
      dropped, which would turn the probe into `python -c` and reject a GOOD
      interpreter -- the same class of silent misjudgement this whole file
      exists to prevent), so the no-op is spelled `pass`. Same semantics, no
      quoting hazard.

      With -Probe <module> the probe becomes `import <module>`, matching
      pm-python.sh's `pm_pick_python yaml` branch.
    #>
    param(
        [string[]]$Argv,
        [string]$Probe
    )
    # Function-scoped: a candidate that is not an interpreter is EXPECTED to
    # fail, and under the caller's 'Stop' preference that failure (or a native
    # non-zero exit, under $PSNativeCommandUseErrorActionPreference on PS 7.4+)
    # would terminate the launcher instead of advancing the ladder.
    $ErrorActionPreference = 'SilentlyContinue'
    $PSNativeCommandUseErrorActionPreference = $false
    if (-not $Argv -or $Argv.Count -eq 0) { return $false }
    $exe  = $Argv[0]
    # @(...) is load-bearing: a one-element slice is a bare STRING, and splatting
    # a string passes its characters -- `py -3` became `py - 3`, and a lone `-`
    # makes python run a script read from STDIN (#3356).
    $rest = @(if ($Argv.Count -gt 1) { $Argv[1..($Argv.Count - 1)] })
    $code = if ($Probe) { "import $Probe" } else { 'pass' }
    $global:LASTEXITCODE = 1
    try { & $exe @rest -c $code *> $null } catch { return $false }
    return ($LASTEXITCODE -eq 0)
}

function Get-PmovesPythonArgv {
    <#
      Returns a string[] argv vector for a python that RUNS, or $null.
      Same rung set as pm-python.sh; `py -3` is tried before `python3` because
      on Windows `python3` is the Store alias and `py` is the real launcher.
    #>
    param(
        [Parameter(Mandatory)][string]$Root,
        [string]$Probe
    )

    # 0. Operator pin always wins. Space-separated so multi-word vectors like
    #    `py -3` work, but a path is tried VERBATIM first: the Windows default
    #    install path is C:\Program Files\Python313\python.exe, and splitting
    #    that on whitespace would make the pin the launcher advertises as its
    #    own remedy fail on the platform's default layout.
    if ($env:PMOVES_PYTHON) {
        $verbatim = $env:PMOVES_PYTHON.Trim()
        if ($verbatim -and (Test-Path -LiteralPath $verbatim -PathType Leaf) -and
            (Test-PmovesPythonRuns -Argv @($verbatim) -Probe $Probe)) {
            return , @($verbatim)
        }
        $pin = @($env:PMOVES_PYTHON -split '\s+' | Where-Object { $_ -ne '' })
        if ($pin.Count -gt 0 -and (Test-PmovesPythonRuns -Argv $pin -Probe $Probe)) {
            return , $pin
        }
        # An explicit pin that does not run is an ERROR, not a hint. Falling
        # through to a guess is how `PMOVES_PYTHON=" "` became "python3 is
        # missing" on the POSIX side.
        return $null
    }

    # 1. The canonical venv -- what `make -C pmoves preflight` provisions, and
    #    therefore what the refusal below is allowed to name as a remedy.
    foreach ($c in @(
            (Join-Path $Root 'pmoves\.venv-pmoves\Scripts\python.exe'),
            (Join-Path $Root 'pmoves\.venv-pmoves\bin\python'))) {
        if ((Test-Path -LiteralPath $c -PathType Leaf) -and
            (Test-PmovesPythonRuns -Argv @($c) -Probe $Probe)) {
            return , @($c)
        }
    }

    # 2. Platform launchers. Written out rather than looped for the same reason
    #    pm-python.sh writes its branches out: `py -3` is two words and
    #    `python3` is one, and no array-flattening rule should be load-bearing
    #    in the code that decides whether this node can start a session.
    if (Test-PmovesPythonRuns -Argv @('py', '-3') -Probe $Probe) { return , @('py', '-3') }
    if (Test-PmovesPythonRuns -Argv @('python3') -Probe $Probe)  { return , @('python3') }
    if (Test-PmovesPythonRuns -Argv @('python') -Probe $Probe)   { return , @('python') }
    return $null
}
