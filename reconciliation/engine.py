"""Pure reconciliation rules. No network calls, credentials, or model-generated causes."""

import csv
import hashlib
import io
from collections import Counter
from datetime import timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

from .contracts import (InputError, SEMANTIC_FIELDS, exact_keys, instant, iso_date,
                        number, provisional, require, strict_json, validate_contract)

AGG_HEADERS = ["period_start", "period_end_exclusive", "value", "numerator", "denominator"]
ORDER_HEADERS = ["order_id", "occurred_at", "status", "environment", "amount", "currency"]
CONFIG_FIELDS = ["version", "workspace", "workflow", "comparison", "tolerance", "reference", "observed"]
CLASSES = ("equivalent_under_conditions", "related_not_interchangeable", "unsupported")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_rows(raw, headers, label):
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.reader(stream, strict=True)
        actual = next(reader, None)
        require(actual is not None and len(actual) == len(set(actual)) and set(actual) == set(headers),
                f"{label}: headers must be exactly {headers}, without duplicates")
        for cells in reader:
            line = reader.line_num
            require(len(cells) == len(actual), f"{label}: wrong column count at CSV line {line}")
            require(all("\x00" not in v for v in cells), f"{label}: NUL character at line {line}")
            yield line, dict(zip(actual, cells))
    except (UnicodeError, csv.Error) as exc:
        raise InputError(f"{label}: invalid UTF-8 CSV: {exc}") from exc


def aggregate(raw, c, role):
    require(c["aggregation"] != "records", f"{role}: aggregate workflow requires aggregate values")
    rows = {}
    for line, row in csv_rows(raw, AGG_HEADERS, role):
        start, end = iso_date(row["period_start"]), iso_date(row["period_end_exclusive"])
        require(iso_date(c["start"]) <= start < end <= iso_date(c["end_exclusive"]),
                f"{role}: CSV line {line} is outside the contract period")
        require((end == start + timedelta(days=1)) if c["grain"] == "day"
                else (str(start) == c["start"] and str(end) == c["end_exclusive"]),
                f"{role}: CSV line {line} violates declared grain")
        key = (str(start), str(end))
        require(key not in rows, f"{role}: duplicate/overlapping period at CSV line {line}")
        if c["aggregation"] == "ratio":
            require(row["value"] == "", f"{role}: ratio value must be blank; supply components")
            numerator = number(row["numerator"], "numerator", integer=True)
            denominator = number(row["denominator"], "denominator", integer=True)
            value = numerator / denominator if denominator else None
        else:
            require(row["numerator"] == row["denominator"] == "", f"{role}: unexpected ratio components")
            value = number(row["value"], "value", integer=c["unit"] == "count") if row["value"] != "" else None
            numerator = denominator = None
        rows[key] = {"line": line, "value": value, "numerator": numerator, "denominator": denominator}
    return rows


def orders(raw, c, role):
    require(c["aggregation"] == "records", f"{role}: purchase workflow requires record contracts")
    require(c["filters"] == {"status": "completed", "environment": "production"},
            "Purchase preview supports only completed, production orders")
    groups, excluded = {}, []
    raw_count = 0
    for line, row in csv_rows(raw, ORDER_HEADERS, role):
        raw_count += 1
        require(row["order_id"] and row["order_id"].strip() == row["order_id"] and len(row["order_id"]) <= 256,
                f"{role}: missing/invalid order_id at CSV line {line}; aggregate exports cannot identify missing orders")
        occurred = instant(row["occurred_at"])
        amount = number(row["amount"], "amount")
        require(len(row["currency"]) == 3 and row["currency"].isascii() and row["currency"].isupper()
                and row["currency"].isalpha(), f"{role}: invalid currency at line {line}")
        require(row["status"] and row["environment"], f"{role}: missing scope fields at line {line}")
        day = occurred.astimezone(ZoneInfo(c["timezone"])).date()
        reasons = [k for k, v in c["filters"].items() if row[k] != v]
        if not iso_date(c["start"]) <= day < iso_date(c["end_exclusive"]):
            reasons.append("outside_period")
        if reasons:
            excluded.append({"line": line, "order_id": row["order_id"], "reasons": reasons})
            continue
        require(row["currency"] == c["currency"], f"{role}: mixed currency at line {line}; no FX conversion is available")
        # A completed order ID is unique under this contract. Conflicts are quarantined.
        signature = (occurred.astimezone(timezone.utc).isoformat(), amount, row["currency"])
        groups.setdefault(row["order_id"], []).append({"line": line, "signature": signature, "amount": amount})
    valid, duplicates, conflicts = {}, [], []
    for order_id, records in groups.items():
        if len({r["signature"] for r in records}) != 1:
            conflicts.append({"order_id": order_id, "lines": [r["line"] for r in records]})
        else:
            valid[order_id] = records[0]
            if len(records) > 1:
                duplicates.append({"order_id": order_id, "lines": [r["line"] for r in records], "extra_rows": len(records)-1})
    return {"valid": valid, "duplicates": duplicates, "conflicts": conflicts,
            "excluded": excluded, "raw_rows": raw_count, "eligible_rows": sum(map(len, groups.values()))}


