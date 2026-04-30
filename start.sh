#!/usr/bin/env sh
# Container entrypoint: run the FastAPI on :8000 (internal) and Streamlit on
# :8080 (the public Fly port). Streamlit is the foreground process; if it
# exits, the container exits and Fly restarts it.

set -e

uvicorn src.api:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Make sure uvicorn is killed if streamlit exits or the container is stopped.
trap "kill $UVICORN_PID 2>/dev/null || true" EXIT INT TERM

exec streamlit run streamlit_app.py \
    --server.port 8080 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
