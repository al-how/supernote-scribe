# Plan: Docker CI/CD Pipeline Setup

## Goal
Automate the build and publication of Docker images to GitHub Container Registry (GHCR) to eliminate manual file copying for deployment.

## Steps

1.  **Create GitHub Actions Workflow**
    *   File: `.github/workflows/docker-publish.yml`
    *   Triggers:
        *   Push to `main` branch (tags as `edge` or `latest`).
        *   New Release published (tags with version number and `latest`).
    *   Actions:
        *   Checkout code.
        *   Set up Docker Buildx.
        *   Login to GHCR using `GITHUB_TOKEN`.
        *   Extract metadata (tags, labels).
        *   Build and push the Docker image.

2.  **Create Production Docker Compose File**
    *   File: `docker-compose.prod.yml`
    *   Purpose: For use on the deployment server (e.g., Unraid/NAS).
    *   Changes:
        *   Remove `build` section.
        *   Add `image: ghcr.io/<username>/supernote-converter:latest`.
        *   Keep volume mounts and environment variables consistent.

3.  **Documentation**
    *   Update `docs/DEPLOYMENT.md` (or create if missing, checking file list... it exists) with instructions on:
        *   How to enable the workflow (permissions in GitHub).
        *   How to update the container using the new `docker-compose.prod.yml`.

## Deployment Workflow (Future State)
1.  User pushes code to GitHub.
2.  User creates a Release on GitHub.
3.  GitHub Action builds image -> Pushes to `ghcr.io`.
4.  User on Server runs: `docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d`

## Required User Actions (to be communicated)
*   Ensure GitHub repository "Actions" permissions allow read/write packages.
*   Update the `image` name in the compose file to match their GitHub username/repo.
