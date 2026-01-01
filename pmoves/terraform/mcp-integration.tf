# ====================================================================
# MCP Integration Terraform Configuration
# PMOVES.AI Hostinger Deployment with Submodule Architecture
# ====================================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    hostinger = {
      source  = "hostinger/hostinger"
      version = "~> 0.1.3"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# ====================================================================
# Variables for PMOVES.AI Deployment
# ====================================================================

variable "hostinger_api_token" {
  description = "Hostinger API authentication token (MCP)"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Project identifier (used for resource naming and namespacing)"
  type        = string
  default     = "pmoves-ai"
  validation {
    condition     = can(regex("^[a-z0-9-]{3,30}$", var.project_name))
    error_message = "Project name must be 3-30 chars, lowercase alphanumeric + hyphens."
  }
}

variable "vps_plan" {
  description = "Hostinger VPS plan for gateway (recommend 6GB+ for multi-service stack)"
  type        = string
  default     = "hostingercom-vps-kvm2-usd-4m"  # 8GB RAM / 8 vCPU / 200GB SSD
}

variable "data_center_id" {
  description = "Data center location (13=US, 23=UK, 4=Canada, etc.)"
  type        = number
  default     = 13
}

variable "hostname" {
  description = "VPS hostname (FQDN)"
  type        = string
  default     = "pmoves-gateway.example.com"
}

variable "root_password" {
  description = "Root password for VPS (12+ chars, mixed case)"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for passwordless access"
  type        = string
  default     = ""
  sensitive   = true
}

variable "domain_name" {
  description = "Base domain for services (DNS, TLS certificates)"
  type        = string
  default     = "pmoves.local"
}

variable "git_repo_url" {
  description = "PMOVES.AI git repository URL"
  type        = string
  default     = "https://github.com/POWERFULMOVES/PMOVES.AI.git"
}

variable "git_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "submodule_init" {
  description = "Whether to initialize and update git submodules on deployment"
  type        = bool
  default     = true
}

variable "docker_compose_profile" {
  description = "Docker Compose profile to activate (full, agents, knowledge, media, monitoring)"
  type        = string
  default     = "full"
  validation {
    condition     = contains(["full", "agents", "knowledge", "media", "monitoring", "yt"], var.docker_compose_profile)
    error_message = "Profile must be one of: full, agents, knowledge, media, monitoring, yt"
  }
}

variable "enable_gpu" {
  description = "Enable GPU support (Hi-RAG v2, ComfyUI model inference)"
  type        = bool
  default     = false  # Requires GPU-enabled host
}

variable "nats_url" {
  description = "NATS broker URL for event messaging"
  type        = string
  default     = "nats://nats:4222"
}

variable "supabase_url" {
  description = "Supabase project URL (if using external Supabase)"
  type        = string
  default     = ""
}

variable "supabase_service_key" {
  description = "Supabase service role API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "open_notebook_api_url" {
  description = "Open Notebook API URL for knowledge base"
  type        = string
  default     = ""
}

variable "open_notebook_api_token" {
  description = "Open Notebook API authentication token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "hirag_url" {
  description = "Hi-RAG v2 gateway URL for GPU retrieval"
  type        = string
  default     = "http://hirag-v2:8192"
}

variable "comfyui_webhook_url" {
  description = "ComfyUI webhook URL for render callbacks"
  type        = string
  default     = "http://comfyui:8188"
}

variable "youtube_api_key" {
  description = "YouTube Data API key (for channel monitoring)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "monitoring_retention_days" {
  description = "Prometheus metrics retention period"
  type        = number
  default     = 30
}

# ====================================================================
# Local Variables & Computed Values
# ====================================================================

locals {
  environment = "production"
  region      = "us-east-1"
  
  service_ports = {
    agent_zero   = 8080
    agent_zero_ui = 8081
    archon       = 8091
    archon_ui    = 3737
    pmoves_yt    = 8077
    hirag        = 8192
    comfyui      = 8188
    supabase_rest = 65421
    neo4j_browser = 7474
    neo4j_bolt   = 7687
    qdrant       = 6333
    prometheus   = 9090
    grafana      = 3000
    nats         = 4222
    nats_mgmt    = 8222
    minio_api    = 9000
    minio_console = 9001
    nginx_http   = 80
    nginx_https  = 443
  }
  
  submodules = [
    "PMOVES-Agent-Zero",
    "PMOVES-Archon",
    "archon-ui-main",
    "pmoves-yt",
    "hi-rag-v2",
    "open-notebook-api"
  ]
  
  common_tags = {
    Project     = var.project_name
    Environment = local.environment
    ManagedBy   = "Terraform"
    Repository  = "PMOVES.AI"
    CreatedAt   = timestamp()
  }
}

