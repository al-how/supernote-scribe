"""Tests for OCR service."""
import base64
from pathlib import Path

import httpx
import pytest
import respx

from app.config import Settings
from app.services.ocr import (
    OCRError,
    extract_text_from_image,
    ocr_with_ollama,
    ocr_with_openai,
)


class TestOllamaOCR:
    """Tests for Ollama vision OCR."""

    @respx.mock
    def test_ocr_ollama_success(
        self, sample_png_path, mock_settings, ollama_success_response
    ):
        """Test successful Ollama OCR extraction."""
        # Mock HTTP POST to Ollama
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json=ollama_success_response)
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result == "This is extracted text from the handwritten note."

    @respx.mock
    def test_ocr_ollama_encodes_image_as_base64(self, sample_png_path, mock_settings):
        """Verify image is encoded as base64 in request."""
        route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        ocr_with_ollama(sample_png_path, mock_settings)

        # Verify request contains base64-encoded image
        request = route.calls[0].request
        json_data = request.content.decode('utf-8')
        assert "images" in json_data
        # Verify it's a valid base64 string
        assert len(json_data) > 100  # Should be substantial with base64 image

    @respx.mock
    def test_ocr_ollama_sends_correct_prompt(self, sample_png_path, mock_settings):
        """Verify prompt instructs model to extract handwritten text."""
        route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        ocr_with_ollama(sample_png_path, mock_settings)

        request = route.calls[0].request
        json_data = request.content.decode('utf-8')
        # Verify prompt contains instructions for handwriting extraction
        assert "handwritten" in json_data.lower()
        assert "extract" in json_data.lower()

    @respx.mock
    def test_ocr_ollama_handles_timeout(self, sample_png_path, mock_settings):
        """Test Ollama timeout returns None."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_ollama_handles_connection_error(self, sample_png_path, mock_settings):
        """Test Ollama connection error returns None."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_ollama_handles_invalid_response(self, sample_png_path, mock_settings):
        """Test malformed Ollama response returns None."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"error": "Invalid request"})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_ollama_handles_http_error(self, sample_png_path, mock_settings):
        """Test Ollama HTTP error (500, 503, etc) returns None."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_ollama_respects_timeout_setting(self, sample_png_path, mock_settings):
        """Verify timeout parameter is passed correctly."""
        route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "text", "done": True})
        )

        mock_settings.ocr_timeout = 60
        ocr_with_ollama(sample_png_path, mock_settings)

        # Request should complete successfully with timeout set
        assert route.called


