# Supernote Converter

A Python Streamlit application designed to automate the conversion of handwritten Supernote `.note` files to digital text using local vision AI (Ollama) and export them to an Obsidian vault.

Test Push

## Features

*   **Scanning:** Automatically detects `.note` files in a synchronized directory.
*   **Conversion:** Converts Supernote proprietary format to PNG images.
*   **OCR:** Extracts text from images using Ollama (local Qwen vision models) with OpenAI fallback options.
*   **Review UI:** A Streamlit dashboard to review, edit, and approve extracted text alongside the original image.
*   **Export:** Generates Markdown files with frontmatter suitable for Obsidian.
*   **Automation:** Supports headless CLI execution for background tasks or cron jobs.

## Prerequisites

*   **Python 3.10+** installed on your system.
*   **Ollama** running locally (or accessible via network) with a vision model pulled (e.g., `qwen2.5-vl`).
    *   Example: `ollama pull qwen2.5-vl`

## Windows Development Setup

Follow these steps to get the Streamlit server running on Windows.

### 1. Set up a Virtual Environment

Open your terminal (Command Prompt or PowerShell) in the project root directory and run:

```powershell
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
# For PowerShell:
.\.venv\Scripts\Activate.ps1
# For Command Prompt (cmd.exe):
.\.venv\Scripts\activate.bat
```

### 2. Install Dependencies

With the virtual environment activated, install the required packages:

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

1.  Copy the example environment file:
    ```powershell
    copy .env.example .env
    ```
2.  Open `.env` in a text editor and configure your paths:
    *   `SUPERNOTE_PATH`: Path to your synced Supernote files.
    *   `OBSIDIAN_VAULT_PATH`: Path where you want the markdown files exported.
    *   Configure OCR settings (Ollama URL, model name, etc.).

### 4. Run the Streamlit Application

To start the web interface:

```powershell
streamlit run app/Home.py
```

The application should automatically open in your default web browser at `http://localhost:8501`.

## CLI / Headless Mode

For background processing (e.g., scheduled tasks) without the UI:

```powershell
# Process new files
python -m app --process

# Process files with a specific cutoff date
python -m app --process --cutoff 2026-01-01
```

## Docker

You can also run the application using Docker Compose:

1.  Update `docker-compose.yml` with your local paths.
2.  Run:
    ```bash
    docker-compose up --build -d
    ```

## Project Structure

*   `app/`: Main source code.
    *   `Home.py`: Streamlit dashboard entry point.
    *   `pages/`: UI pages (Scan, Review, History, Settings).
    *   `services/`: Business logic (Scanner, OCR, Exporter).
*   `data/`: Local storage (SQLite DB, image cache).

## Webhook Endpoints
The webhook server is already running on your Unraid box at port 8002:

Method	URL	Purpose
POST	http://<unraid-ip>:8002/process	Trigger a conversion run
GET	http://<unraid-ip>:8002/status	Check pending queue
GET	http://<unraid-ip>:8002/health	Health check
n8n Workflow Setup
The simplest flow is a single HTTP Request node:

Add a trigger — whatever you want to kick it off (Schedule, webhook from another service, manual, etc.)
Add an HTTP Request node:
Method: POST
URL: http://<your-unraid-ip>:8002/process
No body needed
The endpoint returns immediately with {"status": "accepted", "message": "Processing N note(s) in background"} — processing continues in the background on Unraid.

Optional: Check Results
If you want to verify results after a delay, add a Wait node (e.g. 2 minutes) followed by another HTTP Request node:

Method: GET
URL: http://<your-unraid-ip>:8002/status
This returns {"pending_count": 0, "recent_activity": [...]} which you can use to send a notification.

The /process endpoint automatically looks back 7 days for notes, so no parameters needed.