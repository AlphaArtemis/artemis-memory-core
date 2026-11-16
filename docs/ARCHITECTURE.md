# Architecture and threat model

## Components

The Community Edition extracts the existing local immutable acquisition,
SQLite FTS5 and verified document retrieval code. It removes deployment-specific
historical corpus adapters and their configuration. It does not add another
retrieval service, model or database technology.

An explicit operator-selected inbox supplies a capsule. Preview validates its
shape and calculates an approval fingerprint. Import rechecks that fingerprint,
preserves the original bytes as a custody copy, stores version metadata and
indexes text in SQLite FTS5. Search resolves candidate IDs through the verified
source reader before emitting text; fetch returns bounded source windows.

`supersedes` records an edition link. `corrects` records a separate explicit
correction. Original documents, summaries, alternate branches and unknown dates
remain distinguishable. A reference to an unavailable attachment is metadata.

The CLI is a local operator interface, including import and revocation commands.
It is not suitable as an unrestricted remote tool endpoint. No HTTP listener,
browser session, tunnel, MCP transport or authentication server is distributed.

## Trust boundary

Trusted: the installed application, the operator's explicit source selection,
the registry and the local operating system account. Untrusted: capsule text,
filenames, input metadata, cursors and source files that may change after import.

The engine verifies bytes against registry hashes and validates membership and
revocation when reading. Hashes detect mismatches relative to the trusted
registry; they are not independent signatures or a guarantee against a local
administrator replacing the program and all metadata together.

Document contents are never instructions to the engine. They are returned as
JSON strings, without evaluating code, rendering remote media or following
links. A consuming assistant must retain this distinction; this package cannot
guarantee the behavior of an external consumer that ignores it.

## Defenses and limits

- Bounded reads through descriptors, regular-file checks and rejection of
  symlinks, traversal and special files.
- Explicit import fingerprint; custody copies and versioned derived data;
  original input not rewritten.
- Exact source IDs, local revocation checks, no implicit retrieval of neighbors.
- Bounded excerpt/search windows and request-bound continuation cursors.
- Credential-pattern rejection as a supplementary check, never an assertion
  that a source is anonymous or free of personal data.
- Source-only, allowlisted offline packaging; application state is kept outside
  the package and excluded from packaging and Git defaults.

Not provided: encryption at rest, separate user roles, trusted hardware,
protection against a malicious local administrator, remote access control,
guaranteed availability, automatic backups or audited multitenant concurrency.
Use operating-system access controls for the plaintext state. Revocation blocks
later engine retrieval; it cannot retract an already returned excerpt and does
not delete originals or the index.

## Validation boundary

Synthetic tests cover the documented cases. They are not a penetration-test
certification or evidence of general answer accuracy. Installation and demo are
checked from the exported package separately from development tests. Local
runtime instrumentation and an empty HOME are useful evidence, but not a
substitute for an OS-enforced sandbox. That sandbox was unavailable on the
preparation host. Public-clone verification and GitHub CI remain unexecuted
until publication is authorized.
