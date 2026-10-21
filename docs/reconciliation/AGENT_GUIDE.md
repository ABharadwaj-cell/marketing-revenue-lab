# Operating and extending reconciliation

Read [the operating guide](README.md), the actual example contracts and `reconciliation/contracts.py` before interpreting a result. User-supplied definitions are assertions. Do not describe them as provider-verified settings.

## Existing entry points

```python
from reconciliation import analyze, run

report, snapshots = analyze("examples/reconciliation/purchases/config.json")
# Pure analysis: no writes or network calls. Values can contain Decimal instances.
folder = run("examples/reconciliation/purchases/config.json", ".private/reconciliation")
# Writes the report and exact input snapshots, or verifies a replay.
```

`reconciliation.reports.json_text(report)` serializes decimal values without binary floating-point conversion. Use that function when exporting the in-memory result. `verify_run(folder)` verifies a completed folder's manifest and checksums. It does not authenticate a source or make a modified manifest trustworthy.

| File | Responsibility |
| --- | --- |
| `reconciliation/contracts.py` | Strict JSON, types, dates, decimals, metric contracts and maturity |
| `reconciliation/engine.py` | CSV validation, scoped parsing, deterministic comparison and evidence |
| `reconciliation/reports.py` | HTML/CSV/JSON serialization, snapshots, checksums and atomic publication |
| `reconciliation/__main__.py` | CLI and documented exit codes |
| `examples/reconciliation/` | Committed synthetic bundles and deterministic regeneration script |
| `tests/test_reconciliation.py` | Behavioral, failure and isolation checks |
| `schemas/reconciliation/v1/` | Versioned configuration, metric-contract and serialized-finding shapes |
| `scripts/benchmark_reconciliation.py` | Reproducible synthetic aggregate throughput check |

## Rules for explanations

1. Lead with `summary.comparison_performed`. If false, explain the contract gate before quoting any native numeric difference.
2. Quote IDs, rule names, CSV line references and native amounts from findings. Distinguish finding counts from affected-record counts.
3. Check source warnings, completeness and maturity. Do not turn a provisional gap into a final tracking-loss claim.
4. Treat duplicates as an established property of the supplied export under its declared contract. Their originating cause requires additional evidence.
5. Keep recommended investigations separate from established facts. Missing orders can have several explanations; the tool supplies no causal diagnosis.
6. Use valid unique-order totals and partial flags. Never add raw duplicate rows, double-count overlapping runs, sum daily distinct users or average ratios.
7. Run local analyses in an explicit workspace and retain the evidence. Do not upload actual exports or publish reports as part of routine diagnosis.

## Adding an adapter later

An adapter must preserve native metric names, exact query settings, native warnings, completeness and original snapshots. It should emit the canonical bundle rather than bypass contract validation. Native exports with multiple dimensions must be aggregated at a deliberately defined grain before import; daily distinct counts cannot be rolled up this way. Explain any transformation as an operator-reviewed mapping.

Live API adapters, MCP resources/tools, an upload UI and an AI explanation layer are not implemented. Future integrations should call the same deterministic functions and return source-backed evidence. They must handle pagination, source-specific maturity, retries and denied access without marking partial imports complete. Do not invent connector capabilities or silently choose semantics to make numbers agree.

Before proposing a change, run all tests, the three example commands and a relevant synthetic benchmark. Add tests for new interpretation or failure behavior. Update the operating guide and examples when their contract or meaning changes. Bump the engine version for a release and include actual measured validation results. Keep existing revenue calculations passing.