# ====================================================================
# VPS Instance Provisioning
# ====================================================================

resource "hostinger_vps" "pmoves_gateway" {
  plan           = var.vps_plan
  data_center_id = var.data_center_id
  hostname       = var.hostname
  password       = var.root_password
  
  ssh_key_ids = var.ssh_public_key != "" ? [hostinger_vps_ssh_key.deployer[0].id] : []
  
  tags = {
    Environment = "production"
    Project     = var.project_name
    Services    = "agent-zero,archon,pmoves-yt,hirag,supabase,neo4j,qdrant,monitoring"
    Role        = "pmoves-ai-gateway"
  }
  
  lifecycle {
    ignore_changes = [password, ssh_key_ids]
  }
}

# SSH Key Management (optional)
resource "hostinger_vps_ssh_key" "deployer" {
  count       = var.ssh_public_key != "" ? 1 : 0
  name        = "${var.project_name}-deployer"
  public_key  = var.ssh_public_key
  description = "Deployer SSH key for PMOVES.AI CI/CD"
}

# ====================================================================
# Bootstrap Script - Install Docker & Deploy PMOVES.AI
# ====================================================================

resource "hostinger_vps_post_install_script" "pmoves_bootstrap" {
  name        = "${var.project_name}-bootstrap"
  description = "Initialize VPS with Docker, Git, and PMOVES.AI deployment"
  
  script = base64encode(templatefile("${path.module}/bootstrap-script.sh", {
    project_name                = var.project_name
    git_repo_url                = var.git_repo_url
    git_branch                  = var.git_branch
    submodule_init              = var.submodule_init
    docker_compose_profile      = var.docker_compose_profile
    enable_gpu                  = var.enable_gpu
    nats_url                    = var.nats_url
    supabase_url                = var.supabase_url
    supabase_service_key        = var.supabase_service_key
    open_notebook_api_url       = var.open_notebook_api_url
    open_notebook_api_token     = var.open_notebook_api_token
    hirag_url                   = var.hirag_url
    comfyui_webhook_url         = var.comfyui_webhook_url
    youtube_api_key             = var.youtube_api_key
    monitoring_retention_days   = var.monitoring_retention_days
    domain_name                 = var.domain_name
  }))
}

# ====================================================================
# Configuration Files Generation (local)
# ====================================================================

