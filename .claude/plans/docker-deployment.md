# Docker Configuration and Unraid Deployment Plan

**Goal:** Containerize the Supernote Converter application and deploy it to Unraid server for production use.

## Current State

- Application code complete (Steps 1-9 from main plan)
- All services implemented: scanner, exporter, OCR, processor, markdown
- Streamlit UI fully functional: Dashboard, Scan, Review, History, Settings
- Local development tested with Python runtime

## Scope

This plan covers:
1. Docker containerization (Step 10)
2. Local Docker testing (Step 11)
3. Unraid deployment (Step 12)

## Key Architectural Decisions

Based on Unraid deployment best practices, this plan implements:

1. **Unified Docker Compose** - Single `docker-compose.yml` for both local and Unraid deployments using environment variables
2. **Environment-Driven Configuration** - All paths and URLs configurable via `.env` file (no hardcoded values)
3. **Simplified Permissions** - Run as root inside container to avoid UID/GID mismatch with Unraid's `nobody:users` filesystem
4. **Explicit System Dependencies** - Install `libjpeg-dev`, `zlib1g-dev` for Pillow, `curl` for healthcheck
5. **Container Healthcheck** - Streamlit health endpoint monitoring for production reliability
6. **Flexible Networking** - Support for both LAN IP and Docker network container names for Ollama connectivity
7. **Robust Cron Jobs** - Container status check before execution to prevent errors when container is stopped

## Step 1: Create Dockerfile

**File:** `Dockerfile`

**Requirements:**
- Base image: Python 3.11 (official slim variant)
- Install system dependencies for Pillow/supernotelib
- Copy application code
- Install Python dependencies from requirements.txt
- Expose Streamlit port (8501)
- Set working directory
- Add healthcheck for container monitoring
- Ensure data directory exists for volume mount
- Default CMD to run Streamlit web UI

