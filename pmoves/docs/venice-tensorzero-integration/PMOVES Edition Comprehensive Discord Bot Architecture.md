# PMOVES Edition: Comprehensive Discord Bot Architecture

**The PMOVES Edition Discord bot represents a sophisticated multi-agent AI system** that merges ElizaOS with Venice.ai Pro, implements Model Context Protocol (MCP) for bidirectional tool integration, orchestrates creative workflows through n8n automation, and leverages Supabase vector storage for intelligent RAG-powered conversations. This production-ready architecture supports three distinct server contexts with isolated behaviors while maintaining unified codebase deployment from Windows development to Linux VPS production.

## System architecture overview

The PMOVES bot operates as a **distributed microservices architecture** with five core layers: the Discord interface layer running ElizaOS with Venice.ai as the primary LLM provider, an MCP gateway layer enabling both server (exposing Discord capabilities) and client (consuming external tools) functionality, an n8n workflow orchestration layer for creative automation pipelines, a Supabase backend providing PostgreSQL with pgvector for 3584-dimension semantic search, and a deployment layer supporting local Windows development with seamless VPS production deployment via Coolify.

**Core technology stack:** ElizaOS framework (TypeScript) for agent orchestration, Venice.ai Pro API for uncensored LLM inference with 235B parameter models, FastMCP for Python-based MCP server implementation, Discord.py 2.0+ for bot functionality, n8n for visual workflow automation, Supabase for vector storage with pgvector extension, Redis for embedding caching, and Docker containerization managed by Coolify. The architecture supports **three isolated server contexts** (Personal, Cataclysm Studios, UNFCU) with distinct personalities, rate limits, and feature sets while sharing the same deployment infrastructure.

**Key architectural decisions:** Use Venice.ai's OpenAI-compatible API as drop-in replacement for immediate integration while preparing custom ElizaOS provider for production. Implement MCP with both stdio (local development) and Streamable HTTP (production) transports. Deploy n8n workflows asynchronously with webhook callbacks rather than synchronous polling. Store per-server configurations in Supabase with guild_id partitioning for perfect isolation. Cache embeddings in Redis with 1-hour TTL to reduce Hugging Face API calls by 80%. Use Windows Subsystem for Linux (WSL2) or native PowerShell for development, then deploy to Ubuntu VPS via GitHub Actions CI/CD pipeline.

## ElizaOS integration with Venice.ai Pro

ElizaOS provides the autonomous agent framework with its four-layer plugin system: **Providers** supply contextual information before response generation, **Actions** define executable behaviors triggered by user input, **Evaluators** perform post-conversation analysis for learning, and **Services** handle platform integrations including Discord. The AgentRuntime coordinates message processing, memory management through RAG-based vector search, state composition, and AI model interfacing. Character files define agent personality, model provider selection, plugin loading, and behavioral patterns through JSON configuration.

**Venice.ai serves as the primary LLM provider** through OpenAI-compatible API at api.venice.ai/api/v1. The Pro subscription ($18/month) provides $10 API credit and Explorer tier rate limits, while VVV token staking enables zero-marginal-cost inference through daily Diem allocation. Key models for PMOVES: **qwen3-235b** (131k context) for complex reasoning and agent planning, **venice-uncensored** (32k context) for creative content generation without filtering, **mistral-31-24b** (131k context) for vision processing and function calling, **flux-dev** for image generation, and **qwen3-4b** (40k context) for fast classification and simple responses.

