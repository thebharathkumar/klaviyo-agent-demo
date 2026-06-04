# klaviyo-agent-demo

> A LangGraph multi-agent demo of an autonomous marketing campaign generator.
> Five agents, structured-output validated, traced end-to-end, with an LLM-as-grader gating quality.

## Why this exists

A compact, end-to-end demo of how I decompose an agentic workflow: rule-based
segmentation, an LLM strategist, parallel content generation, and an automated
quality gate. Scoped small on purpose so every design choice is easy to inspect
in the trace.

## What it does

Takes a fake e-commerce dataset (50 customers, 10 products, ~240 orders, ~440 email
opens) and runs five agents to produce a per-segment marketing campaign: email + SMS
copy, A/B subject-line variants, a recommended send time, and a quality review.
Every step is structured-output validated via Pydantic and traced to Langfuse.

```
$ make demo
Wrote: 10 products, 50 customers, 238 orders, 442 opens to data/

Segments: ['loyalists', 'lapsed', 'new_onboarding']
Quality scores: [('loyalists', 4), ('lapsed', 4), ('new_onboarding', 4)]
Campaign written to examples/output_campaign.json
```

A real generated campaign is committed at [`examples/output_campaign.json`](examples/output_campaign.json).

## Architecture

```
                    ┌───────────────┐
       CSVs ──────► │   Segmenter   │  rule-based; no LLM
                    │  (3 buckets)  │
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │  Strategist   │  Claude — picks campaign type per segment
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │ Content writer│  Claude — fan-out, one per segment
                    │  (parallel)   │
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │ A/B generator │  Claude — fan-out, 2 variants per segment
                    │  (parallel)   │
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │   Reviewer    │  Claude — automated grader
                    └───────┬───────┘
                            ▼
                    Campaign JSON ───► FastAPI ───► Streamlit
```

The graph is linear; fan-out happens *inside* the content_writer and ab_generator nodes
via `ThreadPoolExecutor`. Linear topology keeps the Langfuse trace readable; parallelism
keeps wall-clock under ~20s for three segments on Haiku.

## The five agents

**1. Segmenter** (`src/agents/segmenter.py`) — pure pandas, no LLM. Buckets customers
into `loyalists` (≥5 orders, last purchase ≤30d), `lapsed` (no purchase in 60+ days),
and `new_onboarding` (signed up in last 14 days). I left this rule-based on purpose:
this is a SQL-shaped problem and an LLM here would be slow, expensive, and harder to
audit. Real product would replace this with RFM scoring or learned clusters; the
interface stays the same.

**2. Strategist** (`src/agents/strategist.py`) — Claude. Reads segment summaries,
picks one `campaign_type` per segment from a fixed enum (`loyalty_reward`,
`win_back_discount`, `welcome_series`, `re_engagement`, `upsell_complementary`),
and proposes a send-time heuristic. Output validated against
`StrategyPlan` Pydantic schema.

**3. Content writer** (`src/agents/content_writer.py`) — Claude, one call per segment
in parallel. Writes one email (subject < 50 chars, body 80-140 words) and one SMS
(< 160 chars). Constrained to a defined brand voice ("Field & Hearth", warm/considered)
and picks 1-2 featured products from the catalog. Schema enforces the length limits at
parse time.

**4. A/B generator** (`src/agents/ab_generator.py`) — Claude, one call per segment
in parallel. Takes the control subject line and produces two alternates that test
*different* angles (urgency / curiosity / benefit / social_proof / personalization). Includes a
**stubbed** Bayesian winner-selection function (`select_winner_stub`) — see "What's
defensible / what's not" below.

**5. Quality reviewer** (`src/agents/reviewer.py`) — Claude. Acts as a "skeptical
marketing director" prompt and scores every piece of generated content on brand voice,
clarity, and actionability (1-5 each), flags anything that sounds AI-generated, and
produces a `blocking_issues` list. This is the eval gate: in a real system, content
with blocking issues never auto-sends — it routes to a human queue.

## What's defensible / what's not

This is a **weekend sketch**, not a production system. Specifically:

- **The Bayesian A/B winner selection is stubbed.** `select_winner_stub` documents
  the math (Beta-Binomial conjugate posteriors over CTR, Thompson sampling with a
  regret-based stopping rule) but returns `None`. Wiring it to live impressions data
  is the obvious next step — the schema already carries the slot.
- **CTR and engagement data are simulated.** No real Klaviyo Flows API integration.
  The `opens.csv` fixture exists so the segmenter has a story for engagement, but
  nothing in the demo conditions content on it yet.
- **Quality scores are not validated against human raters.** The reviewer agent's
  judgments are plausible but uncalibrated. In a real eval pipeline, you'd seed it
  with a few hundred human-graded examples and compute Cohen's κ between human and
  agent scores per axis before trusting it as a gate.
- **Segments are hardcoded to three buckets.** Real product would either learn them
  (k-means on RFM features, or HDBSCAN) or let the user define them; this would also
  change the strategist's prompt to be segment-agnostic.
- **Prompts are inline, not versioned.** Easy to fix with Langfuse Prompts or even
  a `prompts/` directory with hashed versions on each campaign trace.

If this were the real thing, the next five things I'd build, in order:

1. Real Klaviyo Flows JSON output adapter — emit something the API can ingest.
2. True Bayesian winner selection on live impressions, with regret-based stopping.
3. A reviewer-agent eval set: ~200 hand-graded examples, compute agreement, calibrate.
4. Drift monitoring on quality scores over time (PSI on score distributions per
   segment per week).
5. Prompt versioning + A/B'ing the agents themselves against the same input fixtures.

## How to run

Three commands:

```bash
pip install -e ".[dev]"
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env  # see .env.example
make demo                                    # seeds data, runs the graph
```

Then optionally:

```bash
make api                # FastAPI on :8000
make streamlit          # Streamlit UI on :8501 (hits the API)
make test               # smoke tests; offline-safe (uses fakes)
```

`docker compose up` brings up local Langfuse + the API in tandem if you want the trace
viewer.

## Deploy (Fly.io)

The repo ships with a `Dockerfile` + `fly.toml` that runs both processes (Streamlit
public on 8080, FastAPI internal on 8000) in one machine.

```bash
brew install flyctl                                  # or curl -L https://fly.io/install.sh | sh
fly auth login
fly launch --copy-config --no-deploy                 # accepts the existing fly.toml
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set LANGFUSE_PUBLIC_KEY=...   # optional
fly secrets set LANGFUSE_SECRET_KEY=...   # optional
fly deploy
```

`auto_stop_machines` is on, so the VM sleeps when idle and wakes on the next request
(~3-5s cold start). Plenty for a recruiter link.

## Why I built it

Autonomous marketing agents that create, execute, and optimize campaigns are a clear
near-term application of agentic systems. The closest thing in my recent work is a
multi-agent LangGraph system with an automated quality grader (the Pace eval
pipeline), so I built a small marketing agent end-to-end with the same shape:
structured output, traced reasoning, and an LLM-as-grader gating quality.

The point is the trace, not the polish. Run `make demo`, open the Langfuse UI, and you'll
see how I think about agent decomposition, contracts, and the eval loop.
