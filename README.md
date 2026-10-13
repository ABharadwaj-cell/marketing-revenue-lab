# Marketing Revenue Lab

A **marketing-to-revenue intelligence prototype** for CMOs, Marketing Directors, Demand Generation leaders, and Revenue Operations teams in B2B SaaS and enterprise technology.

Connect synthetic leads and CRM opportunities to **marketing-sourced pipeline, marketing-influenced pipeline, open pipeline, closed-won bookings, recognized revenue, win rates, and cost per accepted opportunity**. Measures are clearly defined and avoid double-counting.

## Status

- **Implemented:** deterministic Python metrics, data validation, synthetic fixtures, unit tests, GitHub Actions workflow, interactive static dashboard.
- **Not yet implemented:** live CRM, production attribution, consent management, financial reconciliation, hosted model inference, or automated acquisition actions.
- **Security:** no customer information, credentials, or confidential CERTIFY data in this public repo.

## Run locally

Python 3.11+; no third-party packages:

```bash
python -m unittest discover -s tests -v
python src/revenue.py
```

## Core definitions

- **Qualified opportunity:** `sales_accepted = true`. Unaccepted records are excluded from pipeline calculations.
- **Marketing-sourced:** the opportunity's original acquisition `source_channel` is in the approved marketing-channel list. One source per opportunity.
- **Marketing-influenced:** at least one approved marketing channel appears in the opportunity's recorded touches, including its source when applicable. A deal can appear in several individual channel views, so **never sum influenced amounts across channels**.
- **Qualified pipeline created:** sum of original deal values for accepted opportunities created in the snapshot period, including deals that subsequently won or lost. This is NOT today's open pipeline.
- **Open pipeline:** current face value of accepted open opportunities.
- **Closed-won bookings:** accepted deal values for `closed_won`. **Not recognized revenue.**
- **Recognized revenue:** separately recorded `recognized_revenue_usd`, never derived automatically from deal value.
- **Win rate:** won / (won + lost); open deals not in denominator.
- **Cost per accepted opportunity:** channel spend / accepted sourced opportunity count; this is NOT CAC or ROI.
- **Attribution vs causation:** source and touch views do not establish incremental contribution.

The `fixtures/synthetic_crm.json` data is an educational example. Values are fictional and denominated in USD.

## Static demo

Enable GitHub Pages at **Settings → Pages → Deploy from a branch → main → /docs**.
The browser dashboard loads `docs/data.json` and calculates interactive channel views without a backend. GitHub Pages is **not** a hosted CRM connector or AI inference service.

## Next milestones

1. Connect an authorized read-only CRM sandbox.
2. Implement canonical lifecycle stages and cross-system identity resolution.
3. Add first-touch and campaign-touch evidence with explicit missingness.
4. Reconcile bookings and recognized revenue against authorized Finance records.
5. Build source/influence cohort drilldowns, forecast calibration and model evaluation.
6. Publish normalized events into the Universal Marketing OS.

No real company data should be published without documented approval.
