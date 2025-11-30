#!/bin/bash
# yt-dlp Advanced Download Script for Linux/WSL
# Usage: ./yt-dlp-advanced.sh [URL] [quality] [format]

set -e

# Configuration
CONFIG_DIR="$HOME/yt-dlp-config"
DEFAULT_OUTPUT="$HOME/Downloads/yt-dlp"
LOG_FILE="$CONFIG_DIR/download.log"

# Create directories if they don't exist
mkdir -p "$DEFAULT_OUTPUT" "$CONFIG_DIR"

# Function to log downloads
log_download() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to show usage
show_usage() {
    cat << EOF
yt-dlp Advanced Download Script

Usage: $0 [URL] [quality] [format]

Arguments:
  URL     : Video/playlist URL to download
  quality : Video quality (auto, 4k, 1080, 720, audio)
  format  : Output format (mp4, mkv, mp3, best)

Examples:
  $0 "https://youtube.com/watch?v=VIDEO_ID"
  $0 "https://youtube.com/watch?v=VIDEO_ID" 1080 mp4
  $0 "https://youtube.com/playlist?list=PLAYLIST_ID" 720 mp4
  $0 "https://youtube.com/watch?v=VIDEO_ID" audio mp3

EOF
}

# Parse arguments
URL="$1"
QUALITY="${2:-auto}"
FORMAT="${3:-best}"

# Validate input
if [[ -z "$URL" ]]; then
    show_usage
    exit 1
fi

log_download "Starting download: $URL (quality: $QUALITY, format: $FORMAT)"

# Set format selector based on quality
case "$QUALITY" in
    "4k")
        FORMAT_SELECTOR="best[height<=2160]+bestaudio/best"
        ;;
    "1080")
        FORMAT_SELECTOR="best[height<=1080]+bestaudio/best"
        ;;
    "720")
        FORMAT_SELECTOR="best[height<=720]+bestaudio/best"
        ;;
    "audio")
        FORMAT_SELECTOR="bestaudio/best"
        ;;
    *)
        FORMAT_SELECTOR="bv+ba/best"
        ;;
esac

# Set output format and additional options
case "$FORMAT" in
    "mp4")
        MERGE_FORMAT="mp4"
        ;;
    "mkv")
        MERGE_FORMAT="mkv"
        ;;
    "mp3")
        MERGE_FORMAT="mp3"
        AUDIO_ONLY="--extract-audio --audio-format mp3"
        ;;
    *)
        MERGE_FORMAT="best"
        AUDIO_ONLY=""
        ;;
esac

# Build yt-dlp command
YTDLP_CMD=(
    yt-dlp
    --config-location "$CONFIG_DIR/config.txt"
    --format "$FORMAT_SELECTOR"
    --merge-output-format "$MERGE_FORMAT"
    $AUDIO_ONLY
    --write-info-json
    --write-description
    --write-annotations
    "$URL"
)

echo "Downloading: $URL"
echo "Quality: $QUALITY | Format: $FORMAT"

# Execute download
"${YTDLP_CMD[@]}"

if [[ $? -eq 0 ]]; then
    log_download "Successfully downloaded: $URL"
    echo "Download completed successfully!"
else
    log_download "Failed to download: $URL"
    echo "Download failed! Check log for details."
    exit 1
fi