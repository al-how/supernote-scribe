"""Non-fatal Pushover notifications for worker activity."""

from __future__ import annotations

import logging
import threading
from typing import Callable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
PostFunc = Callable[..., httpx.Response]


class PushoverNotifier:
    def __init__(
        self,
        settings: Settings,
        *,
        post_func: PostFunc = httpx.post,
        timeout: float = 10.0,
    ) -> None:
        self.settings = settings
        self.post_func = post_func
        self.timeout = timeout

    def _can_send(self, event_enabled: bool) -> bool:
        return (
            self.settings.notify_enabled
            and event_enabled
            and bool(self.settings.pushover_token)
            and bool(self.settings.pushover_user)
        )

    def _send_payload(self, payload: dict[str, str]) -> None:
        try:
            response = self.post_func(PUSHOVER_URL, data=payload, timeout=self.timeout)
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Pushover returned HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
        except Exception as exc:
            logger.warning("Pushover notification failed: %s", exc)

    def _send(self, *, message: str, event_enabled: bool, priority: int = 0) -> bool:
        if not self._can_send(event_enabled):
            return False

        payload = {
            "token": self.settings.pushover_token,
            "user": self.settings.pushover_user,
            "message": message,
            "priority": str(priority),
        }
        thread = threading.Thread(
            target=self._send_payload,
            args=(payload,),
            daemon=True,
            name="pushover-notification",
        )
        thread.start()
        return True

    def send_start(self) -> bool:
        return self._send(
            message="Supernote processing started.",
            event_enabled=self.settings.notify_on_start,
        )

    def send_complete(self, *, processed: int, review_count: int, errors: int) -> bool:
        has_review = review_count > 0
        event_enabled = self.settings.notify_on_complete or (
            has_review and self.settings.notify_on_review
        )
        if has_review and not self.settings.notify_on_review and not self.settings.notify_on_complete:
            event_enabled = False

        message = (
            f"Supernote processing complete: {processed} processed, "
            f"{review_count} need review, {errors} errors."
        )
        return self._send(
            message=message,
            event_enabled=event_enabled,
            priority=1 if has_review and self.settings.notify_on_review else 0,
        )

    def send_error(self, message: str) -> bool:
        return self._send(
            message=f"Supernote processing error: {message}",
            event_enabled=self.settings.notify_on_error,
            priority=1,
        )


def build_notifier(settings: Settings) -> PushoverNotifier:
    return PushoverNotifier(settings)
