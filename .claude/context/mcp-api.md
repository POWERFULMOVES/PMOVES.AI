# Agent Zero MCP API Reference

**Model Context Protocol (MCP)** is the standardized API for agent-to-agent communication in PMOVES.AI. Agent Zero exposes an MCP server that other services use for orchestration and task delegation.

## MCP Server Endpoint

**Base URL:** `http://localhost:8080/mcp/`

**Agent Zero** acts as the central MCP server, allowing:
- External services to issue commands to agents
- Archon to manage agent forms and prompts
- SupaSerch to delegate tasks requiring agent execution
- Custom integrations to leverage agent capabilities

## Authentication

MCP endpoints require authentication:

```bash
# Set environment variables
export MCP_CLIENT_ID="your-client-id"
export MCP_CLIENT_SECRET="your-secret-key"

# Include in requests
curl -X POST http://localhost:8080/mcp/command \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"command": "..."}'
```

## Core MCP Endpoints

### Health Check

**`GET /mcp/health`**

Check if MCP server is operational.

```bash
curl http://localhost:8080/mcp/health
```

**Response:**
```json
{
  "status": "healthy",
  "mcp_version": "1.0",
  "agent_runtime": "operational",
  "nats_connected": true
}
```

### List Available Commands

**`GET /mcp/commands`**

Get list of available MCP commands.

```bash
curl http://localhost:8080/mcp/commands \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

**Response:**
```json
{
  "commands": [
    {
      "name": "execute_task",
      "description": "Execute a task via agent runtime",
      "parameters": ["task_description", "context"]
    },
    {
      "name": "create_subordinate",
      "description": "Create a subordinate agent for specialized tasks",
      "parameters": ["agent_config"]
    },
    {
      "name": "query_agent_status",
      "description": "Get status of agent or subordinate",
      "parameters": ["agent_id"]
    }
  ]
}
```

### Execute Task

**`POST /mcp/execute`**

Request Agent Zero to execute a task.

```bash
curl -X POST http://localhost:8080/mcp/execute \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze the logs from hi-rag-v2 and identify performance bottlenecks",
    "context": {
      "service": "hi-rag-v2",
      "time_range": "last_1h"
    },
    "priority": "normal",
    "timeout_seconds": 300
  }'
```

**Response:**
```json
{
  "task_id": "task-12345",
  "status": "accepted",
  "estimated_completion": "2025-12-06T12:05:00Z",
  "assigned_agent": "agent-0"
}
```

### Query Task Status

**`GET /mcp/task/{task_id}`**

Check status of previously submitted task.

```bash
curl http://localhost:8080/mcp/task/task-12345 \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

**Response:**
```json
{
  "task_id": "task-12345",
  "status": "completed",
  "result": {
    "findings": "Analysis of hi-rag-v2 logs...",
    "recommendations": ["Recommendation 1", "Recommendation 2"]
  },
  "execution_time_seconds": 234,
  "agent_id": "agent-0"
}
```

### Create Subordinate Agent

**`POST /mcp/subordinate/create`**

Create a specialized subordinate agent for focused tasks.

```bash
curl -X POST http://localhost:8080/mcp/subordinate/create \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "log-analyzer",
      "specialization": "log analysis and pattern detection",
      "tools": ["grep", "awk", "analysis"],
      "context_allocation": 0.3,
      "prompts": {
        "system": "You are a specialized log analysis agent..."
      }
    }
  }'
```

**Response:**
```json
{
  "subordinate_id": "agent-1",
  "parent_id": "agent-0",
  "status": "created",
  "capabilities": ["log_analysis", "pattern_detection"]
}
```

### List Agents

**`GET /mcp/agents`**

Get list of active agents (supervisor + subordinates).

```bash
curl http://localhost:8080/mcp/agents \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

**Response:**
```json
{
  "agents": [
    {
      "id": "agent-0",
      "type": "supervisor",
      "status": "active",
      "tasks_running": 2,
      "subordinates": ["agent-1"]
    },
    {
      "id": "agent-1",
      "type": "subordinate",
      "parent": "agent-0",
      "specialization": "log-analyzer",
      "status": "idle"
    }
  ]
}
```

## MCP Integration Patterns

### Archon → Agent Zero

Archon uses MCP to:
- Submit agent tasks from Supabase-backed forms
- Manage agent configurations and prompts
- Query agent status for UI display

**Example:** Archon UI creates task → Posts to Archon server → Calls Agent Zero MCP API → Agent executes

### SupaSerch → Agent Zero

SupaSerch uses MCP for:
- Code execution tasks during research
- Web crawling/scraping operations
- Tool use that requires agent runtime

**Example:** SupaSerch research needs code execution → Publishes to NATS → Agent Zero picks up → Executes via MCP tools

### Custom Services → Agent Zero

Your services can integrate via MCP:

```python
import requests

