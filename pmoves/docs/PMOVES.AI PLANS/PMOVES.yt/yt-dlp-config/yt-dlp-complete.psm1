# Enhanced PowerShell Module for Complete Media Collection
# Import with: Import-Module ./yt-dlp-complete.psm1

# Configuration
$script:ConfigDir = "$env:USERPROFILE\yt-dlp-config"
$script:CompleteConfig = "$script:ConfigDir\complete-config.txt"
$script:CookiesFile = "$script:ConfigDir\cookies.txt"
$script:DefaultOutput = "E:\Downloads\yt-dlp\complete"
$script:LogFile = "$script:ConfigDir\complete-downloads.log"

function Write-CompleteLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $Message" | Out-File -FilePath $script:LogFile -Append
    Write-Host "[$timestamp] $Message" -ForegroundColor Cyan
}

function Invoke-CompleteDownload {
    <#
    .SYNOPSIS
    Downloads video with all media files (combined, separate audio/video, metadata, transcripts)
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Url,
        
        [ValidateSet("4k", "1080", "720", "best")]
        [string]$Quality = "1080",
        
        [string]$OutputPath = $script:DefaultOutput,
        
        [switch]$IncludePremium,
        
        [switch]$OnlyMetadata,
        
        [switch]$OnlyAudio,
        
        [switch]$SkipExisting,
        
        [string]$DownloadType = "complete"
    )
    
    Write-CompleteLog "Starting complete download: $Url"
    Write-CompleteLog "Quality: $Quality | Type: $DownloadType"
    
    # Build base arguments
    $ytdlpArgs = @(
        "--config-location", $script:CompleteConfig
    )
    
    if ($IncludePremium -and (Test-Path $script:CookiesFile)) {
        $ytdlpArgs += @("--cookies", $script:CookiesFile)
        Write-Host "Using premium authentication" -ForegroundColor Green
    }
    
    if ($SkipExisting) {
        $ytdlpArgs += @("--download-archive", "$script:ConfigDir\downloaded-complete.txt")
    }
    
    # Determine format based on quality
    $formatSelector = switch ($Quality) {
        "4k" { "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]" }
        "1080" { "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" }
        "720" { "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" }
        default { "bestvideo+bestaudio/best" }
    }
    
    if ($OnlyMetadata) {
        Write-Host "Downloading metadata only..." -ForegroundColor Yellow
        $ytdlpArgs += @(
            "--write-info-json", "--write-description", "--write-annotations"
            "--write-comments", "--write-thumbnail", "--write-all-thumbnails"
            "--skip-download", "--print", "%(title)s"
        )
    }
    elseif ($OnlyAudio) {
        Write-Host "Downloading audio only..." -ForegroundColor Yellow
        $ytdlpArgs += @(
            "--format", "bestaudio/best"
            "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"
            "--extract-audio", "--audio-format", "flac", "--audio-quality", "0"
            "--output", "%(title)s [%(id)s].audio.%(ext)s"
        )
    }
    else {
        Write-Host "Downloading complete media collection..." -ForegroundColor Yellow
        
        # Phase 1: Combined
        $combinedArgs = $ytdlpArgs + @(
            "--format", $formatSelector, "--merge-output-format", "mp4"
            "--output", "combined:%(title)s [%(id)s].%(ext)s"
        )
        
        Write-Host "Phase 1: Combined video + audio" -ForegroundColor Gray
        & "yt-dlp" $combinedArgs $Url
        
        # Phase 2: Separate video
        $videoArgs = $ytdlpArgs + @(
            "--format", "bestvideo"
            "--output", "video:%(title)s [%(id)s].video.%(ext)s"
        )
        
        Write-Host "Phase 2: Separate video stream" -ForegroundColor Gray
        & "yt-dlp" $videoArgs $Url
        
        # Phase 3: Separate audio
        $audioArgs = $ytdlpArgs + @(
            "--format", "bestaudio/best"
            "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"
            "--extract-audio", "--audio-format", "flac", "--audio-quality", "0"
            "--output", "audio:%(title)s [%(id)s].audio.%(ext)s"
        )
        
        Write-Host "Phase 3: Separate audio streams" -ForegroundColor Gray
        & "yt-dlp" $audioArgs $Url
        
        # Phase 4: Metadata
        $metadataArgs = $ytdlpArgs + @(
            "--write-info-json", "--write-description", "--write-annotations"
            "--write-comments", "--write-thumbnail", "--write-all-thumbnails"
            "--skip-download"
        )
        
        Write-Host "Phase 4: Metadata and media files" -ForegroundColor Gray
        & "yt-dlp" $metadataArgs $Url
        
        # Phase 5: Transcripts
        $transcriptArgs = $ytdlpArgs + @(
            "--sub-langs", "all,live_chat", "--write-subs", "--write-auto-subs"
            "--convert-subs", "srt", "--convert-subs", "vtt", "--convert-subs", "ass"
            "--skip-download"
        )
        
        Write-Host "Phase 5: Transcripts and subtitles" -ForegroundColor Gray
        & "yt-dlp" $transcriptArgs $Url
        
        Write-Host "Complete download finished!" -ForegroundColor Green
        return
    }
    
    # Execute single command
    & "yt-dlp" $ytdlpArgs $Url
    
    if ($LASTEXITCODE -eq 0) {
        Write-CompleteLog "Successfully processed: $Url"
        Write-Host "Operation completed successfully!" -ForegroundColor Green
    } else {
        Write-CompleteLog "Failed to process: $Url (exit code: $LASTEXITCODE)"
        Write-Host "Operation failed! Exit code: $LASTEXITCODE" -ForegroundColor Red
    }
}

