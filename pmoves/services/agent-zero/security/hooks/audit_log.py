#!/usr/bin/env python3
"""
Audit Logging for Agent Zero

Logs all tool executions for security and debugging.
Based on PMOVES-BoTZ audit pattern.

SECURITY: Automatically scrubs sensitive data (API keys, tokens, passwords)
from audit logs to prevent credential exposure.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


# Patterns for detecting and scrubbing sensitive data
SECRET_PATTERNS = [
    # API Keys (common formats) - Order matters: more specific first
    (r'Bearer [a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', '[REDACTED_BEARER_TOKEN]'),
    (r'(sk_|pk_|sk-|pk-)[a-zA-Z0-9]{20,}', '[REDACTED_API_KEY]'),
    (r'AIza[a-zA-Z0-9_-]{35}', '[REDACTED_GOOGLE_API_KEY]'),
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
    (r'xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32}', '[REDACTED_SLACK_TOKEN]'),
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'ghu_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'ghs_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'ghr_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gh_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),

    # Passwords - be more specific to avoid false positives
    (r'password\s*[:=]\s*[^\s\'"]{8,}', 'password=[REDACTED]'),
    (r'passwd\s*[:=]\s*[^\s\'"]{8,}', 'passwd=[REDACTED]'),
    (r'-p\s+[^\s\'"]{8,}', '-p [REDACTED]'),
    (r'--password\s*=\s*[^\s\'"]{8,}', '--password=[REDACTED]'),

    # Connection strings
    (r'mongodb://[^@]+:[^@]+@', 'mongodb://[USER]:[REDACTED]@'),
    (r'postgres://[^@]+:[^@]+@', 'postgres://[USER]:[REDACTED]@'),
    (r'mysql://[^@]+:[^@]+@', 'mysql://[USER]:[REDACTED]@'),
    (r'redis://:[^@]+@', 'redis://:[REDACTED]@'),  # Redis with empty username
    (r'redis://[^@]+:[^@]+@', 'redis://[USER]:[REDACTED]@'),  # Redis with username

    # Generic secrets - Put these AFTER more specific patterns
    (r'secret\s*[:=]\s*[^\s\'"]{16,}', 'secret=[REDACTED]'),
    (r'token\s*[:=]\s*[^\s\'"]{20,}', 'token=[REDACTED]'),
    (r'api[_-]?key\s*[:=]\s*[^\s\'"]{16,}', 'api_key=[REDACTED]'),  # Reduced min length
    (r'access[_-]?token\s*[:=]\s*[^\s\'"]{20,}', 'access_token=[REDACTED]'),

    # Private keys (SSH, GPG, etc.) - Use DOTALL to match multiline
    (r'-----BEGIN [A-Z]+ PRIVATE KEY-----(.|\n)*?-----END [A-Z]+ PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]'),
    (r'ssh-rsa [A-Za-z0-9+/=]+', '[REDACTED_SSH_KEY]'),
    (r'ssh-ed25519 [A-Za-z0-9+/=]+', '[REDACTED_SSH_KEY]'),
]


def _scrub_secrets(data: Any) -> Any:
    """
    Recursively scrub sensitive data from a data structure.

    Args:
        data: Any Python object (dict, list, str, etc.)

    Returns:
        Data with sensitive values replaced with [REDACTED_*] placeholders
    """
    if isinstance(data, dict):
        return {key: _scrub_secrets(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_scrub_secrets(item) for item in data]
    elif isinstance(data, str):
        text = data
        # Apply all secret patterns
        for pattern, replacement in SECRET_PATTERNS:
            try:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            except re.error:
                # If pattern fails, skip it (fail safe)
                continue
        return text
    else:
        return data


class AuditLogger:
    """Thread-safe audit logger for agent actions with secret scrubbing."""

    def __init__(self, audit_path: Optional[Path] = None) -> None:
        """
        Initialize AuditLogger.

        Args:
            audit_path: Path to audit log directory. Defaults to ../memory/audit
        """
        if audit_path is None:
            audit_path = Path(__file__).parent.parent.parent / "memory" / "audit"
        self.audit_path = audit_path
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()  # Thread-safe file writing

    def log(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Log an event to the audit trail with automatic secret scrubbing.

        Args:
            event_type: Type of event (e.g., "command_execution", "tool_use")
            data: Event data (will be scrubbed for secrets)

        Returns:
            Event ID (timestamp-based)
        """
        event_id = f"{int(time.time() * 1000)}"

        # CRITICAL: Scrub secrets before logging
        scrubbed_data = _scrub_secrets(data)

        event = {
            "id": event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": scrubbed_data
        }

        # Write to daily log file (thread-safe)
        log_file = self.audit_path / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

        with self._lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except IOError as e:
                # Log to stderr if file write fails
                print(f"ERROR: Failed to write audit log: {e}")

        return event_id

    def log_command_execution(
        self,
        command: str,
        result: str,
        duration_ms: int,
        agent_id: str
    ) -> None:
        """
        Log a command execution event with automatic secret scrubbing.

        Args:
            command: Command that was executed
            result: Result of the command
            duration_ms: Execution time in milliseconds
            agent_id: ID of the agent executing the command
        """
        self.log("command_execution", {
            "command": command,
            "result": result,
            "duration_ms": duration_ms,
            "agent_id": agent_id
        })

    def log_tool_use(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_id: str
    ) -> None:
        """
        Log a tool use event with automatic secret scrubbing.

        Args:
            tool_name: Name of the tool being used
            parameters: Tool parameters (will be scrubbed for secrets)
            agent_id: ID of the agent using the tool
        """
        self.log("tool_use", {
            "tool": tool_name,
            "parameters": parameters,
            "agent_id": agent_id
        })


if __name__ == "__main__":
    # Test the audit logger
    import sys

    logger = AuditLogger()

    print("Testing AuditLogger:")
    print("-" * 60)

    # Test command execution log
    event_id = logger.log_command_execution(
        command="ls -la",
        result="success",
        duration_ms=45,
        agent_id="agent-zero-test"
    )
    print(f"Logged command execution: {event_id}")

    # Test tool use log
    event_id = logger.log_tool_use(
        tool_name="read_file",
        parameters={"file_path": "/tmp/test.txt"},
        agent_id="agent-zero-test"
    )
    print(f"Logged tool use: {event_id}")

    # Test generic log
    event_id = logger.log("custom_event", {"key": "value"})
    print(f"Logged custom event: {event_id}")

    # Show log file location
    print(f"\nLog file location: {logger.audit_path}")

    # Read and display latest entry
    log_file = logger.audit_path / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
    if log_file.exists():
        with open(log_file, "r") as f:
            lines = f.readlines()
            print(f"\nTotal log entries: {len(lines)}")
            if lines:
                print(f"Latest entry:\n{lines[-1]}")

    sys.exit(0)
