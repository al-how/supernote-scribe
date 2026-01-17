# Step 6: OCR Service Implementation Plan

## Overview

Implement the OCR service that extracts text from PNG images using Ollama vision (primary) and OpenAI vision (fallback). Following TDD approach from [test-plan.md](../../docs/test-plan.md).

## Goals

1. Extract handwritten text from PNG images using vision models
2. Support dual OCR providers: Ollama (primary) and OpenAI (fallback)
3. Handle errors gracefully (timeouts, connection failures, API errors)
4. Respect user preferences for OCR provider selection
5. Follow TDD: write tests first, then implement

## Prerequisites

- ✅ Step 1-3: Database, config, and settings complete
- ✅ Step 4: Scanner service complete
- ✅ Step 5: Exporter service complete (generates PNGs to process)
- ✅ Test infrastructure: pytest, conftest.py, fixtures

## Dependencies

All already in `requirements.txt`:
- `httpx>=0.26.0` - HTTP client for API calls
- `pytest` - Testing framework

Additional test dependencies needed:
- `pytest-mock` - For mocking HTTP responses
- `pytest-httpx` or `respx` - HTTP request mocking (choose one)

## Architecture

### Module: `app/services/ocr.py`

```python
"""OCR service for extracting text from PNG images using vision models."""

# Public API:
# - ocr_with_ollama(image_path, settings) -> str | None
# - ocr_with_openai(image_path, settings) -> str | None
# - extract_text_from_image(image_path, settings, prefer_openai=False) -> tuple[str, str]
#   Returns: (extracted_text, provider_used)
```

### Function Responsibilities

1. **`ocr_with_ollama(image_path: Path, settings: Settings) -> str | None`**
   - Encode image to base64
   - POST to Ollama `/api/generate` endpoint
   - Parse response and extract text
   - Return `None` on errors (timeout, connection, invalid response)
   - Timeout: Use `settings.ocr_timeout`

2. **`ocr_with_openai(image_path: Path, settings: Settings) -> str | None`**
   - Check if API key is configured
   - Encode image to base64
   - POST to OpenAI Chat Completions API
   - Parse response and extract text
   - Return `None` on errors (missing key, API errors, timeout)
   - Timeout: Use `settings.ocr_timeout`

3. **`extract_text_from_image(image_path: Path, settings: Settings, prefer_openai: bool = False) -> tuple[str, str]`**
   - High-level function that orchestrates OCR with fallback logic
   - Try primary provider first (based on `prefer_openai` flag)
   - If primary fails, try fallback provider
   - If both fail, raise exception with descriptive error
   - Returns: `(extracted_text, provider_used)` where provider is `"ollama"` or `"openai"`

## Test-Driven Development Workflow

### Phase 1: Write Tests First

**File:** `tests/test_ocr.py`

#### Test Structure

```python
"""Tests for OCR service."""
import base64
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from app.config import Settings
from app.services.ocr import (
    extract_text_from_image,
    ocr_with_ollama,
    ocr_with_openai,
)

# Test fixtures, mocks, and test cases...
```

#### Required Fixtures (add to `conftest.py`)

```python
@pytest.fixture
def sample_png_path():
    """Path to a sample PNG for OCR testing."""
    return Path("tests/fixtures/sample_page.png")

@pytest.fixture
def mock_settings():
    """Mock Settings object for testing."""
    return Settings(
        ollama_url="http://localhost:11434",
        ollama_model="qwen3-vl:8b",
        openai_api_key="sk-test-key",
        openai_model="gpt-4o",
        ocr_timeout=120,
    )

@pytest.fixture
def ollama_success_response():
    """Mock successful Ollama API response."""
    return {
        "model": "qwen3-vl:8b",
        "response": "This is extracted text from the handwritten note.",
        "done": True,
    }

@pytest.fixture
def openai_success_response():
    """Mock successful OpenAI API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is extracted text from the handwritten note.",
                },
                "finish_reason": "stop",
            }
        ],
    }
```

#### Test Cases (from test-plan.md)

##### 1. Ollama OCR Tests

