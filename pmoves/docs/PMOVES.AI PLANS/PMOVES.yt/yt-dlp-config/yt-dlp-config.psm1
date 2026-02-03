# yt-dlp PowerShell Module
# Import with: Import-Module ./yt-dlp-config.psm1

# Configuration
$script:ConfigDir = "$env:USERPROFILE\yt-dlp-config"
$script:DefaultOutput = "E:\Downloads\yt-dlp"
$script:LogFile = "$ConfigDir\download.log"

# Ensure directories exist
if (-not (Test-Path $script:DefaultOutput)) {
    New-Item -ItemType Directory -Path $script:DefaultOutput -Force | Out-Null
}
if (-not (Test-Path $script:ConfigDir)) {
    New-Item -ItemType Directory -Path $script:ConfigDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $Message" | Out-File -FilePath $script:LogFile -Append
}

function Invoke-YtDlp {
    <#
    .SYNOPSIS
    Enhanced yt-dlp download function with preset configurations
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Url,
        
        [ValidateSet("audio", "video", "playlist", "custom")]
        [string]$Preset = "video",
        
        [ValidateSet("mp3", "mp4", "mkv", "best")]
        [string]$Format = "mp4",
        
        [ValidateSet("4k", "1080", "720", "best")]
        [string]$Quality = "1080",
        
        [string]$OutputPath = $script:DefaultOutput,
        
        [switch]$SkipExisting,
        
        [hashtable]$CustomOptions = @{}
    )
    
    Write-Log "Starting download: $Url (Preset: $Preset, Quality: $Quality, Format: $Format)"
    
    # Base command
    $ytdlpArgs = @(
        "--config-location", "$script:ConfigDir\config.txt"
        "--output", "`"$OutputPath\%(uploader)s\%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s`""
    )
    
    # Preset configurations
    switch ($Preset) {
        "audio" {
            $ytdlpArgs += @(
                "--extract-audio", "--audio-format", "mp3"
                "--embed-thumbnail", "--add-metadata"
            )
        }
        "video" {
            switch ($Quality) {
                "4k" { $formatSelector = "best[height<=2160]+bestaudio/best" }
                "1080" { $formatSelector = "best[height<=1080]+bestaudio/best" }
                "720" { $formatSelector = "best[height<=720]+bestaudio/best" }
                default { $formatSelector = "bv+ba/best" }
            }
            $ytdlpArgs += @("--format", $formatSelector, "--merge-output-format", $Format)
        }
        "playlist" {
            $ytdlpArgs += @("--yes-playlist", "--download-archive", "$script:ConfigDir\downloaded.txt")
        }
        "custom" {
            # Apply custom options
            foreach ($key in $CustomOptions.Keys) {
                $ytdlpArgs += @("--$key", $CustomOptions[$key])
            }
        }
    }
    
    if ($SkipExisting) {
        $ytdlpArgs += @("--download-archive", "$script:ConfigDir\downloaded.txt")
    }
    
    $ytdlpArgs += $Url
    
    Write-Host "Downloading: $Url" -ForegroundColor Green
    Write-Host "Command: yt-dlp $($ytdlpArgs -join ' ')" -ForegroundColor Gray
    
    try {
        & "yt-dlp" $ytdlpArgs
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Successfully downloaded: $Url"
            Write-Host "Download completed successfully!" -ForegroundColor Green
        } else {
            Write-Log "Failed to download: $Url (exit code: $LASTEXITCODE)"
            Write-Host "Download failed! Exit code: $LASTEXITCODE" -ForegroundColor Red
        }
    }
    catch {
        Write-Log "Error downloading $Url`: $($_.Exception.Message)"
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Get-YtDlpInfo {
    <#
    .SYNOPSIS
    Get information about a video without downloading
    #>
    param([Parameter(Mandatory=$true)][string]$Url)
    
    Write-Host "Getting video info for: $Url" -ForegroundColor Yellow
    yt-dlp --dump-json "$Url" | ConvertFrom-Json | Format-List Title, Duration, Uploader, View_Count, Like_Count, Upload_Date
}

function Update-YtDlp {
    <#
    .SYNOPSIS
    Update yt-dlp to the latest version
    #>
    Write-Host "Updating yt-dlp..." -ForegroundColor Yellow
    yt-dlp --update
    Write-Host "Update completed!" -ForegroundColor Green
}

# Export functions
Export-ModuleMember -Function Invoke-YtDlp, Get-YtDlpInfo, Update-YtDlp