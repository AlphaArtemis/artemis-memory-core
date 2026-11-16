# Candidate acceptance criteria

These expectations are defined before running the public candidate. All fixtures
are invented and labelled **SYNTHETIC DEMO — NOT REAL CONVERSATIONS**. A test pass
establishes only the behavior exercised, not general security or answer accuracy.

| ID | Scope | Expected result |
| --- | --- | --- |
| T01 | Exported installation | Install the exported package without project credentials, then run the included demo with only declared dependencies. Record separately from development tests. |
| T02 | Search and filters | Expected synthetic IDs match literal search and documented filters; malformed input produces a structured error rather than an empty-success result. |
| T03 | Search pagination | All eligible matches appear exactly once; cursors bind query, filters, page size and registry revision. Follow a non-null cursor even if a page is empty. |
| T04 | Long source | Reassemble every character with offsets; full text length and SHA-256 equal the original capsule string. |
| T05 | Provenance and relations | Preserve unknown dates, same-ID variants, branches, unavailable attachments, original versus summary, editions without correction and explicit correction links. |
| T06 | Exclusion and revocation | Deny excluded and revoked text before and after reading; search and fetch must not reveal cached text or admit unselected neighbors. |
| T07 | Hostile files and input | Reject traversal, symlinks, nonregular files, malformed input and bounded-size violations; document instructions remain inert text. |
| T08 | Advertised interfaces | Exercise CLI and importable Python API separately. HTTP, GUI and MCP are not part of this candidate and have no claimed PASS. |
| T09 | Reopening | Reopen without reimporting; repeating an identical import changes neither originals nor document count. One-time UI codes do not apply to the CLI. |
| T10 | Release contents | Exact export allowlist, local content review, bounded artifact scan and clean new Git tree; record package/tree checks separately. |
| T11 | Operational preservation | Compare selected private operational file hashes against the pre-work baseline outside this public package. Never include private evidence here. |

Result vocabulary: **PASS**, **FAIL**, **BLOCKED**, **NOT_RUN**,
**NOT_APPLICABLE**. Repeated runs are not additional independent experiments.
Source integrity is not a claim that a document is historically true.
