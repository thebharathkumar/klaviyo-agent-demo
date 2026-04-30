"""Strategist agent.

Decides the campaign type and primary goal per segment. Pure planner — does
not write copy. Output is consumed by the content writer.
"""

from __future__ import annotations

import json

from src.llm import call_structured
from src.schemas import SegmentSummary, StrategyPlan

SYSTEM_PROMPT = """You are a senior marketing strategist working at a DTC e-commerce
brand. You receive segment summaries and decide one campaign per segment.

Constraints:
- Each segment gets exactly one strategy.
- campaign_type must be one of: re_engagement, upsell_complementary,
  welcome_series, loyalty_reward, win_back_discount.
- Match the campaign type to segment behavior. Lapsed customers get
  re_engagement or win_back_discount, never welcome_series.
- recommended_send_time: pick a single concrete suggestion ("Tuesday 10am ET")
  based on what's typical for the segment (loyalists tolerate weekday mornings,
  lapsed need a softer Sunday, new onboarding triggers off signup).
- rationale: one sentence, no fluff.

Respond ONLY with a JSON object matching this schema:
{
  "strategies": [
    {
      "segment": "loyalists" | "lapsed" | "new_onboarding",
      "campaign_type": "...",
      "rationale": "...",
      "primary_goal": "...",
      "recommended_send_time": "..."
    }
  ]
}
"""


def run_strategist(segments: list[SegmentSummary]) -> StrategyPlan:
    user = (
        "Here are the segment summaries. Produce one strategy per segment.\n\n"
        + json.dumps([s.model_dump() for s in segments], indent=2)
    )
    return call_structured(
        system=SYSTEM_PROMPT,
        user=user,
        response_model=StrategyPlan,
        temperature=0.3,
        span_name="strategist.claude",
    )
