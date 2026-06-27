#!/bin/bash
set -e

uvicorn app.worker:app --host 0.0.0.0 --port 8000 &
worker_pid=$!

streamlit run app/Home.py --server.address 0.0.0.0 &
streamlit_pid=$!

cleanup() {
    kill "$worker_pid" "$streamlit_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait -n "$worker_pid" "$streamlit_pid"
exit_code=$?
cleanup
wait "$worker_pid" "$streamlit_pid" 2>/dev/null || true
exit "$exit_code"
