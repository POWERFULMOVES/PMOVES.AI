# yt-dlp Configuration Documentation

## Overview
This setup provides a comprehensive yt-dlp configuration with multiple download presets, automation scripts, and enhanced features.

## Files Created

### 1. `config.txt` - Main Configuration
- **Output Organization**: Files organized by uploader and date
- **Format Selection**: Best video + audio, merged to MP4
- **Quality Settings**: Prefers 1080p H.264
- **Subtitles**: English subtitles auto-downloaded and embedded
- **Metadata**: Embeds metadata, chapters, thumbnails
- **SponsorBlock**: Removes sponsor segments, creates chapters
- **Network**: Robust retry and timeout settings
- **Aliases**: Quick shortcuts for music, video, and playlist downloads

### 2. `yt-dlp-quick.bat` - Windows Batch Script
Quick download with presets:
```cmd
yt-dlp-quick.bat https://youtube.com/watch?v=VIDEO_ID music    # Audio as MP3
yt-dlp-quick.bat https://youtube.com/watch?v=VIDEO_ID video    # Video 1080p
yt-dlp-quick.bat https://youtube.com/playlist?list=PLAYLIST_ID playlist  # Entire playlist
```

### 3. `yt-dlp-advanced.sh` - Linux/WSL Script
Advanced download with quality/format control:
```bash
./yt-dlp-advanced.sh "URL" [quality] [format]
./yt-dlp-advanced.sh "https://youtube.com/watch?v=VIDEO_ID" 1080 mp4
```

### 4. `yt-dlp-config.psm1` - PowerShell Module
PowerShell functions for enhanced control:
```powershell
Import-Module ./yt-dlp-config.psm1
Invoke-YtDlp -Url "URL" -Preset video -Quality 1080 -Format mp4
```

## Installation Steps

1. **Copy Config to AppData** (for global usage):
```cmd
mkdir %APPDATA%\yt-dlp
copy "C:\Users\russe\yt-dlp-config\config.txt" %APPDATA%\yt-dlp\
```

2. **Add Scripts to PATH**:
   - Add `C:\Users\russe\yt-dlp-config` to your PATH environment variable
   - Or copy scripts to a directory already in PATH

3. **Set Up PowerShell Module**:
```powershell
# Add to PowerShell profile
echo "Import-Module 'C:\Users\russe\yt-dlp-config\yt-dlp-config.psm1'" >> $PROFILE
```

## Enhanced Features

### Preset Aliases
- `music`: Best audio → MP3 with metadata
- `video-high`: Best video (1080p max) → MP4
- `playlist-audio`: Audio playlist with archive

### Output Template
```
E:/Downloads/yt-dlp/[Uploader]/[YYYY-MM-DD] - [Video Title] [Video ID].ext
```

### SponsorBlock Integration
- Removes: sponsor, intro, outro, selfpromo, preview, filler, interaction
- Marks: All segments as chapters for navigation

### Quality Settings
- Priority: 1080p → 720p → best available
- Codec preference: H.264 for compatibility
- Audio: Best quality with AAC fallback

### Network Robustness
- 10 retries with 60s timeout
- Fragment retry for streaming
- Sleep intervals to avoid rate limiting

## Customization Options

### Modify Output Path
Edit `config.txt` line:
```txt
-o "YOUR/DESIRED/PATH/%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"
```

### Change Quality Defaults
Edit format selector:
```txt
-f "bv[height<=720]+ba/b"  # For 720p max
```

### Add New Aliases
```txt
--alias "podcast" "-x --audio-format mp3 --embed-thumbnail --add-metadata --playlist-reverse"
```

### Custom Filters
```txt
--match-filters "duration >= 60 & like_count > 100"
```

## Usage Examples

### Download YouTube Video as MP3
```cmd
yt-dlp --config-location "C:\Users\russe\yt-dlp-config\config.txt" -x --audio-format mp3 "URL"
```

### Download Playlist with Custom Path
```cmd
yt-dlp --config-location "C:\Users\russe\yt-dlp-config\config.txt" -o "D:\Music\%(playlist_title)s\%(title)s.%(ext)s" "PLAYLIST_URL"
```

### Download with Date Filtering
```cmd
yt-dlp --config-location "C:\Users\russe\yt-dlp-config\config.txt" --dateafter 20240101 "URL"
```

## Troubleshooting

### FFmpeg Location
If FFmpeg is not found, add to `config.txt`:
```txt
--ffmpeg-location "C:\Users\russe\Documents\ffmpeg\ffmpeg_folder\bin\ffmpeg.exe"
```

### Proxy Settings
```txt
--proxy "http://proxy.example.com:8080"
```

### Rate Limiting
Increase sleep intervals:
```txt
--sleep-interval 2
--max-sleep-interval 5
```

## Maintenance

### Update yt-dlp
```cmd
yt-dlp --update
```

### Clear Download Archive
```cmd
del "C:\Users\russe\yt-dlp-config\downloaded.txt"
```

### Check Logs
```cmd
type "C:\Users\russe\yt-dlp-config\download.log"
```