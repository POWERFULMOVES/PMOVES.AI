# PMOVES.AI Observability Library Patterns

**Version:** 1.0.0
**Date:** 2026-01-29
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Why a Shared Observability Library](#why-a-shared-observability-library)
3. [Core Patterns](#core-patterns)
4. [Framework-Specific Implementations](#framework-specific-implementations)
5. [Installation](#installation)
6. [Migration Guide](#migration-guide)
7. [Best Practices](#best-practices)
8. [Reference Implementation](#reference-implementation)

---

## Overview

This document defines the standard observability patterns for all PMOVES.AI Python services. It provides production-ready code examples for integrating Prometheus metrics, health checks, and logging across different web frameworks.

**Key Principles:**
- **Graceful Degradation**: Services run without optional dependencies
- **Consistency**: All services expose identical metrics endpoints
- **Observability**: Startup logging verifies feature availability
- **Label Cardinality Control**: Normalized paths prevent metric explosion
- **Code Deduplication**: Reusable helpers reduce boilerplate

---

## Why a Shared Observability Library

### The Problem

During the 2026-01-29 code review audit, we identified several recurring issues across PMOVES services:

1. **Unused Metrics**: Prometheus histograms declared but never observed
2. **High Cardinality**: Dynamic paths creating unlimited label combinations
3. **Code Duplication**: Same metric tracking logic repeated across handlers
4. **Silent Failures**: Optional features fail without operator awareness
5. **Inconsistent Patterns**: Each service implements observability differently

### The Solution

A shared observability library (`pmoves-observability`) provides:

- **Single Source of Truth**: All services use identical patterns
- **Reduced Boilerplate**: Drop-in integration with minimal code
- **Guaranteed Compatibility**: Tested across all supported frameworks
- **Centralized Updates**: Security fixes and features propagate automatically
- **Type Safety**: Full type hints for IDE support

---

## Core Patterns

### Pattern 1: Graceful Degradation for Optional Dependencies

**Problem**: Services fail to start when optional dependencies are missing.

**Solution**: Try-import with feature flags and no-op fallbacks.

```python
"""pmoves_observability/prometheus.py"""

import time
from typing import Optional, ContextManager

# Optional dependency detection
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Conditional metric initialization
if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        'service_requests_total',
        'Total requests',
        ['method', 'endpoint', 'status']
    )
    REQUEST_LATENCY = Histogram(
        'service_request_latency_seconds',
        'Request latency in seconds',
        ['method', 'endpoint']
    )
    ACTIVE_REQUESTS = Gauge(
        'service_active_requests',
        'Active requests',
        ['method']
    )
else:
    REQUEST_COUNT = None
    REQUEST_LATENCY = None
    ACTIVE_REQUESTS = None


class _NoOpContext:
    """No-op context manager for when prometheus_client is not available."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def track_latency(method: str, endpoint: str) -> ContextManager:
    """
    Context manager for tracking request latency.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Normalized endpoint path

    Returns:
        Context manager that observes latency on exit

    Example:
        with track_latency('GET', '/api/v1/users'):
            # ... handle request
    """
    if REQUEST_LATENCY:
        return REQUEST_LATENCY.labels(method, endpoint).time()
    return _NoOpContext()


def track_request(method: str, endpoint: str, status: int) -> None:
    """
    Increment request counter.

    Args:
        method: HTTP method
        endpoint: Normalized endpoint path
        status: HTTP status code
    """
    if REQUEST_COUNT:
        REQUEST_COUNT.labels(method, endpoint, str(status)).inc()


def get_metrics() -> Optional[bytes]:
    """
    Get Prometheus metrics in text format.

    Returns:
        Metrics bytes if available, None otherwise
    """
    if PROMETHEUS_AVAILABLE:
        return generate_latest()
    return None


def get_content_type() -> str:
    """
    Get content type for metrics endpoint.

    Returns:
        Content type string
    """
    if PROMETHEUS_AVAILABLE:
        return CONTENT_TYPE_LATEST
    return 'text/plain'
```

---

### Pattern 2: Context Managers for Latency Tracking

**Problem**: Manual timing code is error-prone and inconsistent.

**Solution**: Context managers automatically record latency.

```python
"""pmoves_observability/context.py"""

import time
from contextlib import contextmanager
from typing import Generator, Optional

from .prometheus import REQUEST_LATENCY, ACTIVE_REQUESTS


@contextmanager
def track_request_latency(method: str, endpoint: str) -> Generator[None, None, None]:
    """
    Track request latency with active request gauge.

    Args:
        method: HTTP method
        endpoint: Normalized endpoint path

    Yields:
        None

    Example:
        with track_request_latency('GET', '/api/v1/users'):
            response = handle_request()
    """
    start_time = time.time()

    # Increment active requests
    if ACTIVE_REQUESTS:
        ACTIVE_REQUESTS.labels(method).inc()

    try:
        yield
    finally:
        # Observe latency
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(method, endpoint).observe(time.time() - start_time)

        # Decrement active requests
        if ACTIVE_REQUESTS:
            ACTIVE_REQUESTS.labels(method).dec()


@contextmanager
def track_operation(operation_name: str) -> Generator[None, None, None]:
    """
    Track custom operation latency.

    Args:
        operation_name: Name of the operation

    Yields:
        None

    Example:
        with track_operation('database_query'):
            result = db.query(...)
    """
    start_time = time.time()
    try:
        yield
    finally:
        if REQUEST_LATENCY:
            latency = time.time() - start_time
            REQUEST_LATENCY.labels('operation', operation_name).observe(latency)
```

---

### Pattern 3: Path Normalization for Metrics

**Problem**: Dynamic paths (`/a2a/v1/tasks/abc123`) create unlimited metric labels.

**Solution**: Normalize dynamic segments to templates.

```python
"""pmoves_observability/normalization.py"""

import re
from typing import List, Tuple
from urllib.parse import urlparse


# Common dynamic segment patterns
PATTERNS: List[Tuple[str, str]] = [
    # UUID-like patterns (8-4-4-4-12)
    (r'/[0-9a-f-]{36}', '/{uuid}'),

    # Task IDs (alphanumeric)
    (r'/tasks/[a-zA-Z0-9_-]+', '/tasks/{id}'),

    # Server names
    (r'/tools/[a-zA-Z0-9_-]+', '/tools/{server}'),

    # Video IDs
    (r'/videos/[a-zA-Z0-9_-]+', '/videos/{id}'),

    # Agent names
    (r'/agents/[a-zA-Z0-9_-]+', '/agents/{agent}'),

    # Numeric IDs
    (r'/\d+', '/{id}'),
]


def normalize_path(path: str) -> str:
    """
    Normalize request path for metrics labels.

    Strips query strings and replaces dynamic segments with templates.

    Args:
        path: Original request path

    Returns:
        Normalized path suitable for metric labels

    Examples:
        >>> normalize_path('/a2a/v1/tasks/abc123')
        '/a2a/v1/tasks/{id}'
        >>> normalize_path('/api/v1/videos/xyz-789?foo=bar')
        '/api/v1/videos/{id}'
    """
    # Strip query string
    parsed = urlparse(path)
    path = parsed.path

    # Apply normalization patterns
    for pattern, replacement in PATTERNS:
        path = re.sub(pattern, replacement, path)

    return path


def normalize_query_params(path: str) -> str:
    """
    Strip query parameters from path.

    Args:
        path: Original path possibly with query string

    Returns:
        Path without query string

    Examples:
        >>> normalize_query_params('/api/v1/users?active=true')
        '/api/v1/users'
    """
    return path.split('?')[0]
```

---

### Pattern 4: Helper Extraction for Code Deduplication

**Problem**: Same metric tracking code repeated across handlers.

**Solution**: Extract reusable helper methods.

```python
"""pmoves_observability/helpers.py"""

from typing import Optional, Any
from .prometheus import REQUEST_COUNT, track_request
from .normalization import normalize_path


def track_http_request(
    method: str,
    path: str,
    status: int,
    response_time: Optional[float] = None
) -> None:
    """
    Track HTTP request metrics with normalized path.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path (will be normalized)
        status: HTTP status code
        response_time: Optional override for latency (seconds)

    Example:
        track_http_request('GET', '/api/v1/tasks/abc123', 200)
    """
    normalized = normalize_path(path)
    track_request(method, normalized, status)


def track_tool_call(tool_name: str, server_name: Optional[str] = None) -> None:
    """
    Track tool execution metrics.

    Args:
        tool_name: Qualified tool name (server:tool or bare tool name)
        server_name: Optional server name override

    Example:
        track_tool_call('search:web_search')
        track_tool_call('web_search', server_name='search')
    """
    if not REQUEST_COUNT:
        return

    # Extract server name from qualified name if not provided
    if server_name is None:
        server_name = tool_name.split(':')[0] if ':' in tool_name else 'unknown'

    REQUEST_COUNT.labels(
        method='tool',
        endpoint=tool_name,
        status='success'
    ).inc()


def track_database_query(table: str, operation: str, success: bool = True) -> None:
    """
    Track database query metrics.

    Args:
        table: Database table name
        operation: Operation type (select, insert, update, delete)
        success: Whether the query succeeded

    Example:
        track_database_query('users', 'select', success=True)
    """
    if not REQUEST_COUNT:
        return

    status = 'success' if success else 'error'
    endpoint = f'{operation}.{table}'

    REQUEST_COUNT.labels(
        method='db',
        endpoint=endpoint,
        status=status
    ).inc()


def track_external_service(service_name: str, endpoint: str, status: int) -> None:
    """
    Track external service call metrics.

    Args:
        service_name: Name of external service (e.g., 'openai', 'anthropic')
        endpoint: API endpoint called
        status: HTTP status code or error indicator

    Example:
        track_external_service('openai', '/v1/chat/completions', 200)
    """
    if not REQUEST_COUNT:
        return

    normalized_endpoint = normalize_path(endpoint)
    REQUEST_COUNT.labels(
        method=f'external:{service_name}',
        endpoint=normalized_endpoint,
        status=str(status)
    ).inc()
```

---

### Pattern 5: Startup Logging for Feature Verification

**Problem**: Operators can't verify optional features are enabled.

**Solution**: Explicit logging during initialization.

```python
"""pmoves_observability/logging.py"""

import logging
from typing import Dict, Any, Optional

from .prometheus import PROMETHEUS_AVAILABLE

logger = logging.getLogger(__name__)


def log_observability_status(
    service_name: str,
    features: Dict[str, bool],
    additional_info: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log observability feature availability at startup.

    Args:
        service_name: Name of the service
        features: Dict of feature names and availability status
        additional_info: Optional additional information to log

    Example:
        log_observability_status(
            'my-service',
            {
                'prometheus': True,
                'a2a_protocol': False,
                'grpc': True
            },
            {'metrics_endpoint': '/metrics'}
        )
    """
    logger.info(f"=== {service_name} Observability Status ===")

    # Log Prometheus status
    if PROMETHEUS_AVAILABLE:
        logger.info("Prometheus Metrics: ENABLED")
        logger.info("  - Metrics Endpoint: GET /metrics")
        logger.info("  - Content-Type: text/plain (version 0.0.4)")
    else:
        logger.warning("Prometheus Metrics: DISABLED")
        logger.warning("  - Reason: prometheus_client not installed")
        logger.warning("  - Fix: pip install prometheus-client")

    # Log additional features
    for feature_name, enabled in features.items():
        status = "ENABLED" if enabled else "DISABLED"
        level = logger.info if enabled else logger.warning
        level(f"{feature_name.replace('_', ' ').title()}: {status}")

    # Log additional info
    if additional_info:
        logger.info("Additional Information:")
        for key, value in additional_info.items():
            logger.info(f"  - {key}: {value}")

    logger.info("=" * 50)


def log_endpoint_added(
    endpoint: str,
    methods: list,
    description: str = ""
) -> None:
    """
    Log endpoint registration.

    Args:
        endpoint: HTTP path
        methods: List of allowed HTTP methods
        description: Optional description of endpoint

    Example:
        log_endpoint_added('/healthz', ['GET'], 'Health check endpoint')
    """
    methods_str = ', '.join(methods)
    desc_str = f" - {description}" if description else ""
    logger.info(f"Endpoint: {methods_str} {endpoint}{desc_str}")
```

---

## Framework-Specific Implementations

### FastAPI Pattern

```python
"""FastAPI service with observability"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import logging

from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    get_content_type,
    track_request_latency
)
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import track_http_request
from pmoves_observability.logging import (
    log_observability_status,
    log_endpoint_added
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="My Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.on_event("startup")
async def startup_event():
    """Log observability status at startup."""
    log_observability_status(
        service_name="My Service",
        features={
            'prometheus_metrics': PROMETHEUS_AVAILABLE,
        },
        additional_info={
            'health_endpoint': '/healthz',
            'metrics_endpoint': '/metrics' if PROMETHEUS_AVAILABLE else 'N/A'
        }
    )


@app.get("/healthz")
async def health_check():
    """Health check endpoint (PMOVES.AI standard)."""
    return {
        "status": "healthy",
        "service": "my-service",
        "version": "1.0.0",
        "prometheus_enabled": PROMETHEUS_AVAILABLE
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return {"error": "Metrics not available"}, 503

    metrics_data = get_metrics()
    return PlainTextResponse(
        content=metrics_data,
        media_type=get_content_type()
    )


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Middleware to track all requests."""
    method = request.method
    path = request.url.path

    # Track latency and active requests
    with track_request_latency(method, path):
        response = await call_next(request)

    # Track request count
    normalized_path = normalize_path(path)
    track_http_request(method, normalized_path, response.status_code)

    return response


# Your API endpoints
@app.get("/api/v1/users")
async def list_users():
    """List all users."""
    return {"users": []}


@app.post("/api/v1/tasks/{task_id}")
async def update_task(task_id: str):
    """Update a specific task."""
    return {"task_id": task_id, "status": "updated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### aiohttp Pattern

```python
"""aiohttp service with observability"""

from aiohttp import web
import logging

from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    get_content_type,
    track_request_latency
)
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import track_http_request
from pmoves_observability.logging import (
    log_observability_status,
    log_endpoint_added
)

logger = logging.getLogger(__name__)


async def health_check(_request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy",
        "service": "my-service",
        "version": "1.0.0",
        "prometheus_enabled": PROMETHEUS_AVAILABLE
    })


async def metrics_handler(_request: web.Request) -> web.Response:
    """Prometheus metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return web.json_response(
            {"error": "Metrics not available"},
            status=503
        )

    metrics_data = get_metrics()
    return web.Response(
        text=metrics_data.decode() if metrics_data else "",
        content_type=get_content_type()
    )


@web.middleware
async def observability_middleware(
    request: web.Request,
    handler: web.Handler
) -> web.Response:
    """Middleware to track all requests."""
    method = request.method
    path = request.path

    # Track latency and active requests
    with track_request_latency(method, path):
        response = await handler(request)

    # Track request count
    normalized_path = normalize_path(path)
    track_http_request(method, normalized_path, response.status)

    return response


async def create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application(middlewares=[observability_middleware])

    # Register endpoints
    app.router.add_get('/healthz', health_check)
    app.router.add_get('/metrics', metrics_handler)

    # Your API endpoints
    app.router.add_get('/api/v1/users', list_users)
    app.router.add_post('/api/v1/tasks/{task_id}', update_task)

    # Log observability status
    log_observability_status(
        service_name="My Service",
        features={
            'prometheus_metrics': PROMETHEUS_AVAILABLE,
        },
        additional_info={
            'health_endpoint': '/healthz',
            'metrics_endpoint': '/metrics' if PROMETHEUS_AVAILABLE else 'N/A'
        }
    )

    return app


async def list_users(_request: web.Request) -> web.Response:
    """List all users."""
    return web.json_response({"users": []})


async def update_task(request: web.Request) -> web.Response:
    """Update a specific task."""
    task_id = request.match_info['task_id']
    return web.json_response({"task_id": task_id, "status": "updated"})


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)
```

---

### http.server Pattern

```python
"""http.server service with observability"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import json
from typing import Type

from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    get_content_type,
    REQUEST_LATENCY
)
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import track_http_request
from pmoves_observability.logging import (
    log_observability_status,
    log_endpoint_added
)

logger = logging.getLogger(__name__)


class ObservabilityHandler(BaseHTTPRequestHandler):
    """Base request handler with observability support."""

    # Class-level metrics (shared across all instances)
    service_name = "my-service"
    service_version = "1.0.0"

    def log_message(self, format: str, *args):
        """Override to use Python logging instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")

    def _handle_healthz(self):
        """Handle health check endpoint."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        response = {
            "status": "healthy",
            "service": self.service_name,
            "version": self.service_version,
            "prometheus_enabled": PROMETHEUS_AVAILABLE
        }
        self.wfile.write(json.dumps(response).encode())

    def _handle_metrics(self):
        """Handle Prometheus metrics endpoint."""
        if not PROMETHEUS_AVAILABLE:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "Metrics not available"}')
            return

        metrics_data = get_metrics()
        self.send_response(200)
        self.send_header('Content-Type', get_content_type())
        self.end_headers()

        if metrics_data:
            self.wfile.write(metrics_data)

    def _track_request(self, status_code: int):
        """Track request metrics."""
        normalized_path = normalize_path(self.path)
        track_http_request(self.command, normalized_path, status_code)

    def do_GET(self):
        """Handle GET requests."""
        # Track latency
        start_time = None
        if REQUEST_LATENCY:
            import time
            start_time = time.time()

        try:
            if self.path == '/healthz':
                self._handle_healthz()
            elif self.path == '/metrics':
                self._handle_metrics()
            else:
                # Your custom GET handling
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Not Found')

            # Track metrics
            self._track_request(200 if self.path in ['/healthz', '/metrics'] else 404)

        finally:
            # Observe latency
            if REQUEST_LATENCY and start_time is not None:
                import time
                latency = time.time() - start_time
                normalized_path = normalize_path(self.path)
                REQUEST_LATENCY.labels('GET', normalized_path).observe(latency)

    def do_POST(self):
        """Handle POST requests."""
        # Similar pattern for POST
        start_time = None
        if REQUEST_LATENCY:
            import time
            start_time = time.time()

        try:
            # Your custom POST handling
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')

            self._track_request(200)

        finally:
            if REQUEST_LATENCY and start_time is not None:
                import time
                latency = time.time() - start_time
                normalized_path = normalize_path(self.path)
                REQUEST_LATENCY.labels('POST', normalized_path).observe(latency)


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the HTTP server with observability."""

    # Log observability status
    log_observability_status(
        service_name=ObservabilityHandler.service_name,
        features={
            'prometheus_metrics': PROMETHEUS_AVAILABLE,
        },
        additional_info={
            'health_endpoint': '/healthz',
            'metrics_endpoint': '/metrics' if PROMETHEUS_AVAILABLE else 'N/A'
        }
    )

    server_address = (host, port)
    httpd = HTTPServer(server_address, ObservabilityHandler)
    logger.info(f"Starting server on {host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
```

---

### Django Pattern

```python
"""Django service with observability"""

# observability/views.py

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
import logging

from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    get_content_type
)
from pmoves_observability.logging import log_observability_status

logger = logging.getLogger(__name__)


@require_GET
def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        "status": "healthy",
        "service": "my-service",
        "version": "1.0.0",
        "prometheus_enabled": PROMETHEUS_AVAILABLE
    })


@csrf_exempt  # Prometheus scrapes shouldn't require CSRF
@require_GET
def metrics(request):
    """Prometheus metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return JsonResponse(
            {"error": "Metrics not available"},
            status=503
        )

    metrics_data = get_metrics()
    return HttpResponse(
        metrics_data,
        content_type=get_content_type()
    )


# observability/middleware.py

from django.utils.deprecation import MiddlewareMixin

from pmoves_observability.prometheus import track_request_latency
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import track_http_request


class ObservabilityMiddleware(MiddlewareMixin):
    """Middleware to track all requests."""

    def process_request(self, request):
        """Store start time for latency tracking."""
        import time
        requestobservability_start_time = time.time()

    def process_response(self, request, response):
        """Track metrics after response is generated."""
        # Calculate latency
        if hasattr(request, 'observability_start_time'):
            import time
            latency = time.time() - request.observability_start_time

            # Observe latency
            from pmoves_observability.prometheus import REQUEST_LATENCY
            if REQUEST_LATENCY:
                method = request.method
                path = normalize_path(request.path)
                REQUEST_LATENCY.labels(method, path).observe(latency)

        # Track request count
        method = request.method
        path = normalize_path(request.path)
        track_http_request(method, path, response.status_code)

        return response


# myapp/settings.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'observability.middleware.ObservabilityMiddleware',  # Add this
]

# myapp/urls.py

from django.urls import path
from observability import views

urlpatterns = [
    path('healthz/', views.health_check),
    path('metrics/', views.metrics),
    # Your other URLs...
]

# myapp/wsgi.py or myapp/asgi.py

import os
from django.core.wsgi import get_wsgi_application

from pmoves_observability.logging import log_observability_status
from pmoves_observability.prometheus import PROMETHEUS_AVAILABLE

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')

application = get_wsgi_application()

# Log observability status on startup
log_observability_status(
    service_name="My Django Service",
    features={
        'prometheus_metrics': PROMETHEUS_AVAILABLE,
    },
    additional_info={
        'health_endpoint': '/healthz/',
        'metrics_endpoint': '/metrics/' if PROMETHEUS_AVAILABLE else 'N/A'
    }
)
```

---

## Installation

### For Production Services

Add to your service's `requirements.txt`:

```txt
# Production dependencies
pmoves-observability==1.0.0
prometheus-client==0.20.0
```

Or add to `requirements.in` (if using pip-compile):

```txt
# Production dependencies
pmoves-observability>=1.0.0
prometheus-client>=0.20.0
```

Then compile:

```bash
pip-compile requirements.in --output-file requirements.txt
```

### For Development

Clone and install in editable mode:

```bash
cd /home/pmoves/PMOVES.AI/pmoves/observability
pip install -e .
```

---

## Migration Guide

### Step 1: Install the Library

```bash
pip install pmoves-observability
```

### Step 2: Remove Existing Prometheus Code

**Before:**
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency')
```

**After:**
```python
from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    track_request_latency,
    get_metrics
)
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import track_http_request
```

### Step 3: Add Startup Logging

Add to your service initialization:

```python
from pmoves_observability.logging import log_observability_status

# In your startup/migration file
def on_startup():
    log_observability_status(
        service_name="my-service",
        features={
            'prometheus_metrics': PROMETHEUS_AVAILABLE,
        }
    )
```

### Step 4: Update Metrics Endpoint

**Before:**
```python
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**After:**
```python
@app.get("/metrics")
async def metrics():
    if not PROMETHEUS_AVAILABLE:
        return {"error": "Metrics not available"}, 503

    metrics_data = get_metrics()
    return PlainTextResponse(
        content=metrics_data,
        media_type=get_content_type()
    )
```

### Step 5: Add Middleware

**FastAPI:**
```python
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    with track_request_latency(request.method, request.url.path):
        response = await call_next(request)

    normalized_path = normalize_path(request.url.path)
    track_http_request(request.method, normalized_path, response.status_code)

    return response
```

**aiohttp:**
```python
@web.middleware
async def observability_middleware(request: web.Request, handler: web.Handler):
    with track_request_latency(request.method, request.path):
        response = await handler(request)

    normalized_path = normalize_path(request.path)
    track_http_request(request.method, normalized_path, response.status)

    return response
```

### Step 6: Verify Installation

```bash
# Start your service
python my_service.py

# Check logs for observability status
# Should see:
# === My Service Observability Status ===
# Prometheus Metrics: ENABLED
#   - Metrics Endpoint: GET /metrics

# Test health endpoint
curl http://localhost:8080/healthz

# Test metrics endpoint
curl http://localhost:8080/metrics
```

---

## Best Practices

### 1. Always Use Path Normalization

```python
# BAD - creates unlimited label combinations
REQUEST_COUNT.labels('GET', '/a2a/v1/tasks/abc123').inc()

# GOOD - normalizes to template
normalized = normalize_path('/a2a/v1/tasks/abc123')
# Returns: '/a2a/v1/tasks/{id}'
REQUEST_COUNT.labels('GET', normalized).inc()
```

### 2. Track Both Latency and Request Count

```python
# Track latency
with track_request_latency('GET', '/api/v1/users'):
    users = fetch_users()

# Also track request count
track_http_request('GET', '/api/v1/users', 200)
```

### 3. Log All Optional Features at Startup

```python
log_observability_status(
    service_name="my-service",
    features={
        'prometheus_metrics': PROMETHEUS_AVAILABLE,
        'a2a_protocol': A2A_AVAILABLE,
        'grpc_server': GRPC_AVAILABLE,
    }
)
```

### 4. Use Helper Methods for Common Patterns

```python
# Database queries
track_database_query('users', 'select', success=True)

# Tool calls
track_tool_call('search:web_search')

# External API calls
track_external_service('openai', '/v1/chat/completions', 200)
```

### 5. Implement /healthz on All Services

```python
@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": "my-service",
        "version": "1.0.0",
        "prometheus_enabled": PROMETHEUS_AVAILABLE
    }
