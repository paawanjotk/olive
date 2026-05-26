from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_datetime(timezone_name: str = "UTC") -> str:
    """Return current date/time in the requested timezone."""
    try:
        tz = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, Exception):
        tz = timezone.utc
        timezone_name = "UTC"

    now = datetime.now(tz)
    return (
        f"{now.strftime('%A, %B %d %Y')} at {now.strftime('%H:%M:%S')} {timezone_name}\n"
        f"ISO 8601: {now.isoformat()}\n"
        f"Unix timestamp: {int(now.timestamp())}"
    )
