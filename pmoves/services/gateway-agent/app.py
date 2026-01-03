#!/usr/bin/env python3
"""
PMOVES Gateway Agent - Orchestrates 100+ MCP Tools

This agent serves as the central orchestrator for all MCP tools in PMOVES.AI:
- Discovers and caches MCP tool definitions
- Routes tool execution requests to appropriate upstream servers
- Stores and retrieves skills from Cipher memory
- Manages GitHub Secrets for secure credential injection

Architecture:
    Gateway Agent (8100)
        ├── Agent Zero MCP API (8080) - Tool discovery
        ├── Cipher Memory (3025) - Skills storage
        ├── TensorZero (3030) - LLM inference
        └── 100+ MCP Tools - Upstream servers
"""

from __future__ import annotations

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AGENT_ZERO_URL = os.environ.get("AGENT_ZERO_URL", "http://agent-zero:8080")
CIPHER_URL = os.environ.get("CIPHER_URL", "http://pmoves-botz-cipher:8000")
TENSORZERO_URL = os.environ.get("TENSORZERO_URL", "http://tensorzero-gateway:3030")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PORT = int(os.environ.get("PORT", "8100"))
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY", "")

# ============================================================================
# Authentication
# ============================================================================

API_KEY_NAME = "X-Gateway-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)) -> Optional[str]:
    """
    Verify API key for protected endpoints.

    If GATEWAY_API_KEY is set, the request must include a matching X-Gateway-API-Key header.
    If GATEWAY_API_KEY is not set, authentication is disabled (for development only).

    Returns:
        The API key string if authenticated, None if auth is disabled.

    Raises:
        HTTPException: If GATEWAY_API_KEY is set but header doesn't match.
    """
    if GATEWAY_API_KEY:
        if api_key_header != GATEWAY_API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid or missing API Key. Provide X-Gateway-API-Key header."
            )
        return api_key_header

    # Auth disabled - warn in production-like environments
    if os.environ.get("ENV", "production") != "development":
        logger.warning("GATEWAY_API_KEY not set - authentication disabled for gateway-agent")

    return None

# FastAPI app
app = FastAPI(
    title="PMOVES Gateway Agent",
    description="Orchestrates 100+ MCP tools with Cipher memory integration",
    version="1.0.0"
)


# ============================================================================
# Models
# ============================================================================

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: str
    mcp_server: str
    parameters: Dict[str, Any] = {}
    enabled: bool = True


class ToolListResponse(BaseModel):
    total: int
    tools: List[ToolDefinition]
    categories: Dict[str, int]


class ToolExecuteRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}
    timeout: int = 30


class ToolExecuteResponse(BaseModel):
    success: bool
    result: Any = None
    error: str = None
    execution_time_ms: int = 0


class SkillStoreRequest(BaseModel):
    name: str
    description: str
    category: str
    pattern: str
    outcome: str
    mcp_tool: str


class SkillSearchRequest(BaseModel):
    query: str
    category: str = None
    limit: int = 10


# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """Discovers and caches MCP tool definitions from Agent Zero"""

    def __init__(self):
        self.agent_zero_url = AGENT_ZERO_URL
        self._cache: Dict[str, List[ToolDefinition]] = {}
        self._last_refresh: Optional[datetime] = None
        self.cache_ttl = int(os.environ.get("TOOL_CACHE_TTL", "300"))  # 5 minutes

    async def discover_tools(self, force_refresh: bool = False) -> List[ToolDefinition]:
        """Discover all available MCP tools"""
        # Check cache
        if not force_refresh and self._cache:
            if self._last_refresh:
                age = (datetime.now() - self._last_refresh).total_seconds()
                if age < self.cache_ttl:
                    logger.debug(f"Using cached tools ({len(self._cache.get('all', []))} tools)")
                    return self._cache.get('all', [])

        # Fetch from Agent Zero MCP API
        tools = await self._fetch_from_agent_zero()

        # Update cache
        self._cache['all'] = tools
        self._last_refresh = datetime.now()

        logger.info(f"Discovered {len(tools)} MCP tools")
        return tools

    async def _fetch_from_agent_zero(self) -> List[ToolDefinition]:
        """Fetch tool definitions from Agent Zero MCP API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get MCP commands from Agent Zero
                response = await client.get(f"{self.agent_zero_url}/mcp/commands")
                response.raise_for_status()
                data = response.json()

                tools = []
                # Process commands from Agent Zero
                # Commands is a list of dicts with 'name' and 'description' keys
                commands = data.get("commands", [])
                if isinstance(commands, list):
                    for cmd_info in commands:
                        # Extract tool info from command metadata
                        cmd_name = cmd_info.get("name") if isinstance(cmd_info, dict) else str(cmd_info)
                        tools.append(ToolDefinition(
                            name=cmd_name,
                            description=cmd_info.get("description", f"MCP command: {cmd_name}") if isinstance(cmd_info, dict) else f"MCP command: {cmd_name}",
                            category=self._infer_category(cmd_name),
                            mcp_server="agent-zero",
                            parameters={},
                            enabled=True
                        ))
                else:
                    # Fallback for dict format (backward compatibility)
                    for cmd_name, cmd_info in commands.items():
                        tools.append(ToolDefinition(
                            name=cmd_name,
                            description=cmd_info.get("description", f"MCP command: {cmd_name}"),
                            category=self._infer_category(cmd_name),
                            mcp_server="agent-zero",
                            parameters=cmd_info.get("arguments", {}),
                            enabled=True
                        ))

                # Also load tools from MCP catalog if available
                try:
                    catalog_response = await client.get(f"{self.agent_zero_url}/mcp/catalog")
                    if catalog_response.status_code == 200:
                        catalog_data = catalog_response.json()
                        for server_name, server_info in catalog_data.get("servers", {}).items():
                            for tool_name in server_info.get("tools", []):
                                tools.append(ToolDefinition(
                                    name=f"{server_name}:{tool_name}",
                                    description=f"{server_name} tool: {tool_name}",
                                    category=self._infer_category(server_name),
                                    mcp_server=server_name,
                                    parameters={},
                                    enabled=True
                                ))
                except Exception as e:
                    logger.debug(f"No MCP catalog available: {e}")

                logger.info(f"Discovered {len(tools)} tools from Agent Zero MCP")
                return tools

        except Exception as e:
            logger.error(f"Failed to fetch tools from Agent Zero: {e}")
            # Return fallback tools based on known services
            return self._get_fallback_tools()

    def _infer_category(self, tool_name: str) -> str:
        """Infer category from tool name"""
        name_lower = tool_name.lower()

        category_map = {
            'infrastructure': ['vps', 'dns', 'hostinger', 'tailscale', 'server'],
            'automation': ['workflow', 'n8n', 'schedule', 'cron'],
            'execution': ['sandbox', 'exec', 'e2b', 'run'],
            'vision': ['image', 'video', 'vl', 'vision', 'analyze'],
            'documents': ['document', 'pdf', 'docling', 'convert', 'extract'],
            'memory': ['cipher', 'memory', 'store', 'recall', 'search'],
            'api': ['postman', 'collection', 'api', 'request'],
            'research': ['hirag', 'supaserch', 'research', 'search', 'query']
        }

        for category, keywords in category_map.items():
            if any(kw in name_lower for kw in keywords):
                return category

        return 'general'

    def _get_fallback_tools(self) -> List[ToolDefinition]:
        """Return fallback tools based on known MCP servers"""
        return [
            ToolDefinition(
                name="n8n_agent:list_workflows",
                description="List all n8n workflows",
                category="automation",
                mcp_server="n8n-agent",
                enabled=True
            ),
            ToolDefinition(
                name="n8n_agent:execute_workflow",
                description="Execute an n8n workflow",
                category="automation",
                mcp_server="n8n-agent",
                parameters={"workflow_id": "string", "input_data": "object"},
                enabled=True
            ),
            ToolDefinition(
                name="docling:convert_document",
                description="Convert documents using Docling",
                category="documents",
                mcp_server="docling-mcp",
                enabled=True
            ),
            ToolDefinition(
                name="cipher:store_memory",
                description="Store memory in Cipher",
                category="memory",
                mcp_server="cipher-memory",
                enabled=True
            ),
            ToolDefinition(
                name="hostinger:list_vps",
                description="List all Hostinger VPS instances",
                category="infrastructure",
                mcp_server="hostinger",
                enabled=True
            ),
        ]


# Global tool registry instance
tool_registry = ToolRegistry()


# ============================================================================
# Secrets Manager
# ============================================================================

class SecretManager:
    """Manages GitHub Secrets for MCP tool credentials"""

    SECRETS_MAP = {
        "HOSTINGER_API_KEY": "hostinger",
        "TAILSCALE_AUTHKEY": "tailscale",
        "TAILSCALE_API_KEY": "tailscale",
        "N8N_API_KEY": "n8n",
        "POSTMAN_API_KEY": "postman",
        "E2B_API_KEY": "e2b",
        "VENICE_API_KEY": "cipher",
        "OPENAI_API_KEY": "openai",
        "ANTHROPIC_API_KEY": "anthropic",
        "GEMINI_API_KEY": "gemini",
    }

    @classmethod
    def get_credential(cls, service: str) -> Optional[str]:
        """Get credential for a specific service"""
        # Try exact service name first
        env_var = f"{service.upper()}_API_KEY"
        value = os.environ.get(env_var)

        # Try authkey variant for Tailscale
        if not value and service.lower() == "tailscale":
            value = os.environ.get("TAILSCALE_AUTHKEY")

        return value

    @classmethod
    def get_all_credentials(cls) -> Dict[str, str]:
        """Get all available credentials (masked for logging)"""
        creds = {}
        for env_var, service in cls.SECRETS_MAP.items():
            value = os.environ.get(env_var)
            if value:
                # Mask the value for logs
                masked = value[:8] + "..." if len(value) > 8 else "***"
                creds[service] = masked
        return creds


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {}

    # Check Agent Zero
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AGENT_ZERO_URL}/healthz")
            services["agent_zero"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        services["agent_zero"] = f"unreachable: {e}"

    # Check Cipher
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{CIPHER_URL}/health")
            services["cipher"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        services["cipher"] = f"unreachable: {e}"

    # Check TensorZero
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{TENSORZERO_URL}/healthz")
            services["tensorzero"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        services["tensorzero"] = f"unreachable: {e}"

    return HealthResponse(
        status="healthy" if all(v == "healthy" for v in services.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        services=services
    )


@app.get("/tools", response_model=ToolListResponse)
async def list_tools(category: str = None, force_refresh: bool = False):
    """List all available MCP tools"""
    tools = await tool_registry.discover_tools(force_refresh=force_refresh)

    if category:
        tools = [t for t in tools if t.category == category]

    # Count by category
    categories = {}
    for tool in await tool_registry.discover_tools():
        categories[tool.category] = categories.get(tool.category, 0) + 1

    return ToolListResponse(
        total=len(tools),
        tools=tools,
        categories=categories
    )


@app.post("/tools/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    request: ToolExecuteRequest,
    _auth: Optional[str] = Depends(get_api_key)
):
    """
    Execute an MCP tool via the Gateway.

    Requires authentication when GATEWAY_API_KEY is set.
    """
    start_time = datetime.now()

    try:
        # Find tool definition
        tools = await tool_registry.discover_tools()
        tool = next((t for t in tools if t.name == request.tool_name), None)

        if not tool:
            return ToolExecuteResponse(
                success=False,
                error=f"Tool not found: {request.tool_name}",
                execution_time_ms=0
            )

        # Route to appropriate upstream server
        result = await _route_to_upstream(tool, request.parameters)

        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return ToolExecuteResponse(
            success=True,
            result=result,
            execution_time_ms=execution_time
        )

    except Exception as e:
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.error(f"Tool execution error: {e}")
        return ToolExecuteResponse(
            success=False,
            error=str(e),
            execution_time_ms=execution_time
        )


async def _route_to_upstream(tool: ToolDefinition, parameters: Dict[str, Any]) -> Any:
    """Route tool execution to the appropriate upstream MCP server"""

    # For stdio-based MCP servers (containers), use docker exec
    if tool.mcp_server.startswith("docker-compose-") or tool.mcp_server.startswith("pmoves-"):
        container_name = tool.mcp_server

        # For container-based MCP servers, we'd call their HTTP API if available
        # or use Agent Zero's MCP proxy
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AGENT_ZERO_URL}/mcp/tools/{tool.name}/execute",
                json={"parameters": parameters},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()

    # For HTTP-based MCP servers
    return {"message": "Tool routed to upstream", "server": tool.mcp_server}


@app.post("/skills/store", response_model=dict)
async def store_skill(
    request: SkillStoreRequest,
    background_tasks: BackgroundTasks,
    _auth: Optional[str] = Depends(get_api_key)
):
    """
    Store a learned skill pattern in Cipher memory.

    Requires authentication when GATEWAY_API_KEY is set.
    """
    try:
        # Store in Cipher memory
        skill_data = {
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "pattern": request.pattern,
            "outcome": request.outcome,
            "mcp_tool": request.mcp_tool,
            "created_at": datetime.now().isoformat()
        }

        # Store via Cipher API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{CIPHER_URL}/skills/store",
                json=skill_data
            )
            response.raise_for_status()
            return response.json()

    except Exception as e:
        logger.error(f"Failed to store skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/search", response_model=dict)
async def search_skills(
    request: SkillSearchRequest,
    _auth: Optional[str] = Depends(get_api_key)
):
    """
    Search for skills in Cipher memory.

    Requires authentication when GATEWAY_API_KEY is set.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"query": request.query, "limit": request.limit}
            if request.category:
                params["category"] = request.category

            response = await client.get(
                f"{CIPHER_URL}/skills/search",
                params=params
            )
            response.raise_for_status()
            return response.json()

    except Exception as e:
        logger.error(f"Failed to search skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/secrets", response_model=Dict[str, str], dependencies=[Depends(get_api_key)])
async def list_secrets():
    """
    List available service credentials (masked for security).

    **Requires Authentication**: X-Gateway-API-Key header must be provided
    if GATEWAY_API_KEY is set in the environment.
    """
    return SecretManager.get_all_credentials()


# ============================================================================
# Main Entry Point
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize tool registry on startup"""
    logger.info("Gateway Agent starting up...")
    logger.info(f"Agent Zero URL: {AGENT_ZERO_URL}")
    logger.info(f"Cipher URL: {CIPHER_URL}")
    logger.info(f"TensorZero URL: {TENSORZERO_URL}")

    # Initial tool discovery
    await tool_registry.discover_tools(force_refresh=True)

    # Log available secrets count
    secrets = SecretManager.get_all_credentials()
    logger.info(f"Loaded {len(secrets)} service credentials from environment")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Gateway Agent shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=os.environ.get("ENV", "production") == "development",
        log_level="info"
    )
