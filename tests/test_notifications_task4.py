import logging
import threading
import time

import httpx

from app.config import Settings


def test_notification_payload_respects_enabled_event_toggle(monkeypatch):
    from app.services.notifications import PushoverNotifier

    requests = []
    sent = threading.Event()

    def fake_post(url, data, timeout):
        requests.append((url, data, timeout))
        sent.set()
        return httpx.Response(200, json={"status": 1})

    notifier = PushoverNotifier(
        Settings(
            notify_enabled=True,
            pushover_token="token",
            pushover_user="user",
            notify_on_start=True,
        ),
        post_func=fake_post,
    )

    assert notifier.send_start() is True
    assert sent.wait(timeout=1)
    assert requests[0][0] == "https://api.pushover.net/1/messages.json"
    assert requests[0][1]["token"] == "token"
    assert requests[0][1]["user"] == "user"
    assert "started" in requests[0][1]["message"].lower()


def test_notification_send_returns_before_slow_http_post_completes():
    from app.services.notifications import PushoverNotifier

    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def slow_post(url, data, timeout):
        started.set()
        release.wait(timeout=1)
        finished.set()
        return httpx.Response(200, json={"status": 1})

    notifier = PushoverNotifier(
        Settings(
            notify_enabled=True,
            pushover_token="token",
            pushover_user="user",
            notify_on_start=True,
        ),
        post_func=slow_post,
    )

    start_time = time.monotonic()
    try:
        assert notifier.send_start() is True
        elapsed = time.monotonic() - start_time

        assert elapsed < 0.2
        assert started.wait(timeout=0.5)
        assert not finished.is_set()
    finally:
        release.set()
        finished.wait(timeout=1)


def test_notification_skips_disabled_event(monkeypatch):
    from app.services.notifications import PushoverNotifier

    requests = []
    notifier = PushoverNotifier(
        Settings(
            notify_enabled=True,
            pushover_token="token",
            pushover_user="user",
            notify_on_start=False,
        ),
        post_func=lambda *args, **kwargs: requests.append(args),
    )

    assert notifier.send_start() is False
    assert requests == []


def test_notification_http_errors_are_logged_and_non_fatal(caplog):
    from app.services.notifications import PushoverNotifier

    failed = threading.Event()

    def fail_post(*args, **kwargs):
        try:
            raise httpx.HTTPError("network down")
        finally:
            failed.set()

    notifier = PushoverNotifier(
        Settings(
            notify_enabled=True,
            pushover_token="token",
            pushover_user="user",
            notify_on_error=True,
        ),
        post_func=fail_post,
    )

    with caplog.at_level(logging.WARNING):
        assert notifier.send_error("OCR failed") is True
        assert failed.wait(timeout=1)
        deadline = time.monotonic() + 1
        while "Pushover notification failed" not in caplog.text and time.monotonic() < deadline:
            time.sleep(0.01)

    assert "Pushover notification failed" in caplog.text


def test_complete_notification_bumps_priority_when_review_needed():
    from app.services.notifications import PushoverNotifier

    requests = []
    sent = threading.Event()

    def fake_post(url, data, timeout):
        requests.append(data)
        sent.set()
        return httpx.Response(200, json={"status": 1})

    notifier = PushoverNotifier(
        Settings(
            notify_enabled=True,
            pushover_token="token",
            pushover_user="user",
            notify_on_complete=True,
            notify_on_review=True,
        ),
        post_func=fake_post,
    )

    assert notifier.send_complete(processed=3, review_count=2, errors=0) is True
    assert sent.wait(timeout=1)
    assert requests[0]["priority"] == "1"
    assert "review" in requests[0]["message"].lower()