class AgentZeroMCPClient:
    def __init__(self, base_url, client_secret):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {client_secret}",
            "Content-Type": "application/json"
        }

    def execute_task(self, task, context=None):
        response = requests.post(
            f"{self.base_url}/mcp/execute",
            headers=self.headers,
            json={
                "task": task,
                "context": context or {},
                "priority": "normal"
            }
        )
        return response.json()

    def get_task_status(self, task_id):
        response = requests.get(
            f"{self.base_url}/mcp/task/{task_id}",
            headers=self.headers
        )
        return response.json()

# Usage
client = AgentZeroMCPClient(
    "http://localhost:8080",
    os.getenv("MCP_CLIENT_SECRET")
)

result = client.execute_task(
    "Analyze system logs for errors",
    context={"time_range": "1h"}
)
print(f"Task ID: {result['task_id']}")
```

## MCP Configuration

**Environment Variables:**

```bash
# Agent Zero MCP Server
MCP_SERVICE_URL=http://localhost:8080/mcp
MCP_CLIENT_ID=your-client-id
MCP_CLIENT_SECRET=your-secret-key

# JetStream for reliable delivery
AGENTZERO_JETSTREAM=true
```

## MCP + NATS Integration

Agent Zero's MCP API integrates with NATS for:
- **Task queue** - Tasks submitted via MCP can be queued in NATS
- **Event notifications** - Task completion published to NATS subjects
- **Reliable delivery** - JetStream ensures no task loss

**Flow:**
1. Client calls MCP API → Agent Zero accepts task
2. Agent Zero queues task in NATS JetStream
3. Agent runtime processes task
4. Result published to NATS + returned via MCP

## Agent Capabilities Exposed via MCP

### Tool Use
- **Code execution** - Python, Bash, etc.
- **Web crawling** - HTTP requests, scraping
- **File operations** - Read, write, search
- **Database queries** - Supabase, Postgres

### Subordinate Management
- **Create specialized agents** - Focused on narrow tasks
- **Least privilege** - Limited tool access for subordinates
- **Context efficiency** - Smaller context allocations

### Knowledge Access
- **Hi-RAG integration** - Query knowledge base
- **SupaSerch access** - Trigger deep research
- **Open Notebook** - Store/retrieve notes

## MCP Security

**Best Practices:**

1. **Rotate secrets regularly** - Change `MCP_CLIENT_SECRET` periodically
2. **Use HTTPS in production** - Never send secrets over plain HTTP
3. **Limit client IDs** - One per service, track usage
4. **Audit MCP calls** - Log all API requests for security review
5. **Rate limiting** - Protect against abuse (implement if needed)

## MCP Error Handling

**Common error codes:**

```json
{
  "error": "unauthorized",
  "code": 401,
  "message": "Invalid or missing MCP client secret"
}
```

```json
{
  "error": "task_timeout",
  "code": 408,
  "message": "Task exceeded timeout of 300 seconds",
  "task_id": "task-12345"
}
```

```json
{
  "error": "agent_unavailable",
  "code": 503,
  "message": "No agents available to process task",
  "retry_after": 30
}
```

**Error handling pattern:**

```python
response = requests.post(url, json=payload, headers=headers)

if response.status_code == 401:
    print("Authentication failed - check MCP_CLIENT_SECRET")
elif response.status_code == 408:
    print("Task timed out - consider increasing timeout")
elif response.status_code == 503:
    print("Agents busy - retry after delay")
else:
    result = response.json()
