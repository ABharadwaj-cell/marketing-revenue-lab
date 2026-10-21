import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reconciliation import analyze, run
from reconciliation.contracts import InputError, provisional, strict_json, validate_contract
from reconciliation.reports import findings_csv, json_text, report_html, verify_run


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "examples/reconciliation", self.root / "examples")
        self.aggregate = self.root / "examples/aggregate/config.json"
        self.purchases = self.root / "examples/purchases/config.json"
        self.definitions = self.root / "examples/definitions/config.json"
        self.output = self.root / "output"

    def edit_json(self, config, filename, update):
        path = config.parent / filename
        obj = json.loads(path.read_text())
        update(obj)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def edit_csv(self, config, role, update):
        path = config.parent / f"{role}.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        update(rows)
        with path.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)

    def test_purchase_fixture_counts_and_evidence(self):
        report, _ = analyze(self.purchases)
        summary = report["summary"]
        self.assertEqual(summary["reference"]["raw_rows"], 100)
        self.assertEqual(summary["observed"]["raw_rows"], 103)
        self.assertEqual(summary["observed"]["duplicate_extra_rows"], 5)
        self.assertEqual(summary["observed"]["excluded_rows"], 2)
        self.assertEqual(summary["matched_orders"], 96)
        self.assertEqual(summary["missing_orders"], 4)
        self.assertEqual(summary["unexpected_orders"], 0)
        missing = [f for f in report["findings"] if f["rule"] == "PUR_MISSING"]
        self.assertEqual([f["subject"] for f in missing], [f"order-{i:03d}" for i in range(97, 101)])
        self.assertEqual(missing[0]["evidence"]["row"]["line"], 98)
        self.assertEqual(summary["valid_order_amount_totals"], {"reference": Decimal("10000"), "observed": Decimal("9600")})

    def test_aggregate_fixture_threshold_and_totals(self):
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["within_tolerance_periods"], 2)
        self.assertEqual(report["summary"]["outside_tolerance_periods"], 1)
        mismatch = next(f for f in report["findings"] if f["rule"] == "AGG_VARIANCE")
        self.assertEqual(mismatch["evidence"]["variance"]["delta"], Decimal(-3))
        self.assertEqual(mismatch["evidence"]["variance"]["allowed_absolute_delta"], Decimal("1.20"))
        self.assertEqual(mismatch["evidence"]["reference"]["line"], 3)
        self.assertEqual(report["summary"]["native_totals"]["reference"]["value"], 220)

    def test_missing_period_is_not_zero(self):
        self.edit_csv(self.aggregate, "observed", lambda rows: rows.pop())
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["missing_or_undefined_periods"], 1)
        self.assertTrue(report["summary"]["native_totals"]["observed"]["partial"])
        missing = next(f for f in report["findings"] if f["rule"] == "AGG_MISSING")
        self.assertIsNone(missing["evidence"]["observed"])
        self.assertEqual(missing["evidence"]["reference"]["value"], 0)

    def test_period_missing_in_both_exports_is_reported(self):
        for role in ("reference", "observed"):
            self.edit_csv(self.aggregate, role, lambda rows: rows.pop())
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["missing_or_undefined_periods"], 1)

    def test_explicit_null_is_not_zero(self):
        self.edit_csv(self.aggregate, "observed", lambda rows: rows[-1].__setitem__(2, ""))
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["missing_or_undefined_periods"], 1)
        self.assertIsNone(report["summary"]["native_totals"]["observed"]["value"])

    def test_daily_distinct_values_are_not_summed(self):
        for role in ("reference", "observed"):
            self.edit_json(self.aggregate, f"{role}.contract.json", lambda obj: obj.update(aggregation="distinct"))
        report, _ = analyze(self.aggregate)
        self.assertIsNone(report["summary"]["native_totals"]["reference"]["value"])
        self.assertIn("cannot be summed", report["summary"]["native_totals"]["reference"]["reason"])

    def test_ratios_recompute_from_components(self):
        def ratio_rows(rows):
            for row, numerator, denominator in zip(rows[1:], [1, 9, 0], [2, 10, 1]):
                row[2:] = ["", str(numerator), str(denominator)]
        for role in ("reference", "observed"):
            self.edit_json(self.aggregate, f"{role}.contract.json", lambda obj: obj.update(aggregation="ratio", unit="ratio"))
            self.edit_csv(self.aggregate, role, ratio_rows)
        report, _ = analyze(self.aggregate)
        total = report["summary"]["native_totals"]["reference"]
        self.assertEqual(total["numerator"], 10)
        self.assertEqual(total["denominator"], 13)
        self.assertTrue(abs(total["value"] - Decimal(10)/13) < Decimal("1e-27"))
        self.assertNotEqual(total["value"], (Decimal("0.5")+Decimal("0.9"))/3)

    def test_zero_denominator_is_undefined(self):
        for role in ("reference", "observed"):
            self.edit_json(self.aggregate, f"{role}.contract.json", lambda obj: obj.update(aggregation="ratio", unit="ratio"))
            self.edit_csv(self.aggregate, role, lambda rows: [row.__setitem__(slice(2, None), ["", "0", "0"]) for row in rows[1:]])
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["missing_or_undefined_periods"], 3)

    def test_zero_denominator_day_does_not_prevent_component_total(self):
        for role in ("reference", "observed"):
            self.edit_json(self.aggregate, f"{role}.contract.json", lambda obj: obj.update(aggregation="ratio", unit="ratio"))
            def update(rows):
                rows[1][2:] = ["", "0", "0"]
                rows[2][2:] = ["", "2", "10"]
                rows[3][2:] = ["", "3", "10"]
            self.edit_csv(self.aggregate, role, update)
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["native_totals"]["reference"]["value"], Decimal("0.25"))
        self.assertTrue(report["summary"]["period_total_variance"]["within_tolerance"])

    def test_small_daily_differences_can_fail_period_total_tolerance(self):
        for role in ("reference", "observed"):
            self.edit_csv(self.aggregate, role, lambda rows: [r.__setitem__(2, "0" if role == "reference" else "1") for r in rows[1:]])
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["outside_tolerance_periods"], 0)
        self.assertFalse(report["summary"]["period_total_variance"]["within_tolerance"])
        self.assertTrue(any(f["rule"] == "AGG_TOTAL_VARIANCE" for f in report["findings"]))

    def test_related_definitions_block_numeric_comparison(self):
        report, _ = analyze(self.definitions)
        self.assertFalse(report["summary"]["comparison_performed"])
        self.assertEqual(report["findings"][0]["classification"], "expected_definition_difference")
        self.assertIn("definition", report["findings"][0]["evidence"]["differences"])

    def test_same_label_different_scope_still_blocks(self):
        original = (self.aggregate.parent / "observed.contract.json").read_bytes()
        mutations = {"project_id": "different", "timezone": "Asia/Kolkata", "filters": {"environment": "test"},
                     "tracking": "server event", "consent_policy": "all events", "bot_policy": "all traffic",
                     "attribution": "last click", "end_exclusive": "2026-09-05", "definition": "Another definition"}
        for field, value in mutations.items():
            with self.subTest(field=field):
                (self.aggregate.parent / "observed.contract.json").write_bytes(original)
                self.edit_json(self.aggregate, "observed.contract.json", lambda obj: obj.update({field: value}))
                report, _ = analyze(self.aggregate)
                self.assertFalse(report["summary"]["comparison_performed"])
                self.assertIn(field, report["findings"][0]["evidence"]["differences"])

    def test_unsupported_comparison_blocks(self):
        self.edit_json(self.aggregate, "config.json", lambda obj: obj["comparison"].update({"class": "unsupported"}))
        report, _ = analyze(self.aggregate)
        self.assertFalse(report["summary"]["comparison_performed"])
        self.assertEqual(report["findings"][0]["classification"], "not_comparable")

    def test_provisional_sources_do_not_claim_final_gaps(self):
        for change in ({"complete": False}, {"exported_at": "2026-09-02T00:00:00Z"}, {"native_warnings": ["Sampled export"]}):
            with self.subTest(change=change):
                self.edit_json(self.purchases, "observed.contract.json", lambda obj: obj.update(change))
                report, _ = analyze(self.purchases)
                missing = [f for f in report["findings"] if f["rule"] == "PUR_MISSING"]
                self.assertTrue(all(f["classification"] == "provisional_source_changing" for f in missing))

    def test_money_is_decimal_and_zero_reference_has_no_infinite_ratio(self):
        self.edit_csv(self.purchases, "reference", lambda rows: rows[1].__setitem__(4, "0.10"))
        # Remove duplicate copies to avoid deliberately conflicting IDs in this test.
        self.edit_csv(self.purchases, "observed", lambda rows: rows.__setitem__(slice(97, 102), []))
        self.edit_csv(self.purchases, "observed", lambda rows: rows[1].__setitem__(4, "0.30"))
        report, _ = analyze(self.purchases)
        mismatch = next(f for f in report["findings"] if f["rule"] == "PUR_AMOUNT")
        self.assertEqual(mismatch["evidence"]["variance"]["delta"], Decimal("0.20"))
        self.edit_csv(self.purchases, "reference", lambda rows: rows[1].__setitem__(4, "0"))
        report, _ = analyze(self.purchases)
        mismatch = next(f for f in report["findings"] if f["rule"] == "PUR_AMOUNT")
        self.assertIsNone(mismatch["evidence"]["variance"]["absolute_relative_delta"])

    def test_conflicting_duplicate_is_quarantined_without_false_missing(self):
        self.edit_csv(self.purchases, "observed", lambda rows: rows[97].__setitem__(4, "101"))
        report, _ = analyze(self.purchases)
        self.assertEqual(report["summary"]["quarantined_ids"], 1)
        self.assertEqual(report["summary"]["matched_orders"], 95)
        self.assertEqual(report["summary"]["missing_orders"], 4)
        self.assertTrue(report["summary"]["totals_partial"])
        self.assertTrue(any(f["rule"] == "PUR_CONFLICT" for f in report["findings"]))

    def test_reference_duplicates_do_not_create_join_fanout(self):
        self.edit_csv(self.purchases, "reference", lambda rows: rows.append(rows[1][:]))
        report, _ = analyze(self.purchases)
        self.assertEqual(report["summary"]["matched_orders"], 96)
        self.assertEqual(report["summary"]["reference"]["duplicate_extra_rows"], 1)
        self.assertEqual(report["summary"]["valid_order_amount_totals"]["reference"], 10000)

    def test_equivalent_timestamp_offsets_do_not_create_conflict(self):
        self.edit_csv(self.purchases, "observed", lambda rows: rows[97].__setitem__(1, "2026-09-01T14:00:00+02:00"))
        report, _ = analyze(self.purchases)
        self.assertEqual(report["summary"]["observed"]["duplicate_extra_rows"], 5)
        self.assertEqual(report["summary"]["quarantined_ids"], 0)

    def test_unexpected_order_and_explicit_status_exclusion(self):
        self.edit_csv(self.purchases, "observed", lambda rows: rows.append(["extra", "2026-09-01T12:00:00Z", "completed", "production", "1", "USD"]))
        self.edit_csv(self.purchases, "reference", lambda rows: rows[-1].__setitem__(2, "cancelled"))
        report, _ = analyze(self.purchases)
        self.assertEqual(report["summary"]["unexpected_orders"], 1)
        self.assertEqual(report["summary"]["reference"]["excluded_rows"], 1)
        self.assertEqual(report["summary"]["missing_orders"], 3)

    def test_dst_uses_calendar_boundaries_and_exclusive_end(self):
        for role in ("reference", "observed"):
            self.edit_json(self.purchases, f"{role}.contract.json", lambda obj: obj.update(start="2026-03-08", end_exclusive="2026-03-09", timezone="America/New_York"))
            self.edit_csv(self.purchases, role, lambda rows: rows.__setitem__(slice(1, None), [
                ["late-on-dst-day", "2026-03-09T03:30:00Z", "completed", "production", "1", "USD"],
                ["next-day", "2026-03-09T04:00:00Z", "completed", "production", "1", "USD"],
                ["before-day", "2026-03-08T04:59:59Z", "completed", "production", "1", "USD"]]))
        report, _ = analyze(self.purchases)
        self.assertEqual(report["summary"]["matched_orders"], 1)
        self.assertEqual(report["summary"]["observed"]["excluded_rows"], 2)

    def test_maturity_window_is_elapsed_hours_across_dst(self):
        c = json.loads((self.purchases.parent / "reference.contract.json").read_text())
        c.update(start="2026-03-07", end_exclusive="2026-03-08", timezone="America/New_York", exported_at="2026-03-09T04:30:00Z")
        self.assertTrue(provisional(c))  # 23.5 elapsed hours, though local calendar advanced.
        c["exported_at"] = "2026-03-09T05:00:00Z"
        self.assertFalse(provisional(c))

    def test_input_schema_and_numeric_failures(self):
        cases = [lambda rows: rows[0].__setitem__(0, "unknown"),
                 lambda rows: rows[0].__setitem__(1, rows[0][0]),
                 lambda rows: rows[1].pop(),
                 lambda rows: rows[1].__setitem__(4, "NaN"),
                 lambda rows: rows[1].__setitem__(4, "-1"),
                 lambda rows: rows[1].__setitem__(4, "1e3"),
                 lambda rows: rows[1].__setitem__(0, ""),
                 lambda rows: rows[1].__setitem__(1, "2026-09-01T12:00:00"),
                 lambda rows: rows[1].__setitem__(5, "EUR")]
        original = (self.purchases.parent / "observed.csv").read_bytes()
        for change in cases:
            with self.subTest(change=change):
                (self.purchases.parent / "observed.csv").write_bytes(original)
                self.edit_csv(self.purchases, "observed", change)
                with self.assertRaises(InputError):
                    analyze(self.purchases)

    def test_duplicate_or_wrong_grain_period_rejected(self):
        original = (self.aggregate.parent / "observed.csv").read_bytes()
        for change in (lambda rows: rows.append(rows[1][:]),
                       lambda rows: rows[1].__setitem__(1, "2026-09-03"),
                       lambda rows: rows[1].__setitem__(0, "2026-08-31"),
                       lambda rows: rows[1].__setitem__(2, "1.5")):
            with self.subTest(change=change):
                (self.aggregate.parent / "observed.csv").write_bytes(original)
                self.edit_csv(self.aggregate, "observed", change)
                with self.assertRaises(InputError):
                    analyze(self.aggregate)

    def test_period_grain_preserves_native_distinct_count(self):
        for role in ("reference", "observed"):
            self.edit_json(self.aggregate, f"{role}.contract.json", lambda obj: obj.update(grain="period", aggregation="distinct"))
            self.edit_csv(self.aggregate, role, lambda rows: rows.__setitem__(slice(1, None), [["2026-09-01", "2026-09-04", "150", "", ""]]))
        report, _ = analyze(self.aggregate)
        self.assertEqual(report["summary"]["native_totals"]["reference"]["value"], 150)

    def test_unknown_contract_field_and_duplicate_json_key_rejected(self):
        self.edit_json(self.aggregate, "reference.contract.json", lambda obj: obj.update(unknown=True))
        with self.assertRaises(InputError):
            analyze(self.aggregate)
        with self.assertRaises(InputError):
            strict_json('{"version":1,"version":2}')
        with self.assertRaises(InputError):
            strict_json('{"value":NaN}')

    def test_contract_types_and_timezone_are_explicit(self):
        original = json.loads((self.aggregate.parent / "reference.contract.json").read_text())
        for field, value in (("version", True), ("complete", "true"), ("mature_after_hours", -1),
                             ("timezone", "Not/AZone"), ("currency", "USD"), ("unit", "widgets"),
                             ("grain", "month"), ("start", "2026-02-30"), ("native_warnings", "warning")):
            with self.subTest(field=field):
                c = {**original, field: value}
                with self.assertRaises(InputError):
                    validate_contract(c)

    def test_path_traversal_and_cross_project_workspace_rejected(self):
        self.edit_json(self.aggregate, "config.json", lambda obj: obj.update(workspace="../other-project"))
        with self.assertRaises(InputError):
            run(self.aggregate, self.output)
        self.edit_json(self.aggregate, "config.json", lambda obj: obj.update(workspace="valid-project"))
        outside = self.root / "outside.csv"
        outside.write_text("anything")
        self.edit_json(self.aggregate, "config.json", lambda obj: obj["reference"].update(csv="../../../outside.csv"))
        with self.assertRaises((InputError, OSError)):
            analyze(self.aggregate)
        self.assertFalse(self.output.exists())

    def test_symlink_input_and_output_escape_rejected(self):
        outside = self.root / "outside.csv"
        outside.write_text("anything")
        observed = self.aggregate.parent / "observed.csv"
        observed.unlink()
        observed.symlink_to(outside)
        with self.assertRaises(InputError):
            analyze(self.aggregate)
        self.output.mkdir()
        (self.output / "synthetic-purchases").symlink_to(self.root / "other")
        with self.assertRaises(InputError):
            run(self.purchases, self.output)

    def test_read_only_analysis_and_snapshot_identity(self):
        before = {p: p.read_bytes() for p in self.aggregate.parent.iterdir()}
        a, snapshots = analyze(self.aggregate)
        b, _ = analyze(self.aggregate)
        self.assertEqual(a, b)
        self.assertEqual(before, {p: p.read_bytes() for p in self.aggregate.parent.iterdir()})
        self.assertEqual(snapshots["reference.csv"], before[self.aggregate.parent / "reference.csv"])
        self.assertFalse(self.output.exists())

    def test_atomic_run_replay_does_not_rewrite_or_double_count(self):
        folder = run(self.purchases, self.output)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}
        self.assertEqual(run(self.purchases, self.output), folder)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()})
        self.assertEqual(verify_run(folder)["status"], "complete")
        self.assertEqual(json.loads((folder / "report.json").read_text())["summary"]["matched_orders"], 96)

    def test_changed_input_creates_new_immutable_run(self):
        first = run(self.aggregate, self.output)
        self.edit_csv(self.aggregate, "observed", lambda rows: rows[2].__setitem__(2, "120"))
        second = run(self.aggregate, self.output)
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertNotEqual((first / "inputs/observed.csv").read_bytes(), (second / "inputs/observed.csv").read_bytes())

    def test_workspace_names_isolate_run_paths(self):
        first = run(self.aggregate, self.output)
        self.edit_json(self.aggregate, "config.json", lambda obj: obj.update(workspace="another-project"))
        second = run(self.aggregate, self.output)
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(json.loads((first / "report.json").read_text())["workspace"], "synthetic-aggregate")

    def test_interrupted_render_never_publishes_partial_report(self):
        with patch("reconciliation.reports.report_html", side_effect=OSError("injected disk failure")):
            with self.assertRaises(OSError):
                run(self.aggregate, self.output)
        self.assertEqual(list((self.output / "synthetic-aggregate").iterdir()), [])

    def test_interrupted_file_write_cleans_staging_and_keeps_previous_run(self):
        previous = run(self.purchases, self.output)
        original = Path.write_bytes
        def fail_on_csv(path, data):
            if path.name == "findings.csv":
                raise OSError("injected write failure")
            return original(path, data)
        with patch.object(Path, "write_bytes", fail_on_csv):
            with self.assertRaises(OSError):
                run(self.aggregate, self.output)
        self.assertEqual(list((self.output / "synthetic-aggregate").iterdir()), [])
        verify_run(previous)

    def test_concurrent_replays_publish_one_complete_run(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            folders = list(pool.map(lambda _: run(self.purchases, self.output), range(2)))
        self.assertEqual(folders[0], folders[1])
        verify_run(folders[0])
        self.assertEqual(len(list(folders[0].parent.iterdir())), 1)

    def test_saved_output_corruption_is_rejected(self):
        folder = run(self.aggregate, self.output)
        (folder / "report.html").write_text("changed")
        with self.assertRaisesRegex(InputError, "checksum mismatch"):
            run(self.aggregate, self.output)

    def test_unexpected_saved_file_is_rejected(self):
        folder = run(self.aggregate, self.output)
        (folder / "unexpected.txt").write_text("changed")
        with self.assertRaisesRegex(InputError, "file set changed"):
            run(self.aggregate, self.output)

    def test_malformed_manifest_is_an_input_error(self):
        folder = run(self.aggregate, self.output)
        (folder / "manifest.json").write_text("[]")
        with self.assertRaisesRegex(InputError, "must be an object"):
            run(self.aggregate, self.output)

    def test_html_escapes_source_content_and_csv_neutralizes_formulas(self):
        payload = '<script>alert("unsafe")</script>'
        self.edit_json(self.aggregate, "reference.contract.json", lambda obj: obj.update(source=payload))
        report, _ = analyze(self.aggregate)
        rendered = report_html(report)
        self.assertNotIn(payload, rendered)
        self.assertIn("&lt;script&gt;", rendered)
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
        parser = Tags()
        parser.feed(rendered)
        self.assertNotIn("script", parser.tags)
        self.assertNotIn("img", parser.tags)
        self.assertIn("Content-Security-Policy", rendered)
        report["findings"][0]["subject"] = '=HYPERLINK("https://example.invalid")'
        parsed = list(csv.DictReader(io.StringIO(findings_csv(report))))
        self.assertTrue(parsed[0]["subject"].startswith("'="))

    def test_decimal_output_is_exact_text_and_null_is_json_null(self):
        self.assertEqual(json.loads(json_text({"amount": Decimal("0.10"), "absent": None})), {"amount": "0.10", "absent": None})

    def test_cli_success_and_failure_codes(self):
        result = subprocess.run([sys.executable, "-m", "reconciliation", "--config", str(self.definitions), "--output", str(self.output)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)["html_report"]).is_file())
        result = subprocess.run([sys.executable, "-m", "reconciliation", "--config", str(self.root / "missing.json"), "--output", str(self.output)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