**Implementation approach:** Create custom Venice provider for ElizaOS following the ModelProvider interface. Since native Venice integration is pending (GitHub issue #5820), use OpenAI SDK with custom baseURL as interim solution. Initialize OpenAI client with `baseURL: "https://api.venice.ai/api/v1"` and pass to AgentRuntime as customModelClient. Implement context-aware model routing: select qwen3-4b for messages under 1000 characters, qwen3-235b for complex reasoning tasks, venice-uncensored for creative requests, and mistral-31-24b for image analysis. Add exponential backoff retry logic for 429/500/503 errors with maximum 3 retries and base delay of 1 second.

**Character configuration for multi-server support:** Create three character files (personal.character.json, studio.character.json, unfcu.character.json) with distinct personalities. Personal server uses casual tone with high emoji usage and "friendly" personality. Cataclysm Studios uses professional tone with "constructive" personality and technical depth for creative feedback. UNFCU uses formal business tone with "compliance" personality and concise responses. Each character file specifies unique settings for model selection, temperature, voice settings, and custom knowledge bases loaded from server-specific FAQ files.

```json
{
  "name": "PMOVESPersonal",
  "clients": ["discord"],
  "modelProvider": "venice",
  "settings": {
    "secrets": {"VENICE_API_KEY": "process.env.VENICE_API_KEY"},
    "model": "qwen3-235b",
    "temperature": 0.8,
    "maxInputTokens": 131000,
    "maxOutputTokens": 4096
  },
  "plugins": ["@elizaos/plugin-discord"],
  "bio": ["Personal assistant for creative work and daily automation"],
  "personality": "casual",
  "style": {
    "all": ["friendly and supportive", "uses emojis frequently"],
    "chat": ["conversational", "asks follow-up questions"]
  }
}
```

## Model Context Protocol implementation

**MCP enables bidirectional tool integration:** The bot acts as an MCP server exposing Discord operations (send_message, read_messages, manage_roles, moderate_content) to external AI agents like Claude Desktop or ChatGPT, while simultaneously acting as an MCP client to consume tools from external MCP servers (weather APIs, database queries, custom integrations). This creates a universal interface for AI agent interoperability following the Anthropic-developed protocol adopted by OpenAI, Google, and Microsoft.

**MCP server implementation (exposing Discord capabilities):** Use FastMCP Python library for rapid development. Create discord_mcp_server.py that initializes Discord.py bot and FastMCP server simultaneously. Decorate Discord operations with `@mcp.tool()` to expose them as callable tools. Each tool receives Discord context (guild_id, channel_id, user_id) as parameters and returns structured JSON responses. Implement tools for: list_servers (returns all guilds with member counts), send_message (posts to specified channel), read_messages (fetches recent messages with pagination), add_reaction (reacts to messages), manage_roles (assigns/removes roles), and moderate_content (uses Venice uncensored model to analyze content violations).

```python
from mcp.server.fastmcp import FastMCP
import discord
from discord.ext import commands

mcp = FastMCP("pmoves-discord")
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@mcp.tool()
async def send_message(channel_id: str, content: str) -> dict:
    """Send message to Discord channel"""
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return {"error": "Channel not found"}
    message = await channel.send(content)
    return {"success": True, "message_id": str(message.id)}

@mcp.tool()
async def read_messages(channel_id: str, limit: int = 10) -> list[dict]:
    """Retrieve recent messages from channel"""
    channel = bot.get_channel(int(channel_id))
    messages = []
    async for msg in channel.history(limit=limit):
        messages.append({
            "id": str(msg.id),
            "author": str(msg.author),
            "content": msg.content,
            "timestamp": msg.created_at.isoformat()
        })
    return messages
```

**MCP client implementation (consuming external tools):** Create MCPOrchestrator class that manages connections to multiple MCP servers simultaneously. Support both stdio (local tools) and HTTP/SSE (remote services) transports. For local development, connect to MCP servers via stdio using StdioServerParameters. For production, connect via Streamable HTTP for scalability and multi-node support. Implement tool discovery by calling list_tools() on each connected server and maintaining a registry mapping tool names to their host servers. Create custom ChatGPT MCP connector using OpenAI function calling with MCP tool schemas.

**Transport configuration for development vs production:** In development, use stdio transport launching MCP servers as subprocess. In production on VPS, deploy MCP servers as separate Docker containers exposing HTTP endpoints. Configure Claude Desktop integration by adding server configuration to claude_desktop_config.json. For ChatGPT integration, create custom GPT with action schema matching MCP tool definitions and callback URL pointing to Discord bot webhook endpoint.

**Authentication and security:** Implement OAuth 2.1 for production MCP servers. Use custom TokenVerifier class to validate JWT tokens with public key verification. Include required scopes (discord:read, discord:write, discord:admin) in token claims. For development, use simple header authentication with X-API-Key. Create rate limiting wrapper around MCP tool calls to prevent abuse. Log all MCP operations to Supabase audit table with timestamp, user_id, tool_name, and parameters.

## Multi-server Discord architecture with context-aware behavior

**Guild-based configuration isolation:** Store all server settings in Supabase servers table with guild_id as primary key. Each guild has unique prefix, personality type, enabled features, channel assignments, role mappings, custom commands, and rate limits. Use server_features table with JSONB column for flexible per-feature configuration. Implement channel_configs table linking channel_id to guild_id for channel-specific behavior like auto-responses and message logging.

**Context detection and dynamic behavior switching:** Extract guild context from Discord message event using `message.guild.id` and `message.channel.id`. Query Supabase for guild configuration using async SQLAlchemy or Supabase client. Load appropriate character file and LLM settings based on guild personality. Apply guild-specific rate limits using Redis-backed rate limiter with key pattern `{guild_id}:{user_id}:{command}`. Inject guild context into ElizaOS AgentRuntime state so LLM responses reflect proper tone and knowledge base.

**Three-server configuration examples:** Personal server (guild_id: PERSONAL_ID) uses command prefix "!", casual personality with emoji-rich responses, enabled features include welcome_messages and music playback, loose rate limits (20 commands/minute), and loads gaming-focused knowledge base. Cataclysm Studios server uses prefix "/", professional constructive personality, enabled features include project management and design feedback, moderate rate limits (10 commands/minute), integrates with Notion and Google Drive, and requires embeds with timestamps. UNFCU server uses prefix ".", formal business personality, strict security (2FA required, all actions logged), enabled features include task tracking and compliance logging, tight rate limits (5 commands/minute), and integrates with Jira and Confluence.

**Database schema for multi-server state:**

```sql
CREATE TABLE servers (
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(10) DEFAULT '!',
    personality VARCHAR(50) DEFAULT 'friendly',
    model VARCHAR(100) DEFAULT 'qwen3-235b',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE server_features (
    guild_id BIGINT REFERENCES servers(guild_id) ON DELETE CASCADE,
    feature_name VARCHAR(50),
    enabled BOOLEAN DEFAULT true,
    config JSONB,
    PRIMARY KEY (guild_id, feature_name)
);

CREATE TABLE user_guild_data (
    user_id BIGINT,
    guild_id BIGINT REFERENCES servers(guild_id) ON DELETE CASCADE,
    xp INTEGER DEFAULT 0,
    preferences JSONB,
    PRIMARY KEY (user_id, guild_id)
);

CREATE INDEX idx_servers_guild ON servers(guild_id);
CREATE INDEX idx_features_guild ON server_features(guild_id);
```

**Privacy and data isolation best practices:** Never use global bot.get_channel() lookups without guild context validation. Always scope queries with guild_id to prevent cross-guild data leakage. Store user preferences per-guild in user_guild_data table with composite primary key (user_id, guild_id). Implement Row-Level Security (RLS) policies in Supabase ensuring users only access data from guilds they belong to. Cache guild configurations in Redis with key pattern `guild:config:{guild_id}` and 5-minute TTL to reduce database load.

**Discord Nitro and Server Boost optimization:** Leverage boosted server benefits for Cataclysm Studios creative work. Level 2 boost (15 boosts) unlocks 100MB upload limit for all members, enabling high-resolution asset sharing. Use 256kbps audio quality for voice feedback sessions. Enable 1080p 60fps screen share for design reviews. Custom emojis serve as workflow triggers: 🎨 initiates image generation, 💾 saves to project gallery, ✅ approves design, 🔄 requests iteration. Track server boost status and adjust file handling logic accordingly: compress uploads on non-boosted servers, allow full-resolution on boosted servers.

## n8n workflow orchestration for creative automation

**Webhook integration architecture:** Discord bot sends HTTP POST to n8n webhook endpoints when users trigger creative commands. n8n webhooks use Header Authentication with custom X-API-Key header for security. Pass complete Discord context in payload including user_id, channel_id, guild_id, message content, and any attachments. For workflows completing under 5 seconds, use synchronous response mode ("When Last Node Finishes"). For longer workflows, use asynchronous pattern: n8n responds immediately, bot acknowledges with "Processing...", and n8n posts results via Discord webhook when complete.

**VibeVoice TTS workflow integration:** User types `!tts "text"` in Discord while connected to voice channel. Bot extracts text and voice channel ID, posts to n8n webhook endpoint `/tts-generate`. n8n workflow: Webhook receives request → HTTP Request to ElevenLabs/VibeVoice API with text and voice settings → Wait for audio generation → Upload audio file to Cloudinary → Return audio URL in response. Bot receives URL, joins voice channel using @discordjs/voice library, creates audio resource from URL, plays through voice connection. Implement queue system for multiple TTS requests in same channel.

**Image generation and editing pipeline:** User types `!generate photorealistic cat` in Discord. Bot parses style keyword ("photorealistic") and prompt, posts to n8n `/image-gen` webhook. n8n workflow: Webhook → Switch node routes by style → HTTP Request to appropriate model (Flux.1-schnell for photorealistic, SDXL for stylized, Stable Diffusion as fallback) → Poll or wait for generation → Download image → Optional Qwen Image Edit Plus for refinements → Upload to Cloudinary → Log to Google Sheets → Post to Discord with embed. Bot displays image with interactive buttons: Upscale (triggers RealESRGAN workflow), Variations (re-generates with seed variation), Animate (triggers Wan Animate workflow).

**Wan Animate 2.2 animation workflow:** User clicks Animate button on generated image. Discord interaction event sends image URL to n8n `/animate` webhook. n8n workflow: Download image → HTTP Request to Wan Animate API with image and animation parameters → Receive job_id → Loop: Wait 10 seconds → Check job status → Until complete → Download video file → Upload to cloud storage → Post to Discord as video attachment. Handle Nitro file size limits: compress video for non-boosted servers (under 10MB), send full quality for boosted servers (under 100MB).

**ComfyUI integration via webhooks:** Install ComfyUI-DiscordWebhook custom node in ComfyUI instance. Configure node to post to n8n webhook `/comfyui-result` when workflows complete. n8n receives notification with image metadata, downloads images from ComfyUI view endpoint, processes and posts to Discord. For triggering ComfyUI from Discord: Bot posts to n8n → n8n POST to ComfyUI `/prompt` API with workflow JSON → ComfyUI processes → Webhook callback to n8n → Post results to Discord.

**Complete creative pipeline architecture:**

```
Discord Command (!generate, !tts, !animate)
    ↓
Parse Intent + Extract Parameters
    ↓
POST to n8n Webhook (with auth header)
    ↓
n8n Switch Node (routes by workflow type)
    ├→ Image: Flux/SDXL/SD → Qwen Edit → Upscale → Cloud Upload
    ├→ TTS: ElevenLabs → Audio Processing → Cloud Upload
    ├→ Animation: Wan Animate → Video Processing → Cloud Upload
    └→ ComfyUI: Trigger Workflow → Poll Status → Download Results
    ↓
n8n Callback (via Discord webhook or synchronous response)
    ↓
Bot Posts Results with Interactive Buttons
    ↓
User Interactions trigger additional workflows
```

**Error handling and retry logic:** Configure n8n Error Workflow that sends Discord webhook notification on any workflow failure. Include error details, workflow name, timestamp, and input data. Implement exponential backoff in HTTP Request nodes: 3 retries with 1s, 2s, 4s delays. Set workflow-level timeout of 10 minutes for image generation, 5 minutes for TTS, 30 minutes for animation. Bot handles timeout by switching to async mode automatically if synchronous response exceeds 30 seconds.

## Supabase vector store and RAG implementation

**pgvector setup for 3584-dimension embeddings:** Enable pgvector extension in Supabase SQL Editor: `CREATE EXTENSION IF NOT EXISTS vector;`. Create messages table with vector column: `embedding vector(3584)`. Create HNSW index for fast similarity search: `CREATE INDEX ON messages USING hnsw (embedding vector_cosine_ops);`. Alternative IVFFlat index for memory efficiency: `CREATE INDEX ON messages USING ivflat (embedding vector_cosine_ops) WITH (lists = 100);`. HNSW provides sub-100ms query times for datasets under 1M vectors with higher memory usage. IVFFlat uses less memory with slightly slower queries.

**Hugging Face embeddings generation:** Install sentence-transformers Python library. For 3584 dimensions, use custom trained model or ensemble approach combining multiple smaller models. Standard recommendation: use Supabase/gte-small (384 dim) for production unless specific use case requires higher dimensionality. Generate embeddings asynchronously: `model.encode(text, convert_to_tensor=True, show_progress_bar=False)`. Batch process 32 messages at a time for efficiency. Cache embeddings in Redis with key pattern `embed:{hash(text)}` and 1-hour TTL to avoid redundant computation.

**RAG workflow for Discord conversations:** When message arrives, check if user query requires context (using keyword detection or LLM classification). Generate embedding for user query using same model. Query Supabase: `SELECT content, metadata FROM messages WHERE guild_id = $1 ORDER BY embedding <=> $2 LIMIT 5`. The `<=>` operator performs cosine distance search, returning most semantically similar messages. Construct augmented prompt: "Context: {retrieved_messages}\n\nUser: {current_message}". Send to Venice.ai qwen3-235b with augmented context. Stream response back to Discord. Store new message and embedding in database for future retrieval.

**Schema design for Discord RAG:**

```sql
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(3584),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_guild ON messages(guild_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
CREATE INDEX idx_messages_embedding ON messages 
    USING hnsw (embedding vector_cosine_ops);

-- Row-Level Security for multi-tenant isolation
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY guild_isolation ON messages
    FOR ALL
    USING (guild_id = current_setting('app.guild_id')::BIGINT);
```

**Chunking strategies for Discord:** Message-level chunking works best for Discord conversations since messages are naturally atomic units. For long messages exceeding 1000 characters, implement semantic chunking: split on sentence boundaries using NLTK or spaCy, create overlapping chunks of 500 characters with 100 character overlap, generate embeddings for each chunk, store with parent message reference. Thread-based chunking: group messages within same thread, concatenate with separators, embed entire thread context for better conversation understanding.

**Performance optimization for real-time RAG:** Use connection pooling with asyncpg: 20 connections for production, 5 for development. Implement embedding cache in Redis avoiding redundant Hugging Face API calls. Pre-compute embeddings for FAQ documents and common queries. Use approximate nearest neighbor search with HNSW for sub-100ms query times. Batch embed new messages every 10 seconds rather than individually. Monitor query performance with Supabase dashboard and add indexes as needed.

**Integration with ElizaOS memory system:** ElizaOS has built-in RAG through RAGKnowledgeManager. Replace default embedding provider with custom Hugging Face provider. Override getMemories() method to query Supabase instead of local SQLite. Maintain ElizaOS message format while storing in Supabase for compatibility. Use ElizaOS evaluators to extract facts and entities, storing them as separate embeddings for fine-grained retrieval.

## Windows development environment setup

**PowerShell setup script for Python virtual environment:**

```powershell
# setup-env.ps1
# Enable script execution if needed
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host "Setting up PMOVES Discord Bot development environment..."

# Check Python installation
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ from python.org"
    exit 1
}

# Create virtual environment
Write-Host "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..."
pip install discord.py python-dotenv fastapi uvicorn sqlalchemy asyncpg redis sentence-transformers supabase mcp

# Install ElizaOS (Node.js required)
Write-Host "Installing ElizaOS CLI..."
npm install -g @elizaos/cli pnpm

# Create directory structure
Write-Host "Creating project structure..."
New-Item -ItemType Directory -Force -Path src, config, characters, data, logs

# Create .env file from template
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file..."
    @"
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token
DISCORD_APPLICATION_ID=your_app_id

# Venice.ai Configuration
VENICE_API_KEY=your_venice_api_key
VENICE_MODEL=qwen3-235b

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# n8n Configuration
N8N_WEBHOOK_BASE=https://your-n8n-instance.com/webhook
N8N_API_KEY=your_n8n_api_key

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Server IDs
PERSONAL_GUILD_ID=123456789
STUDIO_GUILD_ID=987654321
UNFCU_GUILD_ID=456789123

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG
"@ | Out-File -FilePath .env -Encoding UTF8
}

Write-Host "✅ Development environment setup complete!"
Write-Host "Next steps:"
Write-Host "1. Edit .env file with your API keys"
Write-Host "2. Run: python src/bot.py"
```

**VS Code configuration for debugging:**

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "editor.formatOnSave": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".venv": true,
    "venv": true
  }
}

// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Discord Bot",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/bot.py",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      },
      "envFile": "${workspaceFolder}/.env"
    },
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "src.api:app",
        "--reload",
        "--host", "127.0.0.1",
        "--port", "8000"
      ],
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

**Local testing architecture:** Run Discord bot on main thread with FastAPI on separate async task. FastAPI serves on port 8000 providing health check endpoint, metrics endpoint, and MCP server HTTP transport. Next.js dashboard runs on port 3000 for bot configuration UI and analytics visualization. Redis runs locally via Docker or Windows installer for caching. Supabase accessed remotely via API. n8n accessed remotely via webhook URLs. Use ngrok for local webhook testing: `ngrok http 8000` to expose local FastAPI to n8n callbacks.

**Package management with npm/pnpm:** Install Node.js 20+ LTS. Install pnpm globally: `npm install -g pnpm`. Initialize Next.js dashboard: `pnpm create next-app dashboard --typescript --tailwind --app`. Install ElizaOS dependencies: `pnpm install @elizaos/core @elizaos/plugin-discord`. Use pnpm workspaces for monorepo structure with bot (Python), api (FastAPI), and dashboard (Next.js) packages.

**Environment variable management:** Use python-dotenv to load .env file. Never commit .env to Git (add to .gitignore). Create .env.example with placeholder values for documentation. Use separate .env files for different environments: .env.development, .env.production. Validate required environment variables on startup and exit with clear error messages if missing.

