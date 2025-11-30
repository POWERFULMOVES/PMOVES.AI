# Complete Media Collection System - Documentation

## Overview
This enhanced yt-dlp setup provides complete media collection with automatic channel tracking, premium authentication, and comprehensive metadata extraction.

## Installation and Setup

### 1. Install Python for Tracker
```cmd
winget install Python.Python.3.11
```

### 2. Set Up Premium Authentication
```cmd
C:\Users\russe\yt-dlp-config\setup-premium.bat
```

### 3. Import PowerShell Module
```powershell
Import-Module C:\Users\russe\yt-dlp-config\yt-dlp-complete.psm1
```

## Features

### 🔥 Complete Media Download
- **Combined**: Best video + audio merged to MP4
- **Separate Video**: Raw video stream (highest quality)
- **Separate Audio**: MP3 + FLAC versions
- **Metadata**: JSON, description, comments, annotations
- **Media**: All thumbnails in multiple formats
- **Transcripts**: All subtitles in SRT, VTT, ASS formats

### 🎯 Channel & Playlist Tracking
- **Automatic Monitoring**: Checks for new content hourly
- **Smart Filtering**: Downloads only recent content
- **Archive Tracking**: Prevents duplicate downloads
- **Batch Processing**: Handle multiple sources simultaneously

### 👑 Premium Authentication
- **Cookie Extraction**: Auto-extract from browser
- **Premium Content**: Access YouTube Premium exclusives
- **Member-Only Videos**: Download members-only content
- **Age-Restricted**: Bypass age restrictions with login

## Quick Start Commands

### PowerShell Commands
```powershell
# Import the complete module
Import-Module C:\Users\russe\yt-dlp-config\yt-dlp-complete.psm1

# Complete download with everything
Invoke-CompleteDownload -Url "https://youtube.com/watch?v=VIDEO_ID" -Quality 1080

# Download with premium access
Invoke-CompleteDownload -Url "URL" -IncludePremium -Quality "4k"

# Download only metadata
Invoke-CompleteDownload -Url "URL" -OnlyMetadata

# Add channels to tracking
Add-TrackedChannel "https://www.youtube.com/c/ChannelName"
Add-TrackedPlaylist "https://youtube.com/playlist?list=PLAYLIST_ID"

# Start automatic tracking
Start-TrackerDaemon

# Test premium authentication
Test-PremiumAccess

# Show tracked content
Get-TrackedContent
```

### Batch Commands
```cmd
# Complete download
complete-downloader.bat "https://youtube.com/watch?v=VIDEO_ID" 1080

# With premium (after setup)
complete-downloader.bat "https://youtube.com/premium-video" 4k

# Channel tracking (Python)
python tracker.py add-channel "https://youtube.com/c/ChannelName"
python tracker.py check
python tracker.py daemon
```

## File Organization

### Directory Structure
```
E:/Downloads/yt-dlp/complete/
├── [Channel Name]/
│   └── [YYYY-MM-DD]/
│       └── [Video Title] [Video ID]/
│           ├── combined/
│           │   └── [Video Title] [ID].mp4
│           ├── video/
│           │   └── [Video Title] [ID].video.mp4
│           ├── audio/
│           │   ├── [Video Title] [ID].audio.mp3
│           │   └── [Video Title] [ID].audio.flac
│           ├── thumbnails/
│           │   ├── [Video Title] [ID].jpg
│           │   ├── [Video Title] [ID].png
│           │   └── [Video Title] [ID].webp
│           ├── metadata/
│           │   ├── [Video Title] [ID].info.json
│           │   ├── [Video Title] [ID].description
│           │   ├── [Video Title] [ID].annotations.xml
│           │   └── [Video Title] [ID].comments.json
│           └── subtitles/
│               ├── [Video Title] [ID].en.srt
│               ├── [Video Title] [ID].en.vtt
│               ├── [Video Title] [ID].live_chat.srt
│               └── ... (all available languages)
```

## Configuration Files

### complete-config.txt
Main configuration with:
- Output templates for different media types
- Quality preferences (4K → 1080p → 720p)
- Metadata extraction settings
- Premium authentication paths
- SponsorBlock integration

### tracker-config.json
Channel tracking configuration:
```json
{
  "channels": [
    "https://www.youtube.com/c/Channel1",
    "https://www.youtube.com/c/Channel2"
  ],
  "playlists": [
    "https://youtube.com/playlist?list=PLAYLIST_ID"
  ],
  "check_interval": 3600,
  "max_age_days": 30,
  "quality": "1080",
  "download_complete": true,
  "auto_download": false
}
```

## Advanced Usage

### Quality Selection
```powershell
# 4K maximum quality
Invoke-CompleteDownload -Url "URL" -Quality "4k"

# 1080p maximum (recommended)
Invoke-CompleteDownload -Url "URL" -Quality "1080"

# 720p for space saving
Invoke-CompleteDownload -Url "URL" -Quality "720"

# Best available
Invoke-CompleteDownload -Url "URL" -Quality "best"
```