def finding(rule, classification, subject, evidence, next_check, severity="warning"):
    return {"rule": rule, "classification": classification, "severity": severity,
            "subject": subject, "evidence": evidence, "next_check": next_check}


def scope_findings(config, contracts):
    ref, obs = contracts["reference"], contracts["observed"]
    differences = {k: {"reference": ref[k], "observed": obs[k]} for k in SEMANTIC_FIELDS if ref[k] != obs[k]}
    mode = config["comparison"]["class"]
    if mode != "equivalent_under_conditions" or differences:
        category = "expected_definition_difference" if mode == "related_not_interchangeable" else "not_comparable"
        return [finding("CONTRACT_SCOPE", category, "Comparison blocked",
                        {"declared_class": mode, "rationale": config["comparison"]["rationale"], "differences": differences},
                        "Align the metric definition and scope, or keep these metrics separate.")]
    result = []
    for role, c in contracts.items():
        if provisional(c):
            result.append(finding("SOURCE_PROVISIONAL", "provisional_source_changing", role,
                                  {k: c[k] for k in ("complete", "exported_at", "mature_after_hours", "native_warnings")},
                                  "Re-export the complete period after the source maturity window; inspect source warnings."))
    return result


def variance(reference, observed, tolerance):
    delta = observed - reference
    relative = abs(delta) / abs(reference) if reference else (Decimal(0) if delta == 0 else None)
    allowed = max(number(tolerance["absolute"], "absolute tolerance"),
                  abs(reference) * number(tolerance["relative"], "relative tolerance"))
    return {"reference": reference, "observed": observed, "delta": delta,
            "absolute_relative_delta": relative, "allowed_absolute_delta": allowed,
            "within_tolerance": abs(delta) <= allowed}


def total(rows, c):
    values = list(rows.values())
    if not values:
        return {"value": None, "reason": "Empty export; missing is not zero."}
    if c["aggregation"] == "distinct" and c["grain"] != "period":
        return {"value": None, "reason": "Daily distinct counts cannot be summed into period distinct users."}
    if c["aggregation"] == "ratio":
        numerator = sum(r["numerator"] for r in values)
        denominator = sum(r["denominator"] for r in values)
        return {"value": numerator / denominator if denominator else None,
                "numerator": numerator, "denominator": denominator, "method": "sum components, then divide"}
    if any(r["value"] is None for r in values):
        return {"value": None, "reason": "Null value; missing is not zero."}
    return {"value": sum(r["value"] for r in values), "method": "sum" if c["aggregation"] == "sum" else "native period value"}


