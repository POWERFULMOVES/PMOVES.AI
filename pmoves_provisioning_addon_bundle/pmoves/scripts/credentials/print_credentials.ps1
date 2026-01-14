$envFile = "pmoves/.env.local"
$sharedFile = "pmoves/env.shared"
function GetV($k){ if (Test-Path $envFile){ (Get-Content $envFile) | Where-Object {$_ -match "^$k="} | Select-Object -Last 1 | % { $_.Split("=",2)[1] } } }
function GetSV($k){ if (Test-Path $sharedFile){ (Get-Content $sharedFile) | Where-Object {$_ -match "^$k="} | Select-Object -Last 1 | % { $_.Split("=",2)[1] } } }

Write-Host "PMOVES Provisioned Services — Default Login Summary"
Write-Host "---------------------------------------------------"
$wger = (GetSV "WGER_BASE_URL"); if (-not $wger) { $wger = "http://localhost:8000" }
$ff   = (GetSV "FIREFLY_BASE_URL"); if (-not $ff) { $ff = "http://localhost:8082" }
$jurl = (GetSV "JELLYFIN_PUBLISHED_URL"); if (-not $jurl) { $jurl = "http://localhost:8096" }
$apikey = (GetSV "JELLYFIN_API_KEY"); if (-not $apikey) { $apikey = "<not set>" }
$rest = (GetSV "SUPABASE_URL"); if (-not $rest) { $rest = "http://localhost:3000" }
$anon = (GetSV "SUPABASE_ANON_KEY"); if (-not $anon) { $anon = "<not set>" }
$svc  = (GetSV "SUPABASE_SERVICE_ROLE_KEY"); if (-not $svc) { $svc = "<not set>" }
$minio = (GetV "MINIO_ENDPOINT"); if (-not $minio) { $minio = "http://localhost:9000" }
$hook = (GetSV "DISCORD_WEBHOOK_URL"); if (-not $hook) { $hook = "<not set>" }

Write-Host "Wger         : URL=$wger | admin / adminadmin"
Write-Host "Firefly III  : URL=$ff | First user you register becomes admin"
Write-Host "Jellyfin     : URL=$jurl | Set on first run; API key: $apikey"
Write-Host "Supabase     : REST=$rest | anon=$anon service=$svc"
Write-Host "MinIO        : URL=$minio | minioadmin / minioadmin"
Write-Host "Discord Webhook: $hook"