# Generate comprehensive deployment documentation
resource "local_file" "deployment_manifest" {
  filename = "${path.module}/deployment-manifest-${var.project_name}.md"
  
  content = <<-EOT
    # PMOVES.AI Deployment Manifest
    Generated: ${timestamp()}
    
    ## Gateway VPS
    - **Hostname**: ${hostinger_vps.pmoves_gateway.hostname}
    - **IP Address**: ${hostinger_vps.pmoves_gateway.ip_address}
    - **VPS ID**: ${hostinger_vps.pmoves_gateway.id}
    - **Plan**: ${var.vps_plan}
    - **Status**: ${hostinger_vps.pmoves_gateway.status}
    
    ## Service Architecture
    
    ### Core Orchestration (Agent Coordination)
    - **Agent Zero** (Port 8080/8081)
      - Control plane supervisor
      - NATS event bus integration
      - MCP command interface
      - Dashboard: http://${hostinger_vps.pmoves_gateway.ip_address}:8081
    
    - **Archon** (Port 8091/3737)
      - Supabase-driven agent
      - Form-based prompt management
      - Archon UI: http://${hostinger_vps.pmoves_gateway.ip_address}:3737
    
    - **Mesh Agent**
      - Distributed node announcer
      - Multi-host orchestration support
    
    ### Content Ingestion
    - **PMOVES.YT** (Port 8077)
      - Video ingestion pipeline
      - Transcription & chunking
      - Ingest API: POST http://${hostinger_vps.pmoves_gateway.ip_address}:8077/yt/ingest
    
    - **Channel Monitor**
      - YouTube/RSS feed watcher
      - Automated content discovery
    
    ### AI & Retrieval Services
    - **Hi-RAG v2** (Port 8192)
      - GPU-accelerated retrieval
      - Vector embeddings generation
      - Semantic search
    
    - **ComfyUI** (Port 8188)
      - Visual content generation
      - Image processing workflows
      - StableDiffusion, ControlNet, custom nodes
    
    ### Data & Knowledge Layer
    - **Supabase** (Port 65421)
      - PostgreSQL database
      - PostgREST API (auto-generated)
      - Realtime subscriptions
    
    - **Neo4j** (Ports 7474/7687)
      - Knowledge graph database
      - Entity relationship management
      - Browser UI: http://${hostinger_vps.pmoves_gateway.ip_address}:7474
    
    - **Qdrant** (Port 6333)
      - Vector embeddings storage
      - Semantic search index
      - REST API: http://${hostinger_vps.pmoves_gateway.ip_address}:6333
    
    - **Open Notebook API**
      - Knowledge base storage
      - Document management
    
    ### Message Bus & Events
    - **NATS** (Port 4222/8222)
      - Pub/Sub event broker
      - Inter-service communication
      - Management: http://${hostinger_vps.pmoves_gateway.ip_address}:8222
    
    ### Monitoring & Observability
    - **Prometheus** (Port 9090)
      - Metrics collection
      - Retention: ${var.monitoring_retention_days} days
      - Dashboard: http://${hostinger_vps.pmoves_gateway.ip_address}:9090
    
    - **Grafana** (Port 3000)
      - Visualization & dashboards
      - Data source: Prometheus
      - Dashboard: http://${hostinger_vps.pmoves_gateway.ip_address}:3000
    
    ### Reverse Proxy & Load Balancing
    - **Nginx** (Ports 80/443)
      - HTTP/HTTPS termination
      - Route consolidation
      - TLS certificates
    
    ## Git Submodules
    The following submodules are initialized during bootstrap:
    ${join("\n    ", [for sm in local.submodules : "- ${sm}"])}
    
    ## Deployment Profile
    **Selected Profile**: ${var.docker_compose_profile}
    
    This profile enables the following service groups:
    %{if var.docker_compose_profile == "full"~}
    ✓ All services (agents, knowledge, media, monitoring)
    %{endif~}
    %{if var.docker_compose_profile == "agents"~}
    ✓ Core agents (Agent Zero, Archon, Mesh Agent)
    %{endif~}
    %{if var.docker_compose_profile == "knowledge"~}
    ✓ Data services (Supabase, Neo4j, Qdrant, Open Notebook)
    %{endif~}
    %{if var.docker_compose_profile == "media"~}
    ✓ Media processing (ComfyUI, Hi-RAG v2)
    %{endif~}
    %{if var.docker_compose_profile == "monitoring"~}
    ✓ Observability (Prometheus, Grafana, NATS management)
    %{endif~}
    
    ## Environment Configuration
    
    ### NATS Event Bus
    - URL: ${var.nats_url}
    - Purpose: Event-driven orchestration, inter-service messaging
    
    ### Supabase Integration
    - URL: ${var.supabase_url != "" ? var.supabase_url : "Internal (docker-compose)"}
    - Service Key: [REDACTED]
    - Purpose: Agent state, form management, knowledge storage
    
    ### Hi-RAG v2 Configuration
    - Gateway URL: ${var.hirag_url}
    - GPU Support: ${var.enable_gpu ? "ENABLED" : "DISABLED"}
    - Purpose: Vector embeddings, semantic retrieval
    
    ### ComfyUI Configuration
    - Webhook URL: ${var.comfyui_webhook_url}
    - Purpose: Image generation workflows, render callbacks
    
    ### Knowledge Management
    - Open Notebook API: ${var.open_notebook_api_url != "" ? var.open_notebook_api_url : "Not configured"}
    - Purpose: Knowledge base, document storage
    
    ### Content Discovery
    - YouTube API Key: ${var.youtube_api_key != "" ? "[CONFIGURED]" : "[NOT CONFIGURED]"}
    - Channel Monitor: Active (when YT profile enabled)
    
    ## Access Instructions
    
    ### SSH Access
    \`\`\`bash
    ssh root@${hostinger_vps.pmoves_gateway.ip_address}
    \`\`\`
    
    ### View Running Services
    \`\`\`bash
    cd /opt/pmoves-ai
    docker compose ps
    \`\`\`
    
    ### Check Logs
    \`\`\`bash
    # Agent Zero
    docker compose logs -f agent-zero
    
    # Archon
    docker compose logs -f archon
    
    # PMOVES.YT
    docker compose logs -f pmoves-yt
    \`\`\`
    
    ### Monitor Events
    \`\`\`bash
    # Subscribe to NATS events
    nats sub ">" --server=${var.nats_url}
    \`\`\`
    
    ## Service Health Checks
    
    ### Agent Zero
    \`\`\`bash
    curl http://${hostinger_vps.pmoves_gateway.ip_address}:8080/healthz
    \`\`\`
    
    ### Archon
    \`\`\`bash
    curl http://${hostinger_vps.pmoves_gateway.ip_address}:8091/healthz
    \`\`\`
    
    ### Neo4j
    \`\`\`bash
    curl http://${hostinger_vps.pmoves_gateway.ip_address}:7474/browser/
    \`\`\`
    
    ### Prometheus
    \`\`\`bash
    curl http://${hostinger_vps.pmoves_gateway.ip_address}:9090/api/v1/targets
    \`\`\`
    
    ## Typical Workflow
    
    1. **Content Discovery**
       - Channel Monitor detects new YouTube videos
       - Posts to PMOVES.YT /ingest endpoint
    
    2. **Video Processing**
       - Download & transcription
       - Chunking into logical segments
       - Metadata extraction
    
    3. **Vector Generation**
       - Hi-RAG v2 generates embeddings
       - Stores in Qdrant
    
    4. **Knowledge Management**
       - Neo4j stores entity relationships
       - Open Notebook API archives documents
       - Supabase manages state
    
    5. **Agent Orchestration**
       - Agent Zero coordinates tasks via NATS
       - Archon manages prompts & forms
       - Mesh Agent tracks distributed nodes
    
    6. **Content Generation**
       - ComfyUI generates related visuals
       - Webhooks return results to Agent Zero
    
    7. **Monitoring**
       - Prometheus collects metrics
       - Grafana visualizes dashboards
       - Alerts trigger on anomalies
    
    ## Security Checklist
    
    - [ ] SSH key configured for passwordless access
    - [ ] Firewall rules restrict access (allow: 22, 80, 443 minimum)
    - [ ] Secrets stored in environment variables (not committed to git)
    - [ ] HTTPS enabled (nginx + self-signed or Let's Encrypt)
    - [ ] Supabase service key rotated regularly
    - [ ] GPU compute isolation (if enabled)
    - [ ] NATS authentication configured (production)
    - [ ] Database backups scheduled
    - [ ] API rate limiting enabled on public endpoints
    - [ ] Audit logging for sensitive operations
    
    ## Next Steps
    
    1. SSH into gateway and verify Docker Compose health
    2. Configure firewall rules for service accessibility
    3. Set up DNS records pointing to ${hostinger_vps.pmoves_gateway.ip_address}
    4. Install/configure SSL/TLS certificates
    5. Create PMOVES.AI admin accounts in Supabase
    6. Configure YouTube API key in Channel Monitor
    7. Add channels to monitor in configuration
    8. Test ingest pipeline with sample video
    9. Configure Grafana dashboards
    10. Implement backup & disaster recovery procedures
    
    ## Support & Debugging
    
    - **Agent Zero Issues**: Check /mcp/* endpoints for MCP command errors
    - **Archon Connection**: Verify Supabase SUPA_REST_URL is reachable
    - **NATS Events**: Monitor NATS dashboard (port 8222)
    - **GPU Memory**: Monitor ComfyUI/Hi-RAG v2 VRAM usage
    - **Database**: Use psql or Supabase dashboard to inspect Postgres
    - **Knowledge Graph**: Access Neo4j Browser to query entities
    
    ---
    Generated by Terraform MCP Integration
    Repository: ${var.git_repo_url}
    Branch: ${var.git_branch}
  EOT
}

# ====================================================================
# Outputs
# ====================================================================

output "gateway_hostname" {
  description = "Gateway VPS hostname"
  value       = hostinger_vps.pmoves_gateway.hostname
}

output "gateway_ip_address" {
  description = "Gateway VPS public IP address"
  value       = hostinger_vps.pmoves_gateway.ip_address
}

output "gateway_id" {
  description = "Hostinger VPS resource ID"
  value       = hostinger_vps.pmoves_gateway.id
}

output "ssh_access_command" {
  description = "SSH command to connect to gateway"
  value       = "ssh root@${hostinger_vps.pmoves_gateway.ip_address}"
}

output "service_endpoints" {
  description = "All service endpoints"
  value = {
    agent_zero    = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.agent_zero}"
    agent_zero_ui = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.agent_zero_ui}"
    archon_api    = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.archon}"
    archon_ui     = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.archon_ui}"
    pmoves_yt     = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.pmoves_yt}/yt"
    hirag         = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.hirag}"
    comfyui       = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.comfyui}"
    neo4j_browser = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.neo4j_browser}"
    qdrant        = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.qdrant}"
    prometheus    = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.prometheus}"
    grafana       = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.grafana}"
    nats_mgmt     = "http://${hostinger_vps.pmoves_gateway.ip_address}:${local.service_ports.nats_mgmt}"
  }
}

output "git_submodules" {
  description = "Initialized git submodules"
  value       = local.submodules
}

output "deployment_manifest_path" {
  description = "Path to generated deployment manifest"
  value       = local_file.deployment_manifest.filename
}

output "docker_compose_profile" {
  description = "Active Docker Compose profile"
  value       = var.docker_compose_profile
}

output "gpu_support_enabled" {
  description = "GPU acceleration enabled for Hi-RAG v2 / ComfyUI"
  value       = var.enable_gpu
}
