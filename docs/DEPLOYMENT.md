# Deployment Guide

This guide covers how to deploy the Supernote Converter application to an Unraid server or any Docker-compatible environment.

## Prerequisites

1.  **Unraid Server** (or other Docker host)
    *   Docker service enabled
    *   Access to the filesystem (via SMB or SSH)
2.  **Files to Transfer**
    *   `Dockerfile`
    *   `docker-compose.yml`
    *   `requirements.txt`
    *   `app/` (directory)
    *   `.env.example`

## 1. Preparation

1.  **Create Directory on Unraid**
    Create a directory for the application, e.g., `/mnt/user/appdata/supernote-converter/`.

2.  **Transfer Files**
    Copy the files listed above to the new directory on your Unraid server.

    **Example via SCP:**
    ```bash
    scp -r app/ Dockerfile docker-compose.yml requirements.txt .env.example root@YOUR_UNRAID_IP:/mnt/user/appdata/supernote-converter/
    ```

## 2. Configuration

1.  **Create .env File**
    On the server, make a copy of `.env.example` named `.env`.
    ```bash
    cp .env.example .env
    ```

2.  **Edit .env**
    Update the values in `.env` to match your Unraid paths.

    ```bash
    # Example Unraid Configuration
    HOST_SOURCE_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/supernote-notes
    HOST_OUTPUT_PATH=/mnt/cache/appdata/obsidian_vault_copy/Personal_Vault/03-Resources/Journals
    HOST_DATA_PATH=/mnt/cache/appdata/supernote-converter
    
    OLLAMA_URL=http://192.168.1.138:11434  # Use your Unraid IP
    OLLAMA_MODEL=qwen3-vl:8b
    ```

## 3. Deployment

1.  **Build the Image**
    Navigate to the directory and build the Docker image.
    ```bash
    cd /mnt/user/appdata/supernote-converter
    docker-compose build
    ```

2.  **Start the Container**
    ```bash
    docker-compose up -d
    ```

3.  **Check Logs**
    ```bash
    docker-compose logs -f
    ```

## 4. Verification

1.  Access the web UI at `http://YOUR_UNRAID_IP:8086`.
2.  Go to **Settings** and verify the configuration.
3.  Try scanning for notes.

## 5. Automation (Cron Job)

To run the processing automatically every night (e.g., at 3 AM), set up a cron job on the Unraid host.

**Recommended: Use "User Scripts" Plugin**

Create a new script:
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
Set the schedule to "Custom" or "Daily".

**Alternative: Manual Cron**
Add to `/etc/cron.d/supernote`:
```
0 3 * * * root docker ps | grep -q supernote-converter && docker exec supernote-converter python -m app --process >> /var/log/supernote-converter.log 2>&1
```

## Troubleshooting

*   **Permission Errors:**
    The container runs as root to maximize compatibility with Unraid shares. If you see permission denied errors, check the ownership of your mapped directories on the host.
    ```bash
    chmod -R 777 /mnt/user/appdata/supernote-converter/data
    ```

*   **Ollama Connection Refused:**
    Ensure you are using the correct IP address for `OLLAMA_URL`. `localhost` inside the container refers to the container itself, not the Unraid host. Use the Unraid LAN IP.
