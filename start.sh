#!/usr/bin/env sh
# Container entrypoint: run the FastAPI on :8000 (internal) and Streamlit on
# the public PORT. Streamlit is the foreground process; if it exits, the
# container exits and the platform restarts it.
#
# PORT is set by Render; falls back to 8080 for Fly / local Docker.

set -e

PUBLIC_PORT="${PORT:-8080}"

uvicorn src.api:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

trap "kill $UVICORN_PID 2>/dev/null || true" EXIT INT TERM

exec streamlit run streamlit_app.py \
    --server.port "$PUBLIC_PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
