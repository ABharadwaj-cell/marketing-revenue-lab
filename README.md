# Marketing Revenue Lab

**Traffic is useful. Pipeline tells you whether it reached the business.**

If you run marketing alone, it's easy to spend the week improving campaigns and still struggle to answer the question a CEO asks: *How much qualified pipeline did marketing actually contribute?* Even experienced marketing leaders run into trouble when sourced, influenced, won, and recognized revenue are mixed together.

Marketing Revenue Lab is a working, deterministic analytics prototype designed to make those distinctions visible and understandable.

[Read the five-minute executive walkthrough](docs/START_HERE.md) · [Run the reconciliation preview](docs/reconciliation/README.md) · [Review the Python calculations](src/revenue.py)

> **Project status:** Private development. A tested pipeline calculation engine, an interactive synthetic dashboard, and a local CSV reconciliation preview. No live analytics/CRM integration, model inference, actual revenue attribution, deployed API or public site.

## New: explain conflicting analytics exports

The reconciliation preview compares explicitly defined aggregate metrics or matches tracked purchases against reference orders. It blocks incompatible definitions, preserves original input bytes, checks duplicates and missing records, and saves HTML, CSV and JSON evidence locally.

```bash
python -m reconciliation --config examples/reconciliation/purchases/config.json --output .private/reconciliation
```

The synthetic example has 100 reference orders and 103 observed rows. After finding five extra duplicate rows and excluding two test rows, it identifies 96 matches and four missing orders. [Read the operating guide, input contracts, limits and measured validation](docs/reconciliation/README.md). This module is separate from the CRM pipeline example below.

## Who this is for

**Founder running marketing:** Understand whether leads turned into sales-accepted opportunities and how many of those opportunities are still open, won, or lost.

**CMO / VP / Director of Marketing:** Separate sourced from influenced performance, question channel efficiency, and make investment decisions using defensible definitions.

**Demand Generation and RevOps professionals:** Trace opportunity IDs to acquisition sources, recorded marketing touches, pipeline status, bookings and separately entered revenue.

**Engineer / analyst:** Run the unit-tested calculation logic, validate data contracts, and prepare for a permissioned CRM and Finance integration.

## Start with a business question

> Paid search is generating inquiries. How much qualified pipeline is actually marketing-sourced, how much did the channel influence, and what revenue is recorded against those deals?

Use the demo's **Attribution lens** selector to compare *sourced* and *influenced*. Then filter to one channel and examine the actual fictional opportunities included in each result.

In the included sample, the all-channel marketing-sourced view shows **$680,000 in qualified pipeline created** from seven sales-accepted opportunities. The all-channel marketing-influenced view shows **$990,000** across nine unique opportunities because it also includes deals originally sourced through Sales that had recorded marketing touches. **Do not add those two figures.**

The same sample records **$200,000 in closed-won bookings** and **$70,000 in separately recorded recognized revenue** in the sourced view. Bookings and recognized revenue are different measurements.

**These figures are fictional examples, not performance results from a business.**

## What the dashboard actually measures

| Metric | Plain-language meaning | What not to assume |
| --- | --- | --- |
| Accepted opportunities | Deals Sales has accepted as real opportunities in this sample | Not all leads are qualified |
| Marketing-sourced pipeline | Original opportunity value attached to approved marketing acquisition sources | Not necessarily current open pipeline or closed revenue |
| Marketing-influenced pipeline | Unique accepted opportunities with any recorded marketing touch | Not exclusive credit and not incremental lift |
| Open pipeline | Accepted opportunities currently open | Not guaranteed future revenue |
| Closed-won bookings | Recorded value of deals marked won | Not automatically invoiced or recognized revenue |
| Recognized revenue | Explicit separate revenue values provided in the fixture | Not derived from opportunity value |
| Win rate | Won divided by won plus lost | Open deals are excluded |
| Cost per accepted opportunity | Marketing channel spend divided by sourced accepted opportunity count | Not CAC, payback, or marketing ROI |

A deal can appear in more than one **channel-specific influenced** view. The overall influenced figure deduplicates by opportunity. Never total the influenced channel bars as if they were mutually exclusive.

## What should you do with the answer?

Consider a channel producing plenty of raw leads but few accepted opportunities. The next decision may be to investigate audience targeting, landing-page promises, lead qualification, CRM routing or Sales follow-up. Reporting more traffic doesn't solve that problem.

A useful marketing-to-revenue workflow is:

**Acquisition source → Lead → Sales acceptance → Opportunity → Stage progress → Won/lost → Bookings → Recorded revenue.**

A production system also needs campaign touches, account identity resolution, buying-group context, time windows, costs, attribution governance and Sales/Finance reconciliation before it can support company reporting.

## Try it without code

1. Run `python -m http.server 8000 --bind 127.0.0.1 --directory docs` and open `http://127.0.0.1:8000/` locally. This serves the synthetic dashboard only.
2. Choose *Marketing-sourced* and **All marketing channels**.
3. Read the pipeline, open pipeline, bookings and recorded revenue cards.
4. Switch to *Marketing-influenced*. Notice the larger, non-additive coverage.
5. Filter to **Organic Search** or **Paid Search** and inspect the opportunity table.
6. Write down which commercial decision each number can support, and which information is still missing.

[The founder and executive walkthrough](docs/START_HERE.md) provides an example.

## Run and inspect the engine

Python 3.11+, no paid APIs or third-party Python libraries required.

```bash
python -m unittest discover -s tests -v
python src/revenue.py
```

The calculation engine lives in `src/revenue.py`. The canonical synthetic dataset is `docs/data.json`, used by both the Python calculations and the static website. `tests/test_revenue.py` verifies expected numbers and rejects several bad input conditions.

## Limitations and responsibility

- **No causal attribution:** a tracked touch does not prove the channel caused a deal.
- **No live CRM or Finance source:** all numbers are sample values, and timing/identity assumptions need much more rigor before production use.
- **Not a forecasting engine or financial ledger:** no automatic revenue recognition, CAC or return-on-investment calculation.
- **Not an AI model:** the intentionally deterministic calculations are the trustworthy foundation an AI explanation layer would sit on top of.
- **Synthetic repository data only:** don't commit real customer records, CRM exports, company financials or access tokens. Local reconciliation runs retain raw input snapshots; keep actual exports under `.private/`.

## Next build steps

Authorized CRM sandbox → account/contact/deal joins → source and touch provenance → funnel cohort analysis → sales handoff checks → Finance reconciliation → confidence and missing-data indicators → budget/forecast scenarios → integration with the universal Marketing OS.

Related projects: [Market Intelligence MCP](https://github.com/ABharadwaj-cell/marketing-market-intelligence-mcp) and [Marketing Practice Radar](https://github.com/ABharadwaj-cell/marketing-practice-radar).

