"""OCR service for extracting text from PNG images using vision models.

Supports two OCR providers:
- llama-server (local vision model, default)
- Ollama (optional local vision model)
- OpenAI (cloud API, fallback)

All functions return None on errors to enable graceful fallback handling.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Callable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Raised when all OCR providers fail."""

    pass


def _encode_image_base64(image_path: Path) -> str:
    """Encode image file as base64 string.

    Args:
        image_path: Path to PNG image

    Returns:
        Base64-encoded image string

    Raises:
        FileNotFoundError: If image doesn't exist
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def ocr_with_llama_server(
    image_path: Path,
    settings: Settings,
    log_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Extract text from image using llama-server's OpenAI-compatible API.

    Args:
        image_path: Path to PNG image
        settings: Application settings (llama-server URL, model, timeout)
        log_callback: Optional callback for log messages

    Returns:
        Extracted text, or None if OCR failed
    """
    def log(msg: str):
        logger.warning(msg)
        if log_callback:
            log_callback(msg)

    try:
        image_b64 = _encode_image_base64(image_path)

        url = f"{settings.llama_server_url}/v1/chat/completions"

        payload = {
            "model": settings.llama_server_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all handwritten text from this image. "
                                "Output only the text content, preserving paragraph structure and formatting. "
                                "Do not include any commentary or descriptions."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        }

        logger.info(
            f"Calling llama-server OCR: {url} (model: {settings.llama_server_model})"
        )
        if log_callback:
            log_callback(
                f"llama-server: Connecting to {settings.llama_server_url} "
                f"(model: {settings.llama_server_model})"
            )

        with httpx.Client(timeout=settings.ocr_timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()
        extracted_text = data["choices"][0]["message"]["content"]

        logger.info(f"llama-server OCR succeeded ({len(extracted_text)} chars)")
        if log_callback:
            log_callback(f"llama-server: Success ({len(extracted_text)} chars)")
        return extracted_text

    except httpx.TimeoutException:
        log(f"llama-server OCR timeout ({settings.ocr_timeout}s)")
        return None
    except httpx.ConnectError as e:
        log(f"llama-server connection error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        log(f"llama-server HTTP error: {e.response.status_code}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        log(f"llama-server response parsing error: {e}")
        return None
    except FileNotFoundError:
        raise  # Re-raise file not found
    except Exception as e:
        log(f"Unexpected llama-server error: {e}")
        return None


def ocr_with_ollama(
    image_path: Path,
    settings: Settings,
    log_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Extract text from image using Ollama vision model.

    Args:
        image_path: Path to PNG image
        settings: Application settings (Ollama URL, model, timeout)
        log_callback: Optional callback for log messages

    Returns:
        Extracted text, or None if OCR failed
    """
    def log(msg: str):
        logger.warning(msg)
        if log_callback:
            log_callback(msg)

    try:
        image_b64 = _encode_image_base64(image_path)

        # Ollama generate endpoint
        url = f"{settings.ollama_url}/api/generate"

        payload = {
            "model": settings.ollama_model,
            "prompt": (
                "Extract all handwritten text from this image. "
                "Output only the text content, preserving paragraph structure and formatting. "
                "Do not include any commentary or descriptions."
            ),
            "images": [image_b64],
            "stream": False,
        }

        logger.info(f"Calling Ollama OCR: {url} (model: {settings.ollama_model})")
        if log_callback:
            log_callback(f"Ollama: Connecting to {settings.ollama_url} (model: {settings.ollama_model})")

        with httpx.Client(timeout=settings.ocr_timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()

        # Check for error in response
        if "error" in data:
            log(f"Ollama returned error: {data['error']}")
            return None

        extracted_text = data.get("response", "")

        logger.info(f"Ollama OCR succeeded ({len(extracted_text)} chars)")
        if log_callback:
            log_callback(f"Ollama: Success ({len(extracted_text)} chars)")
        return extracted_text

    except httpx.TimeoutException:
        log(f"Ollama OCR timeout ({settings.ocr_timeout}s)")
        return None
    except httpx.ConnectError as e:
        log(f"Ollama connection error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        log(f"Ollama HTTP error: {e.response.status_code}")
        return None
    except (KeyError, ValueError) as e:
        log(f"Ollama response parsing error: {e}")
        return None
    except FileNotFoundError:
        raise  # Re-raise file not found
    except Exception as e:
        log(f"Unexpected Ollama error: {e}")
        return None


def ocr_with_openai(
    image_path: Path,
    settings: Settings,
    log_callback: Callable[[str], None] | None = None,
) -> str | None:
    """Extract text from image using OpenAI vision model.

    Args:
        image_path: Path to PNG image
        settings: Application settings (API key, model, timeout)
        log_callback: Optional callback for log messages

    Returns:
        Extracted text, or None if OCR failed or API key not configured
    """
    def log(msg: str):
        logger.warning(msg)
        if log_callback:
            log_callback(msg)

    # Check if API key is configured
    if not settings.openai_api_key or settings.openai_api_key.strip() == "":
        logger.debug("OpenAI API key not configured, skipping")
        if log_callback:
            log_callback("OpenAI: API key not configured")
        return None

    try:
        image_b64 = _encode_image_base64(image_path)

        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.openai_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all handwritten text from this image. "
                                "Output only the text content, preserving paragraph structure. "
                                "Do not include any commentary."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        }

        logger.info(f"Calling OpenAI OCR (model: {settings.openai_model})")
        if log_callback:
            log_callback(f"OpenAI: Calling API (model: {settings.openai_model})")

        with httpx.Client(timeout=settings.ocr_timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        extracted_text = data["choices"][0]["message"]["content"]

        logger.info(f"OpenAI OCR succeeded ({len(extracted_text)} chars)")
        if log_callback:
            log_callback(f"OpenAI: Success ({len(extracted_text)} chars)")
        return extracted_text

    except httpx.TimeoutException:
        log(f"OpenAI OCR timeout ({settings.ocr_timeout}s)")
        return None
    except httpx.HTTPStatusError as e:
        log(f"OpenAI HTTP error: {e.response.status_code}")
        return None
    except (KeyError, ValueError) as e:
        log(f"OpenAI response parsing error: {e}")
        return None
    except FileNotFoundError:
        raise  # Re-raise file not found
    except Exception as e:
        log(f"Unexpected OpenAI error: {e}")
        return None


def extract_text_from_image(
    image_path: Path,
    settings: Settings,
    prefer_openai: bool = False,
    status_callback: Callable[[str], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """Extract text from image with automatic fallback between providers.

    Tries primary OCR provider first, falls back to secondary if it fails.
    Raises exception if both providers fail.

    Args:
        image_path: Path to PNG image
        settings: Application settings
        prefer_openai: If True, use OpenAI as primary (default: False, use configured local provider)
        status_callback: Optional callback for status updates (e.g., "Sending to Ollama...")
        log_callback: Optional callback for log messages (errors, warnings)

    Returns:
        Tuple of (extracted_text, provider_used) where provider is "llama_server", "ollama", or "openai"

    Raises:
        OCRError: If both OCR providers fail
        FileNotFoundError: If image file doesn't exist
    """
    local_provider = settings.ocr_provider
    if local_provider == "ollama":
        local_fn = ocr_with_ollama
        local_name = "ollama"
    else:
        local_fn = ocr_with_llama_server
        local_name = "llama_server"

    # Determine primary and fallback providers
    if prefer_openai:
        primary_fn = ocr_with_openai
        primary_name = "openai"
        fallback_fn = local_fn
        fallback_name = local_name
    else:
        primary_fn = local_fn
        primary_name = local_name
        fallback_fn = ocr_with_openai
        fallback_name = "openai"

    # Try primary
    logger.info(f"Attempting OCR with primary provider: {primary_name}")
    if status_callback:
        status_callback(f"Sending to {primary_name.title()}...")

    result = primary_fn(image_path, settings, log_callback=log_callback)

    if result is not None:
        return (result, primary_name)

    # Primary failed, try fallback
    logger.info(f"Primary OCR failed, trying fallback: {fallback_name}")
    if status_callback:
        status_callback(f"{primary_name.title()} failed, trying {fallback_name.title()}...")

    result = fallback_fn(image_path, settings, log_callback=log_callback)

    if result is not None:
        return (result, fallback_name)

    # Both failed
    error_msg = (
        f"OCR failed with both providers. "
        f"Primary ({primary_name}) and fallback ({fallback_name}) both returned errors. "
        f"Check logs for details."
    )
    logger.error(error_msg)
    if log_callback:
        log_callback(error_msg)
    raise OCRError(error_msg)
