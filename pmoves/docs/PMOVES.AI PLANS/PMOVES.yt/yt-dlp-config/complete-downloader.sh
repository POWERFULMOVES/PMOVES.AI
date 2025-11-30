#!/bin/bash
# Complete Media Downloader - Downloads everything with full metadata
# Usage: ./complete-downloader.sh [URL] [quality] [options]

set -e

# Configuration
CONFIG_DIR="$HOME/yt-dlp-config"
LOG_FILE="$CONFIG_DIR/complete-downloads.log"
ERROR_LOG="$CONFIG_DIR/download-errors.log"
DEFAULT_OUTPUT="$HOME/Downloads/yt-dlp/complete"

# Ensure directories exist
mkdir -p "$DEFAULT_OUTPUT" "$CONFIG_DIR"

# Logging functions
log_info() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo "$message"
    echo "$message" >> "$LOG_FILE"
}

log_error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo "$message" >&2
    echo "$message" >> "$ERROR_LOG"
}

# Usage information
show_usage() {
    cat << EOF
Complete Media Downloader - Downloads video, audio, metadata, transcripts, and media

Usage: $0 [URL] [QUALITY] [OPTIONS]

Arguments:
  URL       : Video/playlist/channel URL
  QUALITY   : Video quality (4k, 1080, 720, best)
  OPTIONS   : Additional options

Quality Options:
  4k        - 2160p maximum
  1080      - 1080p maximum
  720       - 720p maximum
  best      - Best available

Examples:
  $0 "https://youtube.com/watch?v=VIDEO_ID" 1080
  $0 "https://youtube.com/playlist?list=PLAYLIST_ID" 720
  $0 "https://youtube.com/c/CHANNELNAME/videos" best

EOF
}

# Parse arguments
URL="$1"
QUALITY="${2:-best}"
EXTRA_OPTS="${3}"

# Validate input
if [[ -z "$URL" ]]; then
    show_usage
    exit 1
fi

log_info "Starting complete download: $URL"
log_info "Quality setting: $QUALITY"

# Determine format selector based on quality
case "$QUALITY" in
    "4k")
        VIDEO_FORMAT="bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]"
        ;;
    "1080")
        VIDEO_FORMAT="bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        ;;
    "720")
        VIDEO_FORMAT="bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
        ;;
    *)
        VIDEO_FORMAT="bestvideo+bestaudio/best"
        ;;
esac

# Main download command
log_info "Phase 1: Downloading combined video + audio"
yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --format "$VIDEO_FORMAT" \
    --merge-output-format "mp4" \
    --output "combined:%(title)s [%(id)s].%(ext)s" \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to download combined video"

log_info "Phase 2: Downloading separate video stream"
yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --format "bestvideo" \
    --output "video:%(title)s [%(id)s].video.%(ext)s" \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to download separate video"

log_info "Phase 3: Downloading separate audio streams"
yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --extract-audio \
    --audio-format "mp3" \
    --audio-quality "0" \
    --output "audio:%(title)s [%(id)s].audio.%(ext)s" \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to extract MP3 audio"

yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --extract-audio \
    --audio-format "flac" \
    --audio-quality "0" \
    --output "audio:%(title)s [%(id)s].audio.%(ext)s" \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to extract FLAC audio"

log_info "Phase 4: Downloading metadata and media files"
yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --write-info-json \
    --write-description \
    --write-annotations \
    --write-comments \
    --write-thumbnail \
    --write-all-thumbnails \
    --skip-download \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to download metadata"

log_info "Phase 5: Downloading transcripts and subtitles"
yt-dlp \
    --config-location "$CONFIG_DIR/complete-config.txt" \
    --sub-langs "all,live_chat" \
    --write-subs \
    --write-auto-subs \
    --convert-subs "srt" \
    --convert-subs "vtt" \
    --convert-subs "ass" \
    --skip-download \
    $EXTRA_OPTS \
    "$URL" || log_error "Failed to download transcripts"

log_info "Complete download finished for: $URL"
echo "Download completed! Check: $DEFAULT_OUTPUT"
echo "Logs: $LOG_FILE"

# Show summary
echo ""
echo "=== Download Summary ==="
echo "Video files: Combined + Separate"
echo "Audio files: MP3 + FLAC"
echo "Metadata: JSON, description, comments, annotations"
echo "Media: All thumbnails"
echo "Transcripts: All available subtitle formats"
echo "========================"