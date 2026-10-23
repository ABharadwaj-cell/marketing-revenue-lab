# Contributing

Use Python 3.11 or later. No external Python dependencies are required.

```sh
python -m unittest discover -s tests -v
python src/revenue.py
```

Use synthetic fixtures only. Explain the business definition and denominator of every
metric, and add regression tests for changed behavior. Keep sourced and influenced
amounts separate. Never claim causality, CAC or ROI from unsupported inputs. Submit a
focused pull request with test output and limitations. Contributions use the MIT license.
