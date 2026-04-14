from datetime import datetime, timezone

from app.services.access import build_completion_window, has_access_window_expired, is_access_window_active


def test_completion_window_starts_at_assessment_start() -> None:
    started_at = datetime(2026, 4, 13, 9, 30, tzinfo=timezone.utc)

    access_window = build_completion_window(started_at)

    assert access_window.activated_at == started_at
    assert access_window.expires_at == datetime(2026, 4, 20, 9, 30, tzinfo=timezone.utc)


def test_access_window_active_and_expired_checks() -> None:
    started_at = datetime(2026, 4, 13, 9, 30, tzinfo=timezone.utc)
    access_window = build_completion_window(started_at)

    assert is_access_window_active(access_window, now=datetime(2026, 4, 15, 9, 30, tzinfo=timezone.utc)) is True
    assert has_access_window_expired(access_window, now=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc)) is True