Param(
  [Parameter(Mandatory=$true)][string]$Registry,
  [string]$Version
)

$Image = "agent-zero"
$Dockerfile = "services/agent-zero/Dockerfile.multiarch"
$Context = "services/agent-zero"

if (-not (docker buildx inspect pmoves-builder 2>$null)) {
  docker buildx create --name pmoves-builder --use | Out-Null
}

$tags = @("-t", "$Registry/$Image:latest")
if ($Version) { $tags += @("-t", "$Registry/$Image:$Version") }

docker buildx build `
  --platform linux/amd64,linux/arm64 `
  -f $Dockerfile `
  @tags `
  --push `
  $Context

Write-Host "Pushed: $Registry/$Image/$($Version ?? 'latest') (multi-arch)"

