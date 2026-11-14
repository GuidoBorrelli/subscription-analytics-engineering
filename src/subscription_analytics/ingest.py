"""Transactional append-only revisions with explicit replay and identity contracts."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

EVENT_FIELDS = {
    "event_id",
    "revision",
    "subscription_id",
    "customer_id",
    "effective_date",
    "status",
    "plan_id",
}


def digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate(payload: dict[str, Any]) -> None:
    if set(payload) != {"customers", "events"}:
        raise ValueError("payload requires exactly customers and events")
    for key in ("customers", "events"):
        if not isinstance(payload[key], list):
            raise ValueError(f"{key} must be a list")
    for customer in payload["customers"]:
        if not isinstance(customer, dict) or set(customer) != {"customer_id", "segment"}:
            raise ValueError("invalid customer fields")
        if not isinstance(customer["customer_id"], str) or not customer["customer_id"].strip():
            raise ValueError("customer_id must be non-empty")
        if customer["segment"] not in {"small", "mid"}:
            raise ValueError("unsupported segment")
    for event in payload["events"]:
        if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
            raise ValueError("invalid event fields")
        for key in ("event_id", "subscription_id", "customer_id"):
            if not isinstance(event[key], str) or not event[key].strip():
                raise ValueError(f"{key} must be non-empty")
        if type(event["revision"]) is not int or event["revision"] < 1:
            raise ValueError("revision must be a positive integer")
        try:
            parsed = date.fromisoformat(event["effective_date"])
        except (TypeError, ValueError) as error:
            raise ValueError("effective_date must be an ISO calendar date") from error
        if parsed.isoformat() != event["effective_date"]:
            raise ValueError("effective_date must use YYYY-MM-DD")
        if event["status"] not in {"active", "cancelled"}:
            raise ValueError("unsupported subscription status")
        if event["status"] == "active" and (
            not isinstance(event["plan_id"], str) or not event["plan_id"].strip()
        ):
            raise ValueError("active events require a non-empty plan; dbt validates the catalog")
        if event["status"] == "cancelled" and event["plan_id"] is not None:
            raise ValueError("cancelled events must have a null plan")


def ingest(database: Path, payload: dict[str, Any]) -> int:
    """Insert new revisions, reject conflicting replays, and return inserted event count.

    Customer attributes and event/subscription identities are immutable in this demo.
    Corrections use a higher revision, preserving previous revisions for traceability.
    """
    validate(payload)
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as connection:
        connection.execute("create schema if not exists raw")
        connection.execute("create sequence if not exists raw.ingestion_sequence")
        connection.execute("""
            create table if not exists raw.customers (
                customer_id varchar primary key, segment varchar not null
            )
        """)
        connection.execute("""
            create table if not exists raw.subscription_events (
                event_id varchar, revision integer, subscription_id varchar not null,
                customer_id varchar not null, effective_date date not null,
                status varchar not null, plan_id varchar, record_hash varchar not null,
                ingestion_sequence bigint default nextval('raw.ingestion_sequence'),
                primary key (event_id, revision)
            )
        """)
        connection.execute("begin transaction")
        inserted = 0
        try:
            for customer in payload["customers"]:
                existing = connection.execute(
                    "select segment from raw.customers where customer_id = ?",
                    [customer["customer_id"]],
                ).fetchone()
                if existing and existing[0] != customer["segment"]:
                    raise ValueError("customer attributes are immutable in this demonstration")
                connection.execute(
                    "insert into raw.customers values (?, ?) on conflict do nothing",
                    [customer["customer_id"], customer["segment"]],
                )
            for event in payload["events"]:
                customer_exists = connection.execute(
                    "select 1 from raw.customers where customer_id = ?", [event["customer_id"]]
                ).fetchone()
                if not customer_exists:
                    raise ValueError("event references an unknown customer")
                previous_identity = connection.execute(
                    "select subscription_id, customer_id from raw.subscription_events "
                    "where event_id = ? limit 1",
                    [event["event_id"]],
                ).fetchone()
                if previous_identity and previous_identity != (
                    event["subscription_id"],
                    event["customer_id"],
                ):
                    raise ValueError("event identity cannot change across revisions")
                owner = connection.execute(
                    "select customer_id from raw.subscription_events "
                    "where subscription_id = ? limit 1",
                    [event["subscription_id"]],
                ).fetchone()
                if owner and owner[0] != event["customer_id"]:
                    raise ValueError("subscription ownership cannot change")
                record_hash = digest(event)
                existing = connection.execute(
                    "select record_hash from raw.subscription_events where event_id = ? "
                    "and revision = ?",
                    [event["event_id"], event["revision"]],
                ).fetchone()
                if existing:
                    if existing[0] != record_hash:
                        raise ValueError("conflicting replay: use a new revision for corrections")
                    continue
                connection.execute(
                    "insert into raw.subscription_events "
                    "(event_id, revision, subscription_id, customer_id, effective_date, "
                    "status, plan_id, record_hash) values (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        event[key]
                        for key in (
                            "event_id",
                            "revision",
                            "subscription_id",
                            "customer_id",
                            "effective_date",
                            "status",
                            "plan_id",
                        )
                    ]
                    + [record_hash],
                )
                inserted += 1
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
    return inserted
