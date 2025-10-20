param(
  [Parameter(Mandatory=$true)][ValidateSet('wger','firefly','open-notebook','jellyfin')] [string]$Kit,
  [Parameter(Mandatory=$true)][string]$Repo
)

$Root = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$KitDir = Join-Path $Root "pmoves/integrations/pr-kits/$Kit"

if (!(Test-Path $KitDir)) { Write-Error "Kit not found: $KitDir"; exit 1 }
if (!(Test-Path $Repo))   { Write-Error "Repo path not found: $Repo"; exit 1 }

Write-Host "→ Applying PR kit '$Kit' to repo: $Repo" -ForegroundColor Cyan

# Copy files
Copy-Item -Recurse -Force (Join-Path $KitDir '*') $Repo

# Ensure git repo
pushd $Repo
try {
  git rev-parse --is-inside-work-tree *> $null
} catch { Write-Error "Not a git repo: $Repo"; exit 1 }

$branch = 'chore/pmoves-net+ghcr'
git checkout -B $branch
git add .github docker-compose.pmoves-net.yml README_PRSUMMARY.md 2>$null
git commit -m "chore: add pmoves-net compose and GHCR publish workflow"
Write-Host "✔ PR kit applied. Next: push and open a PR" -ForegroundColor Green
Write-Host "   git push -u origin $branch"
popd

