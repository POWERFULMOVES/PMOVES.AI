# docker-compose.yml for YouTube RAG Processing Stack
version: '3.8'

services:
  # n8n workflow automation
  n8n:
    image: n8nio/n8n:latest
    container_name: youtube-rag-n8n
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_WEBHOOK_URL=https://${DOMAIN}/n8n/
      - NODE_ENV=production
      - WEBHOOK_TUNNEL_URL=https://${DOMAIN}/n8n/
    volumes:
      - n8n_data:/home/node/.n8n
      - ./workflows:/workflows
    ports:
      - "5678:5678"
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=application"
      - "coolify.name=n8n-rag"

  # MCP Docker server for YouTube tools
  mcp-docker:
    build:
      context: ./mcp-docker
      dockerfile: Dockerfile
    container_name: youtube-mcp-server
    environment:
      - PYTHONUNBUFFERED=1
      - HUGGINGFACE_API_KEY=${HUGGINGFACE_API_KEY}
    volumes:
      - ./transcripts:/data/transcripts
      - ./scripts:/scripts
    ports:
      - "8080:8080"
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=service"
      - "coolify.name=mcp-server"

  # Batch processor service
  batch-processor:
    build:
      context: ./batch-processor
      dockerfile: Dockerfile
    container_name: youtube-batch-processor
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - HUGGINGFACE_API_KEY=${HUGGINGFACE_API_KEY}
      - N8N_WEBHOOK_URL=http://n8n:5678/webhook/youtube-rag-pipeline
      - MCP_SERVER_URL=http://mcp-docker:8080
      - BATCH_SIZE=5
      - MAX_WORKERS=3
    volumes:
      - ./queue:/queue
      - ./processed:/processed
      - ./logs:/logs
    depends_on:
      - n8n
      - mcp-docker
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=worker"
      - "coolify.name=batch-processor"

  # Redis for queue management
  redis:
    image: redis:7-alpine
    container_name: youtube-rag-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=database"
      - "coolify.name=redis-queue"

  # Monitoring with Prometheus
  prometheus:
    image: prom/prometheus:latest
    container_name: youtube-rag-monitoring
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=monitoring"

networks:
  rag_network:
    driver: bridge

volumes:
  n8n_data:
  redis_data:
  prometheus_data:

---
# Dockerfile for MCP Docker Server
# File: mcp-docker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY mcp_server.py .
COPY coca_processor.py .

# Create data directories
RUN mkdir -p /data/transcripts /data/embeddings /data/logs

EXPOSE 8080

CMD ["python", "mcp_server.py"]

---
# requirements.txt for MCP Docker
aiohttp==3.9.1
asyncio==3.4.3
fastapi==0.108.0
uvicorn==0.25.0
yt-dlp==2024.1.1
sentence-transformers==2.2.2
numpy==1.24.3
pandas==2.0.3
redis==5.0.1
psycopg2-binary==2.9.9
supabase==2.3.0
pydantic==2.5.0
youtube-transcript-api==0.6.1
tenacity==8.2.3

---
# Dockerfile for Batch Processor
# File: batch-processor/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy batch processor code
COPY batch_processor.py .
COPY queue_manager.py .
COPY config.py .

# Create necessary directories
RUN mkdir -p /queue /processed /logs

EXPOSE 8081

CMD ["python", "batch_processor.py"]

