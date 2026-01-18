# Supernote Converter Application

## Project Overview

This project is a Python Streamlit application designed to replace a brittle n8n workflow for processing Supernote `.note` files. It automates the conversion of handwritten notes to digital text using local vision AI and exports them to an Obsidian vault.

## IMPORTANT
You are a coding agent assisting a non-coder. Resist the urge to over-engineer. DO NOT add features without discussing with the user. 

Always write plans to this project directory, eg C:\Users\alexn\Documents\Projects\supernote-converter\.gemini\plans\[session_name].md

**Key Features:**
*   **Scanning:** Detects `.note` files in a synchronized directory.
*   **Conversion:** Converts Supernote proprietary format to PNG images using `supernotelib`.
*   **OCR:** Extracts text from images using Ollama (local Qwen vision models) with OpenAI fallback.
*   **Review UI:** Provides a Streamlit interface to review, edit, and approve extracted text alongside the original image.
*   **Export:** Generates Markdown files with frontmatter for Obsidian.
*   **Automation:** Supports headless CLI execution for cron jobs.

**Tech Stack:**
*   **Language:** Python
*   **UI Framework:** Streamlit
*   **Database:** SQLite (local storage for state and history)
*   **Containerization:** Docker & Docker Compose
*   **Libraries:** `supernotelib` (conversion), `httpx` (API requests), `pydantic` (config).

## Architecture

The application is structured as a modular Streamlit app:

*   **`app/`**: Main application source code.
    *   **`Home.py`**: Entry point for the Streamlit web interface (Dashboard).
    *   **`__main__.py`**: Entry point for CLI/Headless mode.
    *   **`pages/`**: Individual Streamlit pages (Scan, Review, History, Settings).
    *   **`services/`**: Core business logic modules (`scanner`, `exporter`, `ocr`, `processor`, `markdown`).
    *   **`database.py`**: SQLite database interactions.
    *   **`config.py`**: Pydantic-based configuration management.
*   **`data/`**: Directory for local data (SQLite DB, PNG cache), typically mounted as a volume.
*   **`docs/`**: Documentation and planning files.

## building and Running

### Prerequisites

*   Python 3.10+
*   Docker & Docker Compose (optional, for containerized run)
*   Ollama (running locally or accessible via network) with a vision model (e.g., `qwen3-vl:8b`)

### Local Development

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Setup:**
    Copy `.env.example` to `.env` and configure your API keys and paths.
    ```bash
    cp .env.example .env
    ```

3.  **Run Web UI:**
    ```bash
    streamlit run app/Home.py
    ```

4.  **Run Headless (CLI):**
    For cron jobs or background processing:
    ```bash
    python -m app --process
    ```
    With a specific cutoff date:
    ```bash
    python -m app --process --cutoff 2026-01-01
    ```

### Docker Deployment

1.  **Build and Run:**
    ```bash
    docker-compose up --build -d
    ```

2.  **Configuration:**
    Modify `docker-compose.yml` environment variables to point to your Supernote sync directory and Output directory.

## Development Conventions

*   **Code Style:** Follow standard Python PEP 8 guidelines.
*   **Configuration:** All settings are managed via Pydantic models in `app/config.py`, loading from environment variables.
*   **State Management:** Application state (processed files, review queue) is persisted in a local SQLite database (`supernote.db`).
*   **Async/Sync:** The application primarily uses synchronous calls for Streamlit compatibility but may use `httpx` for API interactions.
*   **Error Handling:** "Always Vision OCR" approach is preferred over text extraction fallbacks.

## Working Conventions
*   **Always draft a plan:** Never begin writing or editing files until you've drafted a plan.