```python
class TestOllamaOCR:
    """Tests for Ollama vision OCR."""

    def test_ocr_ollama_success(
        self, sample_png_path, mock_settings, ollama_success_response, respx_mock
    ):
        """Test successful Ollama OCR extraction."""
        # Mock HTTP POST to Ollama
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json=ollama_success_response)
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result == "This is extracted text from the handwritten note."

    def test_ocr_ollama_encodes_image_as_base64(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Verify image is encoded as base64 in request."""
        route = respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        ocr_with_ollama(sample_png_path, mock_settings)

        # Verify request contains base64-encoded image
        request = route.calls[0].request
        json_data = request.content
        assert b"images" in json_data
        # Further validation of base64 encoding

    def test_ocr_ollama_sends_correct_prompt(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Verify prompt instructs model to extract handwritten text."""
        route = respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        ocr_with_ollama(sample_png_path, mock_settings)

        request_json = route.calls[0].request
        # Verify prompt contains instructions for handwriting extraction

    def test_ocr_ollama_handles_timeout(self, sample_png_path, mock_settings, respx_mock):
        """Test Ollama timeout returns None."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_ollama_handles_connection_error(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test Ollama connection error returns None."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_ollama_handles_invalid_response(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test malformed Ollama response returns None."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"error": "Invalid request"})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_ollama_handles_http_error(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test Ollama HTTP error (500, 503, etc) returns None."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_ollama_respects_timeout_setting(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Verify timeout parameter is passed correctly."""
        route = respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        mock_settings.ocr_timeout = 60
        ocr_with_ollama(sample_png_path, mock_settings)

        # Verify httpx client was called with timeout=60
        # (Implementation detail - may need to inspect httpx client creation)
```

##### 2. OpenAI OCR Tests

```python
class TestOpenAIOCR:
    """Tests for OpenAI vision OCR."""

    def test_ocr_openai_success(
        self, sample_png_path, mock_settings, openai_success_response, respx_mock
    ):
        """Test successful OpenAI OCR extraction."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result == "This is extracted text from the handwritten note."

    def test_ocr_openai_handles_missing_api_key(self, sample_png_path, mock_settings):
        """Test OpenAI with missing API key returns None."""
        mock_settings.openai_api_key = None

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_openai_handles_empty_api_key(self, sample_png_path, mock_settings):
        """Test OpenAI with empty API key returns None."""
        mock_settings.openai_api_key = ""

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_openai_handles_timeout(self, sample_png_path, mock_settings, respx_mock):
        """Test OpenAI timeout returns None."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_openai_handles_api_error_429(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test OpenAI rate limit error returns None."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                429, json={"error": {"message": "Rate limit exceeded"}}
            )
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_openai_handles_api_error_500(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test OpenAI server error returns None."""
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    def test_ocr_openai_sends_correct_headers(
        self, sample_png_path, mock_settings, openai_success_response, respx_mock
    ):
        """Verify Authorization header with API key is sent."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        ocr_with_openai(sample_png_path, mock_settings)

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer sk-test-key"
        assert "Content-Type" in request.headers

    def test_ocr_openai_sends_vision_request(
        self, sample_png_path, mock_settings, openai_success_response, respx_mock
    ):
        """Verify request format for vision API."""
        route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        ocr_with_openai(sample_png_path, mock_settings)

        # Verify request contains:
        # - model: gpt-4o
        # - messages with image_url content type
        # - base64 encoded image
```

##### 3. High-Level OCR Function Tests