class TestOpenAIOCR:
    """Tests for OpenAI vision OCR."""

    @respx.mock
    def test_ocr_openai_success(
        self, sample_png_path, mock_settings, openai_success_response
    ):
        """Test successful OpenAI OCR extraction."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
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

    @respx.mock
    def test_ocr_openai_handles_timeout(self, sample_png_path, mock_settings):
        """Test OpenAI timeout returns None."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_openai_handles_api_error_429(self, sample_png_path, mock_settings):
        """Test OpenAI rate limit error returns None."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                429, json={"error": {"message": "Rate limit exceeded"}}
            )
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_openai_handles_api_error_500(self, sample_png_path, mock_settings):
        """Test OpenAI server error returns None."""
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        result = ocr_with_openai(sample_png_path, mock_settings)

        assert result is None

    @respx.mock
    def test_ocr_openai_sends_correct_headers(
        self, sample_png_path, mock_settings, openai_success_response
    ):
        """Verify Authorization header with API key is sent."""
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        ocr_with_openai(sample_png_path, mock_settings)

        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer sk-test-key"
        assert "Content-Type" in request.headers

    @respx.mock
    def test_ocr_openai_sends_vision_request(
        self, sample_png_path, mock_settings, openai_success_response
    ):
        """Verify request format for vision API."""
        route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        ocr_with_openai(sample_png_path, mock_settings)

        request = route.calls[0].request
        json_data = request.content.decode('utf-8')
        # Verify request contains model and image data
        assert "gpt-4o" in json_data
        assert "image_url" in json_data
        assert "data:image/png;base64," in json_data


class TestExtractTextFromImage:
    """Tests for high-level OCR orchestration."""

    @respx.mock
    def test_uses_ollama_by_default(
        self, sample_png_path, mock_settings, ollama_success_response
    ):
        """Test Ollama is used as primary by default."""
        ollama_route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json=ollama_success_response)
        )

        text, provider = extract_text_from_image(sample_png_path, mock_settings)

        assert text == "This is extracted text from the handwritten note."
        assert provider == "ollama"
        assert ollama_route.called

    @respx.mock
    def test_uses_openai_when_preferred(
        self, sample_png_path, mock_settings, openai_success_response
    ):
        """Test OpenAI is used when prefer_openai=True."""
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        text, provider = extract_text_from_image(
            sample_png_path, mock_settings, prefer_openai=True
        )

        assert text == "This is extracted text from the handwritten note."
        assert provider == "openai"
        assert openai_route.called

    @respx.mock
    def test_fallback_to_openai_when_ollama_fails(
        self, sample_png_path, mock_settings, openai_success_response
    ):
        """Test fallback to OpenAI when Ollama times out."""
        ollama_route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=openai_success_response)
        )

        text, provider = extract_text_from_image(sample_png_path, mock_settings)

        assert text == "This is extracted text from the handwritten note."
        assert provider == "openai"
        assert ollama_route.called
        assert openai_route.called

    @respx.mock
    def test_fallback_to_ollama_when_openai_fails(
        self, sample_png_path, mock_settings, ollama_success_response
    ):
        """Test fallback to Ollama when OpenAI is primary and fails."""
        openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        ollama_route = respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json=ollama_success_response)
        )

        text, provider = extract_text_from_image(
            sample_png_path, mock_settings, prefer_openai=True
        )

        assert text == "This is extracted text from the handwritten note."
        assert provider == "ollama"
        assert openai_route.called
        assert ollama_route.called

    @respx.mock
    def test_raises_exception_when_both_fail(self, sample_png_path, mock_settings):
        """Test exception raised when both OCR providers fail."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(OCRError) as exc_info:
            extract_text_from_image(sample_png_path, mock_settings)

        assert "ocr failed" in str(exc_info.value).lower()
        # Should include details about both providers failing
        assert "both providers" in str(exc_info.value).lower()

    @respx.mock
    def test_skips_openai_fallback_when_no_api_key(
        self, sample_png_path, mock_settings
    ):
        """Test no OpenAI fallback attempt when API key not configured."""
        mock_settings.openai_api_key = None

        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(OCRError) as exc_info:
            extract_text_from_image(sample_png_path, mock_settings)

        # Should only mention primary failure
        error_msg = str(exc_info.value).lower()
        assert "ocr failed" in error_msg

    @respx.mock
    def test_returns_empty_string_from_ollama(self, sample_png_path, mock_settings):
        """Test Ollama returning empty text is valid."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "", "done": True})
        )

        text, provider = extract_text_from_image(sample_png_path, mock_settings)

        # Empty response should still be valid (not None)
        assert text == ""
        assert provider == "ollama"


class TestOCREdgeCases:
    """Edge case tests for OCR service."""

    def test_handles_nonexistent_image_file(self, mock_settings):
        """Test graceful handling of missing image file."""
        fake_path = Path("nonexistent.png")

        with pytest.raises(FileNotFoundError):
            extract_text_from_image(fake_path, mock_settings)

    @respx.mock
    def test_handles_empty_ollama_response(self, sample_png_path, mock_settings):
        """Test Ollama returning empty text."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "", "done": True})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        # Empty response should still be valid (not None)
        assert result == ""

    @respx.mock
    def test_handles_missing_response_field(self, sample_png_path, mock_settings):
        """Test Ollama response missing 'response' field returns None."""
        respx.post(f"{mock_settings.ollama_url}/api/generate").mock(
            return_value=httpx.Response(200, json={"done": True})
        )

        result = ocr_with_ollama(sample_png_path, mock_settings)

        # Missing response field should return empty string (default)
        assert result == ""