function Add-TrackedChannel {
    <#
    .SYNOPSIS
    Add channel to automatic tracking
    #>
    param([Parameter(Mandatory=$true)][string]$ChannelUrl)
    
    $pythonScript = "$script:ConfigDir\tracker.py"
    if (Test-Path $pythonScript) {
        python $pythonScript add-channel $ChannelUrl
        Write-Host "Channel added to tracker" -ForegroundColor Green
    } else {
        Write-Host "Tracker script not found" -ForegroundColor Red
    }
}

function Add-TrackedPlaylist {
    <#
    .SYNOPSIS
    Add playlist to automatic tracking
    #>
    param([Parameter(Mandatory=$true)][string]$PlaylistUrl)
    
    $pythonScript = "$script:ConfigDir\tracker.py"
    if (Test-Path $pythonScript) {
        python $pythonScript add-playlist $PlaylistUrl
        Write-Host "Playlist added to tracker" -ForegroundColor Green
    } else {
        Write-Host "Tracker script not found" -ForegroundColor Red
    }
}

function Start-TrackerDaemon {
    <#
    .SYNOPSIS
    Start the automatic tracking daemon
    #>
    $pythonScript = "$script:ConfigDir\tracker.py"
    if (Test-Path $pythonScript) {
        Write-Host "Starting tracker daemon..." -ForegroundColor Yellow
        python $pythonScript daemon
    } else {
        Write-Host "Tracker script not found" -ForegroundColor Red
    }
}

function Set-PremiumAuthentication {
    <#
    .SYNOPSIS
    Set up YouTube Premium authentication
    #>
    $setupScript = "$script:ConfigDir\setup-premium.bat"
    if (Test-Path $setupScript) {
        & $setupScript
    } else {
        Write-Host "Premium setup script not found" -ForegroundColor Red
    }
}

function Get-TrackedContent {
    <#
    .SYNOPSIS
    Show all tracked channels and playlists
    #>
    $pythonScript = "$script:ConfigDir\tracker.py"
    if (Test-Path $pythonScript) {
        python $pythonScript list
    } else {
        Write-Host "Tracker script not found" -ForegroundColor Red
    }
}

function Test-PremiumAccess {
    <#
    .SYNOPSIS
    Test if Premium authentication is working
    #>
    if (Test-Path $script:CookiesFile) {
        Write-Host "Testing Premium access..." -ForegroundColor Yellow
        $result = yt-dlp --cookies $script:CookiesFile --simulate --print "%(title)s" "https://www.youtube.com/premium"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Premium access: WORKING" -ForegroundColor Green
            Write-Host "Result: $result"
        } else {
            Write-Host "Premium access: FAILED" -ForegroundColor Red
            Write-Host "Run Set-PremiumAuthentication to fix"
        }
    } else {
        Write-Host "No cookies file found. Run Set-PremiumAuthentication" -ForegroundColor Red
    }
}

function Show-CompleteSummary {
    <#
    .SYNOPSIS
    Show summary of downloaded content
    #>
    $downloadLog = "$script:ConfigDir\complete-downloads.log"
    if (Test-Path $downloadLog) {
        Write-Host "=== Download Summary ===" -ForegroundColor Cyan
        $recentLogs = Get-Content $downloadLog | Select-Object -Last 20
        $recentLogs | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
        Write-Host "========================" -ForegroundColor Cyan
    } else {
        Write-Host "No download log found" -ForegroundColor Yellow
    }
}

# Export functions
Export-ModuleMember -Function @(
    'Invoke-CompleteDownload',
    'Add-TrackedChannel',
    'Add-TrackedPlaylist',
    'Start-TrackerDaemon',
    'Set-PremiumAuthentication',
    'Get-TrackedContent',
    'Test-PremiumAccess',
    'Show-CompleteSummary'
)