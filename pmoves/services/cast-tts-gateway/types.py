"""TypedDict definitions for Cast TTS Gateway responses.

This module provides type-safe response structures for all API endpoints,
improving type checking and IDE autocomplete support.
"""

from typing import TypedDict, Optional, Any, List


class SuccessResponse(TypedDict):
    """Standard success response.

    Attributes:
        success: True if operation succeeded
        message: Human-readable success message
    """
    success: bool
    message: str


class ErrorResponse(TypedDict):
    """Standard error response.

    Attributes:
        success: False if operation failed
        error: Human-readable error message
    """
    success: bool
    error: str


class CastSpeechResponse(TypedDict, total=False):
    """Response from /cast/speech endpoint.

    Attributes:
        success: True if speech was cast successfully
        device: Name of the target device
        duration: Duration of the synthesized audio in seconds
        message: Success message
        error: Error message if operation failed
    """
    success: bool
    device: str
    duration: float
    message: str
    error: Optional[str]


class QueueAnnouncementResponse(TypedDict, total=False):
    """Queue announcement response.

    Attributes:
        success: True if announcement was queued
        announcement: The queued announcement object
        queue_position: Position in the queue (0-indexed)
        message: Success message
        error: Error message if operation failed
    """
    success: bool
    announcement: dict
    queue_position: int
    message: str
    error: Optional[str]


class QueueStatusResponse(TypedDict, total=False):
    """Queue status response.

    Attributes:
        success: True if status was retrieved
        queue: List of queued announcements
        queue_size: Current queue size
        is_processing: Whether queue is currently being processed
        processing_stats: Statistics about queue processing
        error: Error message if operation failed
    """
    success: bool
    queue: List[dict]
    queue_size: int
    is_processing: bool
    processing_stats: dict
    error: Optional[str]


class VoiceProfileResponse(TypedDict, total=False):
    """Voice profile response.

    Attributes:
        success: True if profile was created/updated
        profile: The voice profile object
        message: Success message
        error: Error message if operation failed
    """
    success: bool
    profile: dict
    message: str
    error: Optional[str]


class VoiceProfilesListResponse(TypedDict, total=False):
    """Voice profiles list response.

    Attributes:
        success: True if profiles were retrieved
        profiles: List of voice profiles
        count: Number of profiles
        error: Error message if operation failed
    """
    success: bool
    profiles: List[dict]
    count: int
    error: Optional[str]


class GroupResponse(TypedDict, total=False):
    """Group management response.

    Attributes:
        success: True if group was created/updated
        group: The group object
        message: Success message
        error: Error message if operation failed
    """
    success: bool
    group: dict
    message: str
    error: Optional[str]


class GroupsListResponse(TypedDict, total=False):
    """Groups list response.

    Attributes:
        success: True if groups were retrieved
        groups: List of groups
        count: Number of groups
        error: Error message if operation failed
    """
    success: bool
    groups: List[dict]
    count: int
    error: Optional[str]


class HealthCheckResponse(TypedDict, total=False):
    """Health check response.

    Attributes:
        success: True if device is healthy
        device: Device name
        online: Whether device is online
        availability: Device availability score (0.0-1.0)
        avg_latency_ms: Average latency in milliseconds
        success_rate: Success rate (0.0-1.0)
        error: Error message if check failed
    """
    success: bool
    device: str
    online: bool
    availability: float
    avg_latency_ms: float
    success_rate: float
    error: Optional[str]


class ScheduleResponse(TypedDict, total=False):
    """Schedule response.

    Attributes:
        success: True if schedule was created/updated
        schedule: The schedule object
        next_run: ISO timestamp of next run
        message: Success message
        error: Error message if operation failed
    """
    success: bool
    schedule: dict
    next_run: str
    message: str
    error: Optional[str]


class SchedulesListResponse(TypedDict, total=False):
    """Schedules list response.

    Attributes:
        success: True if schedules were retrieved
        schedules: List of schedules
        count: Number of schedules
        error: Error message if operation failed
    """
    success: bool
    schedules: List[dict]
    count: int
    error: Optional[str]


class DeviceDiscoveryResponse(TypedDict, total=False):
    """Device discovery response.

    Attributes:
        success: True if devices were discovered
        devices: List of discovered devices
        count: Number of devices
        error: Error message if discovery failed
    """
    success: bool
    devices: List[dict]
    count: int
    error: Optional[str]


class DevicesListResponse(TypedDict, total=False):
    """Devices list response.

    Attributes:
        success: True if devices were retrieved
        devices: List of all known devices
        count: Number of devices
        error: Error message if retrieval failed
    """
    success: bool
    devices: List[dict]
    count: int
    error: Optional[str]


class CastStatusResponse(TypedDict, total=False):
    """Cast status response.

    Attributes:
        success: True if status was retrieved
        device: Device name
        status: Current cast status
        is_casting: Whether device is currently casting
        current_media: Info about currently casting media
        error: Error message if status check failed
    """
    success: bool
    device: str
    status: str
    is_casting: bool
    current_media: Optional[dict]
    error: Optional[str]


class MetricsResponse(TypedDict, total=False):
    """Prometheus metrics response.

    Attributes:
        metrics: Prometheus metrics in text format
    """
    metrics: str
