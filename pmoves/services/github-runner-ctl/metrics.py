"""
Prometheus metrics for GitHub Runner Controller.

Following PMOVES SDK pattern: use prometheus_client for metrics
with labeled counters, gauges, and histograms.
"""

from prometheus_client import Counter, Gauge, Histogram

# Runner availability metrics
RUNNER_UP = Gauge(
    'github_runner_up',
    'Runner availability (1=up, 0=down)',
    ['runner', 'location']
)

RUNNER_BUSY = Gauge(
    'github_runner_busy',
    'Runner busy status (1=busy, 0=idle)',
    ['runner', 'location']
)

# Job queue metrics
RUNNER_QUEUE_DEPTH = Gauge(
    'github_runner_queue_depth',
    'Number of jobs waiting for runner',
    ['runner', 'repository']
)

RUNNER_QUEUE_DURATION = Gauge(
    'github_runner_queue_duration_seconds',
    'Average time jobs spend queued',
    ['runner']
)

# Workload metrics
RUNNER_JOBS_TOTAL = Counter(
    'github_runner_jobs_total',
    'Total jobs processed by runner',
    ['runner', 'status', 'type']
)

RUNNER_JOB_DURATION = Histogram(
    'github_runner_job_duration_seconds',
    'Job completion duration in seconds',
    ['runner', 'type'],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400]  # 1min to 4 hours
)

# Resource metrics
RUNNER_CPU_USAGE = Gauge(
    'github_runner_cpu_usage_percent',
    'CPU usage percentage for runner',
    ['runner']
)

RUNNER_MEMORY_USAGE = Gauge(
    'github_runner_memory_bytes',
    'Memory usage in bytes for runner',
    ['runner']
)

RUNNER_DISK_USAGE = Gauge(
    'github_runner_disk_bytes',
    'Disk usage in bytes for runner',
    ['runner']
)

RUNNER_GPU_USAGE = Gauge(
    'github_runner_gpu_usage_percent',
    'GPU usage percentage for runner',
    ['runner', 'gpu_id']
)

# API request metrics
API_REQUESTS_TOTAL = Counter(
    'github_runner_api_requests_total',
    'Total API requests by endpoint and status',
    ['endpoint', 'status']
)

API_LATENCY = Histogram(
    'github_runner_api_latency_seconds',
    'API request latency in seconds',
    ['endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# GitHub API metrics
GITHUB_API_REQUESTS_TOTAL = Counter(
    'github_runner_github_api_requests_total',
    'Total GitHub API requests by endpoint and status',
    ['endpoint', 'status']
)

GITHUB_API_RATE_LIMIT = Gauge(
    'github_runner_github_api_rate_limit',
    'GitHub API rate limit remaining',
    ['user']
)

# NATS event metrics
NATS_EVENTS_PUBLISHED = Counter(
    'github_runner_nats_events_published_total',
    'Total NATS events published by subject',
    ['subject', 'status']
)

NATS_EVENTS_FAILED = Counter(
    'github_runner_nats_events_failed_total',
    'Total NATS events that failed to publish',
    ['subject', 'reason']
)
