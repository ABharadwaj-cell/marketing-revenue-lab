"""Regenerate committed synthetic exports. No actual customer or performance data."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def contract(source, aggregation="sum", unit="count", grain="day", end="2026-09-04"):
    return {"version": 1, "source": source, "project_id": "synthetic-shop", "metric_id": "pageviews",
            "definition": "Pageview events after the declared filters", "aggregation": aggregation,
            "unit": unit, "currency": "USD" if unit == "money" else None, "timezone": "UTC", "grain": grain,
            "start": "2026-09-01", "end_exclusive": end, "filters": {"environment": "production"},
            "attribution": "none", "tracking": "pageview event", "bot_policy": "exclude known bots",
            "consent_policy": "consented events only", "exported_at": "2026-09-06T00:00:00Z",
            "mature_after_hours": 24, "complete": True, "native_warnings": []}


def bundle(name, workflow, reference, observed, rows_ref, rows_obs, comparison="equivalent_under_conditions"):
    folder = ROOT / name
    folder.mkdir(exist_ok=True)
    write_json(folder / "config.json", {
        "version": 1, "workspace": f"synthetic-{name}", "workflow": workflow,
        "comparison": {"class": comparison, "rationale": "Synthetic exports with explicitly declared definitions and scope."},
        "tolerance": {"absolute": "1" if workflow == "aggregate" else "0.01", "relative": "0.01" if workflow == "aggregate" else "0"},
        "reference": {"contract": "reference.contract.json", "csv": "reference.csv"},
        "observed": {"contract": "observed.contract.json", "csv": "observed.csv"},
    })
    headers = (["period_start", "period_end_exclusive", "value", "numerator", "denominator"] if workflow == "aggregate"
               else ["order_id", "occurred_at", "status", "environment", "amount", "currency"])
    for role, definition, rows in (("reference", reference, rows_ref), ("observed", observed, rows_obs)):
        write_json(folder / f"{role}.contract.json", definition)
        with (folder / f"{role}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(headers)
            writer.writerows(rows)


def main():
    reference, observed = contract("reference synthetic export"), contract("observed synthetic export")
    rows_ref = [[f"2026-09-0{i}", f"2026-09-0{i+1}", value, "", ""] for i, value in enumerate([100, 120, 0], 1)]
    rows_obs = [[f"2026-09-0{i}", f"2026-09-0{i+1}", value, "", ""] for i, value in enumerate([100, 117, 0], 1)]
    bundle("aggregate", "aggregate", reference, observed, rows_ref, rows_obs)
    different = {**observed, "metric_id": "active_users", "definition": "Distinct consented active users", "aggregation": "distinct"}
    bundle("definitions", "aggregate", reference, different, rows_ref, rows_obs, "related_not_interchangeable")
    reference, observed = [contract(source, "records", "money", "record", "2026-09-02") for source in ("reference order export", "observed purchase export")]
    for definition in (reference, observed):
        definition.update({"metric_id": "completed_orders", "definition": "One completed production order per immutable order ID; gross amount before refunds",
                           "filters": {"status": "completed", "environment": "production"}, "tracking": "order-ID keyed completed transaction",
                           "bot_policy": "not applicable", "consent_policy": "not applicable"})
    rows_ref = [[f"order-{i:03d}", "2026-09-01T12:00:00Z", "completed", "production", "100.00", "USD"] for i in range(1, 101)]
    rows_obs = [r[:] for r in rows_ref[:96]] + [r[:] for r in rows_ref[:5]]
    rows_obs += [[f"test-{i}", "2026-09-01T12:00:00Z", "completed", "test", "100.00", "USD"] for i in range(1, 3)]
    bundle("purchases", "purchases", reference, observed, rows_ref, rows_obs)


if __name__ == "__main__":
    main()