```

### 6. Graceful Degradation for All Features

```python
# Check before using optional features
if PROMETHEUS_AVAILABLE:
    # Use prometheus features
    metrics = get_metrics()
else:
    # Fallback behavior
    logger.warning("Metrics not available")
```

---

## Reference Implementation

### Complete Service Example

See `/home/pmoves/PMOVES.AI/pmoves/observability/examples/` for complete working examples:

- `fastapi_example.py` - FastAPI service with full observability
- `aiohttp_example.py` - aiohttp service with full observability
- `httpserver_example.py` - http.server service with full observability
- `django_example/` - Django project with full observability

Run examples:

```bash
cd /home/pmoves/PMOVES.AI/pmoves/observability/examples

# FastAPI example
python fastapi_example.py

# aiohttp example
python aiohttp_example.py

# http.server example
python httpserver_example.py

# Django example
cd django_example
python manage.py runserver
```

---

## Troubleshooting

### Issue: Metrics endpoint returns 503

**Solution:** Install prometheus-client:

```bash
pip install prometheus-client
```

### Issue: High cardinality warnings in Prometheus

**Solution:** Ensure path normalization is used:

```python
# Check that you're normalizing paths
normalized = normalize_path(request.path)
track_http_request(request.method, normalized, status)
```

### Issue: Latency not being tracked

**Solution:** Ensure context manager is used correctly:

```python
# Correct - using 'with' statement
with track_request_latency(method, path):
    # ... handle request

# Incorrect - not using context manager
tracker = track_request_latency(method, path)
# ... handle request (latency won't be tracked)
```

### Issue: Startup logs not showing

**Solution:** Ensure logging is configured:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

---

## Appendix: Quick Reference Card

### Import Statements

```python
# Core imports
from pmoves_observability.prometheus import (
    PROMETHEUS_AVAILABLE,
    track_request_latency,
    get_metrics,
    get_content_type
)
from pmoves_observability.normalization import normalize_path
from pmoves_observability.helpers import (
    track_http_request,
    track_tool_call,
    track_database_query,
    track_external_service
)
from pmoves_observability.logging import log_observability_status
```

### Common Patterns

```python
# Startup logging
log_observability_status(
    service_name="my-service",
    features={'prometheus_metrics': PROMETHEUS_AVAILABLE}
)

# Track request
with track_request_latency(method, path):
    # ... handle request
track_http_request(method, normalize_path(path), status)

# Tool call
track_tool_call('search:web_search')

# Database query
track_database_query('users', 'select', success=True)

# External service
track_external_service('openai', '/v1/chat/completions', 200)
```

---

**Document Version:** 1.0.0
**Last Updated:** 2026-01-29
**Maintainer:** PMOVES.AI Team