## VPS production deployment with Coolify

**Coolify overview and setup:** Coolify is open-source, self-hosted PaaS alternative to Heroku/Netlify running on single VPS. Install on Ubuntu 22.04 VPS: `curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash`. Access web UI at https://your-vps-ip:8000. Connect GitHub repository for automatic deployments. Coolify handles Docker containerization, networking, SSL certificates via Let's Encrypt, and application management.

**Docker containerization for PMOVES bot:**

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/botuser/.local
COPY --chown=botuser:botuser . .

# Set path
ENV PATH=/home/botuser/.local/bin:$PATH

USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["python", "src/bot.py"]
```

**Multi-stage Docker build for optimization:** First stage installs dependencies with full build tools. Second stage copies only necessary files and installed packages, reducing final image size by 50-70%. Use .dockerignore to exclude unnecessary files: venv/, .git/, __pycache__/, *.pyc, .env, logs/, data/. Build image: `docker build -t pmoves-bot:latest .`. Test locally: `docker run --env-file .env -p 8000:8000 pmoves-bot:latest`.

**GitHub Actions CI/CD pipeline:**

```yaml
# .github/workflows/deploy.yml
name: Deploy to VPS

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          
      - name: Deploy to VPS via Coolify
        uses: fjogeleit/http-request-action@v1
        with:
          url: ${{ secrets.COOLIFY_WEBHOOK_URL }}
          method: 'POST'
          customHeaders: '{"Authorization": "Bearer ${{ secrets.COOLIFY_TOKEN }}"}'