**Permissions approach for Unraid:**
- Run as root inside container for simplicity (avoids UID/GID mismatch issues with Unraid's `nobody:users` filesystem)
- Alternative: Implement PUID/PGID support via entrypoint script (linuxserver.io pattern) if needed later

**System dependencies:**
- `libjpeg-dev`, `zlib1g-dev` - Required by Pillow for image processing
- `curl` - Required for healthcheck
- Note: If using opencv-python, switch to `opencv-python-headless` or install `libgl1`

**Sample structure:**
```dockerfile
FROM python:3.11-slim

# Install system dependencies for Pillow and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for volume mount
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Healthcheck to verify Streamlit is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run as root (Unraid compatibility - avoids UID/GID permission issues)
# For production security, consider implementing PUID/PGID via entrypoint script

CMD ["streamlit", "run", "app/Home.py", "--server.address", "0.0.0.0"]
```

## Step 2: Create docker-compose.yml

**File:** `docker-compose.yml`

**Strategy:** Use environment variables for all paths and URLs to support both local and Unraid deployments from a single compose file.

**Requirements:**
- Service name: `supernote-converter`
- Port mapping: `8085:8501` (host:container)
- Volume mounts using environment variables:
  - Source (read-only): `${HOST_SOURCE_PATH}:/data/source:ro`
  - Output (read-write): `${HOST_OUTPUT_PATH}:/data/output`
  - App data (read-write): `${HOST_DATA_PATH}:/app/data`
- Environment variables passed from `.env` file:
  - `TZ` - Timezone
  - `SOURCE_PATH` - Container path to notes (typically `/data/source/alexhoward03@gmail.com/Supernote/Note`)
  - `OUTPUT_PATH` - Container path to output (typically `/data/output`)
  - `OLLAMA_URL` - Ollama server URL (varies by environment)
  - `OLLAMA_MODEL` - Ollama model name
  - `OPENAI_API_KEY` - OpenAI API key
- Restart policy: `unless-stopped`

**Path mapping differences:**

| Environment | Host Source Path | Host Output Path | Host Data Path | Ollama URL |
|-------------|------------------|------------------|----------------|------------|
| **Local (Windows)** | `C:\Path\to\supernote-notes` | `C:\Path\to\Journals` | `.\data` | `http://host.docker.internal:11434` or `http://192.168.1.138:11434` |
| **Unraid** | `/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes` | `/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals` | `/mnt/cache/appdata/supernote-converter` | `http://192.168.1.138:11434` or `http://ollama:11434` (if same Docker network) |

**Sample docker-compose.yml:**
```yaml
version: '3.8'

services:
  supernote-converter:
    build: .
    container_name: supernote-converter
    restart: unless-stopped
    ports:
      - "8085:8501"
    volumes:
      # Volume paths configured via .env file
      - ${HOST_SOURCE_PATH}:/data/source:ro
      - ${HOST_OUTPUT_PATH}:/data/output
      - ${HOST_DATA_PATH}:/app/data
    environment:
      # All configuration via .env file
      - TZ=${TZ:-America/Chicago}
      - SOURCE_PATH=${SOURCE_PATH}
      - OUTPUT_PATH=${OUTPUT_PATH}
      - OLLAMA_URL=${OLLAMA_URL}
      - OLLAMA_MODEL=${OLLAMA_MODEL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

## Step 3: Create .env.example

**File:** `.env.example`

**Purpose:** Document required environment variables with examples for both local and Unraid deployments

**Contents:**
```bash
# ==================================================
# Supernote Converter Environment Configuration
# ==================================================
# Copy this file to .env and configure for your environment

# OpenAI API Key (Required)
# Used for fallback OCR when Ollama is unavailable
OPENAI_API_KEY=your-api-key-here

# Timezone
TZ=America/Chicago

# ------------------------------
# Local Development (Windows)
# ------------------------------
# Uncomment and configure these for local testing:

# HOST_SOURCE_PATH=C:\Users\YourName\Documents\supernote-notes
# HOST_OUTPUT_PATH=C:\Users\YourName\Documents\Journals
# HOST_DATA_PATH=.\data
# OLLAMA_URL=http://host.docker.internal:11434
# SOURCE_PATH=/data/source/alexhoward03@gmail.com/Supernote/Note
# OUTPUT_PATH=/data/output
# OLLAMA_MODEL=qwen3-vl:8b

# ------------------------------
# Unraid Production
# ------------------------------
# Uncomment and configure these for Unraid deployment:

# HOST_SOURCE_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes
# HOST_OUTPUT_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals
# HOST_DATA_PATH=/mnt/cache/appdata/supernote-converter
# OLLAMA_URL=http://192.168.1.138:11434
# SOURCE_PATH=/data/source/alexhoward03@gmail.com/Supernote/Note
# OUTPUT_PATH=/data/output
# OLLAMA_MODEL=qwen3-vl:8b

# ------------------------------
# Notes
# ------------------------------
# HOST_*_PATH variables: Host machine paths mounted into container
# SOURCE_PATH/OUTPUT_PATH: Paths INSIDE the container (usually don't change)
# OLLAMA_URL:
#   - Local: Use host.docker.internal:11434 to access host-installed Ollama
#   - Unraid: Use LAN IP or container name if on same Docker network
```

## Step 4: Update .gitignore

**File:** `.gitignore`

**Add:**
```
.env
data/
*.db
png_cache/
__pycache__/
*.pyc
.streamlit/
```

## Step 5: Create .dockerignore

**File:** `.dockerignore`

**Purpose:** Exclude unnecessary files from Docker build context

**Contents:**
```
.git
.gitignore
.env
.env.example
data/
docs/
*.md
*.pyc
__pycache__/
.vscode/
.idea/
```

## Step 6: Local Docker Testing

**Prerequisites:**
- Docker Desktop installed and running on Windows
- Sample `.note` files available for testing
- `.env` file created with valid OPENAI_API_KEY and local paths configured

**Important - Local Ollama Networking:**
If testing with Ollama installed on the Windows host:
- Use `OLLAMA_URL=http://host.docker.internal:11434` in your `.env` file
- `host.docker.internal` is Docker Desktop's special DNS name that resolves to the host machine
- Alternatively, use your LAN IP (e.g., `http://192.168.1.X:11434`) if `host.docker.internal` doesn't work
- Verify Ollama is accessible: From PowerShell, run `curl http://localhost:11434/api/tags`

**Test plan:**

### 6.1: Build the image
```bash
cd C:\Users\alexn\Documents\Projects\supernote-converter
docker-compose build
```

**Verify:** Build completes without errors

### 6.2: Start the container
```bash
docker-compose up -d
```

**Verify:**
- Container starts successfully
- Web UI accessible at http://localhost:8085
- No immediate errors in logs: `docker-compose logs -f`

### 6.3: Test database initialization
**Action:** Visit http://localhost:8085 in browser

**Verify:**
- Dashboard loads
- Settings page accessible
- Database created at `data/supernote.db`
- No errors in Streamlit UI

### 6.4: Test Settings configuration
**Action:** Navigate to Settings page

**Verify:**
- Can update Ollama URL and model
- Can set source/output paths
- Settings persist after page reload
- Can test connection to Ollama (if accessible from dev machine)

### 6.5: Test scan functionality
**Action:**
- Configure source path to local test directory with `.note` files
- Navigate to Scan page
- Click "Scan for New Notes"

**Verify:**
- Scanner discovers `.note` files
- Files appear in scan results
- Database updates with discovered notes

### 6.6: Test processing pipeline (if Ollama accessible)
**Action:** Process a test note

**Verify:**
- PNG export works (check `data/png_cache/`)
- OCR extraction completes
- Note status updates to "review" or "approved"
- Review page shows extracted text if in review queue

### 6.7: Test headless CLI mode
```bash
docker exec supernote-converter python -m app --process --cutoff 2026-01-01
```

**Verify:**
- CLI mode runs without UI
- Processing completes successfully
- Database updates accordingly
- Logs show progress

### 6.8: Test volume persistence
**Action:**
- Stop container: `docker-compose down`
- Restart: `docker-compose up -d`

**Verify:**
- Database persists (previously scanned notes still visible)
- Settings persist
- PNG cache intact

## Step 7: Prepare for Unraid Deployment

### 7.1: Create deployment package
**Files to transfer:**
- `Dockerfile`
- `docker-compose.yml` (single unified file - no separate Unraid version needed)
- `requirements.txt`
- `app/` directory (entire folder)
- `.env.example` (will create `.env` on Unraid with actual values)

**Method:**
- Option A: Git clone on Unraid (if Git available)
- Option B: Create tar/zip and transfer via Unraid web UI or SCP

### 7.2: Document deployment steps
Create `DEPLOYMENT.md` with:
- Prerequisites (Unraid requirements)
- File transfer instructions
- Build and start commands
- Verification steps
- Troubleshooting common issues

## Step 8: Unraid Deployment

### 8.1: Transfer files to Unraid
**Location:** `/mnt/user/appdata/supernote-converter/`

**Methods:**
- SSH/SCP: `scp -r supernote-converter/ root@unraid-ip:/mnt/user/appdata/`
- Unraid web UI file manager
- SMB share mount

**Verify:** All files transferred successfully

### 8.2: Create .env file on Unraid
**Location:** `/mnt/user/appdata/supernote-converter/.env`

**Action:** Copy from `.env.example` and configure with Unraid-specific values

**Contents:**
```bash
# OpenAI API Key
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Timezone
TZ=America/Chicago

# Host volume mount paths (Unraid filesystem)
HOST_SOURCE_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes
HOST_OUTPUT_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals
HOST_DATA_PATH=/mnt/cache/appdata/supernote-converter

# Container paths (usually don't change)
SOURCE_PATH=/data/source/alexhoward03@gmail.com/Supernote/Note
OUTPUT_PATH=/data/output

# Ollama configuration
OLLAMA_URL=http://192.168.1.138:11434
OLLAMA_MODEL=qwen3-vl:8b
```

**Note:** If Ollama runs in another Docker container on the same Unraid server, consider using the container name (e.g., `http://ollama:11434`) instead of the IP address.

### 8.3: Verify volume mount paths exist and permissions
```bash
# On Unraid via SSH

# Check source directory exists
ls -la /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes

# Check output directory exists and is writable
ls -la /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals

# Create app data directory and ensure it's writable
mkdir -p /mnt/cache/appdata/supernote-converter
chmod 777 /mnt/cache/appdata/supernote-converter  # Permissive for initial testing

# Verify output directory is writable (test write)
touch /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals/test.txt && rm /mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals/test.txt
echo "Write test successful"
```

**Critical:** Since the container runs as root (per Dockerfile), permission issues are less likely. However, if you encounter "Permission Denied" errors:
- Verify directory ownership: `ls -la /mnt/cache/appdata/`
- Temporarily set permissive permissions: `chmod -R 777 /mnt/cache/appdata/supernote-converter`
- Check Unraid share settings (User Shares → supernote-converter → Export: Yes)

### 8.4: Build image on Unraid
```bash
cd /mnt/user/appdata/supernote-converter
docker-compose build
```

**Verify:** Image builds successfully on Unraid architecture

### 8.5: Start container
```bash
docker-compose up -d
```

**Verify:**
- Container starts: `docker ps | grep supernote-converter`
- Logs look healthy: `docker-compose logs -f`

### 8.6: Test web UI access
**Action:** Visit `http://<unraid-ip>:8085`

**Verify:**
- Dashboard loads
- No permission errors accessing mounted volumes
- Settings page accessible

### 8.7: Configure production settings
**Via Settings page:**
- Set `SOURCE_PATH` to `/data/source/alexhoward03@gmail.com/Supernote/Note`
- Set `OUTPUT_PATH` to `/data/output`
- Verify Ollama URL: `http://192.168.1.138:11434`
- Verify Ollama model: `qwen3-vl:8b`
- Test Ollama connection

**Verify:** All connections successful

### 8.8: Process a real note end-to-end
**Action:**
1. Scan for notes (should find real Supernote files)
2. Process a recent note
3. Review if needed
4. Approve and save

**Verify:**
- PNG export works with real Supernote files
- Ollama OCR extracts readable text
- Markdown saves to correct Journals folder
- Obsidian can read the generated markdown

### 8.9: Set up automated processing (cron)
**Option A: Unraid User Scripts plugin (Recommended)**
- Install User Scripts plugin from Community Applications
- Create new script named "Supernote Converter - Daily Process"
- Script content:
```bash
#!/bin/bash
# Check if container is running before executing
if docker ps | grep -q supernote-converter; then
    docker exec supernote-converter python -m app --process
else
    echo "Container supernote-converter is not running. Skipping."
    exit 1
fi
```
- Schedule: Daily at 3:00 AM
- Enable logging to view execution history

**Option B: Add cron job to Unraid directly**
```bash
# Edit Unraid cron: vi /etc/cron.d/supernote
# Add this line:
0 3 * * * root docker ps | grep -q supernote-converter && docker exec supernote-converter python -m app --process >> /var/log/supernote-converter.log 2>&1 || echo "Container not running" >> /var/log/supernote-converter.log
```

**Verify:**
- Manual trigger works: `docker exec supernote-converter python -m app --process`
- Logs show successful processing
- Container status check prevents errors if container is stopped
- Wait for scheduled run and verify execution via logs

### 8.10: Migration from n8n
**Steps:**
1. Export n8n workflow history (if available)
2. Import processed file list to avoid reprocessing
3. Set cutoff date in Settings to skip historical notes
4. Run initial scan to verify only new notes are detected
5. Disable/delete n8n workflow once Streamlit app verified working

**Verify:**
- No duplicate processing of old notes
- New notes since cutoff date are processed correctly

## Step 9: Post-Deployment Verification

### Checklist:
- [ ] Web UI accessible from network
- [ ] Can scan and discover new `.note` files
- [ ] PNG export works for multi-page notes
- [ ] Ollama OCR returns readable text
- [ ] Review UI displays PNG and text side-by-side
- [ ] Edit functionality works in review page
- [ ] Approved notes save to correct Journals/ folder
- [ ] Settings persist across container restarts
- [ ] Headless CLI mode works via cron
- [ ] Activity log shows processing history
- [ ] History page allows viewing/re-editing old notes

### Performance verification:
- [ ] Processing speed acceptable for typical daily volume
- [ ] Ollama server handles concurrent requests
- [ ] No memory leaks over 24h operation
- [ ] Database size manageable (monitor `supernote.db` growth)

### Error handling verification:
- [ ] Graceful handling of missing Ollama connection
- [ ] OpenAI fallback works when configured
- [ ] File permission errors display clearly
- [ ] Invalid `.note` files don't crash pipeline

## Rollback Plan

If issues occur on Unraid:

1. Stop container: `docker-compose down`
2. Check logs: `docker-compose logs`
3. Verify volume permissions: `ls -la /mnt/cache/appdata/`
4. Test Ollama connection from Unraid: `curl http://192.168.1.138:11434/api/tags`
5. Rebuild if needed: `docker-compose build --no-cache`
6. Re-enable n8n workflow temporarily if critical processing needed

## Success Criteria

Deployment considered successful when:
1. ✅ Container runs stable for 7 days without restarts
2. ✅ Processes at least 10 real notes successfully
3. ✅ Cron job executes daily without manual intervention
4. ✅ Generated markdown files readable in Obsidian
5. ✅ OCR quality meets or exceeds n8n workflow quality
6. ✅ No data loss or corruption
7. ✅ User can review/edit notes via web UI
8. ✅ Settings changes persist correctly

## Future Enhancements (Post-Deployment)

Not in scope for initial deployment, but consider:
- [ ] Prometheus metrics endpoint for monitoring
- [ ] Email notifications for processing errors
- [ ] Bulk re-processing interface
- [ ] OCR quality comparison (Ollama vs OpenAI side-by-side)
- [ ] Custom OCR prompts per source folder
- [ ] Integration with Obsidian Daily Notes plugin
- [ ] Mobile-responsive UI for phone access
