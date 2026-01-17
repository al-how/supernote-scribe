# Supernote Converter Application

Replace the brittle n8n workflow with a Python Streamlit app running as a Docker container on Unraid.

## Overview

A Streamlit web application that:
1. Scans for `.note` files in your Supernote sync directory
2. Exports all pages to PNG using `supernote-tool`
3. Runs **all** PNGs through Ollama vision OCR (qwen3-vl:8b) - no text extraction fallback
4. Provides a review UI to verify/edit extracted text before saving
5. Outputs markdown files to your Obsidian vault

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| UI Framework | Streamlit | Pure Python, built-in image/text widgets, no frontend code |
| Database | SQLite | Simple, no external deps |
| PNG Export | supernotelib (pip) | Convert .note → PNG pages |
| Vision OCR | Ollama (qwen3-vl:8b) | Local, already running on Unraid |
| Backup OCR | OpenAI gpt-4o | Cloud option for comparison/fallback |

## Key Decisions

- **Always Vision OCR**: All notes go through Ollama vision - supernote-tool text extraction is unreliable
- **Auto-approve**: High-confidence extractions auto-approve. User can still review/edit from history.
- **Scheduling**: Unraid cron job triggers HTTP endpoint + manual trigger via UI
- **Development**: Build at `Projects/supernote-converter/`, deploy to Unraid
- **Documentation**: Plan and docs saved to `Projects/supernote-converter/docs/`

## Key Features

### 1. Dashboard
- Status cards: Pending / In Review / Processed counts
- Quick actions: Scan, Process, Review Queue
- Recent activity log
- Next scheduled scan time

### 2. Scan & Process Page
- Cutoff date picker (filter which notes to process)
- Source folder checkboxes (WORK, Daily Journal, Other)
- File list with status indicators
- Progress bar during batch processing

### 3. Review Interface
- Side-by-side: PNG preview | Extracted text
- Page navigation for multi-page notes
- Editable text area
- Re-extract with different AI option
- Approve/Reject buttons
- Output path preview

### 4. History Page
- All processed notes with search/filter
- Click any note to view/edit (even auto-approved ones)
- Re-process option if needed

### 5. Settings Page
- AI endpoint selector (Ollama primary, OpenAI fallback)
- Ollama URL and model selector
- OpenAI API key input
- Quality threshold (chars before vision fallback)
- Auto-approve threshold (default: 200 chars)
- Schedule configuration (cron expression, enable/disable)
- Source/output path configuration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                          │
├─────────────────────────────────────────────────────────────┤
│  Streamlit App (app.py)                                      │
│  ├── Pages:                                                  │
│  │   ├── Dashboard (status, quick actions)                  │
│  │   ├── Scan (discover & process notes)                    │
│  │   ├── Review (PNG + text side-by-side)                   │
│  │   ├── History (all processed notes)                      │
│  │   └── Settings (AI endpoints, paths, schedule)           │
│  └── Services:                                               │
│      ├── Scanner (discover .note files)                     │
│      ├── Exporter (supernotelib → PNG)                      │
│      ├── OCR (Ollama HTTP / OpenAI HTTP)                    │
│      └── Markdown Builder (frontmatter + line processing)   │
├─────────────────────────────────────────────────────────────┤
│  Volumes:                                                    │
│  ├── /data/source (read-only) → Supernote sync dir          │
│  ├── /data/output (read-write) → Journals/ directories      │
│  └── /app/data → SQLite DB + PNG cache                      │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│  Ollama Server  │          │  OpenAI API     │
│  192.168.1.138  │          │  (backup)       │
│  :11434         │          │                 │
│  qwen3-vl:8b    │          │                 │
└─────────────────┘          └─────────────────┘
```

## Data Flow

1. **Scan**: Find `.note` files → filter by cutoff date → insert into `notes` table
2. **Process**: For each pending note:
   - Export all pages to PNG via supernotelib
   - Send each PNG to Ollama vision OCR
   - Aggregate text from all pages
   - Store extraction in `extractions` table
   - If confident (>200 chars) → auto-approve and save
   - Otherwise → set status to `review`
3. **Review**: User views PNG + text side-by-side → edits if needed → approves
4. **Output**: Build markdown with frontmatter → write to appropriate Journals/ folder → mark as `approved`

## Project Structure

Development location: `C:\Users\alexn\Documents\Projects\supernote-converter\`

```
supernote-converter/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── docs/
│   └── plan.md              # This plan document
├── app/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point (--process flag)
│   ├── Home.py              # Streamlit main entry point (dashboard)
│   ├── config.py            # Settings (Pydantic)
│   ├── settings_manager.py  # Bridge between config and database
│   ├── database.py          # SQLite + migrations
│   ├── pages/
│   │   ├── 1_Scan.py        # Scan & process page
│   │   ├── 2_Review.py      # Review queue page
│   │   ├── 3_History.py     # Processed notes history
│   │   └── 4_Settings.py    # Configuration page
│   └── services/
│       ├── scanner.py          # File discovery
│       ├── exporter.py         # supernotelib PNG export
│       ├── ocr.py              # Ollama + OpenAI vision
│       ├── processor.py        # Main processing pipeline
│       ├── markdown.py         # Output builder
│       └── connection_tester.py # Connection validation utilities
└── data/                    # Volume mount point (local dev + prod)
    ├── supernote.db         # SQLite database
    └── png_cache/           # Cached PNG exports
