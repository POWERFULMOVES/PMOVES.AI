$errs = $null; $tok = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tok, [ref]$errs)
if ($errs -and $errs.Count -gt 0) {
    Write-Host "PARSE_ERRORS:"
    foreach ($x in $errs) { Write-Host ("  line {0}:col {1}: {2}" -f $x.Extent.StartLineNumber, $x.Extent.StartColumnNumber, $x.Message) }
    exit 1
}
Write-Host "OK"
