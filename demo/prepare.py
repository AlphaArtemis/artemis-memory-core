"""Load the explicitly selected fictional demo into a new local state directory."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import os
from pathlib import Path

from artemis_memory_core.core import Engine
from artemis_memory_core.safeio import read_bytes, secure_directory, write_immutable


def prepare_demo(state):
    """Import synthetic capsules; never scan a home directory or contact a service."""
    engine = Engine(state)
    state = engine.state_dir
    if os.path.lexists(state):
        folder = secure_directory(state)
        try:
            populated = bool(os.listdir(folder))
        finally:
            os.close(folder)
        if populated:
            previous = json.loads(read_bytes(state / "demo_ids.json", 500_000))
            if previous.get("notice") != "SYNTHETIC DEMO — NOT REAL CONVERSATIONS":
                raise ValueError("demo_requires_new_or_existing_demo_state")
    engine.initialize()
    data = json.loads(importlib.resources.files("demo").joinpath("synthetic.json").read_text(encoding="utf-8"))
    ids = {}
    source_files = {}
    for item in data["documents"]:
        label = item["label"]
        document = dict(item["document"])
        for field in ("supersedes", "parent_source_id"):
            if isinstance(document.get(field), str) and document[field].startswith("@"):
                document[field] = ids[document[field][1:]]
        if "corrects" in document:
            document["corrects"] = [ids[value[1:]] if value.startswith("@") else value for value in document["corrects"]]
        filename = label + ".json"
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target = state / "inbox" / filename
        # Re-running the demo must never replace a user's existing file.
        write_immutable(target, raw)
        plan = engine.prepare_import(filename)
        result = engine.apply_import(filename, plan["approval_sha256"])
        ids[label] = result["document_ids"][0]
        source_files[label] = filename
    duplicate = source_files[data["duplicate_label"]]
    plan = engine.prepare_import(duplicate)
    repeated = engine.apply_import(duplicate, plan["approval_sha256"])
    engine.revoke(ids[data["revoke_label"]])
    result = {"notice": data["notice"], "ids": ids, "duplicate_import": repeated,
              "revoked_label": data["revoke_label"], "excluded_label": "excluded"}
    output = state / "demo_ids.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_immutable(output, raw)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_demo(args.state), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
