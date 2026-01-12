Param(
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$false)][string]$Note = ""
)

$dir = "pmoves/docs/evidence"
$file = Join-Path $dir "log.csv"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

function EscCsv([string]$s) {
  return '"' + $s.Replace('"','""') + '"'
}

if (-not (Test-Path $file)) {
  "timestamp,label,path,note" | Out-File -Encoding UTF8 -FilePath $file
}

$line = (EscCsv $stamp) + "," + (EscCsv $Label) + "," + (EscCsv $Path) + "," + (EscCsv $Note)
Add-Content -Path $file -Value $line
Write-Output $file

