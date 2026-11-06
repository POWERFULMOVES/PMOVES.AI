# Ensures PMOVES-skills are provisioned into every local AGInTZ instance.
# Idempotent: installs a skill only when it is missing from an instance's usr/skills.
# Usage: pmoves/tools/a0/ensure-agint-skills.ps1 [-AgentZeroRoot C:\Users\russe\agent-zero]
param(
    [string]$AgentZeroRoot = "C:\Users\russe\agent-zero"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$src = Join-Path $repoRoot "skills\PMOVES-skills\skills"

if (-not (Test-Path $src)) {
    Write-Output "ERROR: skills source not found: $src"
    exit 1
}

$installed = 0
$skills = Get-ChildItem $src -Directory

foreach ($skill in $skills) {
    Get-ChildItem $AgentZeroRoot -Directory | ForEach-Object {
        $inst = $_.FullName
        if (Test-Path (Join-Path $inst "usr\skills")) {
            $dst = Join-Path $inst ("usr\skills" + $skill.Name)
            if (-not (Test-Path $dst)) {
                Copy-Item -Recurse -Path $skill.FullName -Destination $dst
                Write-Output "installed $($skill.Name) -> $inst"
                $script:installed++
            }
        }
    }
}

Write-Output "done: $installed skill(s) provisioned"
