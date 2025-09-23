# Jellyfin AI-Powered Media Stack with Supabase & Neo4j

Complete Docker-based solution for hosting media, analyzing content with AI, and creating YouTube content from your music library.

## 🏗️ Architecture Overview

This stack integrates:
- **Jellyfin**: Media server for streaming music, videos, and podcasts
- **Supabase**: Backend database for user data and media metadata
- **Neo4j**: Graph database for content relationships and recommendations
- **Qwen Audio**: AI model for audio content analysis
- **API Gateway**: RESTful API for external integrations
- **Redis**: Caching and job queue management

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- 8GB+ RAM recommended
- 100GB+ storage for media files

### Installation


1. **Clone/Download the configuration files**
2. **Ensure the shared Docker network exists** (needed to reach the PMOVES Supabase stack):
   ```bash
   docker network create pmoves-net 2>/dev/null || true
   ```

3. **Run the setup script:**

1. **Clone/Download the configuration files**
   - If you're running this stack without the core PMOVES services, create the shared network first:
     ```bash
     docker network create pmoves-net
     ```
     (Safe to rerun; Docker will reuse the network if it already exists.)
2. **Run the setup script:**

   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```


4. **Configure environment variables:**
   ```bash
   cp .env.template .env
   # Edit .env with your actual credentials
   ```

5. **Start the stack:**
   ```bash
   docker-compose up -d
   ```


3. **Configure environment variables:**
   ```bash
   cp .env.template .env
   # Edit .env with your actual credentials
   ```

4. **Start the stack:**
   ```bash
   docker-compose up -d
   ```


## 📁 Directory Structure

```
project-root/
├── docker-compose.yml
├── .env.template
├── setup.sh
├── media/
│   ├── music/          # Your music files
│   ├── videos/         # Video content
│   └── podcasts/       # Podcast files
├── jellyfin/
│   ├── config/         # Jellyfin configuration
│   └── cache/          # Jellyfin cache
├── neo4j/
│   ├── data/           # Graph database
│   ├── logs/           # Neo4j logs
│   └── import/         # Data import folder
├── audio-processor/    # AI audio analysis service
├── api-gateway/        # REST API service
└── output/             # AI-processed content
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Security
JWT_SECRET=your-jwt-secret-here
NEO4J_PASSWORD=mediapassword123
JELLYFIN_USERNAME=your-jellyfin-username
JELLYFIN_PASSWORD=your-jellyfin-password
# Optional: provide a Jellyfin API key instead of username/password
JELLYFIN_API_KEY=

# AI Configuration
OPENAI_API_KEY=your-openai-key-if-needed
HUGGINGFACE_TOKEN=your-hf-token-if-needed

