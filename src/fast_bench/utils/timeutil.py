"""Time and timestamp utilities."""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """
    Get current UTC time with timezone info.

    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def utc_iso8601(dt: Optional[datetime] = None) -> str:
    """
    Format datetime as ISO8601 UTC string.

    Args:
        dt: Datetime to format (default: current UTC time)

    Returns:
        ISO8601 formatted string (e.g., "2025-09-30T12:34:56.789Z")
    """
    if dt is None:
        dt = utc_now()

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Format with milliseconds and Z suffix
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def timestamp_filename(prefix: str = '', suffix: str = '', extension: str = '') -> str:
    """
    Generate a filename with timestamp.

    Args:
        prefix: Filename prefix
        suffix: Filename suffix
        extension: File extension (with or without dot)

    Returns:
        Filename like "prefix_YYYYMMDD_HHMMSS_suffix.ext"
    """
    now = utc_now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')

    parts = [prefix, timestamp, suffix]
    name = '_'.join(filter(None, parts))

    if extension:
        if not extension.startswith('.'):
            extension = '.' + extension
        name += extension

    return name


def elapsed_ms(start: datetime, end: Optional[datetime] = None) -> float:
    """
    Calculate elapsed milliseconds between two datetimes.

    Args:
        start: Start datetime
        end: End datetime (default: current UTC time)

    Returns:
        Elapsed time in milliseconds
    """
    if end is None:
        end = utc_now()

    delta = end - start
    return delta.total_seconds() * 1000


def elapsed_seconds(start: datetime, end: Optional[datetime] = None) -> float:
    """
    Calculate elapsed seconds between two datetimes.

    Args:
        start: Start datetime
        end: End datetime (default: current UTC time)

    Returns:
        Elapsed time in seconds
    """
    if end is None:
        end = utc_now()

    delta = end - start
    return delta.total_seconds()


def parse_iso8601(timestamp: str) -> datetime:
    """
    Parse ISO8601 timestamp string to datetime.

    Args:
        timestamp: ISO8601 formatted string

    Returns:
        Parsed datetime with UTC timezone

    Raises:
        ValueError: If timestamp format is invalid
    """
    # Handle Z suffix
    if timestamp.endswith('Z'):
        timestamp = timestamp[:-1] + '+00:00'

    try:
        # Try with timezone info
        return datetime.fromisoformat(timestamp)
    except ValueError:
        # Try without timezone, assume UTC
        dt = datetime.fromisoformat(timestamp)
        return dt.replace(tzinfo=timezone.utc)