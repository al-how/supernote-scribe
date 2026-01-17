"""Manual test script for OCR service.

Usage:
    python tests/manual_ocr_test.py

This script tests the OCR service with a real PNG file exported from a .note file.
It will attempt to use Ollama first, then fall back to OpenAI if configured.
"""
from pathlib import Path

from app.config import get_settings
from app.services.exporter import export_note_to_png
from app.services.ocr import extract_text_from_image, ocr_with_ollama, ocr_with_openai


def test_ollama_ocr():
    """Test Ollama OCR with real PNG."""
    settings = get_settings()
    png_path = Path("data/png_cache/20251222_Note to Maggie_0.png")

    print("=" * 60)
    print("OLLAMA OCR TEST")
    print("=" * 60)
    print(f"Settings:")
    print(f"  Ollama URL: {settings.ollama_url}")
    print(f"  Ollama Model: {settings.ollama_model}")
    print(f"  Timeout: {settings.ocr_timeout}s")
    print(f"  PNG: {png_path}")
    print()

    if not png_path.exists():
        print("ERROR: PNG file not found. Run exporter first.")
        return

    print("Testing Ollama OCR...")
    result = ocr_with_ollama(png_path, settings)

    if result is not None:
        print(f"SUCCESS: Ollama OCR extracted {len(result)} characters")
        print()
        print("Extracted text preview:")
        print("-" * 60)
        print(result[:500])
        if len(result) > 500:
            print("...")
        print("-" * 60)
    else:
        print("FAILED: Ollama returned None")
        print("This is expected if Ollama is not running or not accessible.")
    print()


def test_openai_ocr():
    """Test OpenAI OCR with real PNG."""
    settings = get_settings()
    png_path = Path("data/png_cache/20251222_Note to Maggie_0.png")

    print("=" * 60)
    print("OPENAI OCR TEST")
    print("=" * 60)
    print(f"Settings:")
    print(f"  OpenAI Model: {settings.openai_model}")
    print(f"  API Key: {'***' + settings.openai_api_key[-4:] if settings.openai_api_key else 'Not configured'}")
    print(f"  Timeout: {settings.ocr_timeout}s")
    print(f"  PNG: {png_path}")
    print()

    if not png_path.exists():
        print("ERROR: PNG file not found. Run exporter first.")
        return

    if not settings.openai_api_key:
        print("SKIPPED: OpenAI API key not configured")
        print()
        return

    print("Testing OpenAI OCR...")
    result = ocr_with_openai(png_path, settings)

    if result is not None:
        print(f"SUCCESS: OpenAI OCR extracted {len(result)} characters")
        print()
        print("Extracted text preview:")
        print("-" * 60)
        print(result[:500])
        if len(result) > 500:
            print("...")
        print("-" * 60)
    else:
        print("FAILED: OpenAI returned None")
    print()


def test_ocr_with_fallback():
    """Test high-level OCR function with automatic fallback."""
    settings = get_settings()
    png_path = Path("data/png_cache/20251222_Note to Maggie_0.png")

    print("=" * 60)
    print("OCR WITH FALLBACK TEST")
    print("=" * 60)
    print(f"PNG: {png_path}")
    print()

    if not png_path.exists():
        print("ERROR: PNG file not found. Run exporter first.")
        return

    print("Testing extract_text_from_image() with automatic fallback...")
    try:
        text, provider = extract_text_from_image(png_path, settings)
        print(f"SUCCESS: OCR completed using {provider.upper()}")
        print(f"Extracted {len(text)} characters")
        print()
        print("Extracted text preview:")
        print("-" * 60)
        print(text[:500])
        if len(text) > 500:
            print("...")
        print("-" * 60)
    except Exception as e:
        print(f"FAILED: {e}")
    print()


if __name__ == "__main__":
    print("\n")
    print("*" * 60)
    print("MANUAL OCR SERVICE TEST")
    print("*" * 60)
    print()

    # Ensure we have a PNG to test with
    note_path = Path("tests/fixtures/20251222_Note to Maggie.note")
    if note_path.exists():
        print("Exporting .note file to PNG...")
        pngs = export_note_to_png(note_path)
        print(f"Exported {len(pngs)} PNG(s)")
        print()

    # Run tests
    test_ollama_ocr()
    test_openai_ocr()
    test_ocr_with_fallback()

    print("*" * 60)
    print("Manual testing complete!")
    print("*" * 60)
    print()
