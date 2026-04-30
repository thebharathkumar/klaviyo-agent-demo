FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

# Generate fixture data at build time so the container is runnable out of the box.
RUN python -m data.seed

# Streamlit (public) on 8080, FastAPI (internal) on 8000.
EXPOSE 8080
EXPOSE 8000

RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
