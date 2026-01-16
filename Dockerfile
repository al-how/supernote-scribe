# Placeholder for Dockerfile content
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

# Default command to run Streamlit
CMD ["streamlit", "run", "app/app.py"]
