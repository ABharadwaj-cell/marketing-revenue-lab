"""Strict input contracts. A matching label alone never establishes equivalence."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InputError(ValueError):
    """A supplied export or contract is unsafe to interpret."""


def require(condition, message):
    if not condition:
        raise InputError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise InputError(f"Non-finite JSON number: {value}")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError) as exc:
        raise InputError(f"Invalid JSON: {exc}") from exc


def exact_keys(obj, expected, label):
    require(isinstance(obj, dict), f"{label} must be an object")
    require(set(obj) == set(expected),
            f"{label} fields differ: missing={sorted(set(expected)-set(obj))}, "
            f"unknown={sorted(set(obj)-set(expected))}")


def iso_date(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            f"Expected YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"Invalid date: {value}") from exc


def instant(value):
    require(isinstance(value, str), "Timestamp must be text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError(f"Invalid timestamp: {value}") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            f"Timestamp needs an explicit UTC offset: {value}")
    try:
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise InputError("Timestamp is outside the representable UTC range") from exc
    return parsed


def number(value, label, integer=False):
    require(isinstance(value, str) and re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", value),
            f"{label} must be a nonnegative decimal without separators")
    require(len(value) <= 32, f"{label} exceeds 32 characters")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise InputError(f"Invalid {label}") from exc
    require(parsed.is_finite(), f"{label} must be finite")
    require(not integer or parsed == parsed.to_integral_value(), f"{label} must be an integer")
    return parsed


CONTRACT_FIELDS = (
    "version", "source", "project_id", "metric_id", "definition", "aggregation", "unit",
    "currency", "timezone", "grain", "start", "end_exclusive", "filters", "attribution",
    "tracking", "bot_policy", "consent_policy", "exported_at", "mature_after_hours",
    "complete", "native_warnings",
)
SEMANTIC_FIELDS = (
    "project_id", "metric_id", "definition", "aggregation", "unit", "currency", "timezone",
    "grain", "start", "end_exclusive", "filters", "attribution", "tracking", "bot_policy",
    "consent_policy",
)


def validate_contract(c):
    exact_keys(c, CONTRACT_FIELDS, "contract")
    require(type(c["version"]) is int and c["version"] == 1, "Only contract version 1 is supported")
    for field in ("source", "project_id", "metric_id", "definition", "timezone", "attribution",
                  "tracking", "bot_policy", "consent_policy"):
        require(isinstance(c[field], str) and 0 < len(c[field]) <= 2000 and c[field].strip() == c[field],
                f"{field} must be nonempty text without surrounding whitespace")
    require(c["aggregation"] in ("sum", "distinct", "ratio", "records"), "Invalid aggregation")
    require(c["unit"] in ("count", "money", "ratio"), "Invalid unit")
    require((c["aggregation"] == "ratio") == (c["unit"] == "ratio"), "Ratio aggregation needs ratio units")
    require(c["aggregation"] != "distinct" or c["unit"] == "count", "Distinct values need count units")
    require(c["aggregation"] != "records" or c["unit"] == "money", "Purchase records need money units")
    require(c["grain"] in ("day", "period", "record"), "Invalid grain")
    require((c["aggregation"] == "records") == (c["grain"] == "record"), "Record grain requires records aggregation")
    require((isinstance(c["currency"], str) and re.fullmatch(r"[A-Z]{3}", c["currency"]))
            if c["unit"] == "money" else c["currency"] is None, "Currency must be an ISO-style code for money, otherwise null")
    try:
        ZoneInfo(c["timezone"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InputError(f"Unknown IANA timezone: {c['timezone']}") from exc
    require(iso_date(c["start"]) < iso_date(c["end_exclusive"]), "Period must have positive length")
    require(isinstance(c["filters"], dict) and all(isinstance(k, str) and isinstance(v, str)
            for k, v in c["filters"].items()), "Filters must be text key/value pairs")
    instant(c["exported_at"])
    require(type(c["mature_after_hours"]) is int and 0 <= c["mature_after_hours"] <= 8760,
            "Maturity window must be 0..8760 hours")
    require(type(c["complete"]) is bool, "complete must be boolean")
    require(isinstance(c["native_warnings"], list) and all(isinstance(x, str) and x for x in c["native_warnings"]),
            "native_warnings must contain nonempty strings")
    return c


def provisional(c):
    end = datetime.combine(iso_date(c["end_exclusive"]), datetime.min.time(), ZoneInfo(c["timezone"]))
    try:
        ready = end.astimezone(timezone.utc) + timedelta(hours=c["mature_after_hours"])
    except (OverflowError, ValueError) as exc:
        raise InputError("Period end and maturity exceed the supported datetime range") from exc
    return not c["complete"] or instant(c["exported_at"]) < ready or bool(c["native_warnings"])
