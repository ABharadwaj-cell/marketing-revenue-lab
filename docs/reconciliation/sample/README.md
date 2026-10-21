# Synthetic purchase report

[Open the generated HTML report](synthetic-purchases/b4357bd9a65727260f077f85/report.html) · [JSON evidence](synthetic-purchases/b4357bd9a65727260f077f85/report.json) · [Findings CSV](synthetic-purchases/b4357bd9a65727260f077f85/findings.csv) · [Manifest](synthetic-purchases/b4357bd9a65727260f077f85/manifest.json)

100 reference orders; 103 observed rows; 5 duplicate extras; 2 test rows excluded; 96 matching IDs; 4 missing IDs. These are synthetic fixtures, not a customer performance result.

The complete content-addressed run folder includes exact input snapshots and verified file hashes. Download or serve this directory locally to view HTML; GitHub's source view does not render a report page.

Regenerate after changing engine source:

```bash
python scripts/verify_reconciliation.py --result docs/reconciliation/verification.json --sample-root docs/reconciliation/sample
```

The script runs all behavioral tests and three CLI smoke checks before saving a sample. Old run directories remain immutable; update the index to the current run and remove superseded committed synthetic samples deliberately when preparing a release.
