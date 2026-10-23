# Security policy

The current main branch receives best-effort security fixes; no response SLA is promised.
This repository is a deterministic prototype using synthetic data, not a production CRM service.

Please use GitHub's private vulnerability reporting button on the Security tab when
available. If unavailable, open an issue asking for a private contact channel without
including exploit details. Never post credentials, CRM exports, customer records or
company financials in public issues or commits.

The Python engine reads local JSON and prints metrics. It does not authenticate users,
connect to a CRM, authorize data access or provide tenant isolation. The static dashboard
is public: any data deployed under docs/ is publicly downloadable. Use synthetic data only.

Run `python -m unittest discover -s tests -v` before changes. Review numerical validation,
non-finite values, duplicate records and unsafe HTML rendering separately. Tests do not
certify production security or the correctness of real-world attribution assumptions.
