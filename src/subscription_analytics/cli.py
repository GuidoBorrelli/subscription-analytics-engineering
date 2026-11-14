"""Project commands. Run from the repository root after installing the editable package."""

import argparse
import csv
import html
import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

from subscription_analytics.generate import generate
from subscription_analytics.ingest import ingest

ROOT = Path(__file__).resolve().parents[2]


def run_dbt(database: Path, full_refresh: bool = False, target: Path | None = None) -> None:
    environment = {
        **os.environ,
        "ANALYTICS_DB": str(database.resolve()),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }
    command = [
        str(Path(sys.executable).parent / "dbt"),
        "build",
        "--project-dir",
        str(ROOT),
        "--profiles-dir",
        str(ROOT),
    ]
    if full_refresh:
        command.append("--full-refresh")
    if target:
        command.extend(["--target-path", str(target.resolve()), "--log-path", str(target / "logs")])
    subprocess.run(command, env=environment, check=True, cwd=ROOT)


def export_report(database: Path, output: Path) -> None:
    with duckdb.connect(str(database), read_only=True) as connection:
        catalog = connection.execute("select current_database()").fetchone()[0].replace('"', '""')
        cursor = connection.execute(
            f'SELECT * FROM "{catalog}".analytics.mart_mrr_movements ORDER BY month_start'
        )
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "monthly_metrics.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
    display_columns = ["Month", "Active subscriptions", "Active customers", "Closing MRR (CHF)"]
    display_rows = [[str(row[0]), str(row[8]), str(row[9]), f"{row[7] / 100:,.2f}"] for row in rows]
    header = "".join(f"<th scope='col'>{html.escape(value)}</th>" for value in display_columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in display_rows
    )
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Synthetic subscription analytics</title>
<style>
body {{font-family:system-ui,sans-serif;max-width:850px;margin:3rem auto;
padding:0 1rem;color:#183041}}
h1 {{line-height:1.15}} table {{border-collapse:collapse;width:100%}}
td,th {{padding:.6rem;text-align:right;border-bottom:1px solid #cdd8df}}
td:first-child,th:first-child {{text-align:left}} th {{background:#eaf2f6}}
.table {{overflow-x:auto}} p {{line-height:1.6}}
</style>
<h1>Subscription analytics</h1>
<p>Entirely synthetic demonstration. Month-end contracted recurring revenue in CHF.
These figures are not customer results, cash collections, or recognised revenue.</p>
<div class="table"><table><caption>Monthly portfolio demonstration metrics</caption>
<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>
<p>Full movement bridge: <a href="monthly_metrics.csv">download CSV</a>.
Definitions and limitations are documented in the repository.</p></html>
"""
    (output / "index.html").write_text(document)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "ingest", "build", "report", "demo"])
    parser.add_argument("--database", type=Path, default=ROOT / "data/warehouse.duckdb")
    parser.add_argument("--input", type=Path, default=ROOT / "data/synthetic.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--customers", type=int, default=120)
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()
    if args.command in {"generate", "demo"}:
        args.input.parent.mkdir(parents=True, exist_ok=True)
        args.input.write_text(json.dumps(generate(args.seed, args.customers), indent=2) + "\n")
    if args.command in {"ingest", "demo"}:
        count = ingest(args.database, json.loads(args.input.read_text()))
        print(f"Inserted {count} new event revisions")
    if args.command in {"build", "demo"}:
        run_dbt(args.database, args.full_refresh)
    if args.command in {"report", "demo"}:
        export_report(args.database, args.output)
        print(f"Report: {(args.output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
