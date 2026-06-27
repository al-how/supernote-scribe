"""Compatibility module for the FastAPI worker runtime."""

from app.worker import app, get_status, health, trigger_process

__all__ = ["app", "trigger_process", "get_status", "health"]
