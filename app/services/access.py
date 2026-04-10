from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class AccessWindow:
    activated_at: datetime
    expires_at: datetime


def build_access_window(activated_at: datetime, days: int = 7) -> AccessWindow:
    normalized_activated_at = activated_at.astimezone(timezone.utc)
    return AccessWindow(
        activated_at=normalized_activated_at,
        expires_at=normalized_activated_at + timedelta(days=days),
    )
