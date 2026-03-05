#!/bin/bash
# Start webhook server in background
uvicorn app.webhook:app --host 0.0.0.0 --port 8000 &
# Start Streamlit in foreground (keeps container alive)
streamlit run app/Home.py --server.address 0.0.0.0
