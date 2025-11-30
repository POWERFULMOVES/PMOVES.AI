Param(
  [Parameter(Mandatory=$false)][string]$Label = "evidence",
  [Parameter(Mandatory=$false)][string]$Ext = "png"
)

function New-Slug([string]$s) {
  $lower = $s.ToLowerInvariant()
  return ([regex]::Replace($lower, "[^a-z0-9]+", "-")).Trim('-')
}

$slug = New-Slug $Label
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$dir = "pmoves/docs/evidence"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$pathOut = Join-Path $dir ("{0}_{1}.{2}" -f $stamp, $slug, $Ext)
Write-Output $pathOut

