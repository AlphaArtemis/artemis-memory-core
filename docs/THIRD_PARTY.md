# Third-party components

This preview uses Python's standard library and the SQLite library exposed by
Python's `sqlite3` module, including FTS5. There are no runtime packages to install
from PyPI. A Python build without FTS5 cannot run the documented search path.

The source distribution does not bundle Python, SQLite, model weights, fonts,
images, vendored JavaScript, or third-party package source. Python and SQLite
versions depend on the interpreter installed by the person running the program;
the release validation report records the versions actually tested. The
requirement is Python 3.11 or later with SQLite FTS5, not a claim that every
interpreter version or operating system has been tested.

| Component | Use | License / provenance |
| --- | --- | --- |
| Python standard library | Runtime and tests; provided by the installed Python interpreter | [Python license documentation](https://docs.python.org/3/license.html), including component-specific notices |
| SQLite / FTS5 | Local derived index through `sqlite3`; supplied with the installed interpreter | [SQLite copyright statement](https://www.sqlite.org/copyright.html); SQLite describes its deliverable code as public domain |
| `actions/checkout` v7.0.1 | Optional GitHub CI only, not used by the local application | MIT; GitHub, Inc. and contributors |
| `actions/setup-python` v7.1.0 | Optional GitHub CI only, not used by the local application | MIT; GitHub, Inc. and contributors |

The CI action references are pinned to commits in the official upstream
repositories:

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`

The upstream tag targets and commit metadata were checked on 2026-11-16.
Both actions use Node.js 24 on the CI runner. Their own bundled dependencies
belong to the upstream action distributions; they are not bundled in this
application. A fixed action commit does not freeze the runner image or the
Python distribution downloaded by the action.

Upstream licenses at the pinned commits:

- [checkout LICENSE](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE)
- [setup-python LICENSE](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/LICENSE)

Preserve required third-party notices if future releases incorporate or
redistribute third-party code. Artemis Memory Core is licensed under Apache-2.0;
its complete text is in [LICENSE](../LICENSE). This inventory does not change
upstream licenses.

