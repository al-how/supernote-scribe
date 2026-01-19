FROM python:3.11-slim

# Install system dependencies for Pillow, PyCairo, and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    python3-dev \
    libcairo2-dev \
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
CMD ["streamlit", "run", "app/Home.py", "--server.address", "0.0.0.0"]