---
# batch_processor.py - Main batch processing logic
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict
import aiohttp
from pathlib import Path
import redis
import os
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/batch_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YouTubeBatchProcessor:
    """
    Batch processor for YouTube videos with queue management
    Integrates with n8n, MCP tools, and Supabase
    """
    
    def __init__(self):
        self.n8n_webhook = os.getenv('N8N_WEBHOOK_URL')
        self.mcp_server = os.getenv('MCP_SERVER_URL')
        self.batch_size = int(os.getenv('BATCH_SIZE', 5))
        self.max_workers = int(os.getenv('MAX_WORKERS', 3))
        
        # Redis for queue management
        self.redis_client = redis.Redis(
            host='redis',
            port=6379,
            decode_responses=True
        )
        
        # Queue names
        self.pending_queue = 'youtube:pending'
        self.processing_queue = 'youtube:processing'
        self.completed_queue = 'youtube:completed'
        self.failed_queue = 'youtube:failed'
        
    async def start(self):
        """Start the batch processor"""
        logger.info("Starting YouTube batch processor...")
        
        # Create worker tasks
        workers = [
            asyncio.create_task(self.worker(worker_id))
            for worker_id in range(self.max_workers)
        ]
        
        # Monitor task
        monitor_task = asyncio.create_task(self.monitor_queues())
        
        # Wait for all tasks
        await asyncio.gather(*workers, monitor_task)
    
    async def worker(self, worker_id: int):
        """Worker process that handles video processing"""
        logger.info(f"Worker {worker_id} started")
        
        while True:
            try:
                # Get batch from queue
                batch = self.get_batch_from_queue()
                
                if batch:
                    logger.info(f"Worker {worker_id} processing batch of {len(batch)} videos")
                    await self.process_batch(batch, worker_id)
                else:
                    # No work available, wait
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(10)
    
    def get_batch_from_queue(self) -> List[str]:
        """Get a batch of URLs from the pending queue"""
        batch = []
        
        for _ in range(self.batch_size):
            # Move from pending to processing queue
            url = self.redis_client.rpoplpush(
                self.pending_queue,
                self.processing_queue
            )
            
            if url:
                batch.append(url)
            else:
                break
        
        return batch
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def process_batch(self, urls: List[str], worker_id: int):
        """Process a batch of YouTube URLs"""
        
        for url in urls:
            try:
                # Step 1: Get video metadata
                metadata = await self.get_video_metadata(url)
                
                # Step 2: Get transcript
                transcript = await self.get_transcript(url)
                
                # Step 3: Process with CoCa
                processed_data = await self.process_with_coca(
                    url, metadata, transcript
                )
                
                # Step 4: Trigger n8n workflow
                await self.trigger_n8n_workflow(processed_data)
                
                # Move to completed queue
                self.redis_client.lrem(self.processing_queue, 1, url)
                self.redis_client.lpush(self.completed_queue, url)
                
                # Save processed data
                self.save_processed_data(url, processed_data)
                
                logger.info(f"Worker {worker_id} completed: {url}")
                
            except Exception as e:
                logger.error(f"Worker {worker_id} failed processing {url}: {e}")
                
                # Move to failed queue
                self.redis_client.lrem(self.processing_queue, 1, url)
                self.redis_client.lpush(self.failed_queue, json.dumps({
                    'url': url,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }))
    
    async def get_video_metadata(self, url: str) -> Dict:
        """Get video metadata from MCP server"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.mcp_server}/mcp/docker/get_video_info",
                json={"url": url}
            ) as response:
                return await response.json()
    
    async def get_transcript(self, url: str) -> Dict:
        """Get transcript from MCP server"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.mcp_server}/mcp/docker/get_transcript",
                json={"url": url, "lang": "en"}
            ) as response:
                return await response.json()
    
    async def process_with_coca(self, 
                               url: str, 
                               metadata: Dict, 
                               transcript: Dict) -> Dict:
        """Process with CoCa embeddings"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.mcp_server}/coca/process",
                json={
                    "url": url,
                    "metadata": metadata,
                    "transcript": transcript
                }
            ) as response:
                return await response.json()
    
    async def trigger_n8n_workflow(self, data: Dict):
        """Trigger n8n workflow with processed data"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.n8n_webhook,
                json={"data": data}
            ) as response:
                return await response.json()
    
    def save_processed_data(self, url: str, data: Dict):
        """Save processed data to disk"""
        video_id = self.extract_video_id(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = f"/processed/{video_id}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'url': url,
                'processed_at': datetime.now().isoformat(),
                'data': data
            }, f, indent=2)
    
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from URL"""
        import re
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return match.group(1) if match else 'unknown'
    
    async def monitor_queues(self):
        """Monitor queue status"""
        while True:
            pending = self.redis_client.llen(self.pending_queue)
            processing = self.redis_client.llen(self.processing_queue)
            completed = self.redis_client.llen(self.completed_queue)
            failed = self.redis_client.llen(self.failed_queue)
            
            logger.info(
                f"Queue Status - Pending: {pending}, "
                f"Processing: {processing}, "
                f"Completed: {completed}, "
                f"Failed: {failed}"
            )
            
            # Write metrics for monitoring
            with open('/logs/metrics.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'queues': {
                        'pending': pending,
                        'processing': processing,
                        'completed': completed,
                        'failed': failed
                    }
                }, f)
            
            await asyncio.sleep(30)  # Check every 30 seconds


# Queue Manager API
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="YouTube Batch Queue Manager")

class QueueItem(BaseModel):
    urls: List[str]
    priority: Optional[int] = 0
    metadata: Optional[Dict] = {}

@app.post("/queue/add")
async def add_to_queue(item: QueueItem):
    """Add URLs to processing queue"""
    processor = YouTubeBatchProcessor()
    
    for url in item.urls:
        if item.priority > 0:
            # Add to front of queue for high priority
            processor.redis_client.lpush(processor.pending_queue, url)
        else:
            # Add to end of queue
            processor.redis_client.rpush(processor.pending_queue, url)
    
    return {
        "status": "success",
        "added": len(item.urls),
        "queue_size": processor.redis_client.llen(processor.pending_queue)
    }

@app.get("/queue/status")
async def get_queue_status():
    """Get current queue status"""
    processor = YouTubeBatchProcessor()
    
    return {
        "pending": processor.redis_client.llen(processor.pending_queue),
        "processing": processor.redis_client.llen(processor.processing_queue),
        "completed": processor.redis_client.llen(processor.completed_queue),
        "failed": processor.redis_client.llen(processor.failed_queue)
    }

@app.get("/queue/failed")
async def get_failed_items():
    """Get failed items from queue"""
    processor = YouTubeBatchProcessor()
    
    failed_items = processor.redis_client.lrange(
        processor.failed_queue, 0, -1
    )
    
    return {
        "failed_items": [json.loads(item) for item in failed_items]
    }

@app.post("/queue/retry")
async def retry_failed_items():
    """Retry all failed items"""
    processor = YouTubeBatchProcessor()
    
    count = 0
    while True:
        item = processor.redis_client.rpop(processor.failed_queue)
        if not item:
            break
        
        failed_data = json.loads(item)
        processor.redis_client.lpush(processor.pending_queue, failed_data['url'])
        count += 1
    
    return {
        "status": "success",
        "retried": count
    }

if __name__ == "__main__":
    # Run the batch processor
    processor = YouTubeBatchProcessor()
    asyncio.run(processor.start())

---
# PowerShell script for Windows management
# File: manage-youtube-rag.ps1

param(
    [Parameter(Position=0)]
    [ValidateSet('start', 'stop', 'status', 'add-urls', 'check-queue', 'deploy')]
    [string]$Action = 'status',
    
    [string[]]$Urls = @(),
    [string]$File = "",
    [switch]$Production
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectPath = $PSScriptRoot
$DockerComposePath = Join-Path $ProjectPath "docker-compose.yml"
$LogPath = Join-Path $ProjectPath "logs"
$QueueApiUrl = "http://localhost:8081"

# Ensure log directory exists
if (!(Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "$timestamp [$Level] $Message"
    Write-Host $logMessage -ForegroundColor $(
        switch ($Level) {
            "ERROR" { "Red" }
            "WARNING" { "Yellow" }
            "SUCCESS" { "Green" }
            default { "White" }
        }
    )
    Add-Content -Path (Join-Path $LogPath "powershell.log") -Value $logMessage
}

function Start-Services {
    Write-Log "Starting YouTube RAG services..."
    
    # Check Docker
    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Log "Docker is not installed or not in PATH" "ERROR"
        exit 1
    }
    
    # Start services
    docker-compose -f $DockerComposePath up -d
    
    # Wait for services to be healthy
    Write-Log "Waiting for services to be ready..."
    Start-Sleep -Seconds 10
    
    # Check service health
    $services = docker-compose -f $DockerComposePath ps --format json | ConvertFrom-Json
    
    foreach ($service in $services) {
        if ($service.State -eq "running") {
            Write-Log "$($service.Service) is running" "SUCCESS"
        } else {
            Write-Log "$($service.Service) is not running: $($service.State)" "WARNING"
        }
    }
}

function Stop-Services {
    Write-Log "Stopping YouTube RAG services..."
    docker-compose -f $DockerComposePath down
    Write-Log "Services stopped" "SUCCESS"
}

function Get-ServiceStatus {
    Write-Log "Checking service status..."
    
    # Get Docker containers status
    docker-compose -f $DockerComposePath ps
    
    # Get queue status from API
    try {
        $response = Invoke-RestMethod -Uri "$QueueApiUrl/queue/status" -Method Get
        Write-Log "Queue Status:" "INFO"
        Write-Log "  Pending: $($response.pending)" "INFO"
        Write-Log "  Processing: $($response.processing)" "INFO"
        Write-Log "  Completed: $($response.completed)" "INFO"
        Write-Log "  Failed: $($response.failed)" "INFO"
    } catch {
        Write-Log "Could not get queue status. Is the batch processor running?" "WARNING"
    }
}

function Add-UrlsToQueue {
    param([string[]]$VideoUrls)
    
    if ($VideoUrls.Count -eq 0) {
        Write-Log "No URLs provided" "ERROR"
        return
    }
    
    Write-Log "Adding $($VideoUrls.Count) URLs to queue..."
    
    $body = @{
        urls = $VideoUrls
        priority = 0
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$QueueApiUrl/queue/add" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body
        
        Write-Log "Successfully added $($response.added) URLs" "SUCCESS"
        Write-Log "Queue size: $($response.queue_size)" "INFO"
    } catch {
        Write-Log "Failed to add URLs: $_" "ERROR"
    }
}

function Import-UrlsFromFile {
    param([string]$FilePath)
    
    if (!(Test-Path $FilePath)) {
        Write-Log "File not found: $FilePath" "ERROR"
        return @()
    }
    
    $urls = Get-Content $FilePath | Where-Object { $_ -match "youtube.com|youtu.be" }
    Write-Log "Found $($urls.Count) valid URLs in file" "INFO"
    
    return $urls
}

function Deploy-ToCoolify {
    Write-Log "Deploying to Coolify..." "INFO"
    
    # Create deployment package
    $deployPath = Join-Path $ProjectPath "deploy"
    if (!(Test-Path $deployPath)) {
        New-Item -ItemType Directory -Path $deployPath | Out-Null
    }
    
    # Copy necessary files
    $filesToDeploy = @(
        "docker-compose.yml",
        "mcp-docker/*",
        "batch-processor/*",
        "monitoring/*",
        ".env.example"
    )
    
    foreach ($file in $filesToDeploy) {
        $source = Join-Path $ProjectPath $file
        $dest = Join-Path $deployPath $file
        
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination $dest -Recurse -Force
            Write-Log "Copied $file" "INFO"
        }
    }
    
    # Create deployment script for Coolify
    $deployScript = @"
#!/bin/bash
# Coolify deployment script

# Build and deploy services
docker-compose build
docker-compose up -d

# Wait for services
sleep 10

# Check health
docker-compose ps

echo "Deployment complete!"
"@
    
    Set-Content -Path (Join-Path $deployPath "deploy.sh") -Value $deployScript
    
    Write-Log "Deployment package created at $deployPath" "SUCCESS"
    Write-Log "Upload this to Coolify and run deploy.sh" "INFO"
}

# Main execution
switch ($Action) {
    'start' {
        Start-Services
    }
    'stop' {
        Stop-Services
    }
    'status' {
        Get-ServiceStatus
    }
    'add-urls' {
        if ($File) {
            $Urls = Import-UrlsFromFile -FilePath $File
        }
        
        if ($Urls.Count -gt 0) {
            Add-UrlsToQueue -VideoUrls $Urls
        } else {
            Write-Log "No URLs to add. Use -Urls or -File parameter" "ERROR"
        }
    }
    'check-queue' {
        try {
            $response = Invoke-RestMethod -Uri "$QueueApiUrl/queue/failed" -Method Get
            
            if ($response.failed_items.Count -gt 0) {
                Write-Log "Failed items:" "WARNING"
                foreach ($item in $response.failed_items) {
                    Write-Log "  $($item.url): $($item.error)" "WARNING"
                }
                
                $retry = Read-Host "Retry failed items? (y/n)"
                if ($retry -eq 'y') {
                    Invoke-RestMethod -Uri "$QueueApiUrl/queue/retry" -Method Post
                    Write-Log "Failed items re-queued" "SUCCESS"
                }
            } else {
                Write-Log "No failed items" "SUCCESS"
            }
        } catch {
            Write-Log "Could not check failed items: $_" "ERROR"
        }
    }
    'deploy' {
        Deploy-ToCoolify
    }
}

# Example usage instructions
if ($Action -eq 'status') {
    Write-Host "`nUsage Examples:" -ForegroundColor Cyan
    Write-Host "  Start services:        .\manage-youtube-rag.ps1 start"
    Write-Host "  Stop services:         .\manage-youtube-rag.ps1 stop"
    Write-Host "  Check status:          .\manage-youtube-rag.ps1 status"
    Write-Host "  Add URLs:              .\manage-youtube-rag.ps1 add-urls -Urls 'url1','url2'"
    Write-Host "  Add from file:         .\manage-youtube-rag.ps1 add-urls -File urls.txt"
    Write-Host "  Check failed queue:    .\manage-youtube-rag.ps1 check-queue"
    Write-Host "  Deploy to Coolify:     .\manage-youtube-rag.ps1 deploy"
}
