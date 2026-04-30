"""Content writer agent.

Generates one email + one SMS per segment. The writer runs once per segment
(in parallel from the graph) so each call has a tight, focused context.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.llm import call_structured
from src.schemas import (
    SegmentContent,
    SegmentStrategy,
    SegmentSummary,
)

SYSTEM_PROMPT = """You are a senior copywriter for a DTC home-goods brand
called "Field & Hearth". The brand voice is warm, considered, never pushy;
think Patagonia or Field Notes, not Groupon.

Hard constraints:
- subject_line: under 50 characters, no emoji, no ALL CAPS, no exclamation
  spam.
- preview_text: under 90 characters; should complement, not repeat, the
  subject line.
- email body: 80-140 words, plain text, addressable as {{first_name}}.
  End with one clear CTA line.
- sms body: under 160 characters including the {{first_name}} placeholder
  and a short link placeholder {{link}}.
- Pick 1-2 featured products from the catalog that fit the segment + strategy.
  Return their product_ids.

Respond ONLY with a JSON object matching this schema:
{
  "segment": "...",
  "campaign_type": "...",
  "email": {
    "subject_line": "...",
    "preview_text": "...",
    "body": "..."
  },
  "sms": { "body": "..." },
  "featured_product_ids": ["P001", ...]
}
"""


def _format_products(products: pd.DataFrame) -> str:
    return "\n".join(
        f"- {row.product_id}: {row['name']} ({row.category}, ${row.price:.0f})"
        for _, row in products.iterrows()
    )


def run_content_writer(
    segment: SegmentSummary,
    strategy: SegmentStrategy,
    products: pd.DataFrame,
) -> SegmentContent:
    user = f"""Segment: {segment.name}
Segment description: {segment.description}
Top categories for this segment: {", ".join(segment.top_categories) or "(none)"}

Strategy:
- campaign_type: {strategy.campaign_type}
- primary_goal: {strategy.primary_goal}
- rationale: {strategy.rationale}

Product catalog:
{_format_products(products)}

Write one email and one SMS for this segment, following the brand voice
and constraints. Pick 1-2 featured products from the catalog that fit.
"""
    return call_structured(
        system=SYSTEM_PROMPT,
        user=user,
        response_model=SegmentContent,
        temperature=0.7,
        max_tokens=1024,
        span_name=f"content_writer.{segment.name}.claude",
    )


def load_products(data_dir: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(data_dir) / "products.csv")