### Selective Downloads
```powershell
# Only metadata (no video/audio)
Invoke-CompleteDownload -Url "URL" -OnlyMetadata

# Only audio files
Invoke-CompleteDownload -Url "URL" -OnlyAudio

# Skip already downloaded content
Invoke-CompleteDownload -Url "URL" -SkipExisting
```

### Premium Content
```powershell
# Set up authentication
Set-PremiumAuthentication

# Download premium content
Invoke-CompleteDownload -Url "https://youtube.com/premium" -IncludePremium

# Test if premium is working
Test-PremiumAccess
```

### Tracking Management
```powershell
# Add multiple channels
Add-TrackedChannel "https://youtube.com/c/Channel1"
Add-TrackedChannel "https://youtube.com/c/Channel2"

# Add playlists
Add-TrackedPlaylist "https://youtube.com/playlist?list=PLAYLIST1"
Add-TrackedPlaylist "https://youtube.com/playlist?list=PLAYLIST2"

# View all tracked content
Get-TrackedContent

# Start auto-downloader daemon
Start-TrackerDaemon
```

## Scheduled Tasks

### Windows Task Scheduler Setup
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at specific time
4. Action: Start a program
5. Program: `python`
6. Arguments: `"C:\Users\russe\yt-dlp-config\tracker.py" check`
7. Click Finish

### PowerShell Scheduled Job
```powershell
# Create daily check job
$trigger = New-JobTrigger -Daily -At 9am
Register-ScheduledJob -Name "YouTubeTracker" -Trigger $trigger -ScriptBlock {
    python "C:\Users\russe\yt-dlp-config\tracker.py" check
}
```

## Troubleshooting

### Premium Authentication Issues
```cmd
# Re-run setup
setup-premium.bat

# Check cookies file
dir C:\Users\russe\yt-dlp-config\cookies.txt

# Test manually
yt-dlp --cookies "cookies.txt" "https://youtube.com/premium"
```

### Tracking Not Working
```cmd
# Check tracker config
python tracker.py config

# Test manually
python tracker.py check

# Check logs
type C:\Users\russe\yt-dlp-config\tracker.log
```

### Download Failures
```powershell
# Check complete downloads log
Get-Content "C:\Users\russe\yt-dlp-config\complete-downloads.log" | Select-Object -Last 20

# Check error log
Get-Content "C:\Users\russe\yt-dlp-config\download-errors.log" | Select-Object -Last 10
```

## Maintenance

### Update System
```cmd
# Update yt-dlp
yt-dlp --update

# Run maintenance
C:\Users\russe\yt-dlp-config\maintenance.bat
```

### Clean Archives
```powershell
# Clear download archive
Remove-Item "C:\Users\russe\yt-dlp-config\downloaded-complete.txt" -Force

# Clear logs older than 30 days
Get-ChildItem "C:\Users\russe\yt-dlp-config\*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-30)
} | Remove-Item
```

## Performance Tips

### For Large Collections
1. Use SSD for download directory
2. Increase `--limit-rate` to avoid network issues
3. Set `check_interval` higher (3600+ seconds)
4. Use `max_age_days` to limit scope

### Network Optimization
```powershell
# Add to config.txt:
--limit-rate "50M"
--socket-timeout 300
--retries 50
--fragment-retries 50
```

## File Examples

### Sample Complete Download Output
```
complete/
├── Linus Tech Tips/
│   └── 2025-01-15/
│       └── I Built the Ultimate Gaming PC [abc123]/
│           ├── combined/
│           │   └── I Built the Ultimate Gaming PC [abc123].mp4
│           ├── video/
│           │   └── I Built the Ultimate Gaming PC [abc123].video.mp4
│           ├── audio/
│           │   ├── I Built the Ultimate Gaming PC [abc123].audio.mp3
│           │   └── I Built the Ultimate Gaming PC [abc123].audio.flac
│           ├── thumbnails/
│           │   ├── I Built the Ultimate Gaming PC [abc123].jpg
│           │   ├── I Built the Ultimate Gaming PC [abc123].webp
│           │   └── I Built the Ultimate Gaming PC [abc123].maxres.jpg
│           ├── metadata/
│           │   ├── I Built the Ultimate Gaming PC [abc123].info.json
│           │   ├── I Built the Ultimate Gaming PC [abc123].description
│           │   ├── I Built the Ultimate Gaming PC [abc123].comments.json
│           │   └── I Built the Ultimate Gaming PC [abc123].annotations.xml
│           └── subtitles/
│               ├── I Built the Ultimate Gaming PC [abc123].en.srt
│               ├── I Built the Ultimate Gaming PC [abc123].en.vtt
│               └── I Built the Ultimate Gaming PC [abc123].live_chat.srt
```

This system provides the most comprehensive YouTube media collection possible with yt-dlp!