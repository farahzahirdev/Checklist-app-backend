from datetime import datetime, timezone

from app.services.access import build_access_window


def test_build_access_window_uses_utc_and_seven_days() -> None:
    activated_at = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)

    access_window = build_access_window(activated_at)

    assert access_window.activated_at == activated_at
    assert access_window.expires_at == datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
