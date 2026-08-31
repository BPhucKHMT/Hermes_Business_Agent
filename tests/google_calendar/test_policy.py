from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from tools.calendar.policy import CalendarPolicy, WorkingHours, load_calendar_policy


ROOT = Path(__file__).resolve().parents[2]


def test_load_calendar_policy() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)
    assert policy.schema_version == 1
    assert policy.default_timezone == "Asia/Ho_Chi_Minh"
    assert policy.working_hours.start == "09:00"
    assert policy.working_hours.end == "18:00"
    assert policy.max_lookahead_days == 30
    assert policy.max_event_duration_minutes == 480
    assert policy.min_event_duration_minutes == 15


def test_validate_event_time_window_success() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)

    start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
    policy.validate_event_time_window(start, end)


def test_validate_event_time_window_end_before_start() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)

    start = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="end_time_must_be_after_start_time"):
        policy.validate_event_time_window(start, end)


def test_validate_event_time_window_too_short() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)

    start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 10, 5, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="event_duration_too_short"):
        policy.validate_event_time_window(start, end)


def test_validate_event_time_window_too_long() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)

    start = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="event_duration_too_long"):
        policy.validate_event_time_window(start, end)


def test_validate_lookahead() -> None:
    policy_path = ROOT / "src" / "config" / "calendar_policy.json"
    policy = load_calendar_policy(policy_path)

    now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    valid_future = now + timedelta(days=10)
    policy.validate_lookahead(valid_future, now=now)

    too_far = now + timedelta(days=45)
    with pytest.raises(ValueError, match="lookahead_window_exceeded"):
        policy.validate_lookahead(too_far, now=now)
