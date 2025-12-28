"""
Test data generators and utilities for PMOVES.AI tests.

Provides helper functions for generating test data, creating mock responses,
and setting up test scenarios.
"""

import time
from typing import Any, Dict, List
from datetime import datetime, timezone


def generate_test_notebook_data() -> Dict[str, Any]:
    """Generate test notebook data for Open Notebook API."""
    return {
        "id": "notebook:test123",
        "name": "Test Notebook",
        "description": "Test notebook for automated testing",
        "archived": False,
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "source_count": 0,
        "note_count": 0,
    }


def generate_test_source_data(notebook_id: str = "notebook:test123") -> Dict[str, Any]:
    """Generate test source data for Open Notebook API."""
    return {
        "id": "source:src456",
        "notebook_id": notebook_id,
        "title": "Test Source",
        "type": "link",
        "url": "https://example.com/test",
        "embedded": False,
        "created": datetime.now(timezone.utc).isoformat(),
    }


def generate_test_note_data(notebook_id: str = "notebook:test123") -> Dict[str, Any]:
    """Generate test note data for Open Notebook API."""
    return {
        "id": "note:note789",
        "notebook_id": notebook_id,
        "title": "Test Note",
        "content": "This is a test note content",
        "note_type": "human",
        "created": datetime.now(timezone.utc).isoformat(),
    }


def generate_test_query() -> str:
    """Generate a test search query."""
    return "test search query for validation"


def generate_test_documents(count: int = 5) -> List[Dict[str, Any]]:
    """Generate test documents for indexing tests."""
    return [
        {
            "id": f"doc_{i}",
            "content": f"Test document content {i}",
            "metadata": {
                "source": "test",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        for i in range(count)
    ]


def wait_for_condition(
    condition: callable,
    timeout: float = 30.0,
    interval: float = 0.5,
    error_message: str = "Condition not met within timeout",
) -> bool:
    """
    Wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds
        error_message: Error message if timeout is reached

    Returns:
        True if condition was met

    Raises:
        TimeoutError: If condition was not met within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    raise TimeoutError(error_message)