# YouTube API (for content creation)
YOUTUBE_API_KEY=your-youtube-api-key
```

`JELLYFIN_USERNAME` and `JELLYFIN_PASSWORD` (or the optional `JELLYFIN_API_KEY`) are consumed by the audio processor to securely
authenticate against your Jellyfin server. Populate these secrets through your provisioning workflow so containers can access the
media library without prompting for manual credentials.

### Supabase Setup

1. Create a new Supabase project
2. Run the SQL setup script in your Supabase SQL editor:
   ```sql
   -- Use supabase-setup.sql content
   ```
3. Update your .env file with the project credentials

### Neo4j Configuration

Default credentials:
- Username: `neo4j`
- Password: `mediapassword123`
- Browser: http://localhost:7474

## 🎵 Adding Media Content

1. **Add files to media directories:**
   ```bash
   cp /path/to/your/music/* ./media/music/
   cp /path/to/your/videos/* ./media/videos/
   ```

2. **Configure Jellyfin libraries:**
   - Visit http://localhost:8096
   - Complete initial setup
   - Add libraries pointing to `/media/music`, `/media/videos`, etc.

3. **Auto-analysis:**
   - Media files are automatically analyzed by AI
   - Results stored in Supabase and Neo4j
   - Check processing status via API

## 🤖 AI Audio Analysis Features

### Automated Content Analysis
- **Genre Detection**: Automatically categorizes music by genre
- **Mood Analysis**: Detects emotional content (happy, sad, energetic, etc.)
- **Instrument Recognition**: Identifies instruments and vocals
- **Technical Features**: Extracts tempo, key, spectral features
- **Content Description**: Generates detailed text descriptions

### Integration with Qwen Audio Model
- Processes audio files in real-time
- Generates structured metadata
- Creates searchable content descriptions
- Builds recommendation relationships

## 📊 Graph Database Relationships (Neo4j)

### Node Types
- **Media**: Individual audio/video files
- **Analysis**: AI-generated content analysis
- **AudioFeatures**: Technical audio characteristics
- **Genre**: Music genres
- **Artist**: Musicians/creators
- **Playlist**: Generated playlists

### Relationship Types
- `HAS_ANALYSIS`: Media → Analysis
- `HAS_FEATURES`: Media → AudioFeatures  
- `BELONGS_TO_GENRE`: Media → Genre
- `SIMILAR_TO`: Media → Media (based on features)
- `PERFORMED`: Artist → Media
- `CONTAINS`: Playlist → Media

## 🌐 API Endpoints

### Media Management
- `GET /api/media` - List all media with analysis
- `GET /api/media/:id` - Get specific media details
- `POST /api/analyze/:mediaId` - Trigger AI analysis

### Search & Discovery
- `GET /api/search?q=query` - Search media content
- `GET /api/recommendations/:mediaId` - Get similar content

### Content Creation
- `POST /api/youtube/analyze` - Analyze for YouTube content
- `GET /api/export/:format` - Export data (JSON/CSV)

### Analytics
- `GET /api/analytics` - Dashboard analytics data

## 🎬 YouTube Content Creation Workflow

### 1. Content Analysis
```bash
curl -X POST http://localhost:3000/api/youtube/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "videoUrl": "https://youtube.com/watch?v=example",
    "mediaIds": ["media-id-1", "media-id-2"]
  }'
```

### 2. Generated Suggestions
- Video titles based on music analysis
- Descriptions with technical details
- Timestamp markers for different tracks
- Relevant tags from AI analysis

### 3. Export for Video Editing
- Export metadata as JSON/CSV
- Include audio feature data
- Generate timeline suggestions
- Create comparison charts

## 🔍 Advanced Queries

### Neo4j Cypher Examples

**Find similar music by tempo:**
```cypher
MATCH (m:Media {name: "Your Song"})-[:HAS_FEATURES]->(f:AudioFeatures)
MATCH (similar:Media)-[:HAS_FEATURES]->(sf:AudioFeatures)
WHERE abs(f.tempo - sf.tempo) < 10
RETURN similar.name, sf.tempo
```

**Get genre-based recommendations:**
```cypher
MATCH (m:Media)-[:BELONGS_TO_GENRE]->(g:Genre)<-[:BELONGS_TO_GENRE]-(rec:Media)
WHERE m.name = "Your Song" AND m <> rec
RETURN rec.name, g.name
LIMIT 10
```

**Find mood-based playlists:**
```cypher
MATCH (p:Playlist)-[:CONTAINS]->(m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
WHERE a.ai_analysis.mood = "energetic"
RETURN p.name, count(m) as trackCount
```

## 🚀 Advanced Setup & Integrations

### Custom AI Models

1. **Replace Qwen with other models:**
   ```yaml
   # In docker-compose.yml
   qwen-audio:
     image: your-custom-model:latest
     # ... rest of configuration
   ```

2. **Add multiple AI services:**
   ```yaml
   whisper-transcription:
     image: openai/whisper:latest
     # ... configuration
   
   music-classifier:
     image: your-music-ai:latest
     # ... configuration
   ```

### External Integrations

#### Jellyfin Plugins
- Install SSO authentication plugins
- Add metadata enhancers
- Configure external scrapers

#### Supabase Extensions
- Enable real-time subscriptions
- Set up database functions
- Configure storage buckets

#### Neo4j Plugins
- Graph Data Science library
- APOC procedures
- Bloom visualization

### Scaling & Performance

#### Horizontal Scaling
```yaml
# Add to docker-compose.yml
audio-processor:
  # ... existing config
  deploy:
    replicas: 3
    resources:
      limits:
        memory: 4G
```

#### GPU Acceleration
```yaml
qwen-audio:
  # ... existing config
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## 🛠️ Troubleshooting

### Common Issues

**Services not starting:**
```bash
# Check logs
docker-compose logs -f [service-name]

# Restart specific service
docker-compose restart [service-name]
```

**Database connection issues:**
```bash
# Check network connectivity
docker network ls
docker network inspect [network-name]
```

**AI processing failures:**
```bash
# Check audio processor logs
docker-compose logs audio-processor

# Manually trigger analysis
curl -X POST http://localhost:3000/api/analyze/[media-id]
```

### Performance Optimization

**Jellyfin transcoding:**
- Enable hardware acceleration
- Configure quality settings
- Use appropriate codecs

**Neo4j memory:**
```bash
# Adjust in docker-compose.yml
NEO4J_dbms_memory_heap_max__size=4G
NEO4J_dbms_memory_pagecache_size=2G
```

**Redis caching:**
```bash
# Monitor cache hit rates
docker exec -it redis redis-cli info stats
```

## 📚 Additional Resources

### Documentation Links
- [Jellyfin Documentation](https://jellyfin.org/docs/) - Complete Jellyfin setup guide
- [Supabase Docs](https://supabase.com/docs) - Database and API documentation  
- [Neo4j Developer Guides](https://neo4j.com/developer/) - Graph database tutorials
- [Docker Compose Reference](https://docs.docker.com/compose/) - Container orchestration

### Tutorials & Guides
- [Jellyfin Docker Setup](https://pimylifeup.com/jellyfin-docker/) - Detailed Docker deployment guide
- [Neo4j Data Import](https://neo4j.com/docs/getting-started/appendix/tutorials/guide-import-relational-and-etl/) - Import from relational databases
- [Supabase Integration Guide](https://supabase.com/docs/guides/integrations/build-a-supabase-integration) - Building integrations
- [AI Audio Analysis](https://github.com/QwenLM/Qwen-Audio) - Qwen Audio model documentation

### Community Resources
- [r/jellyfin](https://reddit.com/r/jellyfin) - Jellyfin community
- [r/selfhosted](https://reddit.com/r/selfhosted) - Self-hosting discussions
- [Neo4j Community](https://community.neo4j.com/) - Graph database forum
- [Supabase Discord](https://discord.supabase.com/) - Real-time support

### AI/ML Resources
- [Hugging Face Audio Models](https://huggingface.co/models?pipeline_tag=audio-classification) - Pre-trained audio models
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [Spotify Research](https://research.spotify.com/) - Music recommendation algorithms
- [Music Information Retrieval](https://musicinformationretrieval.com/) - Academic resources

## 🤝 Contributing & Customization

### Extending the Stack

**Add new AI models:**
1. Create Docker service in compose file
2. Add API integration in audio-processor
3. Update database schema if needed
4. Configure API gateway endpoints

**Custom content types:**
1. Extend Supabase schema
2. Add Neo4j node types
3. Update API endpoints
4. Modify dashboard UI

**Integration with other services:**
- Plex integration
- Spotify API connections
- Last.fm scrobbling
- Discord bot integration

This comprehensive setup provides a powerful foundation for AI-powered media analysis and content creation, perfect for music producers, content creators, and media enthusiasts looking to automate and enhance their workflow.