```

## Docker Compose (for Unraid)

```yaml
version: '3.8'
services:
  supernote-converter:
    build: .
    container_name: supernote-converter
    restart: unless-stopped
    ports:
      - "8085:8501"  # Streamlit default port
    volumes:
      # Source .note files (read-only)
      - /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes:/data/source:ro
      # Output directory
      - /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals:/data/output
      # App data (database, PNG cache)
      - /mnt/cache/appdata/supernote-converter:/app/data
    environment:
      - TZ=America/Chicago
      - SOURCE_PATH=/data/source/alexhoward03@gmail.com/Supernote/Note
      - OUTPUT_PATH=/data/output
      - OLLAMA_URL=http://192.168.1.138:11434
      - OLLAMA_MODEL=qwen3-vl:8b
    env_file:
      - .env  # OPENAI_API_KEY
```

## Key Implementation Details

### supernotelib PNG Export
```python
from supernotelib import converter, parser

def export_png(note_path: Path, output_dir: Path) -> list[Path]:
    """Export all pages of a .note file to PNG images."""
    notebook = parser.load_notebook(str(note_path))
    png_paths = []
    for i, page in enumerate(notebook.pages):
        png_path = output_dir / f"{note_path.stem}_{i}.png"
        converter.convert_to_png(page, str(png_path))
        png_paths.append(png_path)
    return png_paths
```

### Ollama Vision OCR
```python
import httpx
import base64

def ocr_with_ollama(image_path: Path, ollama_url: str, model: str) -> str:
    """Extract text from PNG using Ollama vision model."""
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    resp = httpx.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model,
            "prompt": "Extract all handwritten text from this image. "
                     "Output only the text, maintaining paragraph structure.",
            "images": [image_b64],
            "stream": False
        },
        timeout=120
    )
    return resp.json()["response"]
