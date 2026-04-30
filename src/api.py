"""FastAPI endpoint exposing the campaign generator.

POST /generate-campaign     # runs the full graph (or returns fixture if DEMO_MODE=1)
GET  /healthz               # liveness

DEMO_MODE: when set to a truthy value, /generate-campaign returns the committed
sample at examples/output_campaign.json instead of calling Claude. Useful for
public demo links where you don't want to ship an API key or pay per click.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.graph import DEFAULT_DATA_DIR, run_campaign
from src.schemas import Campaign

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = REPO_ROOT / "examples" / "output_campaign.json"


def _demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes", "on"}


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
def healthz() -> dict[str, object]:
    return {"status": "ok", "demo_mode": _demo_mode_enabled()}


@app.post("/generate-campaign", response_model=Campaign)
def generate_campaign(req: GenerateRequest | None = None) -> Campaign:
    if _demo_mode_enabled():
        if not SAMPLE_PATH.exists():
            raise HTTPException(500, f"DEMO_MODE set but {SAMPLE_PATH} not found.")
        return Campaign.model_validate(json.loads(SAMPLE_PATH.read_text()))

    data_dir = Path(req.data_dir) if req and req.data_dir else DEFAULT_DATA_DIR
    if not data_dir.exists():
        raise HTTPException(404, f"data_dir not found: {data_dir}")
    if not (data_dir / "customers.csv").exists():
        raise HTTPException(
            400,
            f"data_dir missing CSVs. Run `python -m data.seed` first. ({data_dir})",
        )
    return run_campaign(data_dir)
