# Working instructions for this repository

## Why this project exists
Connect leads and CRM-like opportunities to sourced and influenced pipeline, bookings and separately reported revenue, using deterministic calculations that nontechnical leaders can audit.

## Who you are building for
- **Solo founders and nontechnical executives:** Lead with the decision they can make and the question they should ask next. Do not require familiarity with Python, MCP or marketing attribution to understand the demo.
- **CMOs and marketing directors:** Explain evidence, trade-offs, operating implications and commercial relevance.
- **Practitioners and developers:** Keep implementation details and limitations inspectable, with runnable tests and explicit source definitions.

## Business outcome to protect
Answer what happened after marketing generated interest: was it accepted by Sales, did it become pipeline, was it won, and what revenue was separately recorded?

## How to write
Write the way a thoughtful marketing operator explains their work to another human. Use direct sentences, concrete examples, accurate terminology and active voice. Avoid inflated claims, buzzword stacks, fake case studies, jargon without explanation, keyword stuffing and generic AI-sounding praise. Keep the tone credible and approachable. Avoid em dashes. Use descriptive page titles, a clear opening answer, logical headings and natural terminology so searchers and readers can understand the project.

## When changing the product
1. Start with the user problem and the real business decision.
2. Check what the current code and data actually support. Don't describe a roadmap item as implemented.
3. Prefer a plain-English first-use path followed by an advanced technical path.
4. Keep a visible separation among synthetic demo data, verified source evidence, opinion, forecast and measured results.
5. Update the README, start-here guide and demo UI when functionality or interpretation changes.
6. Add or update tests, execute them where possible, and report whether they actually passed.
7. Never silently rewrite historical evidence, create invented results, expose credentials or upload private company/customer data.

## Implementation map
src/revenue.py, docs/data.json, tests/test_revenue.py, docs/index.html

## Project-specific guardrails
Never add marketing-sourced and influenced pipeline; never sum overlapping influenced channel totals; keep source identity, accepted status, deal stage and revenue definitions explicit; don't call cost per accepted opportunity CAC/ROI; do not infer causality from touches.

## Definition of done
A first-time visitor can answer: What problem does this solve? Who is it for? What can I try right now? What can the output help me decide? What is still missing? An experienced reviewer can then find the code, understand the data rules, run the tests and identify the limits without guesswork.

This file guides contributors and coding assistants. It is not a substitute for deterministic security policies, human authorization or actual test results.
