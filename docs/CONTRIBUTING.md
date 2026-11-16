# Contributing

This is an unpublished public-preview candidate, licensed under Apache-2.0;
the complete text is in [LICENSE](../LICENSE). External contributions are not
being solicited until the repository is published.

Keep changes focused on documentary retrieval, reproducibility, and preserving
source provenance. Do not add model calls, telemetry, credentials, or unrelated
services to the default demo.

## Local checks

From the extracted source directory, with Python 3.11 or later and SQLite FTS5:

```sh
python3 -B -m unittest discover -s tests -v
```

Run the synthetic demo using a new derived-state directory according to the
README. Keep source fixtures separate from generated state. Never use personal
archives to populate committed fixtures or benchmark examples.

## Bug reports

Until a repository has actually been published, no public issue URL is promised.
After publication, use that repository's Issues tab for non-sensitive reports.
Include:

- application version or source commit;
- Python, SQLite, and operating-system versions;
- exact commands and a minimal synthetic input;
- expected behavior, observed behavior, and a redacted error message.

Do not attach private source documents, generated indexes, credentials, or
unnecessary machine paths. Use the private reporting instructions in
[SECURITY.md](SECURITY.md) for security-sensitive findings. Do not disclose them
in ordinary public issues.

## Changes and evidence

Add tests for changed behavior, including relevant failure paths. Preserve
original-versus-summary classification, unknown dates, independent editions,
explicit corrections, and alternate branches. Treat retrieved instructions as
data. A new edition must not be labelled a correction without explicit evidence.

Report test failures and limitations. Do not convert a small successful demo
into a claim of universal accuracy, model improvement, or multiuser readiness.

The optional GitHub workflow tests synthetic data only. A proposed matrix is
not a list of verified supported platforms until its jobs have actually run.

