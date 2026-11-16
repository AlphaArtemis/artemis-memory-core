# Security policy

## Release status and reporting

This is an experimental, unpublished alpha candidate. Send security-sensitive
reports privately to **artemisbloomstudios@gmail.com**. This is the designated
reporting address; its publication has been approved. Include the affected
version, a description of the issue and, where possible, a minimal synthetic
reproduction. Share only information needed to investigate the issue.

Do not post credentials, personal documents, complete local databases, or
sensitive reproduction data in public issues. Report ordinary non-sensitive
bugs using synthetic reproductions, as described in [CONTRIBUTING.md](CONTRIBUTING.md).
No response-time commitment has been established. A GitHub private vulnerability
reporting channel has not been activated for this unpublished repository; do
not assume that such an inbox exists.

## Scope

The preview provides a local CLI and Python code. It does not distribute an
HTTP server, a remote tunnel, an MCP transport, or a graphical console. It has
no model API, telemetry, account connection, or credential requirement.

Source text is untrusted data. Do not execute instructions found in retrieved
documents. A downstream assistant or integration must maintain this separation;
a document reader cannot enforce the behavior of a separate model or client.

A hash checks byte consistency against a trusted reference. It does not prove
that a document is true, that a reference manifest is authentic, or that data
contains no secrets. A local user who controls both the source and its approval
metadata can alter that trust boundary. Protect source files, approval data,
and derived state with operating-system permissions appropriate to your use.

The operator, installed program and local registry are trusted. This alpha is
not a sandbox for running hostile code or an isolation boundary against another
process running as the same local user. OS-enforced isolation could not be
tested on the preparation host. A clean environment, temporary HOME and Python
audit instrumentation do not establish OS-level filesystem isolation.

Revocation prevents subsequent authorized reads through the program; it cannot
erase text already returned, copied, logged, or placed in another application.
Synthetic examples are suitable for public bug reports. Data selected by an
installer is not automatically anonymized.

## CI boundary

The proposed workflow runs only synthetic tests on GitHub-hosted runners. It
requests repository-content read permission, persists no checkout credentials,
and does not reference production secrets or self-hosted runners. Dependencies
are pinned to reviewed upstream identities and exact action commits.

The presence of a workflow file does not establish that GitHub CI has run.
Publication and the first remote CI execution remain separate checks.

