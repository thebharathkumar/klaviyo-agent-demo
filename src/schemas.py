"""Pydantic models for all agent I/O.

The graph state is the union of every agent's output. Each node populates its
slice and the next node reads from it. Typing here is the contract; if Claude
returns malformed JSON it fails Pydantic validation, not silently downstream.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SegmentName = Literal["loyalists", "lapsed", "new_onboarding"]
CampaignType = Literal[
    "re_engagement",
    "upsell_complementary",
    "welcome_series",
    "loyalty_reward",
    "win_back_discount",
]


# ---------- segmenter -------------------------------------------------------


class SegmentSummary(BaseModel):
    """One row per segment, fed to the strategist."""

    name: SegmentName
    customer_count: int
    avg_order_value: float
    avg_orders_per_customer: float
    days_since_last_purchase_median: int | None = Field(
        default=None,
        description="None for the new_onboarding segment (no purchase history).",
    )
    top_categories: list[str]
    description: str


# ---------- strategist ------------------------------------------------------


class SegmentStrategy(BaseModel):
    segment: SegmentName
    campaign_type: CampaignType
    rationale: str = Field(description="One sentence explaining the choice.")
    primary_goal: str
    recommended_send_time: str = Field(
        description="ISO 8601 datetime or human-readable suggestion like 'Tuesday 10am ET'.",
    )


class StrategyPlan(BaseModel):
    strategies: list[SegmentStrategy]


# ---------- content writer --------------------------------------------------


class EmailContent(BaseModel):
    subject_line: str = Field(max_length=50)
    preview_text: str = Field(max_length=90)
    body: str


class SMSContent(BaseModel):
    body: str = Field(max_length=160)


class SegmentContent(BaseModel):
    segment: SegmentName
    campaign_type: CampaignType
    email: EmailContent
    sms: SMSContent
    featured_product_ids: list[str] = Field(default_factory=list)


# ---------- A/B generator ---------------------------------------------------


class SubjectVariant(BaseModel):
    text: str = Field(max_length=50)
    angle: str = Field(description="One-word/short-phrase tag: urgency, curiosity, benefit, etc.")


class ABTest(BaseModel):
    segment: SegmentName
    control: SubjectVariant
    variants: list[SubjectVariant] = Field(min_length=2, max_length=2)
    winner_selection_method: str = "stub_bayesian_thompson_sampling"
    notes: str | None = None


# ---------- reviewer --------------------------------------------------------


class QualityScore(BaseModel):
    segment: SegmentName
    brand_voice: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    sounds_ai_generated: bool
    flags: list[str] = Field(default_factory=list)
    one_line_verdict: str


class QualityReport(BaseModel):
    scores: list[QualityScore]
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Issues severe enough that a human marketer should fix before send.",
    )


# ---------- final campaign --------------------------------------------------


class Campaign(BaseModel):
    """The thing the API returns."""

    generated_at: str
    segments: list[SegmentSummary]
    strategy: StrategyPlan
    content: list[SegmentContent]
    ab_tests: list[ABTest]
    quality: QualityReport


# ---------- graph state -----------------------------------------------------


class GraphState(BaseModel):
    """Mutable state that flows through the LangGraph nodes."""

    data_dir: str
    segments: list[SegmentSummary] | None = None
    strategy: StrategyPlan | None = None
    content: list[SegmentContent] | None = None
    ab_tests: list[ABTest] | None = None
    quality: QualityReport | None = None

    model_config = {"arbitrary_types_allowed": True}
