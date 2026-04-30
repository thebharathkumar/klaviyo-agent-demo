"""End-to-end smoke test.

We run the *deterministic* slice of the pipeline (data seed + segmenter + graph
build) without an Anthropic key, plus a fake-Claude path to exercise the LLM
nodes against fixture responses. Calling the real API is gated behind
RUN_LIVE_LLM=1 so the default `make test` works offline.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from data.seed import seed
from src.agents.segmenter import run_segmenter
from src.graph import build_graph
from src.schemas import (
    ABTest,
    QualityReport,
    QualityScore,
    SegmentContent,
    SegmentStrategy,
    StrategyPlan,
    SubjectVariant,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_seed_creates_csvs() -> None:
    seed()
    for fname in ("customers.csv", "products.csv", "orders.csv", "opens.csv"):
        assert (DATA_DIR / fname).exists(), f"missing {fname}"


def test_segmenter_yields_three_buckets() -> None:
    summaries = run_segmenter(DATA_DIR)
    names = {s.name for s in summaries}
    assert names == {"loyalists", "lapsed", "new_onboarding"}
    counts = {s.name: s.customer_count for s in summaries}
    # all three must be non-empty for the campaign to be meaningful
    for name, count in counts.items():
        assert count > 0, f"{name} segment is empty"


def test_graph_compiles() -> None:
    g = build_graph()
    assert g is not None


def _fake_strategist(segments):  # noqa: ANN001
    return StrategyPlan(
        strategies=[
            SegmentStrategy(
                segment=s.name,
                campaign_type=(
                    "loyalty_reward"
                    if s.name == "loyalists"
                    else "win_back_discount"
                    if s.name == "lapsed"
                    else "welcome_series"
                ),
                rationale="fixture",
                primary_goal="fixture",
                recommended_send_time="Tuesday 10am ET",
            )
            for s in segments
        ]
    )


def _fake_content_writer(segment, strategy, products):  # noqa: ANN001
    return SegmentContent(
        segment=segment.name,
        campaign_type=strategy.campaign_type,
        email={
            "subject_line": "A short subject",
            "preview_text": "Preview text here",
            "body": "Hi {{first_name}}, this is the body.\n\nShop now.",
        },
        sms={"body": "Hi {{first_name}} — quick note. {{link}}"},
        featured_product_ids=["P001"],
    )


def _fake_ab_generator(content):  # noqa: ANN001
    return ABTest(
        segment=content.segment,
        control=SubjectVariant(text=content.email.subject_line, angle="benefit"),
        variants=[
            SubjectVariant(text="Curiosity variant", angle="curiosity"),
            SubjectVariant(text="Urgency variant", angle="urgency"),
        ],
    )


def _fake_reviewer(content):  # noqa: ANN001
    return QualityReport(
        scores=[
            QualityScore(
                segment=c.segment,
                brand_voice=4,
                clarity=4,
                actionability=4,
                overall=4,
                sounds_ai_generated=False,
                flags=[],
                one_line_verdict="ship it",
            )
            for c in content
        ],
        blocking_issues=[],
    )


def test_graph_end_to_end_with_fakes() -> None:
    """Run the whole graph with fake LLM responses. Verifies wiring without spending tokens."""
    with patch("src.graph.run_strategist", _fake_strategist), patch(
        "src.graph.run_content_writer", _fake_content_writer
    ), patch("src.graph.run_ab_generator", _fake_ab_generator), patch(
        "src.graph.run_reviewer", _fake_reviewer
    ):
        from src.graph import run_campaign

        campaign = run_campaign(DATA_DIR)

    assert len(campaign.segments) == 3
    assert len(campaign.content) == 3
    assert len(campaign.ab_tests) == 3
    assert len(campaign.quality.scores) == 3
    for ab in campaign.ab_tests:
        assert len(ab.variants) == 2


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM") != "1",
    reason="set RUN_LIVE_LLM=1 to exercise the real Anthropic API (costs cents)",
)
def test_graph_end_to_end_live() -> None:
    from src.graph import run_campaign

    campaign = run_campaign(DATA_DIR)
    assert len(campaign.segments) == 3
    assert len(campaign.content) == 3
    assert len(campaign.quality.scores) == 3
