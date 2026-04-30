"""Quality reviewer agent — automated grader for generated content.

Mirrors the eval-pipeline pattern: a "skeptical marketing director" prompt
scores every piece of content on four axes, flags AI-tells, and produces a
go/no-go list of blocking issues. In a real system this is the gate that
decides whether content auto-sends or routes to a human queue.
"""

from __future__ import annotations

import json

from src.llm import call_structured
from src.schemas import QualityReport, SegmentContent

SYSTEM_PROMPT = """You are a skeptical marketing director reviewing AI-generated
campaign content before it ships. You are looking for reasons to NOT send.

For each segment's email + SMS, score 1-5 on:
- brand_voice: does it sound like Field & Hearth (warm, considered, never
  pushy)? 1 = off-brand, 5 = indistinguishable from a human writer.
- clarity: is the offer and CTA obvious in <5 seconds? 1 = confusing,
  5 = crystal clear.
- actionability: would a recipient know exactly what to do next? 1 = vague,
  5 = single obvious action.
- overall: holistic; not necessarily an average.

Also assess:
- sounds_ai_generated: true if it has telltales (hollow superlatives, three-
  parallel-clause structures, "Discover the...", "Elevate your..."), false
  otherwise.
- flags: short bullet strings naming specific issues. Empty list if none.
- one_line_verdict: ship-or-not in a single sentence.

Then list blocking_issues across all segments — issues severe enough that a
human marketer should fix before send. Be specific. If nothing is blocking,
return an empty list.

Be honest. A bad review here is more useful than a charitable one.

Respond ONLY with a JSON object:
{
  "scores": [
    {
      "segment": "...",
      "brand_voice": 1-5,
      "clarity": 1-5,
      "actionability": 1-5,
      "overall": 1-5,
      "sounds_ai_generated": true/false,
      "flags": ["..."],
      "one_line_verdict": "..."
    }
  ],
  "blocking_issues": ["..."]
}
"""


def run_reviewer(content: list[SegmentContent]) -> QualityReport:
    user = (
        "Review the following campaign content. Score every segment and flag "
        "anything that should block send.\n\n"
        + json.dumps([c.model_dump() for c in content], indent=2)
    )
    return call_structured(
        system=SYSTEM_PROMPT,
        user=user,
        response_model=QualityReport,
        temperature=0.2,
        max_tokens=2048,
        span_name="reviewer.claude",
    )
