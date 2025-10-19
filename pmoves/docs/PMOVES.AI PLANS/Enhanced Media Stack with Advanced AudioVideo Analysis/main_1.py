
# YouTube Downloader Service with yt-dlp
import asyncio
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
import tempfile
import subprocess

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
import uvicorn
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import aiofiles

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Downloader Service", version="2.0.0")

class DownloadRequest(BaseModel):
    url: str
    download_type: str = "audio"  # audio, video, both
    quality: str = "best"
    format: str = "auto"  # mp3, mp4, auto
    extract_metadata: bool = True
    extract_subtitles: bool = True
    language_preference: Optional[List[str]] = ["en", "auto"]

class DownloadStatus(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0
    url: str
    file_paths: List[str] = []
    metadata: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

class YouTubeDownloader:
    def __init__(self):
        self.download_dir = Path("/app/downloads")
        self.download_dir.mkdir(exist_ok=True)
        self.tasks = {}  # Store task status
        self.executor = ThreadPoolExecutor(max_workers=3)

    def get_ydl_opts(self, request: DownloadRequest, output_path: str) -> Dict[str, Any]:
        """Generate yt-dlp options based on request"""

        # Base options
        opts = {
            'outtmpl': str(output_path / '%(title)s.%(ext)s'),
            'writesubtitles': request.extract_subtitles,
            'writeautomaticsub': request.extract_subtitles,
            'subtitleslangs': request.language_preference,
            'ignoreerrors': True,
            'no_warnings': False,
            'extractflat': False,
        }

        # Configure based on download type
        if request.download_type == "audio":
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': request.format if request.format != "auto" else 'mp3',
                    'preferredquality': '320' if request.quality == "best" else '192',
                }],
            })
        elif request.download_type == "video":
            if request.quality == "best":
                opts['format'] = 'best[height<=1080]'
            elif request.quality == "medium":
                opts['format'] = 'best[height<=720]'
            elif request.quality == "low":
                opts['format'] = 'best[height<=480]'
            else:
                opts['format'] = 'best'
        elif request.download_type == "both":
            opts['format'] = 'best'
            opts['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
            ]

        return opts

    async def extract_metadata(self, url: str) -> Dict:
        """Extract video metadata without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Clean and structure metadata
                metadata = {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'tags': info.get('tags', []),
                    'categories': info.get('categories', []),
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url'),
                    'extractor': info.get('extractor'),
                    'format_note': info.get('format_note'),
                    'resolution': info.get('resolution'),
                    'fps': info.get('fps'),
                    'vcodec': info.get('vcodec'),
                    'acodec': info.get('acodec'),
                    'filesize': info.get('filesize'),
                }

                # Extract chapter information if available
                if info.get('chapters'):
                    metadata['chapters'] = [
                        {
                            'title': chapter.get('title'),
                            'start_time': chapter.get('start_time'),
                            'end_time': chapter.get('end_time')
                        }
                        for chapter in info['chapters']
                    ]

                return metadata

        except Exception as e:
            logger.error(f"Metadata extraction error: {e}")
            return {'error': str(e)}

    def progress_hook(self, d: Dict, task_id: str):
        """Progress callback for yt-dlp"""
        if task_id not in self.tasks:
            return

        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)

                if total > 0:
                    progress = (downloaded / total) * 100
                    self.tasks[task_id]['progress'] = round(progress, 2)

                self.tasks[task_id]['speed'] = d.get('speed', 0)
                self.tasks[task_id]['eta'] = d.get('eta', 0)

            except (ZeroDivisionError, TypeError):
                pass
        elif d['status'] == 'finished':
            self.tasks[task_id]['progress'] = 100.0
            self.tasks[task_id]['status'] = 'post-processing'
        elif d['status'] == 'error':
            self.tasks[task_id]['status'] = 'error'
            self.tasks[task_id]['error'] = str(d.get('error', 'Unknown error'))

    async def download_content(self, request: DownloadRequest, task_id: str) -> Dict:
        """Download content using yt-dlp"""
        try:
            # Create task-specific directory
            task_dir = self.download_dir / task_id
            task_dir.mkdir(exist_ok=True)

            # Update task status
            self.tasks[task_id]['status'] = 'downloading'

            # Get yt-dlp options
            ydl_opts = self.get_ydl_opts(request, task_dir)
            ydl_opts['progress_hooks'] = [lambda d: self.progress_hook(d, task_id)]

            downloaded_files = []

            def download_thread():
                nonlocal downloaded_files
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # Extract info first
                        info = ydl.extract_info(request.url, download=False)

                        # Store metadata
                        self.tasks[task_id]['metadata'] = {
                            'title': info.get('title'),
                            'duration': info.get('duration'),
                            'uploader': info.get('uploader'),
                            'description': info.get('description', '')[:500],  # Truncate
                            'tags': info.get('tags', []),
                            'upload_date': info.get('upload_date'),
                            'view_count': info.get('view_count'),
                        }

                        # Download the content
                        ydl.download([request.url])

                        # Find downloaded files
                        for file_path in task_dir.rglob('*'):
                            if file_path.is_file() and not file_path.name.startswith('.'):
                                downloaded_files.append(str(file_path))

                except Exception as e:
                    raise e

            # Run download in thread
            await asyncio.get_event_loop().run_in_executor(
                self.executor, download_thread
            )

            # Update task completion
            self.tasks[task_id]['status'] = 'completed'
            self.tasks[task_id]['file_paths'] = downloaded_files
            self.tasks[task_id]['completed_at'] = datetime.now().isoformat()
            self.tasks[task_id]['progress'] = 100.0

            return self.tasks[task_id]

        except Exception as e:
            logger.error(f"Download error for task {task_id}: {e}")
            self.tasks[task_id]['status'] = 'error'
            self.tasks[task_id]['error'] = str(e)
            return self.tasks[task_id]

    async def get_playlist_info(self, url: str) -> Dict:
        """Get playlist information"""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if 'entries' in info:
                    return {
                        'type': 'playlist',
                        'title': info.get('title'),
                        'uploader': info.get('uploader'),
                        'entry_count': len(info['entries']),
                        'entries': [
                            {
                                'id': entry.get('id'),
                                'title': entry.get('title'),
                                'url': entry.get('url'),
                                'duration': entry.get('duration')
                            }
                            for entry in info['entries'][:50]  # Limit to first 50
                        ]
                    }
                else:
                    return {
                        'type': 'single_video',
                        'title': info.get('title'),
                        'duration': info.get('duration')
                    }

        except Exception as e:
            logger.error(f"Playlist info error: {e}")
            return {'error': str(e)}

# Global downloader instance
downloader = YouTubeDownloader()

@app.post("/download")
async def start_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    """Start a download task"""
    task_id = str(uuid.uuid4())

    # Initialize task status
    downloader.tasks[task_id] = DownloadStatus(
        task_id=task_id,
        status="queued",
        url=request.url,
        created_at=datetime.now().isoformat()
    ).dict()

    # Start download in background
    background_tasks.add_task(
        downloader.download_content,
        request,
        task_id
    )

    return {"task_id": task_id, "status": "queued"}

@app.get("/status/{task_id}")
async def get_download_status(task_id: str):
    """Get download status"""
    if task_id not in downloader.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return downloader.tasks[task_id]

@app.get("/metadata")
async def get_metadata(url: str):
    """Get video metadata without downloading"""
    metadata = await downloader.extract_metadata(url)
    return metadata

@app.get("/playlist-info")
async def get_playlist_info(url: str):
    """Get playlist information"""
    info = await downloader.get_playlist_info(url)
    return info

@app.post("/batch-download")
async def batch_download(
    urls: List[str],
    background_tasks: BackgroundTasks,
    download_type: str = "audio",
    quality: str = "best"
):
    """Start multiple downloads"""
    task_ids = []

    for url in urls[:10]:  # Limit to 10 URLs
        request = DownloadRequest(
            url=url,
            download_type=download_type,
            quality=quality
        )

        task_id = str(uuid.uuid4())
        downloader.tasks[task_id] = DownloadStatus(
            task_id=task_id,
            status="queued",
            url=url,
            created_at=datetime.now().isoformat()
        ).dict()

        background_tasks.add_task(
            downloader.download_content,
            request,
            task_id
        )

        task_ids.append(task_id)

    return {"task_ids": task_ids, "status": "queued"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "active_tasks": len([t for t in downloader.tasks.values() if t['status'] in ['queued', 'downloading', 'post-processing']]),
        "total_tasks": len(downloader.tasks),
        "yt_dlp_version": yt_dlp.version.__version__
    }

@app.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a download task"""
    if task_id not in downloader.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    downloader.tasks[task_id]['status'] = 'cancelled'
    return {"message": "Task cancelled"}

@app.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    """List all tasks"""
    tasks = list(downloader.tasks.values())

    if status:
        tasks = [t for t in tasks if t['status'] == status]

    return {"tasks": tasks}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, log_level="info")
