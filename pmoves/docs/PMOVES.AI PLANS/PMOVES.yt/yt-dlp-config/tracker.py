# Channel and Playlist Auto-Tracker
# Monitors channels and playlists for new content

import json
import time
import os
import sys
from datetime import datetime, timedelta
import subprocess
import logging
from pathlib import Path

class ChannelTracker:
    def __init__(self, config_file="tracker-config.json"):
        self.config_file = config_file
        self.config_dir = Path("C:/Users/russe/yt-dlp-config")
        self.config_path = self.config_dir / config_file
        self.downloaded_file = self.config_dir / "downloaded-complete.txt"
        self.setup_logging()
        self.load_config()
        
    def setup_logging(self):
        log_file = self.config_dir / "tracker.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """Load tracker configuration"""
        default_config = {
            "channels": [],
            "playlists": [],
            "check_interval": 3600,  # 1 hour
            "max_age_days": 30,
            "quality": "1080",
            "download_complete": True,
            "auto_download": False,
            "notifications": {
                "enabled": False,
                "email": "",
                "webhook_url": ""
            }
        }
        
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = default_config
            self.save_config()
            
    def save_config(self):
        """Save tracker configuration"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
            
    def add_channel(self, channel_url):
        """Add channel to tracking list"""
        if channel_url not in self.config["channels"]:
            self.config["channels"].append(channel_url)
            self.save_config()
            self.logger.info(f"Added channel: {channel_url}")
            return True
        return False
        
    def add_playlist(self, playlist_url):
        """Add playlist to tracking list"""
        if playlist_url not in self.config["playlists"]:
            self.config["playlists"].append(playlist_url)
            self.save_config()
            self.logger.info(f"Added playlist: {playlist_url}")
            return True
        return False
        
    def remove_channel(self, channel_url):
        """Remove channel from tracking list"""
        if channel_url in self.config["channels"]:
            self.config["channels"].remove(channel_url)
            self.save_config()
            self.logger.info(f"Removed channel: {channel_url}")
            return True
        return False
        
    def remove_playlist(self, playlist_url):
        """Remove playlist from tracking list"""
        if playlist_url in self.config["playlists"]:
            self.config["playlists"].remove(playlist_url)
            self.save_config()
            self.logger.info(f"Removed playlist: {playlist_url}")
            return True
        return False
        
    def get_new_videos(self, url):
        """Get list of new videos from channel or playlist"""
        try:
            cmd = [
                "yt-dlp",
                "--config-location", str(self.config_dir / "complete-config.txt"),
                "--flat-playlist",
                "--print", "%(id)s|%(title)s|%(upload_date)s|%(url)s",
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode != 0:
                self.logger.error(f"Failed to get videos from {url}: {result.stderr}")
                return []
                
            videos = []
            downloaded_ids = self.get_downloaded_ids()
            
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 4:
                        video_id, title, upload_date, video_url = parts[:4]
                        
                        # Skip if already downloaded
                        if video_id in downloaded_ids:
                            continue
                            
                        # Check video age
                        if upload_date and len(upload_date) == 8:
                            try:
                                video_date = datetime.strptime(upload_date, "%Y%m%d")
                                if datetime.now() - video_date > timedelta(days=self.config["max_age_days"]):
                                    continue
                            except ValueError:
                                pass
                                
                        videos.append({
                            "id": video_id,
                            "title": title,
                            "upload_date": upload_date,
                            "url": video_url,
                            "source": url
                        })
                        
            return videos
            
        except Exception as e:
            self.logger.error(f"Error getting videos from {url}: {str(e)}")
            return []
            
    def get_downloaded_ids(self):
        """Get list of already downloaded video IDs"""
        if not self.downloaded_file.exists():
            return set()
            
        with open(self.downloaded_file, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
            
    def download_video(self, video_info):
        """Download video using complete downloader"""
        try:
            cmd = [
                "complete-downloader.bat" if os.name == 'nt' else "./complete-downloader.sh",
                video_info["url"],
                self.config["quality"]
            ]
            
            self.logger.info(f"Downloading: {video_info['title']}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Mark as downloaded
                with open(self.downloaded_file, 'a', encoding='utf-8') as f:
                    f.write(f"{video_info['id']}\n")
                self.logger.info(f"Successfully downloaded: {video_info['title']}")
                return True
            else:
                self.logger.error(f"Failed to download {video_info['title']}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading {video_info['title']}: {str(e)}")
            return False
            
    def check_all(self):
        """Check all tracked channels and playlists for new videos"""
        self.logger.info("Starting check for new videos...")
        
        all_videos = []
        
        # Check channels
        for channel_url in self.config["channels"]:
            self.logger.info(f"Checking channel: {channel_url}")
            videos = self.get_new_videos(channel_url)
            all_videos.extend(videos)
            
        # Check playlists
        for playlist_url in self.config["playlists"]:
            self.logger.info(f"Checking playlist: {playlist_url}")
            videos = self.get_new_videos(playlist_url)
            all_videos.extend(videos)
            
        if not all_videos:
            self.logger.info("No new videos found")
            return []
            
        self.logger.info(f"Found {len(all_videos)} new videos")
        
        # Auto-download if enabled
        if self.config["auto_download"]:
            for video in all_videos:
                self.download_video(video)
                
        return all_videos
        
    def run_daemon(self):
        """Run tracker daemon continuously"""
        self.logger.info("Starting channel tracker daemon...")
        
        while True:
            try:
                self.check_all()
                time.sleep(self.config["check_interval"])
            except KeyboardInterrupt:
                self.logger.info("Tracker stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in tracker daemon: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    tracker = ChannelTracker()
    
    if len(sys.argv) < 2:
        print("""
Channel and Playlist Tracker Commands:

  add-channel URL        Add channel to tracking
  add-playlist URL       Add playlist to tracking
  remove-channel URL     Remove channel from tracking
  remove-playlist URL    Remove playlist from tracking
  check                  Check for new videos now
  daemon                 Run continuous tracker daemon
  list                   Show tracked channels and playlists
  config                 Show current configuration

Examples:
  python tracker.py add-channel "https://www.youtube.com/c/ChannelName"
  python tracker.py add-playlist "https://youtube.com/playlist?list=PLAYLIST_ID"
  python tracker.py daemon
        """)
        return
        
    command = sys.argv[1].lower()
    
    if command == "add-channel" and len(sys.argv) > 2:
        tracker.add_channel(sys.argv[2])
    elif command == "add-playlist" and len(sys.argv) > 2:
        tracker.add_playlist(sys.argv[2])
    elif command == "remove-channel" and len(sys.argv) > 2:
        tracker.remove_channel(sys.argv[2])
    elif command == "remove-playlist" and len(sys.argv) > 2:
        tracker.remove_playlist(sys.argv[2])
    elif command == "check":
        videos = tracker.check_all()
        for video in videos:
            print(f"New: {video['title']} from {video['source']}")
    elif command == "daemon":
        tracker.run_daemon()
    elif command == "list":
        print("Tracked Channels:")
        for channel in tracker.config["channels"]:
            print(f"  {channel}")
        print("\nTracked Playlists:")
        for playlist in tracker.config["playlists"]:
            print(f"  {playlist}")
    elif command == "config":
        print(json.dumps(tracker.config, indent=2))
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()