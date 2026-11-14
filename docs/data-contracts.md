# Data contracts and lineage

This is a deliberately fictional subscription business. The repository's metric specification is the business authority for the demonstration; it is not inferred from any employer system. A real deployment would require a named commercial/finance owner to approve these definitions.

| Layer / relation | Grain / key | Responsibility |
| --- | --- | --- |
| JSON `customers` | `customer_id` | Anonymous fictional ID and small/mid segment; immutable attributes |
| JSON `events` / `raw.subscription_events` | `event_id, revision` | Append-only source revisions, SHA-256 content hash, monotonic arrival sequence |
| `stg_subscription_events` | `event_id` | Highest business revision, regardless of arrival order |
| `int_subscription_watermarks` | `subscription_id` | Maximum arrival sequence across all raw revisions |
| `plans` / `dim_plan` | `plan_id` | Governed CHF monthly price in integer cents; new prices require new plan IDs |
| `dim_customer` | `customer_id` | Customer reference for dimensional joins |
| `dim_month` | `month_start` | Inclusive configured window, currently January–December 2025 |
| `fct_subscription_month` | `subscription_id, month_start` | Latest effective month-end state and source event/revision lineage |
| `mart_mrr_movements` | `month_start` | Reconciled MRR movement bridge and active customer/subscription counts |

The loader validates required fields, non-empty identifiers, ISO dates, positive integer revisions, active/cancelled states, ownership consistency and customer references. It rejects conflicting replays transactionally. It does not mutate or delete earlier event revisions.

An active event requires a plan; a cancelled event requires a null plan. dbt checks plan relationships against the governed seed. Null plan IDs are intentional only for cancelled/not-started states. Unknown mappings fail the pipeline. Blank identifiers and invalid dates fail before ingestion.

There can be at most one current event per subscription and effective date. A data test rejects ambiguity. Event identity and subscription ownership cannot change across revisions; this avoids leaving stale historical facts attached to an old owner.

Each fact row links to the event and revision determining its month-end state. `source_sequence` captures the highest arrival sequence for the subscription, including any superseded revision. It is a processing watermark, not a business timestamp.

Dimension joins are many-to-one and covered by uniqueness/relationship tests. Calendar expansion is the only intentional multiplication: every subscription receives one row per reporting month. The coverage test checks row counts and uniqueness of that grain.

The generator creates one subscription per customer for compact examples. The model supports multiple subscriptions per customer and the integration test checks that active customer counts use distinct IDs.

An empty source is a valid state. The monthly aggregate retains all configured reporting months with zero metrics, so a missing report row does not stand in for zero business activity.
