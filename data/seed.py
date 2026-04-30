"""Generate deterministic fake e-commerce data.

~50 customers, ~10 products, ~200 orders, ~500 email opens.
Run: python -m data.seed
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
DATA_DIR = Path(__file__).parent

# Today is the demo's "now". The seed is deterministic so all relative
# date math (lapsed = no purchase in 60 days, etc.) is reproducible.
NOW = datetime(2026, 4, 30)

PRODUCTS = [
    ("P001", "Cedar Soy Candle, 8oz", "home", 28.0),
    ("P002", "Linen Throw Blanket", "home", 85.0),
    ("P003", "Ceramic Pour-Over Set", "kitchen", 64.0),
    ("P004", "Cast Iron Skillet, 10in", "kitchen", 78.0),
    ("P005", "Merino Wool Beanie", "apparel", 42.0),
    ("P006", "Waxed Canvas Tote", "apparel", 95.0),
    ("P007", "Leather Card Wallet", "accessories", 55.0),
    ("P008", "Brass Desk Lamp", "home", 140.0),
    ("P009", "Stoneware Mug, Set of 2", "kitchen", 38.0),
    ("P010", "Field Notes Journal", "accessories", 14.0),
]

FIRST_NAMES = [
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Gray", "Harper",
    "Indigo", "Jules", "Kai", "Lane", "Morgan", "Nico", "Oakley", "Parker",
    "Quinn", "Riley", "Sage", "Tatum", "Umi", "Vale", "Wren", "Xander", "Yara",
    "Zion",
]
LAST_NAMES = [
    "Adler", "Brooks", "Castro", "Dempsey", "Ellis", "Fontaine", "Greer", "Holt",
    "Iverson", "Janssen", "Knox", "Lowe", "Maeda", "Nash", "Okafor", "Pak",
    "Quist", "Reyes", "Solis", "Tran", "Underwood", "Vega", "Walsh", "Xu",
    "Yamada", "Zhao",
]


def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def seed() -> None:
    rng = random.Random(SEED)

    # ---- products ---------------------------------------------------------
    write_csv(
        DATA_DIR / "products.csv",
        ["product_id", "name", "category", "price"],
        [(pid, name, cat, price) for pid, name, cat, price in PRODUCTS],
    )

    # ---- customers --------------------------------------------------------
    customers = []
    for i in range(50):
        cid = f"C{i + 1:03d}"
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}@example.com"
        signup_days_ago = rng.randint(2, 720)
        signup = (NOW - timedelta(days=signup_days_ago)).date().isoformat()
        customers.append((cid, first, last, email, signup))
    write_csv(
        DATA_DIR / "customers.csv",
        ["customer_id", "first_name", "last_name", "email", "signup_date"],
        customers,
    )

    # ---- orders -----------------------------------------------------------
    # Force three personas so the segmenter has clean buckets:
    #   loyalists: 12 customers, many recent high-value orders
    #   lapsed:    18 customers, last order > 60 days ago
    #   new:       remaining 20, signed up in last 14 days, 0-1 order
    loyalist_ids = [c[0] for c in customers[:12]]
    lapsed_ids = [c[0] for c in customers[12:30]]
    new_ids = [c[0] for c in customers[30:]]

    # Backfill signup dates for "new" so they actually look new.
    # We rebuild the customer rows in place to keep them consistent.
    for idx, cid in enumerate(new_ids):
        first, last = customers[30 + idx][1], customers[30 + idx][2]
        email = customers[30 + idx][3]
        signup = (NOW - timedelta(days=rng.randint(1, 14))).date().isoformat()
        customers[30 + idx] = (cid, first, last, email, signup)
    write_csv(
        DATA_DIR / "customers.csv",
        ["customer_id", "first_name", "last_name", "email", "signup_date"],
        customers,
    )

    orders = []
    order_id = 1

    # loyalists: 8-15 orders, last one within last 30 days
    for cid in loyalist_ids:
        n_orders = rng.randint(8, 15)
        for _ in range(n_orders):
            days_ago = rng.randint(1, 30) if rng.random() < 0.3 else rng.randint(31, 365)
            product = rng.choice(PRODUCTS)
            qty = rng.randint(1, 3)
            orders.append(
                (
                    f"O{order_id:04d}",
                    cid,
                    product[0],
                    qty,
                    round(product[3] * qty, 2),
                    (NOW - timedelta(days=days_ago)).date().isoformat(),
                )
            )
            order_id += 1
        # guarantee at least one recent order
        product = rng.choice(PRODUCTS)
        orders.append(
            (
                f"O{order_id:04d}",
                cid,
                product[0],
                1,
                product[3],
                (NOW - timedelta(days=rng.randint(1, 25))).date().isoformat(),
            )
        )
        order_id += 1

    # lapsed: 2-6 orders, all > 60 days ago
    for cid in lapsed_ids:
        n_orders = rng.randint(2, 6)
        for _ in range(n_orders):
            days_ago = rng.randint(61, 540)
            product = rng.choice(PRODUCTS)
            qty = rng.randint(1, 2)
            orders.append(
                (
                    f"O{order_id:04d}",
                    cid,
                    product[0],
                    qty,
                    round(product[3] * qty, 2),
                    (NOW - timedelta(days=days_ago)).date().isoformat(),
                )
            )
            order_id += 1

    # new: 0-1 orders, recent
    for cid in new_ids:
        if rng.random() < 0.4:
            product = rng.choice(PRODUCTS)
            orders.append(
                (
                    f"O{order_id:04d}",
                    cid,
                    product[0],
                    1,
                    product[3],
                    (NOW - timedelta(days=rng.randint(0, 10))).date().isoformat(),
                )
            )
            order_id += 1

    write_csv(
        DATA_DIR / "orders.csv",
        ["order_id", "customer_id", "product_id", "quantity", "total", "order_date"],
        orders,
    )

    # ---- opens ------------------------------------------------------------
    # ~500 email opens; loyalists open most, lapsed barely, new moderately.
    opens = []
    open_id = 1

    def emit_opens(cid: str, n: int, max_days_ago: int) -> None:
        nonlocal open_id
        for _ in range(n):
            days_ago = rng.randint(0, max_days_ago)
            opens.append(
                (
                    f"E{open_id:04d}",
                    cid,
                    f"campaign_{rng.randint(1, 12)}",
                    (NOW - timedelta(days=days_ago)).date().isoformat(),
                )
            )
            open_id += 1

    for cid in loyalist_ids:
        emit_opens(cid, rng.randint(15, 30), 90)
    for cid in lapsed_ids:
        emit_opens(cid, rng.randint(0, 4), 365)
    for cid in new_ids:
        emit_opens(cid, rng.randint(2, 10), 14)

    write_csv(
        DATA_DIR / "opens.csv",
        ["open_id", "customer_id", "campaign_id", "open_date"],
        opens,
    )

    print(f"Wrote: {len(PRODUCTS)} products, {len(customers)} customers, "
          f"{len(orders)} orders, {len(opens)} opens to {DATA_DIR}")


if __name__ == "__main__":
    seed()
