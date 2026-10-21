# Start here: Follow marketing work all the way to revenue

You don't need to speak in attribution jargon to use this project. The question is simple: **What happened after marketing attracted somebody's attention?**

The demo uses a fictional B2B SaaS business and ten fictional opportunity records, including one that Sales never accepted. Nothing here is your organization's financial performance.

## If you're the founder and the only marketer

From the repository root, run `python -m http.server 8000 --bind 127.0.0.1 --directory docs` and open `http://127.0.0.1:8000/` for the local synthetic dashboard. The project is in private development.

If your immediate question is why two analytics reports disagree, use the separate [analytics reconciliation operating guide](reconciliation/README.md). It has a runnable CSV example and a synthetic purchase report, with exact input contracts and limitations.

1. Leave the lens on **Marketing-sourced**, all channels. You're looking at deals whose original acquisition channel was marketing.
2. Notice **qualified pipeline created**. It is not the same as the amount currently open or the amount won.
3. Notice **closed-won bookings** versus **recognized revenue**. A signed contract isn't automatically revenue earned and recognized.
4. Change to **Marketing-influenced**. Now you also see accepted deals originally generated elsewhere, such as Sales outbound, with recorded marketing touches.
5. Select a channel. Look at the opportunity rows behind the number. Your question is now: *Did this channel produce the right kind of business opportunity, and what happened afterward?*

In the sample, sourced pipeline created is **$680,000** from seven opportunities. Influenced pipeline is **$990,000** from nine unique opportunities. These are separate perspectives on overlapping deals, **not $1.67 million to add together**.

Your real next action would be to confirm deal quality with Sales and examine conversion over time before changing your marketing investment.

## If you lead marketing or Revenue Operations

Use the dashboard to challenge channel performance on more than clicks and leads.

| Ask | Where to look | Caution |
| --- | --- | --- |
| Which channel originally brought an accepted opportunity? | Marketing-sourced filter | Depends on consistent source tagging |
| Which opportunities had a recorded marketing interaction? | Marketing-influenced filter | Touches overlap; credit is not causal |
| What's still in play? | Open pipeline | Value is not weighted or forecast |
| What was won? | Closed-won bookings | Deal value is not recognized revenue |
| What revenue is separately recorded? | Recognized revenue | Only as reliable as Finance input |
| Is spend efficient? | Cost per accepted sourced opportunity | Not full CAC or ROI |
| Why are leads increasing but pipeline falling? | Comparison over time (future integration) | Current demo contains only one static snapshot |

A production review should add period definitions, buying cohorts, deal ownership, multi-touch identity resolution, lead stage rules and audited source-to-Finance reconciliation.

## For analysts and developers

Source of truth: [docs/data.json](data.json). Both the JavaScript demonstration and Python engine use that dataset.

Run:

```bash
python -m unittest discover -s tests -v
python src/revenue.py
```

The Python implementation is [src/revenue.py](../src/revenue.py). Every accepted opportunity has one original source and a set of recorded touches. Channel attribution is explicitly controlled; irrelevant sales-origin deals are excluded from the sourced view, while sales-origin deals with marketing touches enter the influenced view.

The calculation engine does not estimate incremental lift. No CRM connection, forecasting, AI model, or actual revenue tracking has been deployed. A production connector would need authorized access, validation, reconciliations and governance before business leaders could trust the results.

## A practical management conversation

Suppose an SEO report celebrates more traffic, yet accepted opportunities from organic search fall.

Rather than order more content immediately, ask:

**Are we attracting a different audience? Have demo requests changed? Are leads being routed and accepted correctly? Have opportunity definitions changed? Are buyer cycles taking longer?**

Only after examining those factors can you know whether the right response is content, conversion optimization, qualification, sales follow-up or positioning.

That is why this project is intended as a **decision aid**, not a leaderboard for marketing channels.

## What success should eventually mean

A mature system should let a founder or CMO trace relevant marketing effort to *qualified business outcomes*, distinguish what marketing controls from what it influences, and make better investment decisions without inventing return on spend.

The current demo establishes the definitions and calculation behavior that such a system would rely on.

