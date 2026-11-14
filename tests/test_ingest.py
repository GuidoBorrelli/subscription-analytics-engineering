from copy import deepcopy

import duckdb
import pytest

from subscription_analytics.generate import generate
from subscription_analytics.ingest import ingest


def test_generation_is_deterministic_and_seed_sensitive():
    assert generate(42, 10) == generate(42, 10)
    assert generate(42, 10) != generate(43, 10)
    assert len(generate(42, 10)["customers"]) == 10


def test_identical_replay_is_idempotent(tmp_path):
    database = tmp_path / "warehouse.duckdb"
    payload = generate(customers=5)
    assert ingest(database, payload) == len(payload["events"])
    assert ingest(database, payload) == 0
    with duckdb.connect(str(database)) as connection:
        assert connection.execute("select count(*) from raw.subscription_events").fetchone()[
            0
        ] == len(payload["events"])


def test_conflicting_replay_rolls_back_the_entire_batch(tmp_path):
    database = tmp_path / "warehouse.duckdb"
    payload = generate(customers=2)
    ingest(database, payload)
    conflicting = deepcopy(payload["events"][0])
    conflicting["effective_date"] = "2025-12-31"
    new_event = {**payload["events"][0], "event_id": "new_event"}
    with pytest.raises(ValueError, match="conflicting replay"):
        ingest(database, {"customers": [], "events": [new_event, conflicting]})
    with duckdb.connect(str(database)) as connection:
        assert (
            connection.execute(
                "select count(*) from raw.subscription_events where event_id = 'new_event'"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("customer_id", ""),
        ("revision", 0),
        ("revision", True),
        ("effective_date", "2025-02-30"),
        ("status", "unknown"),
        ("plan_id", ""),
    ],
)
def test_invalid_inputs_are_rejected_before_writes(tmp_path, field, value):
    payload = generate(customers=1)
    payload["events"][0][field] = value
    with pytest.raises(ValueError):
        ingest(tmp_path / "warehouse.duckdb", payload)
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_identity_changes_and_unknown_customers_are_rejected(tmp_path):
    database = tmp_path / "warehouse.duckdb"
    payload = generate(customers=2)
    ingest(database, payload)
    event = payload["events"][0]
    with pytest.raises(ValueError, match="identity"):
        ingest(
            database,
            {"customers": [], "events": [{**event, "revision": 2, "subscription_id": "different"}]},
        )
    with pytest.raises(ValueError, match="unknown customer"):
        ingest(
            database,
            {"customers": [], "events": [{**event, "event_id": "new", "customer_id": "missing"}]},
        )
