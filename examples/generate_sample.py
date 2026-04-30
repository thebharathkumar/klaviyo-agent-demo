"""Build a representative example_campaign.json for the README.

Used to seed examples/output_campaign.json without needing a live Anthropic
key. The sample copy below is hand-written to be a plausible Field & Hearth
campaign — matches what you'd actually see if you ran `make demo`. Real runs
overwrite this file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.schemas import (
    ABTest,
    QualityReport,
    QualityScore,
    SegmentContent,
    SegmentStrategy,
    StrategyPlan,
    SubjectVariant,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def _strategist(segments):  # noqa: ANN001
    plans = {
        "loyalists": SegmentStrategy(
            segment="loyalists",
            campaign_type="loyalty_reward",
            rationale="High-frequency buyers respond best to early access, not discounts.",
            primary_goal="Drive repeat purchase via insider-feel reward",
            recommended_send_time="Tuesday 10:00 ET",
        ),
        "lapsed": SegmentStrategy(
            segment="lapsed",
            campaign_type="win_back_discount",
            rationale="60+ day silence justifies a one-time incentive to re-acquire.",
            primary_goal="Reactivate dormant customers with a softer offer",
            recommended_send_time="Sunday 18:00 ET",
        ),
        "new_onboarding": SegmentStrategy(
            segment="new_onboarding",
            campaign_type="welcome_series",
            rationale="Day-3 of a welcome series introduces brand story before pitching product.",
            primary_goal="Build trust before first transactional ask",
            recommended_send_time="3 days post-signup, 09:00 local",
        ),
    }
    return StrategyPlan(strategies=[plans[s.name] for s in segments])


_CONTENT_BY_SEGMENT = {
    "loyalists": SegmentContent(
        segment="loyalists",
        campaign_type="loyalty_reward",
        email={
            "subject_line": "Early access, just for you",
            "preview_text": "A first look at the spring collection before it goes live tomorrow.",
            "body": (
                "Hi {{first_name}},\n\n"
                "You've been with us for a while — long enough that we wanted "
                "to send the spring catalog your way before everyone else.\n\n"
                "Inside: a few new ceramics, a brass piece we've been quietly "
                "perfecting since last fall, and one restock that always sells "
                "out.\n\n"
                "Take a look. No code needed; the prices you see are yours.\n\n"
                "Browse the collection →"
            ),
        },
        sms={
            "body": "Hi {{first_name}}, spring catalog is live for you 24h early. {{link}}"
        },
        featured_product_ids=["P008", "P003"],
    ),
    "lapsed": SegmentContent(
        segment="lapsed",
        campaign_type="win_back_discount",
        email={
            "subject_line": "It's been a while — 15% off, on us",
            "preview_text": "A small thank-you for coming back. No catch.",
            "body": (
                "Hi {{first_name}},\n\n"
                "We noticed you haven't been by in a few months, and we'd "
                "rather not let that go without saying hello.\n\n"
                "Use HEARTH15 at checkout for 15% off anything in the shop "
                "through Sunday. The cast iron skillet has been the most-"
                "loved thing we make this year — if you missed it last time, "
                "this is the moment.\n\n"
                "Come back when you're ready.\n\n"
                "Shop with HEARTH15 →"
            ),
        },
        sms={
            "body": "Hi {{first_name}}, 15% off through Sunday with HEARTH15. {{link}}"
        },
        featured_product_ids=["P004", "P002"],
    ),
    "new_onboarding": SegmentContent(
        segment="new_onboarding",
        campaign_type="welcome_series",
        email={
            "subject_line": "Where Field & Hearth comes from",
            "preview_text": "A quick note on why we make what we make.",
            "body": (
                "Hi {{first_name}},\n\n"
                "Welcome in. This is day three of a short welcome series — "
                "no pitch today, just context.\n\n"
                "Field & Hearth started in a one-room studio in Vermont. "
                "We make slow goods for the home: things designed to be "
                "used every day for a long time, not replaced next season.\n\n"
                "If you're curious, the journals are where most people start. "
                "They're $14, and they last.\n\n"
                "Read the full story →"
            ),
        },
        sms={
            "body": "Hi {{first_name}}, welcome to Field & Hearth. Our story, in 2 mins. {{link}}"
        },
        featured_product_ids=["P010"],
    ),
}


def _content_writer(segment, strategy, products):  # noqa: ANN001
    return _CONTENT_BY_SEGMENT[segment.name]


_AB_BY_SEGMENT = {
    "loyalists": ABTest(
        segment="loyalists",
        control=SubjectVariant(text="Early access, just for you", angle="personalization"),
        variants=[
            SubjectVariant(text="Spring drop opens 24h early", angle="urgency"),
            SubjectVariant(text="A few new things we made", angle="curiosity"),
        ],
        notes="Personalization control feels strongest; urgency variant tests scarcity framing.",
    ),
    "lapsed": ABTest(
        segment="lapsed",
        control=SubjectVariant(text="It's been a while — 15% off, on us", angle="benefit"),
        variants=[
            SubjectVariant(text="Did we lose you?", angle="curiosity"),
            SubjectVariant(text="HEARTH15 expires Sunday", angle="urgency"),
        ],
    ),
    "new_onboarding": ABTest(
        segment="new_onboarding",
        control=SubjectVariant(text="Where Field & Hearth comes from", angle="curiosity"),
        variants=[
            SubjectVariant(text="A studio in Vermont, day 3", angle="personalization"),
            SubjectVariant(text="What we mean by slow goods", angle="benefit"),
        ],
    ),
}


def _ab_generator(content):  # noqa: ANN001
    return _AB_BY_SEGMENT[content.segment]


def _reviewer(content):  # noqa: ANN001
    return QualityReport(
        scores=[
            QualityScore(
                segment="loyalists",
                brand_voice=5,
                clarity=4,
                actionability=4,
                overall=4,
                sounds_ai_generated=False,
                flags=[],
                one_line_verdict="On-brand, soft sell — ship.",
            ),
            QualityScore(
                segment="lapsed",
                brand_voice=4,
                clarity=5,
                actionability=5,
                overall=4,
                sounds_ai_generated=False,
                flags=["The discount code copy is fine but the second sentence is slightly long."],
                one_line_verdict="Strong; trim sentence two and ship.",
            ),
            QualityScore(
                segment="new_onboarding",
                brand_voice=5,
                clarity=4,
                actionability=3,
                overall=4,
                sounds_ai_generated=False,
                flags=["No transactional CTA on day-3 by design — confirm this matches the welcome flow plan."],
                one_line_verdict="Brand voice nailed; verify intent before send.",
            ),
        ],
        blocking_issues=[],
    )


def main() -> None:
    with patch("src.graph.run_strategist", _strategist), patch(
        "src.graph.run_content_writer", _content_writer
    ), patch("src.graph.run_ab_generator", _ab_generator), patch(
        "src.graph.run_reviewer", _reviewer
    ):
        from src.graph import run_campaign

        campaign = run_campaign(DATA_DIR)

    # Stable timestamp so the committed example doesn't churn on every regen.
    campaign.generated_at = datetime(2026, 4, 30, 14, 0, 0, tzinfo=timezone.utc).isoformat()

    out = REPO_ROOT / "examples" / "output_campaign.json"
    out.write_text(json.dumps(campaign.model_dump(), indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
