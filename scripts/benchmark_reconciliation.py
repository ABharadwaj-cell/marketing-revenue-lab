"""Synthetic throughput check; not a usability or provider-accuracy benchmark."""

import argparse
import csv
import json
import platform
import resource
import sys
import tempfile
import time
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reconciliation import __version__, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100000, help="Rows per CSV; four CSVs across two runs")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 500000:
        parser.error("--rows must be 1..500000")
    samples = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for index, money in enumerate((False, True), 1):
            folder = root / f"pair-{index}"
            folder.mkdir()
            c = json.loads((ROOT / "examples/reconciliation/aggregate/reference.contract.json").read_text())
            start = date(1750, 1, 1)
            end = start + timedelta(days=args.rows)
            c.update(start=str(start), end_exclusive=str(end), exported_at=f"{end+timedelta(days=2)}T00:00:00Z",
                     metric_id="synthetic_amount" if money else "synthetic_events", unit="money" if money else "count", currency="USD" if money else None)
            for role in ("reference", "observed"):
                definition = {**c, "source": f"synthetic {role}"}
                (folder / f"{role}.contract.json").write_text(json.dumps(definition), encoding="utf-8")
                with (folder / f"{role}.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.writer(stream, lineterminator="\n")
                    writer.writerow(["period_start", "period_end_exclusive", "value", "numerator", "denominator"])
                    for i in range(args.rows):
                        value = 100 + (3 if role == "observed" and i == 0 else 0)
                        writer.writerow([str(start+timedelta(days=i)), str(start+timedelta(days=i+1)), f"{value}.10" if money else str(value), "", ""])
            config = json.loads((ROOT / "examples/reconciliation/aggregate/config.json").read_text())
            config["workspace"] = f"benchmark-{index}"
            (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
            began = time.perf_counter()
            output = run(folder / "config.json", root / "reports")
            elapsed = time.perf_counter()-began
            report = json.loads((output / "report.json").read_text())
            assert report["summary"]["periods_compared"] == args.rows
            assert report["summary"]["outside_tolerance_periods"] == 1
            samples.append({"workflow": "aggregate", "unit": c["unit"], "input_rows": args.rows*2,
                            "seconds_ingest_analyze_render_verify": round(elapsed, 4), "validated_exception_periods": 1})
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mib = rss / (1024*1024 if sys.platform == "darwin" else 1024)
    result = {"engine_version": __version__, "engine_fingerprint": report["engine_fingerprint"], "measured_at": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "total_input_rows": args.rows*4, "runs": samples,
              "total_seconds": round(sum(x["seconds_ingest_analyze_render_verify"] for x in samples), 4),
              "peak_process_rss_mib": round(peak_mib, 2),
              "notes": ["Synthetic daily count and money exports, 100000 rows each at the default setting.",
                        "CSV generation excluded from elapsed time; process peak RSS includes generation and both runs.",
                        "One exception per pair. Exception-heavy HTML reports and purchase-ID workloads were not benchmarked.",
                        "This environment is not the proposed 8 GB reference laptop. No manual-work time savings or superiority claim was measured."]}
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
