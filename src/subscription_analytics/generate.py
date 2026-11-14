"""Generate anonymous fictional subscriptions, never derived from customer records."""

import random
from typing import Any


def generate(seed: int = 42, customers: int = 120) -> dict[str, list[dict[str, Any]]]:
    if customers < 1:
        raise ValueError("customers must be positive")
    rng = random.Random(seed)
    customer_rows = []
    events = []
    plans = ("starter", "growth", "scale")
    for index in range(1, customers + 1):
        customer_id = f"customer_{index:04d}"
        subscription_id = f"subscription_{index:04d}"
        customer_rows.append({"customer_id": customer_id, "segment": rng.choice(("small", "mid"))})
        start = rng.randint(1, 8)
        plan = rng.choice(plans)
        active = True
        sequence = 0
        for month in range(start, 13):
            if month != start:
                draw = rng.random()
                if active and draw < 0.12:
                    active = False
                elif not active and draw < 0.18:
                    active = True
                    plan = rng.choice(plans)
                elif active and draw < 0.30:
                    plan = rng.choice(plans)
                else:
                    continue
            sequence += 1
            events.append(
                {
                    "event_id": f"event_{index:04d}_{sequence:02d}",
                    "revision": 1,
                    "subscription_id": subscription_id,
                    "customer_id": customer_id,
                    "effective_date": f"2025-{month:02d}-01",
                    "status": "active" if active else "cancelled",
                    "plan_id": plan if active else None,
                }
            )
    return {"customers": customer_rows, "events": events}
