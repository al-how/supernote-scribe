"""Connection testing utilities for validating Ollama servers and file paths."""

import httpx
from pathlib import Path


async def test_ollama_connection(url: str, model: str) -> tuple[bool, str]:
    """Test Ollama server connection and model availability.

    Args:
        url: Ollama server URL (e.g., http://192.168.1.138:11434)
        model: Model name to verify (e.g., qwen3-vl:8b)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Test connection
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code != 200:
                return False, f"Server returned {resp.status_code}"

            # Check if model exists
            models = resp.json().get('models', [])
            model_names = [m['name'] for m in models]
            if model not in model_names:
                available = ', '.join(model_names[:3])
                if len(model_names) > 3:
                    available += f" (and {len(model_names) - 3} more)"
                return False, f"Model '{model}' not found. Available: {available}"

            return True, f"Connected to {url} with model {model}"
    except httpx.TimeoutException:
        return False, "Connection timed out (3s limit)"
    except httpx.ConnectError:
        return False, f"Cannot connect to {url} - check URL and network"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def test_path_readable(path: str) -> tuple[bool, str]:
    """Test if path exists and is readable.

    Args:
        path: File system path to test

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        p = Path(path)
        if not p.exists():
            return False, "Path does not exist"
        if not p.is_dir():
            return False, "Path is not a directory"

        # Count items in directory
        items = list(p.glob('*'))
        return True, f"Path exists with {len(items)} items"
    except Exception as e:
        return False, f"Cannot access path: {str(e)}"


def test_path_writable(path: str) -> tuple[bool, str]:
    """Test if path exists and is writable.

    Args:
        path: File system path to test

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        p = Path(path)
        if not p.exists():
            return False, "Path does not exist"
        if not p.is_dir():
            return False, "Path is not a directory"

        # Try to create a test file
        test_file = p / '.write_test'
        test_file.write_text('test')
        test_file.unlink()
        return True, "Path is writable"
    except PermissionError:
        return False, "Path exists but is not writable (permission denied)"
    except Exception as e:
        return False, f"Path not writable: {str(e)}"
