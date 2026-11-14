import csv
import subprocess

import duckdb
import pytest

from subscription_analytics.cli import export_report, run_dbt
from subscription_analytics.ingest import ingest


def event(event_id, subscription, month, plan="starter", customer="c1", revision=1):
    return {
        "event_id": event_id,
        "revision": revision,
        "subscription_id": subscription,
        "customer_id": customer,
        "effective_date": f"2025-{month:02d}-01",
        "status": "active" if plan else "cancelled",
        "plan_id": plan,
    }


def rows(database, sql):
    with duckdb.connect(str(database), read_only=True) as connection:
        return connection.execute(sql).fetchall()


def test_metrics_corrections_replays_and_incremental_full_refresh_parity(tmp_path):
    database = tmp_path / "warehouse.duckdb"
    payload = {
        "customers": [
            {"customer_id": "c1", "segment": "small"},
            {"customer_id": "c2", "segment": "mid"},
        ],
        "events": [
            event("e1", "s1", 1),
            event("e2", "s1", 2, "growth"),
            event("e3", "s1", 3, None),
            event("e4", "s1", 4, "scale"),
            event("e5", "s2", 1),
            event("e6", "s2", 2, None),
            event("e7", "s3", 2, "growth", "c2"),
        ],
    }
    ingest(database, payload)
    run_dbt(database, full_refresh=True, target=tmp_path / "dbt")
    # Hand-calculated expectations, independent of the SQL implementation.
    assert rows(
        database,
        "select closing_mrr_cents, active_subscriptions, active_customers "
        "from analytics.mart_mrr_movements order by month_start limit 4",
    ) == [(5800, 2, 1), (15800, 2, 2), (7900, 1, 1), (27800, 2, 2)]
    assert rows(
        database,
        "select new_mrr_cents, expansion_mrr_cents, churn_mrr_cents "
        "from analytics.mart_mrr_movements where month_start = '2025-02-01'",
    ) == [(7900, 5000, 2900)]
    assert rows(
        database,
        "select reactivation_mrr_cents from analytics.mart_mrr_movements "
        "where month_start = '2025-04-01'",
    ) == [(19900,)]
    original = rows(
        database,
        "select * from analytics.fct_subscription_month order by subscription_id, month_start",
    )
    assert ingest(database, payload) == 0
    run_dbt(database, target=tmp_path / "dbt")
    assert (
        rows(
            database,
            "select * from analytics.fct_subscription_month order by subscription_id, month_start",
        )
        == original
    )
    # Correct an old effective date and add a late historical event.
    ingest(
        database,
        {
            "customers": [],
            "events": [
                event("e2", "s1", 2, "scale", revision=3),
                event("e8", "s3", 3, "starter", "c2"),
            ],
        },
    )
    run_dbt(database, target=tmp_path / "dbt")
    assert rows(
        database,
        "select closing_mrr_cents from analytics.mart_mrr_movements order by month_start limit 4",
    ) == [(5800,), (27800,), (2900,), (22800,)]
    # An older revision arriving after revision 3 must never replace revision 3.
    ingest(database, {"customers": [], "events": [event("e2", "s1", 2, revision=2)]})
    run_dbt(database, target=tmp_path / "dbt")
    assert rows(
        database,
        "select mrr_cents, source_revision from analytics.fct_subscription_month "
        "where subscription_id = 's1' and month_start = '2025-02-01'",
    ) == [(19900, 3)]
    incremental = rows(
        database,
        "select * from analytics.fct_subscription_month order by subscription_id, month_start",
    )
    run_dbt(database, full_refresh=True, target=tmp_path / "dbt")
    assert (
        rows(
            database,
            "select * from analytics.fct_subscription_month order by subscription_id, month_start",
        )
        == incremental
    )
    export_report(database, tmp_path / "report")
    with (tmp_path / "report/monthly_metrics.csv").open() as handle:
        metrics = list(csv.DictReader(handle))
    assert len(metrics) == 12
    assert metrics[1]["closing_mrr_cents"] == "27800"


def test_missing_plan_and_ambiguous_dates_fail_dbt_quality_gate(tmp_path):
    database = tmp_path / "warehouse.duckdb"
    ingest(
        database,
        {
            "customers": [{"customer_id": "c1", "segment": "small"}],
            "events": [event("e1", "s1", 1), event("e2", "s1", 1, "unmapped_plan")],
        },
    )
    with pytest.raises(subprocess.CalledProcessError):
        run_dbt(database, full_refresh=True, target=tmp_path / "dbt")
