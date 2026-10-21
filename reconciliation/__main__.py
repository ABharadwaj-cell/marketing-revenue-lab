"""Run with python -m reconciliation --config ... --output ..."""

import argparse
import json
import sys

from .contracts import InputError
from .reports import run


def main():
    parser = argparse.ArgumentParser(description="Reconcile local CSV exports using explicit metric contracts.")
    parser.add_argument("--config", required=True, help="Path to the input bundle's config.json")
    parser.add_argument("--output", required=True, help="Local output root; raw snapshots are retained here")
    args = parser.parse_args()
    try:
        folder = run(args.config, args.output)
    except (InputError, OSError) as exc:
        print(f"Reconciliation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"run_directory": str(folder), "html_report": str(folder / "report.html")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