def compare_aggregate(parsed, contracts, config, findings):
    ref, obs = parsed["reference"], parsed["observed"]
    c = contracts["reference"]
    keys = [(c["start"], c["end_exclusive"])]
    if c["grain"] == "day":
        start, end = iso_date(c["start"]), iso_date(c["end_exclusive"])
        keys = ((str(start + timedelta(days=i)), str(start + timedelta(days=i+1))) for i in range((end-start).days))
    counts = Counter()
    unstable = any(provisional(x) for x in contracts.values())
    for key in keys:
        a, b = ref.get(key), obs.get(key)
        evidence = {"period_start": key[0], "period_end_exclusive": key[1],
                    "reference": a, "observed": b}
        if a is None or b is None or a["value"] is None or b["value"] is None:
            counts["missing_or_undefined_periods"] += 1
            if a is None or b is None or c["aggregation"] != "ratio":
                counts["incomplete_coverage"] += 1
            findings.append(finding("AGG_MISSING", "provisional_source_changing" if unstable else "unexplained_variance",
                                    "Missing or undefined period", evidence,
                                    "Inspect the raw export and zero-fill policy; do not replace absence with zero."))
            continue
        result = variance(a["value"], b["value"], config["tolerance"])
        counts["periods_compared"] += 1
        if result["within_tolerance"]:
            counts["within_tolerance_periods"] += 1
        else:
            counts["outside_tolerance_periods"] += 1
            evidence["variance"] = result
            findings.append(finding("AGG_VARIANCE", "provisional_source_changing" if unstable else "unexplained_variance",
                                    "Metric value differs", evidence,
                                    "Inspect source collection, filters and processing with these exact period rows; cause is unproven."))
    if counts["within_tolerance_periods"]:
        findings.append(finding("AGG_WITHIN", "within_tolerance", "Compatible periods within tolerance",
                                {"period_count": counts["within_tolerance_periods"], "tolerance": config["tolerance"]},
                                "No discrepancy outside the declared threshold in these periods. This does not prove collection accuracy.", "info"))
    totals = {role: total(rows, contracts[role]) for role, rows in parsed.items()}
    # Partial daily coverage never masquerades as a complete period total.
    if counts["incomplete_coverage"]:
        for value in totals.values():
            value["partial"] = True
    period_variance = None
    if not counts["incomplete_coverage"] and all(x["value"] is not None for x in totals.values()):
        period_variance = variance(totals["reference"]["value"], totals["observed"]["value"], config["tolerance"])
        if not period_variance["within_tolerance"]:
            findings.append(finding("AGG_TOTAL_VARIANCE", "provisional_source_changing" if unstable else "unexplained_variance",
                                    "Complete period total differs", {"variance": period_variance, "totals": totals},
                                    "Inspect the period exceptions and cumulative small differences. A period total can fail even when individual days pass."))
    return {k: counts[k] for k in ("periods_compared", "within_tolerance_periods", "outside_tolerance_periods", "missing_or_undefined_periods")} | {"native_totals": totals, "period_total_variance": period_variance}


def compare_orders(parsed, contracts, config, findings):
    counts = {}
    for role, data in parsed.items():
        counts[role] = {"raw_rows": data["raw_rows"], "eligible_rows": data["eligible_rows"],
                        "excluded_rows": len(data["excluded"]), "valid_unique_orders": len(data["valid"]),
                        "duplicate_extra_rows": sum(x["extra_rows"] for x in data["duplicates"]),
                        "conflicting_ids": len(data["conflicts"])}
        for duplicate in data["duplicates"]:
            findings.append(finding("PUR_DUPLICATE", "confirmed_processing_defect", f"{role}: duplicate order rows",
                                    {"role": role, **duplicate},
                                    "Inspect export generation and event deduplication. The duplicate export rows are confirmed; their origin is unproven."))
        for conflict in data["conflicts"]:
            findings.append(finding("PUR_CONFLICT", "unexplained_variance", f"{role}: conflicting order ID quarantined",
                                    {"role": role, **conflict}, "Resolve the conflicting rows before using this order or a complete revenue total.", "error"))
        if data["excluded"]:
            findings.append(finding("PUR_EXCLUDED", "expected_definition_difference", f"{role}: rows excluded by explicit scope",
                                    {"role": role, "rows": data["excluded"]}, "Check that completed/production and period filters reflect the intended decision.", "info"))
    ref, obs = parsed["reference"]["valid"], parsed["observed"]["valid"]
    quarantine = {x["order_id"] for data in parsed.values() for x in data["conflicts"]}
    usable_ref, usable_obs = set(ref)-quarantine, set(obs)-quarantine
    matched = usable_ref & usable_obs
    missing, unexpected = usable_ref-usable_obs, usable_obs-usable_ref
    unstable = any(provisional(x) for x in contracts.values())
    classification = "provisional_source_changing" if unstable else "unexplained_variance"
    for rule, ids, role in (("PUR_MISSING", missing, "reference"), ("PUR_UNEXPECTED", unexpected, "observed")):
        for order_id in sorted(ids):
            findings.append(finding(rule, classification, order_id,
                                    {"order_id": order_id, "role": role, "row": parsed[role]["valid"][order_id]},
                                    "Inspect the corresponding source order and tracking record. Missing from this export does not establish the cause."))
    amount_mismatches = 0
    for order_id in sorted(matched):
        result = variance(ref[order_id]["amount"], obs[order_id]["amount"], config["tolerance"])
        if not result["within_tolerance"]:
            amount_mismatches += 1
            findings.append(finding("PUR_AMOUNT", classification, order_id,
                                    {"order_id": order_id, "reference_line": ref[order_id]["line"],
                                     "observed_line": obs[order_id]["line"], "variance": result},
                                    "Check tax, refunds, discounts and amount definitions for this order; no currency conversion was applied."))
    if len(matched) > amount_mismatches:
        findings.append(finding("PUR_MATCHED", "within_tolerance", "Orders with matching IDs",
                                {"matched_ids": len(matched), "amounts_within_tolerance": len(matched)-amount_mismatches},
                                "Matching IDs establish record overlap; they do not establish attribution or causal lift.", "info"))
    counts.update({"matched_orders": len(matched), "missing_orders": len(missing),
                   "unexpected_orders": len(unexpected), "amount_mismatches": amount_mismatches,
                   "quarantined_ids": len(quarantine),
                   "valid_order_amount_totals": {role: sum((x["amount"] for x in data["valid"].values()), Decimal(0))
                                                  for role, data in parsed.items()},
                   "totals_partial": bool(quarantine)})
    return counts