```python
class TestExtractTextFromImage:
    """Tests for high-level OCR orchestration."""

    def test_uses_ollama_by_default(
        self, sample_png_path, mock_settings, respx_mock, ollama_success_response
    ):
        """Test Ollama is used as primary by default."""
        ollama_route = respx_mock.post(
            f"{mock_settings.ollama_url}/api/generate"
        ).mock(return_value=httpx.Response(200, json=ollama_success_response))

        text, provider = extract_text_from_image(sample_png_path, mock_settings)

        assert text == "This is extracted text from the handwritten note."
        assert provider == "ollama"
        assert ollama_route.called

    def test_uses_openai_when_preferred(
        self, sample_png_path, mock_settings, respx_mock, openai_success_response
    ):
        """Test OpenAI is used when prefer_openai=True."""
        openai_route = respx_mock.post(
            "https://api.openai.com/v1/chat/completions"
        ).mock(return_value=httpx.Response(200, json=openai_success_response))

        text, provider = extract_text_from_image(
            sample_png_path, mock_settings, prefer_openai=True
        )

        assert text == "This is extracted text from the handwritten note."
        assert provider == "openai"
        assert openai_route.called

    def test_fallback_to_openai_when_ollama_fails(
        self, sample_png_path, mock_settings, respx_mock, openai_success_response
    ):
        """Test fallback to OpenAI when Ollama times out."""
        ollama_route = respx_mock.post(
            f"{mock_settings.ollama_url}/api/generate"
        ).mock(side_effect=httpx.TimeoutException("Timeout"))

        openai_route = respx_mock.post(
            "https://api.openai.com/v1/chat/completions"
        ).mock(return_value=httpx.Response(200, json=openai_success_response))

        text, provider = extract_text_from_image(sample_png_path, mock_settings)

        assert text == "This is extracted text from the handwritten note."
        assert provider == "openai"
        assert ollama_route.called
        assert openai_route.called

    def test_fallback_to_ollama_when_openai_fails(
        self, sample_png_path, mock_settings, respx_mock, ollama_success_response
    ):
        """Test fallback to Ollama when OpenAI is primary and fails."""
        openai_route = respx_mock.post(
            "https://api.openai.com/v1/chat/completions"
        ).mock(side_effect=httpx.TimeoutException("Timeout"))

        ollama_route = respx_mock.post(
            f"{mock_settings.ollama_url}/api/generate"
        ).mock(return_value=httpx.Response(200, json=ollama_success_response))

        text, provider = extract_text_from_image(
            sample_png_path, mock_settings, prefer_openai=True
        )

        assert text == "This is extracted text from the handwritten note."
        assert provider == "ollama"
        assert openai_route.called
        assert ollama_route.called

    def test_raises_exception_when_both_fail(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test exception raised when both OCR providers fail."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(Exception) as exc_info:
            extract_text_from_image(sample_png_path, mock_settings)

        assert "OCR failed" in str(exc_info.value).lower()
        # Should include details about both providers failing

    def test_skips_openai_fallback_when_no_api_key(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test no OpenAI fallback attempt when API key not configured."""
        mock_settings.openai_api_key = None

        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(Exception) as exc_info:
            extract_text_from_image(sample_png_path, mock_settings)

        # Should only mention Ollama failure, not attempt OpenAI
        assert "openai" not in str(exc_info.value).lower()
```

##### 4. Edge Cases

```python
class TestOCREdgeCases:
    """Edge case tests for OCR service."""

    def test_handles_nonexistent_image_file(self, mock_settings):
        """Test graceful handling of missing image file."""
        fake_path = Path("nonexistent.png")

        with pytest.raises(FileNotFoundError):
            extract_text_from_image(fake_path, mock_settings)

    def test_handles_empty_ollama_response(
        self, sample_png_path, mock_settings, respx_mock
    ):
        """Test Ollama returning empty text."""
        respx_mock.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "", "done": True})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        # Empty response should still be valid (not None)
        assert result == ""

    def test_handles_very_large_image(self, tmp_path, mock_settings, respx_mock):
        """Test OCR handles large images (may need base64 size limits)."""
        # Create a large dummy PNG
        # Test base64 encoding doesn't fail
        # (Implementation detail - may be future consideration)
```

### Phase 2: Run Tests (All Should Fail)

```bash
pytest tests/test_ocr.py -v
```

