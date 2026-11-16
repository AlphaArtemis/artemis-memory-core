# Artemis Memory Core — Community Edition

**0.1.0-alpha.1 · Experimental Public Preview candidate · Apache-2.0**

Local-first documentary memory: retrieve original text, preserve provenance, and
keep versions distinguishable. This small, experimental distribution provides a
local CLI and a Python interface over SQLite FTS5. It runs with synthetic data,
without an API key, model, account, tunnel, telemetry or network connection.

The software retrieves documents. It does **not** certify that their statements
are true. Source instructions remain untrusted text; the engine never executes
them. The demo is labelled **SYNTHETIC DEMO — NOT REAL CONVERSATIONS**.

This is an unpublished release candidate, licensed under the Apache License,
Version 2.0. The complete, unmodified [license text](LICENSE) is included.

Copyright 2026 Armando Graziani

Artemis Bloom Studios is the trade name and project identity; the copyright
holder is Armando Graziani.

## Requirements and installation

- Python 3.11 or newer, with `sqlite3` and SQLite FTS5.
- A POSIX system supporting descriptor-relative filesystem operations and
  `O_NOFOLLOW`. Windows is not supported in this alpha.
- Local verification: macOS arm64, Python 3.14.2, SQLite 3.51.1. Other Python
  versions and Linux are CI targets, not currently verified platforms.
- No Python packages to download. No global installation or shell changes.

Extract the source candidate ZIP into a new directory, open a terminal there,
then run this sequence. `mktemp` creates a separate area for application and data:

```sh
trial_dir="$(mktemp -d)"
trial_dir="$(cd "$trial_dir" && pwd -P)"
python3 -B install.py --output "$trial_dir/artemis-memory-core.pyz"
python3 -B "$trial_dir/artemis-memory-core.pyz" demo --state "$trial_dir/demo-state"
python3 -B "$trial_dir/artemis-memory-core.pyz" status --state "$trial_dir/demo-state"
python3 -B "$trial_dir/artemis-memory-core.pyz" search --state "$trial_dir/demo-state" lantern --limit 2
```

The demo prints source IDs and a `demo_ids.json` lookup in the state directory.
Use an actual returned ID and, for the next search page, the returned cursor:

```sh
python3 -B "$trial_dir/artemis-memory-core.pyz" fetch --state "$trial_dir/demo-state" SOURCE_ID --limit 600
python3 -B "$trial_dir/artemis-memory-core.pyz" fetch --state "$trial_dir/demo-state" SOURCE_ID --start 600 --limit 600
python3 -B "$trial_dir/artemis-memory-core.pyz" search --state "$trial_dir/demo-state" lantern --limit 2 --cursor NEXT_CURSOR
```

`SOURCE_ID` and `NEXT_CURSOR` are placeholders, not literal sample values. Keep
the query, project filter and page size consistent while following a cursor.
Follow `next_cursor` until it is null, even if an intermediate page is empty.
`next_start` is the separate character offset for a document's next excerpt.

You can also run directly from the extracted sources:

```sh
python3 -B -m artemis_memory_core --help
python3 -B -m unittest discover -s tests -v
```

See [the Italian quickstart](docs/QUICKSTART_IT.md), [input format](docs/FORMAT.md)
and [architecture and trust boundary](docs/ARCHITECTURE.md).

## What the demo exercises

The synthetic collection includes a short message, a long source, an unknown
date, a duplicate, text variants of one logical document, an alternate branch,
two editions without an asserted correction, an explicit correction, an excluded
source, a revoked source, harmless hostile-instruction text and a reference to an
unavailable attachment. Versions are retained; newer does not mean more true.

Each successful fetch includes the original file hash, source locator, declared
provenance, document classification, whole-text and excerpt hashes, offsets and
version relations. Unknown event dates stay null; import time is a different field.

## Use your own documents

Only the documented **single-document capsule JSON** format is supported. This
alpha does not import ZIPs, arbitrary ChatGPT exports, PDFs, Markdown folders or
remote URLs. Select and review your sources yourself: no folder is auto-scanned.

1. Initialize a new explicit state directory with `init --state ABSOLUTE_PATH`.
2. Put a reviewed capsule JSON file in its `inbox/`, using a simple filename.
3. Run `preview --state ABSOLUTE_PATH document.json` and inspect its document
   metadata, classifications and exact `approval_sha256`.
4. Run `import --state ABSOLUTE_PATH document.json --approval RETURNED_SHA256`.
   Changing the input invalidates the preview. Import creates immutable custody
   copies and a derived local index; it does not edit the inbox source.
5. Use `revoke --state ABSOLUTE_PATH SOURCE_ID` to deny future engine reads of a
   source. Revocation does not erase custody copies or undo previously obtained text.

Do not put personal data in this source checkout. Keep state elsewhere. The
installer includes only its explicit code/demo allowlist, never an adjacent
database or inbox. The state contains plaintext copies and an index: protect it
with your operating system's account and disk controls. Pattern-based secret
checks are not anonymization or a guarantee that a document has no sensitive data.

## Interfaces and limits

Distributed and locally tested interfaces: **CLI and Python `Engine`**. No web
console, HTTP server, MCP server, model connector or remote service is included.
Local success is not evidence of access from a remote assistant.

Search is lexical FTS5, not semantic reasoning. This alpha is for a single local
operator; continuous availability, concurrent multiuser operation, large-corpus
performance and general improvements in model answers have not been established.
There is no benchmark-derived accuracy or superiority claim.

The state owner controls both the files and their registry. Hash checks detect
inconsistency relative to that registry; they do not protect against an owner who
rewrites all trusted metadata, nor prove historical truth. See the threat model.

## Troubleshooting and removal

- `BLOCKED` means the operation was denied; no partial source body is returned.
  Keep the JSON error code when reporting a problem.
- A changed source, stale cursor or revoked ID must not be worked around by
  editing the registry. Start a fresh reviewed state for a new dataset.
- Symlinked paths, special files and overly large inputs are refused. On macOS,
  use a physical path (`pwd -P`), because `/tmp` and some system paths are symlinks.
- Missing FTS5 requires a Python/SQLite build with FTS5; the program does not
  download another database automatically.
- The installer refuses to overwrite an existing `.pyz`. Choose a new filename.
- To uninstall, remove the installed `.pyz` through your file manager. Data is
  independent; review or back it up before separately deleting your state folder.

For non-sensitive bugs, follow [contribution guidance](docs/CONTRIBUTING.md).
For security issues, follow [the security policy](docs/SECURITY.md) and email
artemisbloomstudios@gmail.com. Never attach real documents, credentials or a state
database to a public issue.

## Verification status

Tests are synthetic and the release procedure repeats them from an exported
source package and runs the installed zip application with a clean environment.
An OS-enforced isolation test was unavailable on the preparation host; a virtual
environment or temporary HOME is not claimed to be a filesystem sandbox. This
alpha is not an environment for running hostile code. The operator, installed
program and local registry must be trusted; protection against malicious code
or another process running as the same local user has not been demonstrated.

The GitHub Actions workflow is prepared with pinned actions. **It has not run on
GitHub.** Repository creation, publication and validation from a public clone
remain separate release steps.
