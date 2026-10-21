"""Escaped reports, input snapshots and atomic, content-addressed run directories."""

import csv
import html
import io
import json
import shutil
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .contracts import require, strict_json
from .engine import analyze, digest


def json_text(value):
    def encode(item):
        if isinstance(item, Decimal):
            return format(item, "f")
        raise TypeError(type(item).__name__)
    return json.dumps(value, default=encode, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def csv_safe(value):
    text = str(value)
    # Spreadsheet programs can evaluate quoted CSV strings too.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) or text.startswith(("\t", "\r", "\n")) else text


def findings_csv(report):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    fields = ["id", "rule", "classification", "severity", "subject", "evidence", "next_check"]
    writer.writerow(fields)
    for finding in report["findings"]:
        writer.writerow([csv_safe(json_text(finding[key]).strip() if key == "evidence" else finding[key]) for key in fields])
    return stream.getvalue()


def report_html(report):
    escape = lambda value: html.escape(str(value), quote=True)
    summary = report["summary"]
    def table(rows):
        return "<table><tbody>" + "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows) + "</tbody></table>"
    def cards(items):
        return "<div class='cards'>" + "".join(f"<div class='card'><strong>{escape(value)}</strong><span>{escape(label)}</span></div>" for label, value in items) + "</div>"
    if not summary["comparison_performed"]:
        result = "<h3>Comparison blocked</h3><p>The declared definitions or scope do not support a numerical reconciliation. Review the contract finding below.</p>"
    elif report["workflow"] == "purchases":
        result = cards([(label, summary[key]) for label, key in (("Matching order IDs", "matched_orders"), ("Missing from observed", "missing_orders"), ("Unexpected observed IDs", "unexpected_orders"), ("Amount mismatches", "amount_mismatches"))])
        result += table([("Export measure", "Reference", "Observed")] + [(label, summary["reference"][key], summary["observed"][key]) for label, key in (("Raw rows", "raw_rows"), ("Eligible rows", "eligible_rows"), ("Duplicate extra rows", "duplicate_extra_rows"), ("Rows excluded by scope", "excluded_rows"), ("Valid unique orders", "valid_unique_orders"), ("Conflicting IDs", "conflicting_ids"))])
        result += table([("Valid order amounts", report["contracts"]["reference"]["currency"]), ("Reference", summary["valid_order_amount_totals"]["reference"]), ("Observed", summary["valid_order_amount_totals"]["observed"])])
        if summary["totals_partial"]:
            result += "<p><strong>Partial totals:</strong> conflicting order IDs are quarantined. Resolve them before interpreting complete order amounts.</p>"
    else:
        result = cards([(label, summary[key]) for label, key in (("Periods compared", "periods_compared"), ("Periods within tolerance", "within_tolerance_periods"), ("Periods outside tolerance", "outside_tolerance_periods"), ("Missing or undefined", "missing_or_undefined_periods"))])
        c = report["contracts"]["reference"]
        result += f"<p>Unit: {escape(c['unit'])}{' (' + escape(c['currency']) + ')' if c['currency'] else ''}. Timezone: {escape(c['timezone'])}.</p>"
        total_rows = [("Period totals", "Value or limitation")]
        for role, item in summary["native_totals"].items():
            value = item["value"] if item["value"] is not None else item.get("reason", "Undefined ratio")
            total_rows.append((role.capitalize(), str(value) + (" (partial)" if item.get("partial") else "")))
        result += table(total_rows)
        if summary["period_total_variance"] is not None:
            variance = summary["period_total_variance"]
            result += f"<p>Complete period delta: <strong>{escape(variance['delta'])}</strong>. Allowed absolute delta: {escape(variance['allowed_absolute_delta'])}. <strong>{'Within tolerance' if variance['within_tolerance'] else 'Outside tolerance'}.</strong></p>"
    count_rows = "".join(f"<tr><td>{escape(k.replace('_', ' '))}</td><td>{v}</td></tr>" for k, v in report["classifications"].items())
    blocks = []
    for f in report["findings"]:
        blocks.append(f"<article><p class='label'>{escape(f['id'])} · {escape(f['rule'])} · {escape(f['classification'].replace('_',' '))}</p>"
                      f"<h3>{escape(f['subject'])}</h3><details><summary>View source rows and measured evidence</summary><pre>{escape(json_text(f['evidence']))}</pre></details>"
                      f"<p><strong>Next check:</strong> {escape(f['next_check'])}</p></article>")
    limitations = "".join(f"<li>{escape(value)}</li>" for value in report["limits"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Reconciliation report · {escape(report['workspace'])}</title>
<style>body{{background:#f4f6f8;color:#172533;font:16px/1.55 system-ui,sans-serif;margin:0}}main{{max-width:1050px;margin:auto;padding:32px 20px}}header,article,section{{background:white;border:1px solid #dce2e8;border-radius:12px;padding:24px;margin-bottom:20px}}h1{{font-size:32px;line-height:1.15}}h2{{font-size:23px}}h3{{font-size:19px}}.label{{font-size:13px;color:#405975;overflow-wrap:anywhere}}pre{{background:#eef2f5;padding:16px;overflow:auto;font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}}td,th{{text-align:left;border-bottom:1px solid #dce2e8;padding:8px 14px 8px 0;overflow-wrap:anywhere}}table{{width:100%}}details{{margin-top:16px}}summary{{cursor:pointer;font-weight:600}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:24px}}.card{{background:#eef2f5;border-radius:8px;padding:16px}}.card strong{{font-size:30px;display:block}}.card span{{font-size:14px}}@media print{{article,section{{break-inside:avoid}}body{{background:white}}details>pre{{display:block}}}}</style></head>
<body><main><header><p class="label">LOCAL EXPORT RECONCILIATION · PREVIEW {escape(report['engine_version'])}</p>
<h1>What differs, and what the exports can establish</h1>
<p>Workspace: <strong>{escape(report['workspace'])}</strong> · Workflow: {escape(report['workflow'])}</p>
<p class="label">Run {escape(report['run_id'])}</p>
<p>Findings describe these supplied files. Operator-defined contracts determine what is comparable. A discrepancy alone does not identify its cause.</p></header>
<section><h2>Result</h2>{result}<details><summary>Machine-readable result</summary><pre>{escape(json_text(report['summary']))}</pre></details><table><thead><tr><th>Finding classification</th><th>Count</th></tr></thead><tbody>{count_rows}</tbody></table>
<p>Counts above are findings, not a count of affected orders or a demand ranking. Use the result fields for record counts.</p></section>
<section><h2>Definitions and provenance</h2><details><summary>Metric contracts, tolerances and input hashes</summary><pre>{escape(json_text({k:report[k] for k in ('comparison','tolerance','contracts','input_sha256')}))}</pre></details>
<p>CSV line references point to the preserved <code>inputs/reference.csv</code> or <code>inputs/observed.csv</code> snapshot. Numeric values in JSON are decimal strings to preserve precision.</p></section>
<h2>Evidence and next checks</h2>{''.join(blocks)}
<section><h2>Limits</h2><ul>{limitations}</ul><p>Raw exports and record IDs remain in this local run folder. Review its contents before sharing.</p></section>
</main></body></html>"""


def verify_run(folder, expected_inputs=None, expected_fingerprint=None):
    require(folder.is_dir() and not folder.is_symlink(), "Existing run is not a regular directory")
    manifest_path = folder / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "Existing run lacks a valid manifest")
    manifest = strict_json(manifest_path.read_bytes())
    require(isinstance(manifest, dict), "Existing run manifest must be an object")
    require(manifest.get("status") == "complete" and manifest.get("run_id") == folder.name, "Existing run manifest is invalid")
    require(isinstance(manifest.get("files"), dict), "Existing run lacks checksums")
    if expected_inputs is not None:
        require(manifest.get("input_sha256") == expected_inputs, "Run ID collision or different inputs")
    if expected_fingerprint is not None:
        require(manifest.get("engine_fingerprint") == expected_fingerprint, "Existing run has a different engine fingerprint")
    expected = set(manifest["files"]) | {"manifest.json"}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() or p.is_symlink()}
    require(actual == expected, "Existing run file set changed; use a fresh output root")
    for name, checksum in manifest["files"].items():
        candidate = folder / name
        require(not candidate.is_symlink() and candidate.resolve().is_relative_to(folder.resolve()), "Run file escapes its directory")
        require(digest(candidate.read_bytes()) == checksum, f"Saved run checksum mismatch: {name}")
    require(isinstance(manifest.get("input_sha256"), dict), "Existing run lacks input hashes")
    for name, checksum in manifest["input_sha256"].items():
        require(manifest["files"].get(f"inputs/{name}") == checksum, f"Input metadata and snapshot checksum differ: {name}")
    return manifest


def run(config_path, output_root):
    """Analyze first, publish a complete directory once, and verify replays."""
    report, snapshots = analyze(config_path)
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / report["workspace"]
    require(not workspace.is_symlink(), "Workspace may not be a symlink")
    workspace.mkdir(exist_ok=True)
    require(workspace.resolve().parent == root, "Workspace escapes output root")
    final = workspace / report["run_id"]
    if final.exists() or final.is_symlink():
        verify_run(final, report["input_sha256"], report["engine_fingerprint"])
        return final
    stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=workspace))
    try:
        payloads = {"report.json": json_text(report).encode(), "report.html": report_html(report).encode(),
                    "findings.csv": findings_csv(report).encode()}
        payloads.update({f"inputs/{name}": data for name, data in snapshots.items()})
        for name, raw in payloads.items():
            target = stage / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw)
            target.chmod(0o600)
        manifest = {"status": "complete", "run_id": report["run_id"], "engine_version": report["engine_version"],
                    "engine_fingerprint": report["engine_fingerprint"], "engine_source_sha256": report["engine_source_sha256"],
                    "created_at": datetime.now(timezone.utc).isoformat(), "input_sha256": report["input_sha256"],
                    "files": {name: digest(data) for name, data in payloads.items()}}
        (stage / "manifest.json").write_text(json_text(manifest), encoding="utf-8")
        (stage / "manifest.json").chmod(0o600)
        try:
            stage.rename(final)
        except OSError:
            # Another writer can finish an identical run while this one renders.
            if not final.exists():
                raise
            verify_run(final, report["input_sha256"], report["engine_fingerprint"])
        verify_run(final, report["input_sha256"], report["engine_fingerprint"])
        return final
    finally:
        if stage.exists():
            shutil.rmtree(stage)
