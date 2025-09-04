# Create comprehensive AI audio/video analysis integration for the media stack

enhanced_integration = """# Enhanced AI Audio/Video Analysis Integration

## 🎯 Latest AI Models Suite (August 2025)

### **Audio Analysis Models**

#### **Speech-to-Text & Transcription**
1. **Whisper Large v3 Turbo** (OpenAI) - Latest flagship model
   - Best accuracy for multilingual transcription
   - 70x realtime processing with optimizations
   - Supports 99 languages

2. **SeaLLMs-Audio-7B** - Multimodal audio-language model
   - Real-time audio conversation analysis
   - Audio + text reasoning capabilities
   - Southeast Asian language support

3. **WhisperX** - Enhanced Whisper with diarization
   - Word-level timestamps
   - Built-in speaker diarization
   - VAD preprocessing

#### **Speaker Diarization Models**
1. **Pyannote Audio** - Industry standard
   - Advanced speaker embedding models
   - Real-time diarization capabilities
   - Integration with Whisper

2. **NVIDIA Sortformer** - Next-gen diarization
   - Transformer-based architecture
   - Superior accuracy on complex audio
   - Optimized for GPU acceleration

3. **DiCoW** - Diarization-conditioned Whisper
   - Direct integration with Whisper
   - No separate embedding models needed
   - End-to-end optimization

### **Video Analysis Models**

#### **Computer Vision Models**
1. **YOLO v11** - Real-time object detection
   - Ultra-fast inference
   - High accuracy on video streams
   - Multi-object tracking

2. **OpenCV DNN** - Comprehensive video processing
   - Frame extraction and analysis
   - Motion detection
   - Scene change detection

3. **Vision Transformers (ViT)** - Advanced image understanding
   - Scene classification
   - Content categorization
   - Visual reasoning

#### **Multimodal Video Models**
1. **Flamingo (DeepMind)** - Video-language understanding
   - Few-shot learning on video tasks
   - Temporal reasoning
   - Context-aware video analysis

2. **CLIP** - Vision-language model
   - Zero-shot video classification
   - Scene understanding
   - Content-based retrieval

## 🔧 Enhanced Docker Configuration"""

# Create enhanced Docker Compose with all AI models
enhanced_docker_compose = '''
version: '3.8'

networks:
  media-stack:
    driver: bridge
  supabase-network:
    external: true
    name: supabase_default

services:
  # Original Jellyfin service remains the same...
  jellyfin:
    image: lscr.io/linuxserver/jellyfin:latest
    container_name: jellyfin
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - JELLYFIN_PublishedServerUrl=http://localhost:8096
    volumes:
      - ./jellyfin/config:/config
      - ./jellyfin/cache:/cache
      - ./media/music:/media/music
      - ./media/videos:/media/videos
      - ./media/podcasts:/media/podcasts
      - ./downloads:/downloads  # For yt-dlp downloads
      - ./output:/output
    ports:
      - "8096:8096"
    networks:
      - media-stack
    restart: unless-stopped

  # Enhanced Audio Analysis Service with Multiple Models
  audio-ai-service:
    build:
      context: ./audio-ai-service
      dockerfile: Dockerfile
    container_name: audio-ai-service
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - TRANSFORMERS_CACHE=/app/cache
      - HF_TOKEN=${HF_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./media:/app/media
      - ./downloads:/app/downloads
      - ./output:/app/output
      - ./models:/app/cache
      - /tmp:/tmp
    ports:
      - "8001:8001"
    networks:
      - media-stack
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          memory: 16G
        reservations:
          memory: 8G

  # Video Analysis Service
  video-ai-service:
    build:
      context: ./video-ai-service
      dockerfile: Dockerfile
    container_name: video-ai-service
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - TRANSFORMERS_CACHE=/app/cache
      - HF_TOKEN=${HF_TOKEN}
      - OPENCV_LOG_LEVEL=ERROR
    volumes:
      - ./media:/app/media
      - ./downloads:/app/downloads
      - ./output:/app/output
      - ./models:/app/cache
      - /tmp:/tmp
    ports:
      - "8002:8002"
    networks:
      - media-stack
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # YouTube Downloader Service with yt-dlp
  ytdl-service:
    build:
      context: ./ytdl-service
      dockerfile: Dockerfile
    container_name: ytdl-service
    environment:
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - MAX_CONCURRENT_DOWNLOADS=3
      - DOWNLOAD_QUALITY=best
    volumes:
      - ./downloads:/app/downloads
      - ./output:/app/output
      - ./logs:/app/logs
    ports:
      - "8003:8003"
    networks:
      - media-stack
    restart: unless-stopped

  # Entity Extraction Service with LangExtract
  entity-service:
    build:
      context: ./entity-service
      dockerfile: Dockerfile
    container_name: entity-service
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - LANGEXTRACT_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./output:/app/output
      - ./processed:/app/processed
    ports:
      - "8004:8004"
    networks:
      - media-stack
    restart: unless-stopped

  # Orchestrator Service
  orchestrator:
    build:
      context: ./orchestrator
      dockerfile: Dockerfile
    container_name: orchestrator
    environment:
      - JELLYFIN_URL=http://jellyfin:8096
      - AUDIO_AI_URL=http://audio-ai-service:8001
      - VIDEO_AI_URL=http://video-ai-service:8002
      - YTDL_URL=http://ytdl-service:8003
      - ENTITY_URL=http://entity-service:8004
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - NEO4J_URI=bolt://neo4j:7687
    volumes:
      - ./downloads:/app/downloads
      - ./output:/app/output
      - ./processed:/app/processed
    ports:
      - "8000:8000"
    networks:
      - media-stack
      - supabase-network
    depends_on:
      - audio-ai-service
      - video-ai-service
      - ytdl-service
      - entity-service
    restart: unless-stopped

  # Neo4j and Redis services remain the same...
  neo4j:
    image: neo4j:5.15
    container_name: neo4j
    environment:
      - NEO4J_AUTH=neo4j/mediapassword123
      - NEO4J_dbms_security_procedures_unrestricted=gds.*,apoc.*
      - NEO4J_dbms_security_procedures_allowlist=gds.*,apoc.*
      - NEO4J_dbms_memory_heap_max__size=4G
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
      - ./neo4j/plugins:/plugins
    ports:
      - "7474:7474"
      - "7687:7687"
    networks:
      - media-stack
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: redis
    command: redis-server --appendonly yes
    volumes:
      - ./redis/data:/data
    ports:
      - "6379:6379"
    networks:
      - media-stack
    restart: unless-stopped

volumes:
  jellyfin-config:
  neo4j-data:
  redis-data:
  downloads:
  models-cache:
'''

print("Enhanced Docker configuration created with:")
print("- Multiple AI model services")
print("- yt-dlp integration")
print("- Entity extraction with LangExtract")
print("- GPU acceleration support")
print("- Orchestrator for workflow management")

with open('docker-compose-enhanced.yml', 'w') as f:
    f.write(enhanced_docker_compose)