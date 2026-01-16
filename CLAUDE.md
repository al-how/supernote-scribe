# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT
You are a coding agent assisting a non-coder. Resist the urge to over-engineer. DO NOT add features without discussing with the user. 

Always write plans to this project directory, eg C:\Users\alexn\Documents\Projects\supernote-converter\.claude\plans\[session_name].md

## Project Overview

Supernote Converter is a Python Streamlit web application that converts handwritten Supernote `.note` files into searchable markdown for Obsidian. It uses local Ollama vision OCR (qwen3-vl:8b) as the primary extraction method with OpenAI gpt-4o as fallback.

**Current State:** Database layer implemented. See `docs/plan.md` for full specification and implementation progress.

## Tech Stack

- **Runtime:** Python 3.11
- **UI:** Streamlit (multi-page app)
- **Database:** SQLite (local state, no external deps)
- **PNG Export:** supernotelib
- **OCR:** Ollama HTTP API (primary), OpenAI API (fallback)
- **HTTP Client:** httpx
- **Config:** Pydantic + pydantic-settings
- **Deployment:** Docker on Unraid

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit web UI
streamlit run app/app.py

# Run headless processor (for cron)
python -m app --process
python -m app --process --cutoff 2026-01-01

# Docker
docker-compose build
docker-compose up -d
docker exec supernote-converter python -m app --process
```

## Architecture

```
app/
├── app.py              # Streamlit main dashboard
├── __main__.py         # CLI entry point (--process flag)
├── config.py           # Pydantic settings from .env
├── database.py         # SQLite schema & operations
├── pages/              # Streamlit multi-page UI
│   ├── 1_Scan.py       # Scan & process notes
│   ├── 2_Review.py     # Review queue (PNG + text side-by-side)
│   ├── 3_History.py    # Processed notes history
│   └── 4_Settings.py   # Configuration
└── services/           # Business logic
    ├── scanner.py      # File discovery & filtering
    ├── exporter.py     # supernotelib PNG export
    ├── ocr.py          # Ollama + OpenAI vision OCR
    ├── processor.py    # Pipeline orchestration
    └── markdown.py     # Frontmatter builder & output routing
```

**Data Flow:** Scan → Export to PNG → Vision OCR → Review (if needed) → Save to Journals/

## Database API (`app/database.py`)

Fully implemented SQLite layer with thread-safe connections for Streamlit.

```python
from app.database import init_db, get_pending_notes, mark_note_approved

# Initialize on startup
init_db()

# Key functions:
# Notes: insert_note, upsert_note, get_note_by_id, get_pending_notes, get_review_queue
# Status: mark_note_processing, mark_note_for_review, mark_note_approved, mark_note_error
# Extractions: insert_extraction, get_extractions_for_note, get_aggregated_text
# Settings: get_setting, set_setting
# Activity: log_activity, get_recent_activity
# Utilities: determine_source_folder, determine_output_folder
```

**Tables:** `notes`, `extractions`, `settings`, `activity_log`, `schema_version`

## Key Patterns

- **OCR Strategy:** All notes go through vision OCR (supernote-tool text extraction is unreliable). Auto-approve if ≥200 characters.
- **Output Routing:** Path-based routing to Journals folders:
  - `/WORK/` → `Journals/Work/`
  - `/Daily Journal/` → `Journals/Daily/`
  - Other → `Journals/Other/`
- **Line Break Processing:** Join lines not ending with `.!?:;`, preserve paragraphs and list items, keep short capitalized lines as headers.
- **Dual Mode:** Web UI via Streamlit, headless CLI via `python -m app --process` for cron scheduling.

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` - OpenAI API key for fallback OCR

Set via docker-compose or shell:
- `SOURCE_PATH` - Path to Supernote sync directory
- `OUTPUT_PATH` - Path to Obsidian Journals output
- `OLLAMA_URL` - Ollama server URL (default: http://192.168.1.138:11434)
- `OLLAMA_MODEL` - Ollama model (default: qwen3-vl:8b)