```

**Windows to Linux migration considerations:** Replace Windows path separators (backslash) with forward slash or use pathlib.Path for cross-platform compatibility. Convert line endings from CRLF to LF: `git config --global core.autocrlf input`. Test all file I/O operations for case-sensitivity issues. Ensure environment variables load correctly in Linux (no PowerShell-specific syntax). Update any Windows-specific commands in scripts (e.g., replace `cls` with `clear`).

**AWS EC2 SSH access via VS Code:** Install Remote-SSH extension in VS Code. Generate SSH key pair: `ssh-keygen -t ed25519 -C "your_email"`. Add public key to EC2 instance via AWS console or authorized_keys file. Configure SSH config file (~/.ssh/config):

```
Host pmoves-vps
    HostName ec2-xx-xx-xx-xx.compute.amazonaws.com
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
```

Connect via VS Code: Press F1 → "Remote-SSH: Connect to Host" → Select pmoves-vps. Edit files directly on VPS, run commands in integrated terminal, debug remotely using same launch configurations.

**Environment-specific configuration strategy:** Use environment variable `ENVIRONMENT=production` to determine configuration loading. Create config/production.py and config/development.py with environment-specific settings. In production: disable debug logging, use connection pooling with higher limits, enable Sentry error tracking, use production Redis URL, set strict rate limits. In development: enable verbose logging, use smaller connection pools, mock external API calls for testing, use local Redis.

**Secrets management in production:** Store secrets in Coolify environment variables UI (encrypted at rest). Mount secrets as files in Docker container: `docker run -v /run/secrets/discord_token:/run/secrets/discord_token`. Read secrets from files rather than environment variables for better security:

```python
def get_secret(secret_name):
    secret_path = Path(f"/run/secrets/{secret_name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return os.getenv(secret_name.upper())

DISCORD_TOKEN = get_secret("discord_token")
```

**Backup and disaster recovery:** Configure automated Supabase backups with 7-day retention. Export critical data daily to S3: guild configurations, custom commands, user data. Store Docker images in GitHub Container Registry for rollback capability. Implement health monitoring with automatic container restart on failure. Log all errors to centralized logging service (Loki, Papertrail). Set up Discord webhook alerts for critical failures. Document recovery procedures and test quarterly.

## Security best practices and API key management

**Token security fundamentals:** Never hardcode API keys or tokens in source code. Use environment variables loaded from .env file (never commit to Git). Rotate Discord bot token quarterly. Use separate API keys for development and production environments. Enable 2FA on all service accounts (Discord Developer Portal, Supabase, Venice.ai). Restrict API key permissions to minimum required (principle of least privilege).

**Multi-context security isolation:** Store separate API keys for each guild in Supabase encrypted field. Personal server uses low-privilege keys for testing. Studio server uses moderate-privilege keys with file access. UNFCU server uses high-privilege keys with strict audit logging. Implement API key validation middleware checking guild_id matches authorized list for each key. Log all API calls to audit table with timestamp, user, guild, endpoint, and response code.

**Discord bot permissions and intents:** Request only required Gateway Intents: Guilds (required for basic operation), GuildMessages (for message handling), MessageContent (privileged intent - requires verification for 100+ servers), GuildVoiceStates (for voice channel integration), GuildMembers (privileged - for user info). In Discord Developer Portal, enable Message Content Intent only after verification. Set bot permissions: Send Messages, Read Message History, Attach Files, Use Slash Commands, Connect (voice), Speak (voice), Manage Roles (only if needed for automation).

**Database security with RLS:** Enable Row-Level Security on all Supabase tables. Create policies restricting access by guild_id and user_id. Example policy: `CREATE POLICY guild_isolation ON messages FOR ALL USING (guild_id = current_setting('app.guild_id')::BIGINT);`. Set guild context in Supabase client before queries: `supabase.rpc('set_config', {'setting': 'app.guild_id', 'value': str(guild_id)})`. Use service role key only in backend, never expose to frontend. Use anon key for client-side operations with RLS enforcement.

**Rate limiting implementation:** Implement multi-tier rate limiting: per-user (5 commands/minute), per-guild (50 commands/minute), per-bot-instance (1000 commands/minute). Use Redis for distributed rate limiting with sliding window algorithm. Key pattern: `ratelimit:{guild_id}:{user_id}:{minute}`. Increment counter on each command, check against limit before processing. Return user-friendly error message when exceeded: "⏰ Rate limit exceeded. Please wait 30 seconds." Apply stricter limits to resource-intensive commands (image generation: 1/minute, TTS: 3/minute).

**Input validation and sanitization:** Validate all user input before processing. Limit message content length to 2000 characters (Discord maximum). Sanitize input before database insertion to prevent SQL injection: use parameterized queries with asyncpg. Escape special characters in prompts sent to AI models. Validate URLs before fetching (whitelist allowed domains for safety). Implement content filtering for inappropriate requests using Venice.ai moderation endpoint or separate moderation model.

**Webhook security for n8n integration:** Use Header Auth with strong random API key (minimum 32 characters). Implement HMAC signature verification for critical workflows: bot signs payload with secret, n8n verifies signature matches. Add timestamp to requests and reject old requests (older than 5 minutes) to prevent replay attacks. Whitelist n8n IP address in firewall rules. Use HTTPS for all webhook URLs (enforce TLS 1.2+). Log all webhook calls with payload hash for audit trail.

## Complete implementation code examples

**Main bot entry point with multi-server support:**

```python
# src/bot.py
import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
import discord
from discord.ext import commands
from supabase import create_client
import redis.asyncio as redis

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize clients
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
redis_client = redis.from_url(os.getenv('REDIS_URL'))

class PMOVESBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            help_command=None
        )
        
        self.guild_configs = {}
        
    async def get_prefix(self, message):
        """Dynamic prefix per guild"""
        if not message.guild:
            return '!'
        
        config = await self.get_guild_config(message.guild.id)
        return config.get('prefix', '!')
    
    async def get_guild_config(self, guild_id):
        """Load guild configuration from cache or database"""
        # Check cache
        cache_key = f"guild:config:{guild_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
        
        # Query database
        response = supabase.table('servers') \
            .select('*') \
            .eq('guild_id', guild_id) \
            .execute()
        
        if response.data:
            config = response.data[0]
        else:
            # Create default config
            config = {
                'guild_id': guild_id,
                'prefix': '!',
                'personality': 'friendly',
                'model': 'qwen3-235b'
            }
            supabase.table('servers').insert(config).execute()
        
        # Cache for 5 minutes
        await redis_client.setex(
            cache_key,
            300,
            json.dumps(config)
        )
        
        return config
    
    async def setup_hook(self):
        """Load cogs and initialize services"""
        await self.load_extension('cogs.rag')
        await self.load_extension('cogs.creative')
        await self.load_extension('cogs.mcp_server')
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Bot startup event"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Sync slash commands
        await self.tree.sync()
        logger.info("Slash commands synced")