def read_inputs(config_path):
    path = Path(config_path).resolve(strict=True)
    config_raw = path.read_bytes()
    config = strict_json(config_raw)
    exact_keys(config, CONFIG_FIELDS, "config")
    require(type(config["version"]) is int and config["version"] == 1, "Only config version 1 is supported")
    import re
    require(isinstance(config["workspace"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", config["workspace"]), "Invalid workspace name")
    require(config["workflow"] in ("aggregate", "purchases"), "Unknown workflow")
    exact_keys(config["comparison"], ["class", "rationale"], "comparison")
    require(config["comparison"]["class"] in CLASSES, "Unknown comparison class")
    require(isinstance(config["comparison"]["rationale"], str) and config["comparison"]["rationale"].strip(), "Comparison rationale is required")
    exact_keys(config["tolerance"], ["absolute", "relative"], "tolerance")
    for key, value in config["tolerance"].items():
        number(value, key + " tolerance")
    snapshots = {"config.json": config_raw}
    contracts, raw = {}, {}
    for role in ("reference", "observed"):
        exact_keys(config[role], ["contract", "csv"], role)
        for kind, filename in config[role].items():
            require(isinstance(filename, str) and filename and not Path(filename).is_absolute(), "Input paths must be relative to the config folder")
            source = (path.parent / filename).resolve(strict=True)
            require(source.is_relative_to(path.parent), "Input path escapes the config folder")
            require(source.is_file(), "Input must be a regular file")
            content = source.read_bytes()
            snapshots[f"{role}.{'contract.json' if kind == 'contract' else 'csv'}"] = content
            if kind == "contract":
                contracts[role] = validate_contract(strict_json(content))
            else:
                raw[role] = content
    return config, contracts, raw, snapshots


def analyze(config_path):
    """Return (report, immutable input bytes) without writing or contacting a service."""
    from . import __version__
    with localcontext() as context:
        context.prec = 80
        config, contracts, raw, snapshots = read_inputs(config_path)
        input_hashes = {name: digest(data) for name, data in snapshots.items()}
        import json
        engine_hashes = {p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))}
        engine_fingerprint = digest(json.dumps(engine_hashes, sort_keys=True).encode())
        run_id = digest(json.dumps({"engine_version": __version__, "engine_fingerprint": engine_fingerprint,
                                    "inputs": input_hashes}, sort_keys=True).encode())[:24]
        parser = aggregate if config["workflow"] == "aggregate" else orders
        parsed = {role: parser(data, contracts[role], role) for role, data in raw.items()}
        findings = scope_findings(config, contracts)
        blocked = any(f["rule"] == "CONTRACT_SCOPE" for f in findings)
        if blocked:
            summary = {"comparison_performed": False, "reason": "Declared class or semantic scope blocks numerical reconciliation"}
        else:
            compare = compare_aggregate if config["workflow"] == "aggregate" else compare_orders
            summary = {"comparison_performed": True, **compare(parsed, contracts, config, findings)}
        for i, item in enumerate(findings, 1):
            item["id"] = f"F{i:05d}"
        return {"schema_version": 1, "engine_version": __version__, "run_id": run_id,
                "engine_fingerprint": engine_fingerprint, "engine_source_sha256": engine_hashes,
                "workspace": config["workspace"], "workflow": config["workflow"],
                "comparison": config["comparison"], "tolerance": config["tolerance"],
                "contracts": contracts, "input_sha256": input_hashes,
                "summary": summary, "classifications": dict(Counter(f["classification"] for f in findings)),
                "findings": findings,
                "limits": ["Contracts are operator assertions, not independently verified source settings.",
                           "CSV exports only. No live connectors, identity inference, FX conversion or causal attribution.",
                           "A reference export is an asserted comparison baseline, not independently established ground truth."]}, snapshots
