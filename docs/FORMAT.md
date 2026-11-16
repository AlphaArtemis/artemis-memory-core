# Capsule input and output

The only input format in this alpha is a UTF-8 JSON object with schema
`artemis-memory-capsule/1`. The input is one document, not a directory, archive,
URL, export bundle or executable template. Unknown fields are rejected.
Duplicate JSON keys and non-finite numbers are invalid.

Minimal invented example:

```json
{
  "schema": "artemis-memory-capsule/1",
  "document_id": "fictional_observatory_note",
  "title": "Synthetic observatory note",
  "project": "Fictional Observatory",
  "author": "Invented recorder",
  "event_at": null,
  "representation": "original_document",
  "assertion_status": "reported_result",
  "text": "SYNTHETIC DEMO — NOT REAL CONVERSATIONS. The lantern is amber.",
  "provenance": {
    "origin": "invented example",
    "approved_by": "local operator"
  }
}
```

| Field | Meaning |
| --- | --- |
| `document_id` | Logical identifier, 1–100 ASCII letters, digits, underscores, dots or hyphens. A new text under this ID is a distinct stored version. |
| `title`, `project`, `author` | Declared metadata, not independently established identity or fact. |
| `event_at` | Timezone-aware ISO date-time or `null`. Never infer it from import time. |
| `representation` | `original_document`, `capsule_summary` or `synthetic_test`. A summary must not be presented as the original. |
| `assertion_status` | `possibility`, `intention`, `decision`, `reported_result`, `attested_action`, `correction` or `unspecified`. These are declarations, not truth verification. |
| `text` | Nonblank text, at most 100,000 characters. Historical instructions are inert content. |
| `provenance` | Exactly `origin` and `approved_by`, both strings supplied by the operator. |
| `evidence_refs` | Optional bounded list of evidence labels; mandatory for `attested_action`. It does not fetch or verify external evidence. |
| `supersedes` | Optional stored source ID for a prior edition of the same logical document. Does not assert a correction. |
| `corrects` | Optional list of stored source IDs explicitly corrected by this document. |
| `parent_source_id`, `branch_id` | Optional branch ancestry and label. Alternative branches remain distinct, not silently merged. |
| `attachments` | Optional list of objects with `name` and `status: "unavailable"`. No attachment bytes are loaded or fetched. |
| `excluded` | Optional boolean. Excluded content is not returned by search or fetch. |

References use actual stored `v1:<sha256>` IDs, obtained after importing the
referenced document. The demo builder resolves its own internal labels to those
IDs; labels beginning with `@` are not a supported production input shortcut.

The filename supplied to `preview` or `import` must be a simple `.json` filename
inside the chosen state's `inbox/`. It cannot be an absolute path or traverse to
another directory. Input is bounded to 2 MiB; text and metadata have tighter
limits. Secret-like patterns cause rejection rather than silent text changes.

## Retrieval and pagination

`fetch(source_id, start=0, limit=6000)` returns at most 6,000 characters. Offsets
count Python Unicode characters, not UTF-8 bytes or screen columns. Reassemble
pages using `citation.start`, `citation.end` and `next_start`; hash the joined
string encoded as UTF-8 to compare with `citation.text_sha256`.

The original file hash covers the imported JSON bytes. The text hash covers the
JSON text value. The excerpt hash covers just the returned text. These are
different commitments; no hash proves the statements are true.

`search(query, limit=5, project=None, cursor=None, filters=None)` provides bounded
lexical FTS5 retrieval. The CLI exposes query, project, limit and cursor. Use
the returned cursor unchanged with the same request parameters. A cursor is
continuation state, not an authorization token. Changes to the corpus or revocation
state invalidate it. Do not stop pagination merely because one page is empty.

All errors deny the requested operation. The CLI emits a JSON error on stderr
with exit status 2; successful JSON goes to stdout. No previous text is included
in an error envelope.

## State and trust

The local registry is the trusted selection authority. Custody originals and
derived documents are checked against registered hashes before output. A local
administrator who can modify all state and code is outside this integrity
boundary. Version relations and provenance are supplied declarations, not a
signature from an independent archivist.