bot = PMOVESBot()

@bot.event
async def on_message(message):
    """Process messages with context awareness"""
    if message.author.bot:
        return
    
    # Get guild configuration
    if message.guild:
        config = await bot.get_guild_config(message.guild.id)
        # Attach config to message for command context
        message.guild_config = config
    
    await bot.process_commands(message)

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
```

**RAG command implementation with Supabase:**

```python
# cogs/rag.py
import discord
from discord.ext import commands
from discord import app_commands
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List
import os

class RAGCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.venice_api_key = os.getenv('VENICE_API_KEY')
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        # Check cache first
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()
        cache_key = f"embed:{text_hash}"
        
        cached = await self.bot.redis_client.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
        
        # Generate embedding
        embedding = self.embedding_model.encode(text, convert_to_tensor=False)
        embedding_list = embedding.tolist()
        
        # Cache for 1 hour
        import json
        await self.bot.redis_client.setex(cache_key, 3600, json.dumps(embedding_list))
        
        return embedding_list
    
    async def retrieve_context(self, guild_id: int, query: str, limit: int = 5) -> List[dict]:
        """Retrieve relevant messages using vector similarity"""
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Query Supabase with vector similarity
        from supabase import create_client
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
        
        # Use RPC for vector search
        response = supabase.rpc(
            'match_messages',
            {
                'query_embedding': query_embedding,
                'match_threshold': 0.7,
                'match_count': limit,
                'filter_guild_id': guild_id
            }
        ).execute()
        
        return response.data if response.data else []
    
    @app_commands.command(name="ask", description="Ask a question with RAG context")
    async def ask_command(self, interaction: discord.Interaction, question: str):
        """RAG-powered question answering"""
        await interaction.response.defer()
        
        # Retrieve relevant context
        context_messages = await self.retrieve_context(
            interaction.guild_id,
            question,
            limit=5
        )
        
        # Build context string
        context = "\n\n".join([
            f"[{msg['created_at']}] {msg['content']}"
            for msg in context_messages
        ])
        
        # Generate response with Venice.ai
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.venice.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.venice_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'qwen3-235b',
                    'messages': [
                        {
                            'role': 'system',
                            'content': f'Answer the question using the provided context. Context:\n{context}'
                        },
                        {
                            'role': 'user',
                            'content': question
                        }
                    ],
                    'temperature': 0.7
                }
            ) as resp:
                data = await resp.json()
                answer = data['choices'][0]['message']['content']
        
        # Create embed with answer and sources
        embed = discord.Embed(
            title="🔍 RAG Answer",
            description=answer,
            color=discord.Color.blue()
        )
        
        if context_messages:
            sources = "\n".join([
                f"• [{msg['created_at'][:10]}] {msg['content'][:100]}..."
                for msg in context_messages[:3]
            ])
            embed.add_field(name="📚 Sources", value=sources, inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Store messages for RAG"""
        if message.author.bot or not message.guild:
            return
        
        # Skip if content too short
        if len(message.content) < 20:
            return
        
        # Generate embedding
        embedding = await self.generate_embedding(message.content)
        
        # Store in Supabase
        from supabase import create_client
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
        
        supabase.table('messages').insert({
            'guild_id': message.guild.id,
            'channel_id': message.channel.id,
            'user_id': message.author.id,
            'content': message.content,
            'embedding': embedding,
            'metadata': {
                'author_name': str(message.author),
                'channel_name': message.channel.name
            }
        }).execute()

async def setup(bot):
    await bot.add_cog(RAGCog(bot))
```

**Creative workflows integration with n8n:**

```python
# cogs/creative.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

class CreativeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.n8n_base = os.getenv('N8N_WEBHOOK_BASE')
        self.n8n_api_key = os.getenv('N8N_API_KEY')
    
    async def trigger_n8n_workflow(self, endpoint: str, data: dict) -> dict:
        """Trigger n8n workflow via webhook"""
        url = f"{self.n8n_base}/{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.n8n_api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"n8n workflow failed: {resp.status}")
    
    @app_commands.command(name="generate", description="Generate AI image")
    async def generate_image(
        self,
        interaction: discord.Interaction,
        prompt: str,
        style: str = "photorealistic"
    ):
        """Generate image via n8n + AI models"""
        await interaction.response.defer()
        
        # Get channel webhook for async callback
        webhooks = await interaction.channel.webhooks()
        webhook = discord.utils.get(webhooks, name='n8n-bot')
        if not webhook:
            webhook = await interaction.channel.create_webhook(name='n8n-bot')
        
        # Trigger n8n workflow
        try:
            result = await self.trigger_n8n_workflow('image-gen', {
                'prompt': prompt,
                'style': style,
                'user_id': interaction.user.id,
                'channel_id': interaction.channel_id,
                'guild_id': interaction.guild_id,
                'discord_webhook': webhook.url
            })
            
            await interaction.followup.send(
                f"🎨 Generating {style} image with prompt: `{prompt}`\n"
                f"This may take 30-60 seconds..."
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Generation failed: {str(e)}")
    
    @app_commands.command(name="tts", description="Text-to-speech in voice channel")
    async def tts_command(
        self,
        interaction: discord.Interaction,
        text: str,
        voice: str = "en_US-male-medium"
    ):
        """Generate TTS and play in voice channel"""
        # Check if user in voice channel
        if not interaction.user.voice:
            return await interaction.response.send_message(
                "❌ Join a voice channel first!",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Trigger TTS workflow
        try:
            result = await self.trigger_n8n_workflow('tts-generate', {
                'text': text,
                'voice': voice,
                'guild_id': interaction.guild_id,
                'channel_id': interaction.channel_id
            })
            
            audio_url = result.get('audio_url')
            
            # Play audio in voice channel
            from discord import FFmpegPCMAudio
            voice_client = await interaction.user.voice.channel.connect()
            voice_client.play(FFmpegPCMAudio(audio_url))
            
            await interaction.followup.send(f"🔊 Playing TTS in {interaction.user.voice.channel.mention}")
            
            # Disconnect when finished
            while voice_client.is_playing():
                await asyncio.sleep(1)
            await voice_client.disconnect()
            
        except Exception as e:
            await interaction.followup.send(f"❌ TTS failed: {str(e)}")

async def setup(bot):
    await bot.add_cog(CreativeCog(bot))
```

## Configuration templates and deployment scripts

**Complete .env template:**

```bash
# .env.example
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here

# Guild IDs for multi-server setup
PERSONAL_GUILD_ID=123456789012345678
STUDIO_GUILD_ID=234567890123456789
UNFCU_GUILD_ID=345678901234567890

# Venice.ai Configuration
VENICE_API_KEY=sk-your-venice-api-key
VENICE_MODEL_SMALL=qwen3-4b
VENICE_MODEL_MEDIUM=mistral-31-24b
VENICE_MODEL_LARGE=qwen3-235b
VENICE_MODEL_IMAGE=flux-dev

# Supabase Configuration
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=optional_password

# n8n Webhook Configuration
N8N_WEBHOOK_BASE=https://your-n8n.com/webhook
N8N_API_KEY=your_n8n_api_key_32_chars_min

# MCP Configuration
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8001

# FastAPI Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# Optional: Monitoring
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

**Docker Compose for local development:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs
    ports:
      - "8000:8000"
    depends_on:
      - redis
    restart: unless-stopped
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
  
  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=changeme
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  redis_data:
  n8n_data:
```

**Production deployment script for Coolify:**

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Deploying PMOVES Bot to Production..."

# Build Docker image
echo "📦 Building Docker image..."
docker build -t pmoves-bot:latest .

# Tag for registry
docker tag pmoves-bot:latest ghcr.io/yourusername/pmoves-bot:latest

# Push to GitHub Container Registry
echo "⬆️ Pushing to registry..."
docker push ghcr.io/yourusername/pmoves-bot:latest

# Trigger Coolify deployment
echo "🔄 Triggering Coolify deployment..."
curl -X POST \
  -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "$COOLIFY_WEBHOOK_URL"

echo "✅ Deployment initiated! Check Coolify dashboard for status."
```

**Supabase SQL setup script:**

```sql
-- setup_database.sql
-- Run this in Supabase SQL Editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Servers configuration table
CREATE TABLE IF NOT EXISTS servers (
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(10) DEFAULT '!',
    personality VARCHAR(50) DEFAULT 'friendly',
    model VARCHAR(100) DEFAULT 'qwen3-235b',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Messages table for RAG
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- Adjust dimension based on your model
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Server features
CREATE TABLE IF NOT EXISTS server_features (
    guild_id BIGINT REFERENCES servers(guild_id) ON DELETE CASCADE,
    feature_name VARCHAR(50),
    enabled BOOLEAN DEFAULT true,
    config JSONB,
    PRIMARY KEY (guild_id, feature_name)
);

-- Audit log for security
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT,
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_embedding ON messages 
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_audit_guild ON audit_log(guild_id);

-- Vector similarity search function
CREATE OR REPLACE FUNCTION match_messages(
    query_embedding vector(384),
    match_threshold float,
    match_count int,
    filter_guild_id bigint
)
RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float,
    created_at timestamp with time zone
)
LANGUAGE sql STABLE
AS $$
    SELECT
        messages.id,
        messages.content,
        messages.metadata,
        1 - (messages.embedding <=> query_embedding) as similarity,
        messages.created_at
    FROM messages
    WHERE messages.guild_id = filter_guild_id
        AND 1 - (messages.embedding <=> query_embedding) > match_threshold
    ORDER BY messages.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Enable Row-Level Security
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE server_features ENABLE ROW LEVEL SECURITY;

-- RLS Policies (service role bypasses these)
CREATE POLICY guild_isolation ON messages
    FOR ALL
    USING (guild_id = current_setting('app.guild_id', true)::BIGINT);

CREATE POLICY guild_servers ON servers
    FOR ALL
    USING (guild_id = current_setting('app.guild_id', true)::BIGINT);

-- Grant permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
```

## Key implementation recommendations and best practices

**Architecture recommendations:** Start with monolithic deployment for simplicity (single Docker container running bot, FastAPI, and MCP server). Migrate to microservices when bot serves 5000+ guilds or requires independent scaling. Use message queue (RabbitMQ or Redis Streams) for asynchronous event processing if handling high message volume. Deploy Redis as separate container for caching and rate limiting. Use Supabase realtime subscriptions for cross-instance coordination if running multiple bot instances.

**ElizaOS and Venice.ai best practices:** Implement multi-provider fallback: Venice.ai as primary, OpenAI as secondary, Anthropic as tertiary. Monitor Venice VCU/USD balance daily and set up alerts at 20% remaining. Use appropriate model sizes: qwen3-4b for simple chat (\u003c$0.01/1K tokens), qwen3-235b for complex reasoning ($0.15/1K tokens). Cache frequent queries in Redis to avoid redundant API calls. Implement request queuing during rate limit periods rather than failing immediately.

**MCP integration strategy:** Deploy MCP server on separate port (8001) from main API (8000) for isolation. Use stdio transport in development for simplicity and fast debugging. Switch to Streamable HTTP in production for better scalability and monitoring. Implement comprehensive logging for all MCP tool invocations including parameters and results. Create separate MCP servers for different capability domains (discord-mcp for Discord ops, workflow-mcp for n8n triggers, data-mcp for database queries).

**N8n workflow organization:** Create separate workflows for each major function: image-gen, tts-generate, animate, comfyui-trigger, upscale. Use n8n's Error Workflow feature to send Discord webhook notifications on any failure. Set appropriate timeouts: 5min for TTS, 10min for image generation, 30min for animation. Implement workflow versioning by exporting workflows to Git repository. Use n8n variables for configuration (API endpoints, model names) to avoid hardcoding.

**Supabase and RAG optimization:** Use HNSW indexing for vector search under 1M messages (provides sub-100ms queries). Switch to IVFFlat for larger datasets (lower memory usage). Implement hybrid search combining vector similarity with keyword matching for better results. Batch embed new messages every 10 seconds rather than individually (reduces API calls by 90%). Set up TimescaleDB hypertable on messages table for automatic partitioning by time. Archive messages older than 90 days to cold storage (S3) to reduce database size.

**Performance monitoring and optimization:** Instrument code with metrics: track command execution time, API latency, cache hit rates, error rates. Export metrics in Prometheus format from FastAPI /metrics endpoint. Set up Grafana dashboard visualizing key metrics. Implement structured JSON logging for easy parsing and analysis. Use correlation IDs to trace requests across services. Set up alerts for: response time \u003e 5 seconds, error rate \u003e 1%, cache hit rate \u003c 70%, API quota utilization \u003e 80%.

**Scaling considerations:** Single VPS handles 50-100 guilds with moderate activity. At 500+ guilds, implement Discord sharding (required at 2500 guilds). Use Redis for cross-shard communication and shared rate limiting. Deploy multiple bot instances behind load balancer for high availability. Implement graceful shutdown handling to avoid losing in-flight requests. Use Kubernetes for container orchestration if deploying across multiple nodes. Monitor memory usage carefully - embeddings consume significant RAM (1GB per 100K cached embeddings).

**Security hardening checklist:** Enable 2FA on all service accounts. Rotate API keys quarterly and immediately after any suspected compromise. Use separate keys for dev/staging/production. Implement API key scoping (separate keys per guild with limited permissions). Enable Supabase RLS policies on all tables. Use non-root user in Docker containers. Mount secrets as read-only files rather than environment variables. Enable audit logging for all privileged operations. Implement rate limiting at multiple layers (per-user, per-guild, per-bot). Use Content Security Policy headers on web dashboard. Enable HTTPS only with valid SSL certificates.

**Disaster recovery procedures:** Automated daily backups of Supabase database to S3 with 30-day retention. Weekly full backup with 1-year retention. Store Docker images in registry with tagged versions for rollback. Document recovery procedures: restore from backup, rebuild containers, verify functionality. Test recovery quarterly to ensure procedures work. Maintain runbook with common failure scenarios and solutions. Set up monitoring with automatic alerts to Discord webhook for critical failures. Implement health checks with automatic container restart on repeated failures.

This comprehensive architecture provides a production-ready foundation for the PMOVES Edition Discord bot, integrating ElizaOS, Venice.ai Pro, MCP, n8n workflows, and Supabase RAG capabilities with seamless deployment from Windows development to Linux VPS production.