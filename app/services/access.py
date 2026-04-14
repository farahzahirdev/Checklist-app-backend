from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class AccessWindow:
    activated_at: datetime
    expires_at: datetime


def _normalize_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def build_access_window(activated_at: datetime, days: int = 7) -> AccessWindow:
    normalized_activated_at = _normalize_utc(activated_at).astimezone(timezone.utc)
    return AccessWindow(
        activated_at=normalized_activated_at,
        expires_at=normalized_activated_at + timedelta(days=days),
    )


def build_completion_window(started_at: datetime, days: int = 7) -> AccessWindow:
    return build_access_window(started_at, days=days)


def is_access_window_active(access_window: AccessWindow, now: datetime | None = None) -> bool:
    current_time = _normalize_utc(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return access_window.activated_at <= current_time < access_window.expires_at


def has_access_window_expired(access_window: AccessWindow, now: datetime | None = None) -> bool:
    return not is_access_window_active(access_window, now=now)
