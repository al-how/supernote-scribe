"""Settings page - Configure OCR endpoints, paths, and processing thresholds."""

import asyncio
import os
from pathlib import Path
import sys

import streamlit as st

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.config import get_settings
from app.database import init_db
from app.services.connection_tester import (
    test_llama_server_connection,
    test_ollama_connection,
    test_path_readable,
    test_path_writable,
)
from app.settings_manager import SettingsManager
import app.styles as styles

# Initialize DB
init_db()

st.set_page_config(page_title="Settings", page_icon=":material/settings:", layout="wide")
styles.load_css()

st.title("Settings")
st.markdown("Configure OCR endpoints, paths, and processing thresholds.")

# Initialize settings manager
manager = SettingsManager()
settings = manager.get_all()

# Status indicator
config = get_settings()
st.info(f"Config loaded from: {config.source_path.parent}")

# ============================================================================
# AI Endpoint Configuration
# ============================================================================
st.subheader("AI Configuration")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Local OCR Provider**")
    provider_options = {
        "llama-server": "llama_server",
        "Ollama": "ollama",
    }
    provider_labels = list(provider_options.keys())
    current_provider = settings.get("ocr_provider", "llama_server")
    current_provider_label = next(
        (label for label, value in provider_options.items() if value == current_provider),
        "llama-server",
    )
    ocr_provider_label = st.selectbox(
        "Provider",
        provider_labels,
        index=provider_labels.index(current_provider_label),
        help="Local OCR backend to use before OpenAI fallback",
    )
    ocr_provider = provider_options[ocr_provider_label]

    llama_server_url = settings["llama_server_url"]
    llama_server_model = settings["llama_server_model"]
    ollama_url = settings["ollama_url"]
    ollama_model = settings["ollama_model"]

    if ocr_provider == "llama_server":
        llama_server_url = st.text_input(
            "llama-server URL",
            value=settings["llama_server_url"],
            help="URL of your llama-server endpoint (e.g., http://192.168.1.138:8080)",
        )
        llama_server_model = st.text_input(
            "llama-server Model",
            value=settings["llama_server_model"],
            help="Model name exposed by llama-server",
        )

        if st.button("Test llama-server Connection"):
            with st.spinner("Testing connection..."):
                success, message = asyncio.run(
                    test_llama_server_connection(llama_server_url, llama_server_model)
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
    else:
        ollama_url = st.text_input(
            "Ollama URL",
            value=settings["ollama_url"],
            help="URL of your Ollama server (e.g., http://192.168.1.138:11434)",
        )
        ollama_model = st.text_input(
            "Ollama Model",
            value=settings["ollama_model"],
            help="Vision model name (e.g., qwen3-vl:8b)",
        )

        if st.button("Test Ollama Connection"):
            with st.spinner("Testing connection..."):
                success, message = asyncio.run(
                    test_ollama_connection(ollama_url, ollama_model)
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)

with col2:
    st.markdown("**OpenAI (Fallback)**")
    openai_key = st.text_input(
        "API Key",
        value=settings["openai_api_key"],
        type="password",
        help="Your OpenAI API key (optional, used as fallback)",
    )
    openai_model = st.text_input(
        "Model",
        value=settings["openai_model"],
        help="OpenAI model name (e.g., gpt-4o)",
    )

# ============================================================================
# Processing Thresholds
# ============================================================================
st.divider()
st.subheader("Processing Thresholds")

col1, col2, col3 = st.columns(3)

with col1:
    quality_threshold = st.number_input(
        "Quality Threshold (chars)",
        min_value=0,
        value=settings["quality_threshold"],
        help="Minimum character count before triggering vision OCR (currently unused - all notes use vision)",
    )

with col2:
    auto_approve_threshold = st.number_input(
        "Auto-Approve Threshold (chars)",
        min_value=0,
        value=settings["auto_approve_threshold"],
        help="Auto-approve extractions with at least this many characters",
    )

with col3:
    ocr_timeout = st.number_input(
        "OCR Timeout (seconds)",
        min_value=30,
        max_value=600,
        value=settings["ocr_timeout"],
        help="Maximum time to wait for OCR response",
    )

# ============================================================================
# Path Configuration
# ============================================================================
st.divider()
st.subheader("Paths")

source_path = st.text_input(
    "Source Path (.note files)",
    value=settings["source_path"],
    help="Directory containing your Supernote .note files",
)

output_path = st.text_input(
    "Output Path (Journals)",
    value=settings["output_path"],
    help="Directory where markdown files will be saved (Journals folder)",
)

col1, col2 = st.columns(2)
with col1:
    if st.button("Verify Source Path"):
        success, message = test_path_readable(source_path)
        if success:
            note_count = len(list(Path(source_path).rglob("*.note")))
            st.success(f"{message} ({note_count} .note files found)")
        else:
            st.error(message)

with col2:
    if st.button("Verify Output Path"):
        success, message = test_path_writable(output_path)
        if success:
            st.success(message)
        else:
            st.error(message)

# ============================================================================
# Schedule Configuration
# ============================================================================
st.divider()
st.subheader("Automated Processing")

schedule_enabled = st.checkbox(
    "Enable Scheduled Processing",
    value=settings["schedule_enabled"],
    help="When enabled, the headless processor will run when triggered by Unraid cron",
)

st.info(
    "**Note:** The actual schedule timing is controlled by Unraid cron "
    "(e.g., `docker exec supernote-converter python -m app --process`). "
    "This toggle only enables/disables whether the processor runs when triggered. "
    "See docs/plan.md for setup instructions."
)

# ============================================================================
# Save Button
# ============================================================================
st.divider()

if st.button("Save Settings", type="primary", use_container_width=True):
    try:
        manager.set("ocr_provider", ocr_provider)
        manager.set("llama_server_url", llama_server_url)
        manager.set("llama_server_model", llama_server_model)
        manager.set("ollama_url", ollama_url)
        manager.set("ollama_model", ollama_model)
        manager.set("openai_api_key", openai_key)
        manager.set("openai_model", openai_model)
        manager.set("quality_threshold", quality_threshold)
        manager.set("auto_approve_threshold", auto_approve_threshold)
        manager.set("ocr_timeout", ocr_timeout)
        manager.set("source_path", source_path)
        manager.set("output_path", output_path)
        manager.set("schedule_enabled", schedule_enabled)

        st.success("Settings saved successfully!")
        st.balloons()
        st.rerun()
    except Exception as e:
        st.error(f"Failed to save settings: {str(e)}")

# ============================================================================
# Advanced Options
# ============================================================================
with st.expander("Advanced Options"):
    st.warning(
        "**Warning:** Resetting to defaults will clear all database settings. "
        "Environment variables from .env will be used instead."
    )

    if st.button("Reset to Environment Defaults", type="secondary"):
        try:
            manager.clear_all()
            st.success("Reset complete. Refresh page to see changes.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to reset settings: {str(e)}")
