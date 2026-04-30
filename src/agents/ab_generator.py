"""A/B variant generator + stub Bayesian winner selection.

Generates 2 subject-line variants per segment that test different angles
than the control. The winner-selection function below is a stub that
*would* run Thompson sampling on a Beta-Binomial posterior over CTR if the
data were live; we just call out the math we'd use and return None.
"""

from __future__ import annotations

from src.llm import call_structured
from src.schemas import (
    ABTest,
    SegmentContent,
)

SYSTEM_PROMPT = """You are an A/B test designer for marketing emails. Given a
control subject line, produce exactly two alternates that test DIFFERENT angles.

Pick angles from this list, do not repeat the control's angle:
- urgency  (deadline, limited inventory)
- curiosity  (open loop, intrigue)
- benefit  (lead with the outcome to the reader)
- social_proof  (others doing it)
- personalization  (lean into segment-specific context)

Hard constraints:
- Each variant: under 50 characters, no emoji, no ALL CAPS.
- variants must be a list of exactly 2 items.
- The angles in the variants must differ from each other AND from the control.

Respond ONLY with a JSON object:
{
  "segment": "...",
  "control": { "text": "<original subject>", "angle": "<inferred angle>" },
  "variants": [
    { "text": "...", "angle": "..." },
    { "text": "...", "angle": "..." }
  ],
  "winner_selection_method": "stub_bayesian_thompson_sampling",
  "notes": null
}
"""


def run_ab_generator(content: SegmentContent) -> ABTest:
    user = f"""Segment: {content.segment}
Campaign type: {content.campaign_type}
Control subject line: "{content.email.subject_line}"

Produce two alternate subject lines testing different angles than the control.
"""
    return call_structured(
        system=SYSTEM_PROMPT,
        user=user,
        response_model=ABTest,
        temperature=0.8,
        max_tokens=512,
        span_name=f"ab_generator.{content.segment}.claude",
    )


# ---------- Stubbed Bayesian winner selection -------------------------------


def select_winner_stub(
    impressions: dict[str, tuple[int, int]],
    *,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    samples: int = 5000,
) -> dict[str, float] | None:
    """Stub for Thompson sampling on Beta-Binomial CTR posteriors.

    impressions: { variant_id: (clicks, sends) }

    The real implementation would:
      1. For each variant, draw `samples` from Beta(alpha + clicks,
         beta + sends - clicks).
      2. For each draw, mark the argmax as the winner of that draw.
      3. Return the empirical probability each variant is best.
      4. Stop the test once one variant's prob_best > 0.95 OR the expected
         loss of picking the leader < a threshold (regret-based stopping).

    For the demo we return None to signal "no live data yet".
    """
    if not impressions:
        return None
    return None
