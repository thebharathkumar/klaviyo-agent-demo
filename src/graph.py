"""LangGraph wiring for the campaign generator.

Topology:

    segmenter ──► strategist ──► content_writer ──► ab_generator ──► reviewer ──► END

The content_writer and ab_generator nodes fan out internally over segments
(executed concurrently via a thread pool). The graph itself stays linear,
which keeps the trace readable in Langfuse.

Tracing uses OpenTelemetry context propagation (Langfuse v3+): nested
context managers automatically establish parent/child observations, so
agents don't have to thread a trace handle through their signatures.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.ab_generator import run_ab_generator
from src.agents.content_writer import load_products, run_content_writer
from src.agents.reviewer import run_reviewer
from src.agents.segmenter import run_segmenter
from src.agents.strategist import run_strategist
from src.schemas import (
    ABTest,
    Campaign,
    GraphState,
    QualityReport,
    SegmentContent,
    SegmentStrategy,
    SegmentSummary,
    StrategyPlan,
)
from src.tracing import agent_span, flush, start_trace

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"


# ---------- nodes -----------------------------------------------------------


def _node_segmenter(state: GraphState) -> dict[str, Any]:
    with agent_span("segmenter", input_payload={"data_dir": state.data_dir}) as span:
        segments = run_segmenter(state.data_dir)
        span.update(output=[s.model_dump() for s in segments])
    return {"segments": segments}


def _node_strategist(state: GraphState) -> dict[str, Any]:
    assert state.segments is not None
    with agent_span("strategist", input_payload=[s.model_dump() for s in state.segments]) as span:
        strategy = run_strategist(state.segments)
        span.update(output=strategy.model_dump())
    return {"strategy": strategy}


def _node_content_writer(state: GraphState) -> dict[str, Any]:
    assert state.segments is not None and state.strategy is not None
    products = load_products(state.data_dir)
    strategy_by_segment: dict[str, SegmentStrategy] = {
        s.segment: s for s in state.strategy.strategies
    }

    def _write_one(segment: SegmentSummary) -> SegmentContent:
        with agent_span(
            f"content_writer:{segment.name}", input_payload=segment.model_dump()
        ) as span:
            out = run_content_writer(segment, strategy_by_segment[segment.name], products)
            span.update(output=out.model_dump())
            return out

    with agent_span("content_writer", input_payload={"n_segments": len(state.segments)}):
        with ThreadPoolExecutor(max_workers=3) as pool:
            contents = list(pool.map(_write_one, state.segments))
    return {"content": contents}


def _node_ab_generator(state: GraphState) -> dict[str, Any]:
    assert state.content is not None

    def _ab_one(content: SegmentContent) -> ABTest:
        with agent_span(
            f"ab_generator:{content.segment}", input_payload=content.model_dump()
        ) as span:
            out = run_ab_generator(content)
            span.update(output=out.model_dump())
            return out

    with agent_span("ab_generator", input_payload={"n_segments": len(state.content)}):
        with ThreadPoolExecutor(max_workers=3) as pool:
            ab_tests = list(pool.map(_ab_one, state.content))
    return {"ab_tests": ab_tests}


def _node_reviewer(state: GraphState) -> dict[str, Any]:
    assert state.content is not None
    with agent_span("reviewer", input_payload=[c.model_dump() for c in state.content]) as span:
        report = run_reviewer(state.content)
        span.update(output=report.model_dump())
    return {"quality": report}


# ---------- builder ---------------------------------------------------------


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("segmenter", _node_segmenter)
    g.add_node("strategist", _node_strategist)
    g.add_node("content_writer", _node_content_writer)
    g.add_node("ab_generator", _node_ab_generator)
    g.add_node("reviewer", _node_reviewer)

    g.set_entry_point("segmenter")
    g.add_edge("segmenter", "strategist")
    g.add_edge("strategist", "content_writer")
    g.add_edge("content_writer", "ab_generator")
    g.add_edge("ab_generator", "reviewer")
    g.add_edge("reviewer", END)
    return g.compile()


# ---------- runner ----------------------------------------------------------


def run_campaign(data_dir: str | Path | None = None) -> Campaign:
    data_dir = str(data_dir or DEFAULT_DATA_DIR)
    graph = build_graph()
    initial = GraphState(data_dir=data_dir)

    with start_trace("generate_campaign", metadata={"data_dir": data_dir}) as root:
        final_state = graph.invoke(initial)
        # final_state is an AddableValuesDict
        segments: list[SegmentSummary] = final_state["segments"]
        strategy: StrategyPlan = final_state["strategy"]
        content: list[SegmentContent] = final_state["content"]
        ab_tests: list[ABTest] = final_state["ab_tests"]
        quality: QualityReport = final_state["quality"]
        campaign = Campaign(
            generated_at=datetime.now(timezone.utc).isoformat(),
            segments=segments,
            strategy=strategy,
            content=content,
            ab_tests=ab_tests,
            quality=quality,
        )
        root.update(output={"n_segments": len(segments), "blocking_issues": len(quality.blocking_issues)})

    flush()
    return campaign


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set. See .env.example.")
    campaign = run_campaign()
    out_path = REPO_ROOT / "examples" / "output_campaign.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(campaign.model_dump(), indent=2))
    print(f"\nCampaign written to {out_path}")
    print(f"\nSegments: {[s.name for s in campaign.segments]}")
    print(f"Quality scores: {[(s.segment, s.overall) for s in campaign.quality.scores]}")