```

### Line Break Processing (port from n8n)
- Join lines not ending with `.!?:;`
- Preserve empty lines (paragraphs)
- Preserve list items (`-`, `*`, `•`, numbered)
- Keep short capitalized lines (headers)

### Output Routing
- `/WORK/` in path → `Journals/Work/`
- `/Daily Journal/` in path → `Journals/Daily/`
- Other → `Journals/Other/`

## Implementation Steps

1. **COMPLETE: Setup project structure** - Create directories, requirements.txt, Dockerfile
2. **COMPLETE: Database layer** - SQLite schema, connection helpers, migrations
3. **COMPLETE: Config & settings** - Pydantic settings model, .env handling, Settings UI page
4. **COMPLETE: Scanner service** - File discovery, date parsing, deduplication
5. **COMPLETE: Exporter service** - supernotelib PNG export
6. **COMPLETE: OCR service** - Ollama vision, OpenAI vision backup
7. **COMPLETE: Processor service** - Pipeline orchestration, auto-approve logic
8. **COMPLETE: Markdown service** - Frontmatter builder, line processing
9. **Streamlit pages** - Dashboard (app.py), Scan, Review, History, Settings
10. **Docker config** - Dockerfile, docker-compose.yml
11. **Local testing** - Run locally with sample .note files
12. **Deploy to Unraid** - Copy to Unraid, configure paths, verify

## Testing Milestones

You don't need to wait until the end to test! Here's when you can start validating functionality:

### Step 5: Exporter Service (First Hands-On Test)
**What you can test:** Convert a real `.note` file to PNG and visually verify output

```python
from app.services.exporter import export_note_to_png
from pathlib import Path

pngs = export_note_to_png(Path("path/to/your_test.note"))
# Opens PNG files to visually verify conversion worked
```

This is your first "does this actually work with my real Supernote files" checkpoint.

### Step 6: OCR Service
**What you can test:** Send PNG to Ollama and see extracted text - validates your Ollama setup works

```python
from app.services.ocr import ocr_with_ollama
from pathlib import Path

text = ocr_with_ollama(Path("test.png"), "http://192.168.1.138:11434", "qwen3-vl:8b")
print(text)  # See what Ollama extracted
```

### Step 7: Processor Service (First Full Pipeline)
**What you can test:** Run full pipeline without UI - `.note` → PNG → OCR text → database

```bash
python -m app --process --cutoff 2026-01-01
```

This exercises scan → export → OCR → database storage headlessly.

### Step 8: Markdown Service
**What you can test:** End-to-end verification - `.note` file becomes markdown in correct Journals folder with proper frontmatter and formatting.

### Step 9: Streamlit Pages (Full Interactive Testing)
**What you can test:** Complete web UI workflow - scan, process, review, approve, search history.

**Recommendation:** Have a sample `.note` file ready for testing after Step 5 (only 2 steps away from current progress).

## Requirements

```
streamlit>=1.32.0
httpx>=0.26.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
supernotelib>=0.5.0
Pillow>=10.0.0
```

## Verification Plan

1. **Local testing**:
   - Scan detects new notes correctly
   - PNG export works for multi-page notes
   - Ollama OCR returns readable text
   - Review UI displays PNG and text side-by-side
   - Edit functionality works
   - Approved notes save to correct Journals/ folder
   - Settings persist across restarts
2. **Integration test** - Full workflow: scan → process → review → save

## Scheduling (Unraid Cron)

The app supports a **headless CLI mode** for cron triggers (no API server needed):

```bash
# Run at 3am daily - execute inside the container
0 3 * * * docker exec supernote-converter python -m app --process
```

**CLI modes:**
- `streamlit run app/app.py` - Web UI (default Docker CMD)
- `python -m app --process` - Headless: scan and process all new notes
- `python -m app --process --cutoff 2026-01-01` - Process with specific cutoff date

## Migration from n8n

- Import existing `supernote_history.json` to mark already-processed files
- Set cutoff date to skip historical notes
- Disable n8n workflow after Streamlit app is verified working

## Advantages Over n8n

| Aspect | n8n | Streamlit App |
|--------|-----|---------------|
| Review capability | None | Full UI with edit |
| OCR quality | supernote-tool (poor) | Ollama vision (good) |
| Error visibility | Node logs | Clear error messages |
| State management | JSON file | SQLite database |
| AI flexibility | Hardcoded | Configurable in UI |
| Progress tracking | Limited | Real-time progress |
| Code maintainability | Visual nodes | Pure Python |
