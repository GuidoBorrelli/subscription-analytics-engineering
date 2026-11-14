# Operations and recovery

Run commands from the repository root in the activated virtual environment. The dependency lock pins the resolved environment; it does not vendor dependencies. First installation needs internet access. Subsequent pipeline runs require no external service.

## Replays and corrections

`subscription-analytics ingest --input path/to/batch.json` appends unseen event revisions in a single transaction. Batches have exactly two lists, `customers` and `events`; either can be empty. Customers must already exist or arrive in the same batch. Inspect a generated `data/synthetic.json` for the contract.

Identical `(event_id, revision)` records are skipped. A conflicting payload for that key fails and rolls back the whole batch. Do not edit the raw tables to correct data: submit a higher event revision with the same event/subscription/customer identity, then run `subscription-analytics build` and `subscription-analytics report`.

Lower revisions can arrive after higher revisions and remain in raw history. They do not replace the latest business revision. Sequence gaps after a rollback are harmless: the incremental predicate compares order, not contiguous numbering.

## Full refresh

```bash
subscription-analytics build --full-refresh
subscription-analytics report
```

Use full refresh after changing reporting bounds, SQL business logic, plan prices or model schema. It rebuilds dbt models from raw history, without deleting source revisions. The configured window must include every effective event date. This demo starts with no subscriptions before that window.

Changing generator seed/customer count against an existing database can intentionally conflict with existing immutable records. Use a new `--database` path for a different generated scenario. A full refresh does **not** erase raw data or resolve source conflicts.

## Quality failures

The CLI returns non-zero if ingestion or `dbt build` fails. It only exports a new report after a successful build when using `demo`. Standalone `report` reads the currently materialised mart; it does not independently rerun quality checks. If a build fails, an older report may still exist: use the terminal status/build artifacts to establish freshness.

Inspect `target/run_results.json` and `logs/dbt.log`. Correct source data through new revisions or correct the governed seed/model, then rerun the build. The raw transaction is atomic; dbt builds individual models transactionally but the entire DAG is not one atomic publication. A serving layer with atomic swaps is a separate production concern.

No deletion/tombstone protocol, concurrent ingestion, scheduler or managed monitoring is implemented. Raw records are synthetic and local; CI reports expire after seven days. dbt anonymous usage statistics are disabled by the CLI environment.

## Explore the data model

```bash
DBT_SEND_ANONYMOUS_USAGE_STATS=false dbt docs generate --profiles-dir .
dbt docs serve --profiles-dir .
```

The default profile points to `data/warehouse.duckdb`. Set `ANALYTICS_DB` to an absolute path when exploring another database. dbt model descriptions and the manifest expose lineage; generated docs stay local.

## Verify the committed example

```bash
subscription-analytics demo
diff docs/example/monthly_metrics.csv reports/monthly_metrics.csv
```

The CSV must match the default seed. To intentionally update it, run tests first and copy the generated CSV and HTML into `docs/example/` together. Keep the synthetic-data notice intact.
