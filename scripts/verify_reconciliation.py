"""Run the behavioral suite and all three CLI examples; preserve synthetic evidence."""

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reconciliation import __version__
from reconciliation.reports import json_text, verify_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--sample-root", required=True, type=Path)
    args = parser.parse_args()
    began = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
    if not result.wasSuccessful():
        return 1
    checks = []
    sample_folder = None
    with tempfile.TemporaryDirectory() as temp:
        for name in ("aggregate", "definitions", "purchases"):
            target = args.sample_root.resolve() if name == "purchases" else Path(temp)
            command = [sys.executable, "-m", "reconciliation", "--config", str(ROOT / f"examples/reconciliation/{name}/config.json"), "--output", str(target)]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
            folder = Path(json.loads(completed.stdout)["run_directory"])
            manifest = verify_run(folder)
            report = json.loads((folder / "report.json").read_text())
            if name == "purchases":
                sample_folder = folder
                assert report["summary"]["matched_orders"] == 96
                assert report["summary"]["missing_orders"] == 4
                assert report["summary"]["observed"]["duplicate_extra_rows"] == 5
                assert report["summary"]["observed"]["excluded_rows"] == 2
            elif name == "aggregate":
                assert report["summary"]["within_tolerance_periods"] == 2
                assert report["summary"]["outside_tolerance_periods"] == 1
                assert report["summary"]["period_total_variance"]["delta"] == "-3"
            else:
                assert report["summary"]["comparison_performed"] is False
            checks.append({"bundle": name, "cli_exit": completed.returncode, "run_id": report["run_id"],
                           "input_sha256": report["input_sha256"], "summary": report["summary"],
                           "manifest_files_verified": len(manifest["files"])})
    relative = sample_folder.relative_to(args.sample_root.resolve()).as_posix()
    args.sample_root.mkdir(parents=True, exist_ok=True)
    (args.sample_root / "README.md").write_text(f"""# Synthetic purchase report

[Open the generated HTML report]({relative}/report.html) · [JSON evidence]({relative}/report.json) · [Findings CSV]({relative}/findings.csv) · [Manifest]({relative}/manifest.json)

100 reference orders; 103 observed rows; 5 duplicate extras; 2 test rows excluded; 96 matching IDs; 4 missing IDs. These are synthetic fixtures, not a customer performance result.

The complete content-addressed run folder includes exact input snapshots and verified file hashes. Download or serve this directory locally to view HTML; GitHub's source view does not render a report page.

Regenerate after changing engine source:

```bash
python scripts/verify_reconciliation.py --result docs/reconciliation/verification.json --sample-root docs/reconciliation/sample
```

The script runs all behavioral tests and three CLI smoke checks before saving a sample. Old run directories remain immutable; update the index to the current run and remove superseded committed synthetic samples deliberately when preparing a release.
""", encoding="utf-8")
    (args.sample_root / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic reconciliation example</title></head><body style="font:18px/1.6 system-ui;max-width:800px;margin:48px auto;padding:20px"><h1>103 purchase rows can still hide 4 missing orders</h1><p>In this synthetic example: 100 reference orders, 5 duplicate extra rows, 2 excluded test rows, 96 matches, and 4 missing order IDs.</p><p><a href="{relative}/report.html">Open the generated evidence report</a></p><p>Local CSV prototype. No live analytics integration or customer performance data.</p><p><a href="../README.md">Read the operating guide</a></p></body></html>""", encoding="utf-8")
    record = {"engine_version": __version__, "engine_fingerprint": report["engine_fingerprint"],
              "verified_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
              "cli_checks": checks, "sample_report": (args.sample_root / relative / "report.html").as_posix(),
              "seconds": round(time.perf_counter()-began, 4),
              "not_verified": ["Live providers and their native export mappings", "Provider-verified metric contracts", "Onboarding time and manual time savings", "8 GB reference laptop performance", "Browser visual layout at multiple viewport sizes"]}
    # Keep the recorded artifact path portable when generated from this repository.
    try:
        record["sample_report"] = (args.sample_root / relative / "report.html").resolve().relative_to(ROOT).as_posix()
    except ValueError:
        pass
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json_text(record), encoding="utf-8")
    print(json_text(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