Expected: All tests fail with `ImportError` or `AttributeError` (functions don't exist yet).

### Phase 3: Implement OCR Service

**File:** `app/services/ocr.py`

#### Implementation Structure

```python
"""OCR service for extracting text from PNG images using vision models.

Supports two OCR providers:
- Ollama (local vision model, primary)
- OpenAI (cloud API, fallback)

All functions return None on errors to enable graceful fallback handling.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

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


def ocr_with_ollama(image_path: Path, settings: Settings) -> str | None:
    """Extract text from image using Ollama vision model.

    Args:
        image_path: Path to PNG image
        settings: Application settings (Ollama URL, model, timeout)

    Returns:
        Extracted text, or None if OCR failed
    """
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

        with httpx.Client(timeout=settings.ocr_timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()
        extracted_text = data.get("response", "")

        logger.info(f"Ollama OCR succeeded ({len(extracted_text)} chars)")
        return extracted_text

    except httpx.TimeoutException:
        logger.warning(f"Ollama OCR timeout ({settings.ocr_timeout}s)")
        return None
    except httpx.ConnectError as e:
        logger.warning(f"Ollama connection error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"Ollama HTTP error: {e.response.status_code}")
        return None
    except (KeyError, ValueError) as e:
        logger.warning(f"Ollama response parsing error: {e}")
        return None
    except FileNotFoundError:
        raise  # Re-raise file not found
    except Exception as e:
        logger.error(f"Unexpected Ollama error: {e}")
        return None


def ocr_with_openai(image_path: Path, settings: Settings) -> str | None:
    """Extract text from image using OpenAI vision model.

    Args:
        image_path: Path to PNG image
        settings: Application settings (API key, model, timeout)

    Returns:
        Extracted text, or None if OCR failed or API key not configured
    """
    # Check if API key is configured
    if not settings.openai_api_key or settings.openai_api_key.strip() == "":
        logger.debug("OpenAI API key not configured, skipping")
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
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        }

        logger.info(f"Calling OpenAI OCR (model: {settings.openai_model})")

        with httpx.Client(timeout=settings.ocr_timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        extracted_text = data["choices"][0]["message"]["content"]

        logger.info(f"OpenAI OCR succeeded ({len(extracted_text)} chars)")
        return extracted_text

    except httpx.TimeoutException:
        logger.warning(f"OpenAI OCR timeout ({settings.ocr_timeout}s)")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"OpenAI HTTP error: {e.response.status_code}")
        return None
    except (KeyError, ValueError) as e:
        logger.warning(f"OpenAI response parsing error: {e}")
        return None
    except FileNotFoundError:
        raise  # Re-raise file not found
    except Exception as e:
        logger.error(f"Unexpected OpenAI error: {e}")
        return None


def extract_text_from_image(
    image_path: Path,
    settings: Settings,
    prefer_openai: bool = False,
) -> tuple[str, str]:
    """Extract text from image with automatic fallback between providers.

    Tries primary OCR provider first, falls back to secondary if it fails.
    Raises exception if both providers fail.

    Args:
        image_path: Path to PNG image
        settings: Application settings
        prefer_openai: If True, use OpenAI as primary (default: False, use Ollama)

    Returns:
        Tuple of (extracted_text, provider_used) where provider is "ollama" or "openai"

    Raises:
        OCRError: If both OCR providers fail
        FileNotFoundError: If image file doesn't exist
    """
    # Determine primary and fallback providers
    if prefer_openai:
        primary_fn = ocr_with_openai
        primary_name = "openai"
        fallback_fn = ocr_with_ollama
        fallback_name = "ollama"
    else:
        primary_fn = ocr_with_ollama
        primary_name = "ollama"
        fallback_fn = ocr_with_openai
        fallback_name = "openai"

    # Try primary
    logger.info(f"Attempting OCR with primary provider: {primary_name}")
    result = primary_fn(image_path, settings)

    if result is not None:
        return (result, primary_name)

    # Primary failed, try fallback
    logger.info(f"Primary OCR failed, trying fallback: {fallback_name}")
    result = fallback_fn(image_path, settings)

    if result is not None:
        return (result, fallback_name)

    # Both failed
    error_msg = (
        f"OCR failed with both providers. "
        f"Primary ({primary_name}) and fallback ({fallback_name}) both returned errors. "
        f"Check logs for details."
    )
    logger.error(error_msg)
    raise OCRError(error_msg)
```

### Phase 4: Run Tests (Should Pass)

```bash
pytest tests/test_ocr.py -v
```

Expected: All tests pass ✅

### Phase 5: Manual Testing

Once tests pass, verify with real PNG files:

```python
# Manual test script: tests/manual_ocr_test.py
from pathlib import Path
from app.config import get_settings
from app.services.ocr import extract_text_from_image

settings = get_settings()
png_path = Path("tests/fixtures/sample_page.png")  # Need real PNG

text, provider = extract_text_from_image(png_path, settings)
print(f"Provider: {provider}")
print(f"Extracted text:\n{text}")
```

Run against:
1. Real Supernote PNG (from exporter service)
2. Verify Ollama connection works
3. Test OpenAI fallback (temporarily break Ollama URL)
4. Verify text quality

## Implementation Checklist

### Setup
- [ ] Add `pytest-mock` and `respx` to `requirements.txt`
- [ ] Install test dependencies: `pip install pytest-mock respx`
- [ ] Create sample PNG fixture: `tests/fixtures/sample_page.png`

### TDD Phase 1: Write Tests
- [ ] Add OCR fixtures to `tests/conftest.py`:
  - [ ] `sample_png_path` fixture
  - [ ] `mock_settings` fixture
  - [ ] `ollama_success_response` fixture
  - [ ] `openai_success_response` fixture
- [ ] Create `tests/test_ocr.py`
- [ ] Write Ollama OCR tests (7-8 tests)
- [ ] Write OpenAI OCR tests (7-8 tests)
- [ ] Write high-level OCR tests (6-7 tests)
- [ ] Write edge case tests (2-3 tests)
- [ ] Run tests: `pytest tests/test_ocr.py -v` (expect failures)

### TDD Phase 2: Implement Service
- [ ] Create `app/services/ocr.py`
- [ ] Implement `_encode_image_base64()` helper
- [ ] Implement `ocr_with_ollama()`
- [ ] Implement `ocr_with_openai()`
- [ ] Implement `extract_text_from_image()`
- [ ] Add `OCRError` exception class
- [ ] Add logging throughout
- [ ] Run tests: `pytest tests/test_ocr.py -v` (expect passes)

### TDD Phase 3: Fix Failing Tests
- [ ] Debug and fix any test failures
- [ ] Achieve 100% test pass rate
- [ ] Check test coverage: `pytest --cov=app.services.ocr tests/test_ocr.py`
- [ ] Aim for >80% coverage

### Manual Validation
- [ ] Export a real .note file to PNG (using exporter service)
- [ ] Test Ollama OCR with real PNG
- [ ] Verify extracted text quality
- [ ] Test OpenAI fallback (break Ollama config temporarily)
- [ ] Verify error handling (timeout Ollama, test fallback)

### Integration Prep
- [ ] Export OCR functions in `app/services/__init__.py` (if needed)
- [ ] Document OCR service in README or docs
- [ ] Update plan.md Step 6 status to "COMPLETE"

## Success Criteria

✅ **All tests pass** (20+ test cases)
✅ **Test coverage >80%** for `ocr.py`
✅ **Manual test**: Real PNG → readable text via Ollama
✅ **Manual test**: Fallback to OpenAI works when Ollama unavailable
✅ **Error handling**: Graceful failures, no crashes
✅ **Ready for Step 7**: Processor service can call `extract_text_from_image()`

## Next Steps (After Step 6)

**Step 7: Processor Service**
- Use `extract_text_from_image()` to process exported PNGs
- Aggregate text from multi-page notes
- Implement auto-approve logic (>200 chars)
- Mark notes for review or approval

## Notes

- **Why respx over pytest-httpx?** Both work. `respx` is more flexible for complex routing. Choose based on preference.
- **Base64 size limits?** Supernote PNGs are typically <1MB, base64 ~1.3x size = ~1.3MB. Well within limits for both APIs.
- **Prompt tuning?** Initial prompts are simple. Can refine based on real extraction quality during manual testing.
- **Streaming?** Not needed. Supernote pages are single images, not long conversations. Use `stream: false`.

## Estimated Effort

- **Write tests**: 2-3 hours (20+ test cases, fixtures, mocking)
- **Implement service**: 1-2 hours (3 functions, error handling, logging)
- **Debug/fix tests**: 30 mins - 1 hour
- **Manual testing**: 30 mins - 1 hour
- **Total**: 4-7 hours

## References

- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion)
- [OpenAI Vision API](https://platform.openai.com/docs/guides/vision)
- [pytest-httpx](https://colin-b.github.io/pytest_httpx/)
- [respx](https://lundberg.github.io/respx/)
- Project test-plan: `docs/test-plan.md` (Section 3: OCR Service)
- Project plan: `docs/plan.md` (Step 6)
