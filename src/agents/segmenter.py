"""Rule-based segmenter.

Three fixed segments — kept dumb on purpose. Real product would learn these
from RFM scoring or a clustering model; we don't need that here, and an LLM
would be slow and expensive for what is fundamentally a SQL query.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.schemas import SegmentSummary

# "Now" matches data/seed.py so segmentation thresholds line up with the data.
NOW = date(2026, 4, 30)
LAPSED_DAYS = 60
NEW_SIGNUP_DAYS = 14


def _last_order_date(orders: pd.DataFrame, customer_id: str) -> date | None:
    cust_orders = orders[orders["customer_id"] == customer_id]
    if cust_orders.empty:
        return None
    return max(datetime.fromisoformat(d).date() for d in cust_orders["order_date"])


def _top_categories(orders: pd.DataFrame, products: pd.DataFrame, ids: list[str]) -> list[str]:
    cust_orders = orders[orders["customer_id"].isin(ids)]
    if cust_orders.empty:
        return []
    merged = cust_orders.merge(products, on="product_id")
    return merged["category"].value_counts().head(3).index.tolist()


def run_segmenter(data_dir: str | Path) -> list[SegmentSummary]:
    data_dir = Path(data_dir)
    customers = pd.read_csv(data_dir / "customers.csv")
    orders = pd.read_csv(data_dir / "orders.csv")
    products = pd.read_csv(data_dir / "products.csv")

    loyalists: list[str] = []
    lapsed: list[str] = []
    new_onboarding: list[str] = []
    days_since_last: dict[str, list[int]] = {"loyalists": [], "lapsed": []}

    for _, row in customers.iterrows():
        cid = row["customer_id"]
        signup = datetime.fromisoformat(row["signup_date"]).date()
        last = _last_order_date(orders, cid)

        if (NOW - signup).days <= NEW_SIGNUP_DAYS:
            new_onboarding.append(cid)
            continue

        if last is None:
            # signed up > 14 days ago, never bought - treat as lapsed
            lapsed.append(cid)
            continue

        days = (NOW - last).days
        cust_order_count = (orders["customer_id"] == cid).sum()

        if days <= 30 and cust_order_count >= 5:
            loyalists.append(cid)
            days_since_last["loyalists"].append(days)
        elif days > LAPSED_DAYS:
            lapsed.append(cid)
            days_since_last["lapsed"].append(days)
        else:
            # warm middle - fold into loyalists for the demo (3 buckets only)
            loyalists.append(cid)
            days_since_last["loyalists"].append(days)

    summaries: list[SegmentSummary] = []
    for name, ids in [
        ("loyalists", loyalists),
        ("lapsed", lapsed),
        ("new_onboarding", new_onboarding),
    ]:
        seg_orders = orders[orders["customer_id"].isin(ids)]
        avg_order_value = float(seg_orders["total"].mean()) if not seg_orders.empty else 0.0
        avg_orders = len(seg_orders) / len(ids) if ids else 0.0
        median_days = (
            int(statistics.median(days_since_last[name]))
            if name in days_since_last and days_since_last[name]
            else None
        )

        if name == "loyalists":
            description = (
                f"{len(ids)} high-engagement customers who purchased recently and repeatedly. "
                f"Avg {avg_orders:.1f} orders, AOV ${avg_order_value:.0f}."
            )
        elif name == "lapsed":
            description = (
                f"{len(ids)} customers with no purchase in {LAPSED_DAYS}+ days. "
                f"Median {median_days} days since last order."
            )
        else:
            description = (
                f"{len(ids)} customers who signed up in the last {NEW_SIGNUP_DAYS} days. "
                "Need a welcome flow."
            )

        summaries.append(
            SegmentSummary(
                name=name,  # type: ignore[arg-type]
                customer_count=len(ids),
                avg_order_value=round(avg_order_value, 2),
                avg_orders_per_customer=round(avg_orders, 2),
                days_since_last_purchase_median=median_days,
                top_categories=_top_categories(orders, products, ids),
                description=description,
            )
        )

    return summaries


if __name__ == "__main__":
    import json

    out = run_segmenter(Path(__file__).parent.parent.parent / "data")
    print(json.dumps([s.model_dump() for s in out], indent=2))
