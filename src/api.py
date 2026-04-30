"""FastAPI endpoint exposing the campaign generator.

POST /generate-campaign     # runs the full graph
GET  /healthz               # liveness
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.graph import DEFAULT_DATA_DIR, run_campaign
from src.schemas import Campaign

app = FastAPI(
    title="Klaviyo Marketing Agent Demo",
    description=(
        "Multi-agent campaign generator. Runs Segmenter → Strategist → "
        "Content Writer → A/B Generator → Reviewer over a fake e-commerce "
        "dataset and returns a structured campaign JSON."
    ),
    version="0.1.0",
)


class GenerateRequest(BaseModel):
    data_dir: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate-campaign", response_model=Campaign)
def generate_campaign(req: GenerateRequest | None = None) -> Campaign:
    data_dir = Path(req.data_dir) if req and req.data_dir else DEFAULT_DATA_DIR
    if not data_dir.exists():
        raise HTTPException(404, f"data_dir not found: {data_dir}")
    if not (data_dir / "customers.csv").exists():
        raise HTTPException(
            400,
            f"data_dir missing CSVs. Run `python -m data.seed` first. ({data_dir})",
        )
    return run_campaign(data_dir)