```

## Monitoring MCP Usage

**Via Agent Zero Metrics:**

```bash
curl http://localhost:8080/metrics | grep mcp
```

**Metrics include:**
- `mcp_requests_total` - Total MCP API calls
- `mcp_tasks_active` - Currently executing tasks
- `mcp_tasks_completed` - Completed task count
- `mcp_errors_total` - Error count by type

**Via NATS:**

MCP activity is logged to NATS subjects:
- Task submissions
- Completion events
- Error notifications

## Persona-Based Agent Creation

**NEW:** `POST /mcp/subordinate/create-with-persona`

Create a subordinate agent from a persona configuration stored in Supabase. Personas define agent behavior, tools, and personality.

```bash
curl -X POST http://localhost:8080/mcp/subordinate/create-with-persona \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "uuid",
    "context_allocation": 0.3,
    "parent_agent_id": "agent-0",
    "overrides": {
      "model": "claude-opus-4-5",
      "temperature": 0.5
    },
    "enhancement_ids": ["uuid1", "uuid2"],
    "create_subordinate": true
  }'
```

**Request Parameters:**
- `persona_id` (required): UUID of persona from Supabase `pmoves_core.personas`
- `context_allocation` (optional): Context window allocation (0.0-1.0, default: 0.3)
- `parent_agent_id` (optional): Parent agent for subordinate relationship
- `overrides` (optional): Runtime parameter overrides (model, temperature, max_tokens, tools)
- `enhancement_ids` (optional): Specific enhancement IDs to apply
- `create_subordinate` (optional): Whether to create the agent (default: true)

**Response:**
```json
{
  "agent_id": "agent-2",
  "config": {
    "name": "Developer",
    "specialization": "Software engineering specialist for PMOVES.AI",
    "thread_type": "chained",
    "model": "claude-sonnet-4-5",
    "temperature": 0.3,
    "max_tokens": 4096,
    "tools": ["git", "code-review", "testing", "documentation"],
    "behavior_weights": {"decode": 0.3, "retrieve": 0.4, "generate": 0.3},
    "nats_subscriptions": ["claude.code.tool.executed.v1"],
    "grounding_packs": ["pmoves-architecture@1.0", "python-patterns@1.0"]
  },
  "persona": {
    "persona_id": "uuid",
    "name": "Developer",
    "version": "1.0",
    "thread_type": "chained"
  },
  "enhancements_applied": [
    {"enhancement_id": "uuid1", "type": "tool", "name": "code-review-access"}
  ]
}
```

### Thread Types

Personas support different orchestration patterns via `thread_type`:

| Thread Type | Description | Use Case | Coordination |
|-------------|-------------|----------|--------------|
| `base` | Single agent, single task | Simple queries, direct actions | none |
| `parallel` | Multiple independent agents | Multi-source research, concurrent tasks | result_aggregation |
| `chained` | Sequential agent handoff | Multi-step workflows, validation pipelines | sequential_handoff |
| `fusion` | Collaborative single output | Complex analysis, consensus building | collaborative_merge |
| `big` | Large context orchestration | Complex projects, architectural design | central_planner |
| `zero_touch` | Fully automated execution | Background tasks, scheduled operations | event_driven |

### Persona Management Endpoints

**`GET /api/persona/list`** - List available personas
```bash
curl http://localhost:8080/api/persona/list?active_only=true&thread_type=chained
```

**`GET /api/persona/{persona_id}`** - Get persona details
```bash
curl http://localhost:8080/api/persona/{uuid}
```

**`GET /api/persona/enhancements/{persona_id}`** - Get persona enhancements
```bash
curl http://localhost:8080/api/persona/enhancements/{uuid}
```

## Future MCP Enhancements

Planned features:
- **Streaming responses** - Real-time task progress via SSE
- **Batch operations** - Submit multiple tasks in one call
- **Agent scheduling** - Schedule tasks for future execution
- **Agent pools** - Dedicated agent groups for specific workloads
- **Persona versioning** - A/B test different persona versions
- **Persona analytics** - Track persona performance metrics

## Developer Notes

**For Claude Code CLI users:**
- Use MCP API to delegate complex tasks to Agent Zero
- MCP is already configured for Archon and SupaSerch
- Create custom MCP clients for your services
- All MCP calls require authentication
- Check `/mcp/health` before submitting tasks
- Monitor task status for long-running operations

**Integration checklist:**
1. Set `MCP_CLIENT_SECRET` in environment
2. Test connectivity: `curl http://localhost:8080/mcp/health`
3. Implement error handling for all MCP calls
4. Log MCP usage for debugging
5. Use appropriate timeout values based on task complexity
