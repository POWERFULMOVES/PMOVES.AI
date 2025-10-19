"""
PMOVES.AI Automated YouTube Channel Monitoring System
Monitors specified YouTube channels for new videos and automatically processes them
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import hashlib
import os
from pathlib import Path

import aiohttp
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import yt_dlp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PMOVES.ChannelMonitor")

class YouTubeChannelMonitor:
    """
    Monitors YouTube channels for new videos and automatically queues them for processing
    """
    
    def __init__(self, config_path: str = "channel_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        
        # Redis for state management
        self.redis_client = None
        
        # PostgreSQL for persistence
        self.db_pool = None
        
        # Scheduler for automated checks
        self.scheduler = AsyncIOScheduler()
        
        # Track processed videos
        self.processed_videos: Set[str] = set()
        
        # API endpoints
        self.queue_api = os.getenv("QUEUE_API_URL", "http://localhost:8081/queue/add")
        
        # YouTube RSS feed base URL
        self.youtube_rss_base = "https://www.youtube.com/feeds/videos.xml?channel_id="
        
        # Rate limiting
        self.last_check = {}
        self.min_check_interval = 300  # 5 minutes minimum between checks per channel
        
    def load_config(self) -> Dict:
        """Load channel monitoring configuration"""
        
        default_config = {
            "channels": [
                {
                    "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",  # Example: Google Developers
                    "channel_name": "Google Developers",
                    "enabled": True,
                    "check_interval_minutes": 60,
                    "auto_process": True,
                    "filters": {
                        "min_duration_seconds": 60,
                        "max_age_days": 30,
                        "title_keywords": [],
                        "exclude_keywords": ["#shorts"],
                        "min_views": 0
                    },
                    "priority": 1,
                    "tags": ["tech", "development"]
                },
                {
                    "channel_id": "UCsBjURrPoezykLs9EqgamOA",  # Example: Fireship
                    "channel_name": "Fireship",
                    "enabled": True,
                    "check_interval_minutes": 120,
                    "auto_process": True,
                    "filters": {
                        "exclude_keywords": ["#shorts"]
                    },
                    "priority": 2,
                    "tags": ["tech", "tutorials"]
                }
            ],
            "global_settings": {
                "max_videos_per_check": 10,
                "use_rss_feed": True,
                "use_youtube_api": False,
                "youtube_api_key": "",
                "check_on_startup": True,
                "notification_webhook": "",
                "batch_processing": True,
                "batch_size": 5
            },
            "monitoring_schedule": {
                "enabled": True,
                "type": "interval",  # "interval" or "cron"
                "interval_minutes": 30,
                "cron_expression": "0 */2 * * *"  # Every 2 hours
            }
        }
        
        # Load or create config file
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                default_config.update(loaded_config)
        else:
            # Save default config
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default config at {config_file}")
        
        return default_config
    
    async def initialize(self):
        """Initialize connections and load state"""
        
        # Redis connection
        self.redis_client = await redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True
        )
        
        # PostgreSQL connection
        self.db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL", "postgresql://localhost/pmoves"),
            min_size=1,
            max_size=10
        )
        
        # Create monitoring table if not exists
        await self.setup_database()
        
        # Load processed videos from database
        await self.load_processed_videos()
        
        # Setup scheduled jobs
        self.setup_schedulers()
        
        logger.info("Channel monitor initialized")
    
    async def setup_database(self):
        """Create database tables for monitoring"""
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pmoves.channel_monitoring (
                    id SERIAL PRIMARY KEY,
                    channel_id VARCHAR(50) NOT NULL,
                    channel_name VARCHAR(255),
                    video_id VARCHAR(20) NOT NULL,
                    video_title TEXT,
                    video_url TEXT,
                    published_at TIMESTAMP,
                    discovered_at TIMESTAMP DEFAULT NOW(),
                    processed_at TIMESTAMP,
                    processing_status VARCHAR(20) DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    tags TEXT[],
                    metadata JSONB DEFAULT '{}',
                    UNIQUE(channel_id, video_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_monitoring_status 
                    ON pmoves.channel_monitoring(processing_status);
                    
                CREATE INDEX IF NOT EXISTS idx_monitoring_channel 
                    ON pmoves.channel_monitoring(channel_id, discovered_at DESC);
            """)
    
    async def load_processed_videos(self):
        """Load already processed videos from database"""
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT video_id 
                FROM pmoves.channel_monitoring 
                WHERE processing_status IN ('completed', 'processing')
            """)
            
            self.processed_videos = {row['video_id'] for row in rows}
            logger.info(f"Loaded {len(self.processed_videos)} processed videos")
    
    def setup_schedulers(self):
        """Setup scheduled monitoring jobs"""
        
        schedule_config = self.config['monitoring_schedule']
        
        if not schedule_config['enabled']:
            logger.info("Scheduled monitoring is disabled")
            return
        
        # Add global monitoring job
        if schedule_config['type'] == 'interval':
            self.scheduler.add_job(
                self.check_all_channels,
                trigger=IntervalTrigger(minutes=schedule_config['interval_minutes']),
                id='global_channel_check',
                name='Global Channel Check',
                misfire_grace_time=60
            )
        else:  # cron
            self.scheduler.add_job(
                self.check_all_channels,
                trigger=CronTrigger.from_crontab(schedule_config['cron_expression']),
                id='global_channel_check',
                name='Global Channel Check'
            )
        
        # Add individual channel jobs if they have custom intervals
        for channel in self.config['channels']:
            if channel.get('enabled') and channel.get('check_interval_minutes'):
                self.scheduler.add_job(
                    self.check_single_channel,
                    trigger=IntervalTrigger(minutes=channel['check_interval_minutes']),
                    args=[channel],
                    id=f"check_{channel['channel_id']}",
                    name=f"Check {channel['channel_name']}",
                    misfire_grace_time=60
                )
        
        logger.info(f"Scheduled {len(self.scheduler.get_jobs())} monitoring jobs")
    
    async def check_all_channels(self):
        """Check all enabled channels for new videos"""
        
        logger.info("Starting global channel check")
        
        enabled_channels = [c for c in self.config['channels'] if c.get('enabled', True)]
        
        # Check channels concurrently
        tasks = [self.check_single_channel(channel) for channel in enabled_channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Summarize results
        total_new = sum(r for r in results if isinstance(r, int))
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"Channel check complete: {total_new} new videos, {errors} errors")
        
        # Send notification if configured
        if total_new > 0 and self.config['global_settings'].get('notification_webhook'):
            await self.send_notification(f"Found {total_new} new videos to process")
    
    async def check_single_channel(self, channel: Dict) -> int:
        """Check a single channel for new videos"""
        
        channel_id = channel['channel_id']
        channel_name = channel.get('channel_name', channel_id)
        
        # Rate limiting
        last_check = self.last_check.get(channel_id, datetime.min)
        if (datetime.now() - last_check).seconds < self.min_check_interval:
            logger.debug(f"Skipping {channel_name} - checked too recently")
            return 0
        
        logger.info(f"Checking channel: {channel_name}")
        
        try:
            # Get new videos
            if self.config['global_settings'].get('use_rss_feed', True):
                new_videos = await self.get_videos_from_rss(channel_id)
            else:
                new_videos = await self.get_videos_from_api(channel_id)
            
            # Apply filters
            filtered_videos = self.apply_filters(new_videos, channel.get('filters', {}))
            
            # Remove already processed
            new_videos_to_process = [
                v for v in filtered_videos 
                if v['video_id'] not in self.processed_videos
            ]
            
            if new_videos_to_process:
                logger.info(f"Found {len(new_videos_to_process)} new videos in {channel_name}")
                
                # Store in database
                await self.store_discovered_videos(channel, new_videos_to_process)
                
                # Queue for processing if auto_process is enabled
                if channel.get('auto_process', True):
                    await self.queue_videos_for_processing(new_videos_to_process, channel)
            
            self.last_check[channel_id] = datetime.now()
            return len(new_videos_to_process)
            
        except Exception as e:
            logger.error(f"Error checking channel {channel_name}: {e}")
            return 0
    
    async def get_videos_from_rss(self, channel_id: str) -> List[Dict]:
        """Get recent videos from YouTube RSS feed"""
        
        feed_url = f"{self.youtube_rss_base}{channel_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url) as response:
                content = await response.text()
        
        # Parse RSS feed
        feed = feedparser.parse(content)
        
        videos = []
        max_videos = self.config['global_settings'].get('max_videos_per_check', 10)
        
        for entry in feed.entries[:max_videos]:
            video_id = entry.yt_videoid if hasattr(entry, 'yt_videoid') else entry.link.split('v=')[1]
            
            videos.append({
                'video_id': video_id,
                'title': entry.title,
                'url': entry.link,
                'published': datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%S%z'),
                'author': entry.get('author', ''),
                'description': entry.get('summary', '')
            })
        
        return videos
    
    async def get_videos_from_api(self, channel_id: str) -> List[Dict]:
        """Get videos using YouTube API (requires API key)"""
        
        api_key = self.config['global_settings'].get('youtube_api_key')
        if not api_key:
            logger.error("YouTube API key not configured")
            return []
        
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'maxResults': self.config['global_settings'].get('max_videos_per_check', 10),
            'order': 'date',
            'type': 'video',
            'key': api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
        
        videos = []
        for item in data.get('items', []):
            snippet = item['snippet']
            videos.append({
                'video_id': item['id']['videoId'],
                'title': snippet['title'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'published': datetime.strptime(snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'),
                'author': snippet['channelTitle'],
                'description': snippet['description'],
                'thumbnail': snippet['thumbnails'].get('high', {}).get('url')
            })
        
        return videos
    
    def apply_filters(self, videos: List[Dict], filters: Dict) -> List[Dict]:
        """Apply filters to video list"""
        
        filtered = []
        
        for video in videos:
            # Check age filter
            if 'max_age_days' in filters:
                age = datetime.now(video['published'].tzinfo) - video['published']
                if age.days > filters['max_age_days']:
                    continue
            
            # Check title keywords
            if 'title_keywords' in filters and filters['title_keywords']:
                if not any(kw.lower() in video['title'].lower() 
                          for kw in filters['title_keywords']):
                    continue
            
            # Check exclude keywords
            if 'exclude_keywords' in filters:
                if any(kw.lower() in video['title'].lower() 
                      for kw in filters['exclude_keywords']):
                    continue
            
            filtered.append(video)
        
        return filtered
    
    async def store_discovered_videos(self, channel: Dict, videos: List[Dict]):
        """Store discovered videos in database"""
        
        async with self.db_pool.acquire() as conn:
            for video in videos:
                await conn.execute("""
                    INSERT INTO pmoves.channel_monitoring 
                    (channel_id, channel_name, video_id, video_title, video_url, 
                     published_at, priority, tags, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (channel_id, video_id) DO NOTHING
                """, 
                channel['channel_id'],
                channel.get('channel_name'),
                video['video_id'],
                video['title'],
                video['url'],
                video['published'],
                channel.get('priority', 0),
                channel.get('tags', []),
                json.dumps({
                    'description': video.get('description', ''),
                    'author': video.get('author', ''),
                    'thumbnail': video.get('thumbnail', '')
                }))
                
                # Add to processed set
                self.processed_videos.add(video['video_id'])
    
    async def queue_videos_for_processing(self, videos: List[Dict], channel: Dict):
        """Queue videos for processing"""
        
        urls = [v['url'] for v in videos]
        
        # Batch processing if enabled
        if self.config['global_settings'].get('batch_processing'):
            batch_size = self.config['global_settings'].get('batch_size', 5)
            for i in range(0, len(urls), batch_size):
                batch = urls[i:i + batch_size]
                await self.send_to_queue(batch, channel.get('priority', 0))
        else:
            await self.send_to_queue(urls, channel.get('priority', 0))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def send_to_queue(self, urls: List[str], priority: int = 0):
        """Send URLs to processing queue"""
        
        async with aiohttp.ClientSession() as session:
            payload = {
                'urls': urls,
                'priority': priority,
                'source': 'channel_monitor'
            }
            
            async with session.post(self.queue_api, json=payload) as response:
                result = await response.json()
                logger.info(f"Queued {len(urls)} videos: {result}")
    
    async def send_notification(self, message: str):
        """Send notification via webhook"""
        
        webhook_url = self.config['global_settings'].get('notification_webhook')
        if not webhook_url:
            return
        
        async with aiohttp.ClientSession() as session:
            payload = {
                'text': f"PMOVES Channel Monitor: {message}",
                'timestamp': datetime.now().isoformat()
            }
            
            try:
                await session.post(webhook_url, json=payload)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
    
    async def get_monitoring_stats(self) -> Dict:
        """Get monitoring statistics"""
        
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_discovered,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed,
                    COUNT(DISTINCT channel_id) as monitored_channels,
                    MIN(discovered_at) as monitoring_since,
                    MAX(discovered_at) as last_discovery
                FROM pmoves.channel_monitoring
            """)
            
            recent_videos = await conn.fetch("""
                SELECT video_id, video_title, channel_name, discovered_at
                FROM pmoves.channel_monitoring
                ORDER BY discovered_at DESC
                LIMIT 10
            """)
        
        return {
            'statistics': dict(stats),
            'recent_discoveries': [dict(r) for r in recent_videos],
            'active_channels': len([c for c in self.config['channels'] if c.get('enabled')]),
            'scheduled_jobs': len(self.scheduler.get_jobs())
        }
    
    async def add_channel(self, channel_url: str) -> Dict:
        """Add a new channel to monitor"""
        
        # Extract channel ID from URL
        channel_id = self.extract_channel_id(channel_url)
        if not channel_id:
            raise ValueError("Invalid YouTube channel URL")
        
        # Get channel info
        channel_info = await self.get_channel_info(channel_id)
        
        # Add to config
        new_channel = {
            'channel_id': channel_id,
            'channel_name': channel_info.get('title', 'Unknown'),
            'enabled': True,
            'check_interval_minutes': 60,
            'auto_process': True,
            'filters': {
                'exclude_keywords': ['#shorts']
            },
            'priority': 1,
            'tags': []
        }
        
        # Check if already exists
        existing = [c for c in self.config['channels'] if c['channel_id'] == channel_id]
        if existing:
            return {'status': 'exists', 'channel': existing[0]}
        
        self.config['channels'].append(new_channel)
        
        # Save config
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Add scheduled job
        self.scheduler.add_job(
            self.check_single_channel,
            trigger=IntervalTrigger(minutes=60),
            args=[new_channel],
            id=f"check_{channel_id}",
            name=f"Check {channel_info.get('title', channel_id)}"
        )
        
        return {'status': 'added', 'channel': new_channel}
    
    def extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats"""
        
        import re
        
        patterns = [
            r'youtube\.com/channel/([A-Za-z0-9_-]+)',
            r'youtube\.com/c/([A-Za-z0-9_-]+)',
            r'youtube\.com/user/([A-Za-z0-9_-]+)',
            r'youtube\.com/@([A-Za-z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                # For @handle, need to resolve to channel ID
                if '/@' in url:
                    return self.resolve_handle_to_channel_id(match.group(1))
                return match.group(1)
        
        return None
    
    async def get_channel_info(self, channel_id: str) -> Dict:
        """Get channel information"""
        
        # Use yt-dlp to get channel info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(
                    f"https://www.youtube.com/channel/{channel_id}", 
                    download=False
                )
                return {
                    'title': info.get('uploader', ''),
                    'description': info.get('description', ''),
                    'subscriber_count': info.get('subscriber_count', 0)
                }
            except:
                return {}
    
    async def start(self):
        """Start the monitoring service"""
        
        await self.initialize()
        
        # Check on startup if configured
        if self.config['global_settings'].get('check_on_startup'):
            await self.check_all_channels()
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info("Channel monitoring service started")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down channel monitor")
            await self.shutdown()
    
    async def shutdown(self):
        """Cleanup connections"""
        
        self.scheduler.shutdown()
        await self.redis_client.close()
        await self.db_pool.close()


# FastAPI Integration
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="PMOVES Channel Monitor API")

monitor = YouTubeChannelMonitor()

class AddChannelRequest(BaseModel):
    url: str
    auto_process: bool = True
    check_interval: int = 60

@app.on_event("startup")
async def startup():
    await monitor.initialize()
    monitor.scheduler.start()

@app.get("/api/monitor/stats")
async def get_monitoring_stats():
    """Get monitoring statistics"""
    return await monitor.get_monitoring_stats()

@app.post("/api/monitor/channel")
async def add_channel(request: AddChannelRequest):
    """Add a new channel to monitor"""
    try:
        result = await monitor.add_channel(request.url)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/monitor/check-now")
async def trigger_check():
    """Manually trigger channel check"""
    asyncio.create_task(monitor.check_all_channels())
    return {"status": "checking"}

@app.get("/api/monitor/channels")
async def get_monitored_channels():
    """Get list of monitored channels"""
    return monitor.config['channels']


if __name__ == "__main__":
    # Run standalone
    monitor = YouTubeChannelMonitor()
    asyncio.run(monitor.start())
