"""Task 1 settings coverage for watcher, scheduler, notifications, and locks."""

from pathlib import Path

from app.settings_manager import SettingsManager


def test_settings_manager_round_trips_watcher_notification_and_lock_fields(test_db):
    manager = SettingsManager()

    values = {
        "watch_enabled": True,
        "watch_stable_seconds": 45,
        "watch_poll_seconds": 10,
        "schedule_cron": "5 4 * * *",
        "notify_enabled": True,
        "pushover_token": "token-123",
        "pushover_user": "user-456",
        "notify_on_start": False,
        "notify_on_complete": True,
        "notify_on_error": True,
        "notify_on_review": False,
        "lock_stale_minutes": 22,
        "source_path": Path("/tmp/source"),
    }

    for key, value in values.items():
        manager.set(key, value)

    all_settings = manager.get_all()

    for key, expected in values.items():
        assert all_settings[key] == expected
        assert manager.get(key) == expected

    assert isinstance(all_settings["watch_enabled"], bool)
    assert isinstance(all_settings["watch_stable_seconds"], int)
    assert isinstance(all_settings["watch_poll_seconds"], int)
    assert isinstance(all_settings["notify_enabled"], bool)
    assert isinstance(all_settings["pushover_token"], str)
    assert isinstance(all_settings["pushover_user"], str)
    assert isinstance(all_settings["notify_on_start"], bool)
    assert isinstance(all_settings["notify_on_complete"], bool)
    assert isinstance(all_settings["notify_on_error"], bool)
    assert isinstance(all_settings["notify_on_review"], bool)
    assert isinstance(all_settings["lock_stale_minutes"], int)
    assert isinstance(all_settings["schedule_cron"], str)
    assert isinstance(all_settings["source_path"], Path)


def test_settings_manager_defaults_include_task1_fields(test_db):
    settings = SettingsManager().get_all()

    expected_keys = {
        "watch_enabled",
        "watch_stable_seconds",
        "watch_poll_seconds",
        "schedule_cron",
        "notify_enabled",
        "pushover_token",
        "pushover_user",
        "notify_on_start",
        "notify_on_complete",
        "notify_on_error",
        "notify_on_review",
        "lock_stale_minutes",
    }

    assert expected_keys.issubset(settings.keys())
