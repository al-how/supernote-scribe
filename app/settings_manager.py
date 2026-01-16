"""Settings manager - Bridge between pydantic Settings and database settings.

Provides a unified interface for accessing settings with proper precedence:
Database > Environment > Code Defaults
"""

import typing
from app.config import get_settings, Settings
from app.database import get_setting, set_setting, get_all_settings


class SettingsManager:
    """Bridge between pydantic Settings and database settings."""

    def get(self, key: str, default=None):
        """Get setting from DB, fall back to config, then default.

        Args:
            key: Setting key name (must match Settings field name)
            default: Default value if not found in DB or config

        Returns:
            Setting value with proper type conversion
        """
        db_value = get_setting(key)
        if db_value is not None:
            return self._deserialize(key, db_value)

        config = get_settings()
        return getattr(config, key, default)

    def set(self, key: str, value):
        """Save setting to database.

        Args:
            key: Setting key name
            value: Value to save (will be serialized to string)
        """
        set_setting(key, self._serialize(value))

    def get_all(self) -> dict:
        """Get all settings with DB overrides merged with config defaults.

        Returns:
            Dictionary of all settings with DB values overriding config defaults
        """
        config = get_settings()
        db_settings = get_all_settings()

        # Start with config defaults
        result = {
            'ollama_url': config.ollama_url,
            'ollama_model': config.ollama_model,
            'openai_api_key': config.openai_api_key or '',
            'openai_model': config.openai_model,
            'source_path': str(config.source_path),
            'output_path': str(config.output_path),
            'quality_threshold': config.quality_threshold,
            'auto_approve_threshold': config.auto_approve_threshold,
            'ocr_timeout': config.ocr_timeout,
            'schedule_enabled': config.schedule_enabled,
        }

        # Override with DB values
        for key, value in db_settings.items():
            result[key] = self._deserialize(key, value)

        return result

    def _serialize(self, value) -> str:
        """Convert Python value to string for DB storage.

        Args:
            value: Python value to serialize

        Returns:
            String representation for database storage
        """
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)

    def _deserialize(self, key: str, value: str):
        """Convert string from DB to appropriate Python type using Pydantic field annotations.

        Uses the Pydantic Settings model field annotations to determine the correct
        type conversion. This prevents issues where numeric-looking strings
        (e.g., model name "007") would be incorrectly converted to integers.

        Args:
            key: Setting key name
            value: String value from database

        Returns:
            Value converted to appropriate Python type
        """
        # Get the expected type from the Pydantic model definition
        field = Settings.model_fields.get(key)
        if not field:
            return value  # Unknown field, return as string

        target_type = field.annotation

        # Handle Optional types (extract the inner type)
        if hasattr(typing, 'get_origin') and typing.get_origin(target_type) is typing.Union:
            # Optional[X] is Union[X, None], so get the first non-None type
            args = typing.get_args(target_type)
            target_type = next((arg for arg in args if arg is not type(None)), str)

        # Convert based on expected type
        if target_type is bool:
            return value.lower() == 'true'
        if target_type is int:
            return int(value)
        # Default to string (preserves "007" as string, prevents numeric model names from breaking)
        return value
