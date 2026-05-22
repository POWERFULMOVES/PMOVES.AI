# Daily PMOVES digest: worktree sitrep + open PR snapshot to Discord.
# Run via Windows Task Scheduler; expects $Env:DISCORD_WEBHOOK_URL set in the task's env.
# Pairs with the cloud routine `PMOVES Daily PR Audit` -- this one covers what the cloud agent can't see:
# local worktree state, uncommitted work, branch divergence.

Param(
  [string]$RepoRoot = "D:\PMOVES.AI\PMOVES.AI",
  [string]$LogDir   = "D:\PMOVES.AI\PMOVES.AI\pmoves\logs",
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$logFile = Join-Path $LogDir ("daily_digest_" + (Get-Date -Format 'yyyy-MM-dd') + ".log")
Start-Transcript -Path $logFile -Force | Out-Null

function Section($title) { "`n### $title`n" }

# --- Worktree sitrep (replaces the unimplemented `make worktree-sitrep-strict`) ---
$wtRaw = (& git worktree list --porcelain 2>$null) -join "`n"
$wtBlocks = $wtRaw -split "(?m)^\s*$" | Where-Object { $_.Trim() -ne '' }

$wtRows = @()
foreach ($block in $wtBlocks) {
  $path = $null; $branch = $null
  foreach ($line in ($block -split "`r?`n")) {
    if ($line -match '^worktree (.+)$')         { $path = $matches[1].Trim() }
    elseif ($line -match '^branch refs/heads/(.+)$') { $branch = $matches[1].Trim() }
  }
  if (-not $path) { continue }
  if (-not (Test-Path $path)) { continue }

  Push-Location $path
  $status = & git status --porcelain 2>$null
  $dirty  = if ($status) { (@($status -split "`r?`n" | Where-Object { $_ -ne '' })).Count } else { 0 }
  $ahead  = 0; $behind = 0
  # Parse ahead/behind from `git status -b --porcelain` (avoids `@{upstream}` arg-passing quirks)
  $sb = (& git status -b --porcelain 2>$null) | Select-Object -First 1
  if ($sb -and ($sb -match 'ahead (\d+)'))  { $ahead  = [int]$matches[1] }
  if ($sb -and ($sb -match 'behind (\d+)')) { $behind = [int]$matches[1] }
  $LASTEXITCODE = 0
  Pop-Location

  $wtRows += [PSCustomObject]@{
    Path   = $path.Replace($RepoRoot, '.')
    Branch = if ($branch) { $branch } else { '(detached)' }
    Dirty  = $dirty
    Ahead  = $ahead
    Behind = $behind
  }
}

$dirtyCount = ($wtRows | Where-Object { $_.Dirty -gt 0 }).Count
$wtSummary  = "$($wtRows.Count) worktrees, $dirtyCount dirty"

# --- Open PR snapshot (light -- cloud routine has the full audit) ---
$prSummary = "gh unavailable"
$urgentCount = 0
try {
  $prs = & gh pr list --repo POWERFULMOVES/PMOVES.AI --state open --limit 200 --json number,title,labels,isDraft,updatedAt 2>$null | ConvertFrom-Json
  if ($prs) {
    $now = Get-Date
    $stale = $prs | Where-Object { ($now - [DateTime]$_.updatedAt).TotalDays -gt 7 }
    $urgent = $prs | Where-Object {
      ($_.labels | Where-Object { $_.name -in @('unfcu','security','incident','production') }) -or
      ($_.title -match 'UNFCU')
    }
    $urgentCount = $urgent.Count
    $prSummary = "$($prs.Count) open / $urgentCount urgent / $($stale.Count) stale (>7d) / $(($prs | Where-Object {$_.isDraft}).Count) draft"
  }
} catch { $prSummary = "gh error: $($_.Exception.Message)" }

# --- Build Discord message (2000 char limit) ---
$header = "**PMOVES Daily Digest - $(Get-Date -Format 'yyyy-MM-dd HH:mm')**"
$body = @()
$body += $header
$body += ""
$body += "**Worktrees:** $wtSummary"

$dirtyRows = $wtRows | Where-Object { $_.Dirty -gt 0 -or $_.Behind -gt 0 } | Select-Object -First 8
foreach ($r in $dirtyRows) {
  $tag = @()
  if ($r.Dirty  -gt 0) { $tag += "$($r.Dirty) dirty" }
  if ($r.Ahead  -gt 0) { $tag += "+$($r.Ahead)" }
  if ($r.Behind -gt 0) { $tag += "-$($r.Behind)" }
  $body += "- $($r.Branch) -- $($tag -join ', ')"
}
if ($dirtyRows.Count -eq 0) { $body += "- all clean" }

$body += ""
$body += "**PRs:** $prSummary"
if ($urgentCount -gt 0) { $body += ":rotating_light: urgent PRs flagged -- check email digest" }

$content = ($body -join "`n")
if ($content.Length -gt 1900) { $content = $content.Substring(0, 1897) + "..." }

Write-Host "--- Digest ---`n$content`n--- end ---"

if ($DryRun) {
  Write-Host "DryRun: not posting to Discord."
  Stop-Transcript | Out-Null
  exit 0
}

if (-not $Env:DISCORD_WEBHOOK_URL) {
  Write-Error "DISCORD_WEBHOOK_URL not set -- set it in the scheduled task's environment."
  Stop-Transcript | Out-Null
  exit 1
}

$payload = @{ content = $content; username = 'PMOVES Daily Digest' } | ConvertTo-Json -Compress
try {
  Invoke-RestMethod -Method Post -Uri $Env:DISCORD_WEBHOOK_URL -ContentType 'application/json' -Body $payload -TimeoutSec 20 | Out-Null
  Write-Host "Digest posted."
} catch {
  Write-Error "Discord post failed: $($_.Exception.Message)"
  Stop-Transcript | Out-Null
  exit 2
}

Stop-Transcript | Out-Null
