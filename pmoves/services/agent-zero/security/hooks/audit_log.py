#!/usr/bin/env python3
"""
Audit Logging for Agent Zero

Logs all tool executions for security and debugging.
Based on PMOVES-BoTZ audit pattern.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class AuditLogger:
    """Thread-safe audit logger for agent actions."""

    def __init__(self, audit_path: Path = None):
        if audit_path is None:
            audit_path = Path(__file__).parent.parent.parent / "memory" / "audit"
        self.audit_path = audit_path
        self.audit_path.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Log an event to the audit trail.

        Returns:
            Event ID (timestamp-based)
        """
        event_id = f"{int(time.time() * 1000)}"

        event = {
            "id": event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }

        # Write to daily log file
        log_file = self.audit_path / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        return event_id

    def log_command_execution(
        self,
        command: str,
        result: str,
        duration_ms: int,
        agent_id: str
    ):
        """Log a command execution event."""
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
    ):
        """Log a tool use event."""
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
