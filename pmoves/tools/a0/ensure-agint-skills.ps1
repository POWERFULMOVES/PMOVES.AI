# Ensures PMOVES-skills are provisioned into every local AGInTZ instance.
# Idempotent: installs a skill only when it is missing from an instance's usr/skills.
#
# Usage:
#   pmoves/tools/a0/ensure-agint-skills.ps1
#   pmoves/tools/a0/ensure-agint-skills.ps1 -AgentZeroRoot C:\Users\russe\agent-zero
#   pmoves/tools/a0/ensure-agint-skills.ps1 -SourcePath D:\other-skills -WhatIf
#
# Exit codes:
#   0  -- all skills present or installed (or WhatIf completed)
#   1  -- $SourcePath does not exist
#   2  -- copy failed
#
# REGRESSION NOTE: do not change `"usr\skills\" + $skill.Name` to
# `"usr\skills" + $skill.Name` -- the original v0 dropped the path separator
# and wrote skills into the wrong directory. Pinned by
# test_ensure_agint_skills_path_separator_regression in
# pmoves/tools/tests/test_a0_ensure_agint_skills.py.
param(
    [string]$AgentZeroRoot = "C:\Users\russe\agent-zero",
    [string]$SourcePath = "",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$src = if ($SourcePath) { $SourcePath } else { Join-Path $repoRoot "skills\PMOVES-skills\skills" }

if (-not (Test-Path $src)) {
    Write-Output "ERROR: skills source not found: $src"
    Write-Output "  hint: pass -SourcePath to override, or check the PMOVES-skills submodule is checked out at the expected commit."
    exit 1
}

$installed = 0
$skipped = 0
$failed = 0
$skills = Get-ChildItem $src -Directory

foreach ($skill in $skills) {
    Get-ChildItem $AgentZeroRoot -Directory | ForEach-Object {
        $inst = $_.FullName
        if (Test-Path (Join-Path $inst "usr\skills")) {
            # Pinned by test_ensure_agint_skills_path_separator_regression:
            # the trailing `\` in "usr\skills\" is load-bearing. Without it,
            # the destination path becomes "usr\skills<skill.Name>" instead
            # of "usr\skills\<skill.Name>", and the skill lands next to the
            # skills directory rather than inside it.
            $dst = Join-Path $inst ("usr\skills\" + $skill.Name)
            if (Test-Path $dst) {
                $script:skipped++
                return
            }
            if ($WhatIf) {
                Write-Output "whatif: would install $($skill.Name) -> $dst"
                $script:installed++
                return
            }
            try {
                Copy-Item -Recurse -Path $skill.FullName -Destination $dst -ErrorAction Stop
                Write-Output "installed $($skill.Name) -> $dst"
                $script:installed++
            } catch {
                Write-Output "FAIL: $($skill.Name) -> $dst :: $($_.Exception.Message)"
                $script:failed++
            }
        }
    }
}

Write-Output "done: installed=$installed skipped=$skipped failed=$failed"
if ($failed -gt 0) { exit 2 }
exit 0
