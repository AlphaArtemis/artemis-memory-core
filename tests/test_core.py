"""Behavioral acceptance tests using invented documents only."""
from __future__ import annotations

import copy
import hashlib
import importlib.resources
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from artemis_memory_core.core import Engine, MemoryError
import artemis_memory_core.core as core
from demo.prepare import prepare_demo


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class CoreAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="memory-core-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.state = self.root / "state"
        self.demo = prepare_demo(self.state)
        self.ids = self.demo["ids"]
        self.engine = Engine(self.state)
        self.fixture = json.loads(importlib.resources.files("demo").joinpath("synthetic.json").read_text(encoding="utf-8"))

    def capsule(self, label):
        return copy.deepcopy(next(item["document"] for item in self.fixture["documents"] if item["label"] == label))

    def put(self, document, filename="extra.json"):
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        (self.state / "inbox" / filename).write_bytes(raw)
        return filename

    def collect(self, query="lantern", limit=2, **kwargs):
        found, cursors, cursor = [], set(), None
        for _ in range(100):
            page = self.engine.search(query, limit=limit, cursor=cursor, **kwargs)
            found.extend(page["results"])
            cursor = page["next_cursor"]
            if cursor is None:
                return found
            self.assertNotIn(cursor, cursors, "cursor must advance, including on empty pages")
            cursors.add(cursor)
        self.fail("pagination exceeded the finite synthetic fixture")

    @staticmethod
    def result_ids(results):
        return [item["source_id"] for item in results]

    def test_search_pagination_no_missing_or_duplicate_sources(self):
        actual = self.result_ids(self.collect())
        expected = set(self.ids.values()) - {self.ids["excluded"], self.ids["revoked"]}
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(set(actual)))

    def test_filters_and_unknown_dates(self):
        summaries = self.collect(filters={"representation": "capsule_summary"})
        self.assertEqual(set(self.result_ids(summaries)), {self.ids["edition_one"], self.ids["edition_two"]})
        branch = self.collect(filters={"branch_id": "route-left"})
        self.assertEqual(self.result_ids(branch), [self.ids["branch_left"]])
        dated = self.collect(filters={"from": "2040-04-12", "to": "2040-04-13"})
        self.assertNotIn(self.ids["unknown_date"], self.result_ids(dated))
        self.assertEqual(self.collect(project="No Such Fictional Project"), [])

    def test_invalid_search_parameters_are_errors(self):
        for arguments in ({"limit": 0}, {"limit": 6}, {"limit": True},
                          {"filters": {"unknown": "value"}}, {"filters": {"from": "yesterday"}},
                          {"cursor": "not-a-cursor"}):
            with self.subTest(arguments=arguments), self.assertRaises(MemoryError):
                self.engine.search("lantern", **arguments)
        for query in ("", " " * 4, "x" * 501, None, 5):
            with self.subTest(query_type=type(query).__name__), self.assertRaises(MemoryError):
                self.engine.search(query)

    def test_cursor_binds_search_context_and_revision(self):
        page = self.engine.search("lantern", limit=1)
        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)
        for arguments in ({"query": "beacon", "limit": 1}, {"query": "lantern", "limit": 2},
                          {"query": "lantern", "limit": 1, "project": "Other Project"},
                          {"query": "lantern", "limit": 1, "filters": {"author": "Nobody"}}):
            with self.subTest(arguments=arguments), self.assertRaises(MemoryError):
                self.engine.search(cursor=cursor, **arguments)
        self.engine.revoke(self.ids["short"])
        with self.assertRaises(MemoryError):
            self.engine.search("lantern", limit=1, cursor=cursor)

    def test_relative_state_rejected_for_engine_and_demo(self):
        for constructor in (Engine, prepare_demo):
            with self.subTest(constructor=constructor.__name__), self.assertRaises(MemoryError):
                constructor("relative-demo-state")

    def test_cursor_from_another_store_with_same_revision_rejected(self):
        other_state = self.root / "other-state"
        prepare_demo(other_state)
        other = Engine(other_state)
        self.assertEqual(self.engine.status()["scope_revision"], other.status()["scope_revision"])
        cursor = self.engine.search("lantern", limit=1)["next_cursor"]
        self.assertIsNotNone(cursor)
        with self.assertRaises(MemoryError):
            other.search("lantern", limit=1, cursor=cursor)

    def test_approval_from_another_store_rejected(self):
        other_state = self.root / "other-state"
        prepare_demo(other_state)
        other = Engine(other_state)
        approval = self.engine.prepare_import("short.json")["approval_sha256"]
        self.assertNotEqual(approval, other.prepare_import("short.json")["approval_sha256"])
        with self.assertRaises(MemoryError):
            other.apply_import("short.json", approval)

    def test_long_source_reassembles_exact_text_and_hash(self):
        expected = self.capsule("long")["text"]
        offset, pieces = 0, []
        for _ in range(100):
            result = self.engine.fetch(self.ids["long"], start=offset, limit=777)
            part = result["text"]
            self.assertEqual(result["citation"]["start"], offset)
            self.assertEqual(result["citation"]["end"], offset + len(part))
            self.assertEqual(result["citation"]["excerpt_sha256"], digest(part.encode()))
            self.assertEqual(result["citation"]["text_sha256"], digest(expected.encode()))
            self.assertEqual(result["total_characters"], len(expected))
            pieces.append(part)
            offset = result["next_start"]
            if offset is None:
                break
        else:
            self.fail("source pagination did not terminate")
        self.assertEqual("".join(pieces), expected)

    def test_unknown_date_provenance_and_unavailable_attachment(self):
        result = self.engine.fetch(self.ids["unknown_date"])
        self.assertIsNone(result["event_at"])
        self.assertEqual(result["provenance"]["origin"], "Invented Community Edition demonstration")
        self.assertTrue(result["source_integrity_verified"])
        self.assertFalse(result["historical_claim_verified"])
        attachment = self.engine.fetch(self.ids["attachment"])
        self.assertEqual(attachment["attachments"], [{"name": "fictional-lantern-sketch.png", "status": "unavailable"}])

    def test_variants_branches_editions_and_correction_are_distinct(self):
        a, b = [self.engine.fetch(self.ids[label]) for label in ("variant_a", "variant_b")]
        self.assertNotEqual(a["source_id"], b["source_id"])
        self.assertNotEqual(a["text"], b["text"])
        self.assertIsNone(a["supersedes"])
        self.assertIsNone(b["supersedes"])
        for label in ("branch_left", "branch_right"):
            branch = self.engine.fetch(self.ids[label])
            self.assertEqual(branch["parent_source_id"], self.ids["branch_parent"])
        edition = self.engine.fetch(self.ids["edition_two"])
        self.assertEqual(edition["representation"], "capsule_summary")
        self.assertEqual(edition["supersedes"], self.ids["edition_one"])
        self.assertEqual(edition["corrects"], [])
        correction = self.engine.fetch(self.ids["correction"])
        self.assertEqual(correction["corrects"], [self.ids["short"]])
        self.assertEqual(correction["assertion_status"], "correction")
        self.assertEqual(self.engine.fetch(self.ids["short"])["representation"], "original_document")

    def test_exclusion_revocation_and_unselected_id_deny_body(self):
        for label in ("excluded", "revoked"):
            with self.subTest(label=label), self.assertRaises(MemoryError):
                self.engine.fetch(self.ids[label])
        before = self.engine.fetch(self.ids["short"])["text"]
        self.assertIn("three glass lenses", before)
        self.engine.revoke(self.ids["short"])
        with self.assertRaises(MemoryError):
            self.engine.fetch(self.ids["short"])
        self.assertNotIn(self.ids["short"], self.result_ids(self.collect()))
        with self.assertRaises(MemoryError):
            self.engine.fetch("v1:" + "0" * 64)

    def test_revoked_newer_version_not_exposed_as_implicit_neighbor(self):
        first = self.engine.fetch(self.ids["edition_one"])
        self.assertIn(self.ids["edition_two"], first["superseded_by"])
        self.engine.revoke(self.ids["edition_two"])
        reread = self.engine.fetch(self.ids["edition_one"])
        self.assertNotIn(self.ids["edition_two"], reread["superseded_by"])

    def test_unsafe_initial_state_refused_without_creating_children(self):
        unsafe = self.root / "unsafe-state"
        unsafe.mkdir()
        unsafe.chmod(0o777)
        with self.assertRaises(MemoryError) as caught:
            Engine(unsafe).initialize()
        self.assertEqual(caught.exception.code, "state_directory_permissions")
        self.assertEqual(list(unsafe.iterdir()), [])

    def test_original_bytes_preserved_duplicate_import_and_reopen(self):
        before = {p.name: p.read_bytes() for p in (self.state / "originals").iterdir()}
        plan = self.engine.prepare_import("short.json")
        self.engine.apply_import("short.json", plan["approval_sha256"])
        after = {p.name: p.read_bytes() for p in (self.state / "originals").iterdir()}
        self.assertEqual(before, after)
        reopened = Engine(self.state)
        self.assertEqual(reopened.fetch(self.ids["short"])["text"], self.capsule("short")["text"])
        self.assertEqual({p.name: p.read_bytes() for p in (self.state / "originals").iterdir()}, before)
        self.assertEqual(prepare_demo(self.state)["ids"], self.ids)

    def test_original_tampering_denies_instead_of_cached_text(self):
        first = self.engine.fetch(self.ids["short"])
        original = self.state / "originals" / (first["original_sha256"] + ".json")
        original.write_bytes(original.read_bytes() + b" ")
        with self.assertRaises(MemoryError):
            self.engine.fetch(self.ids["short"])
        # Search must fail closed rather than return an indexed stale snippet.
        try:
            rows = self.collect()
        except MemoryError:
            pass
        else:
            self.assertNotIn(self.ids["short"], self.result_ids(rows))

    def test_empty_filtered_page_with_cursor_is_not_exhaustion(self):
        cursor = None
        saw_empty_page = False
        found = []
        for _ in range(100):
            page = self.engine.search("lantern", limit=1, cursor=cursor,
                                      filters={"representation": "capsule_summary"})
            cursor = page["next_cursor"]
            if not page["results"] and cursor is not None:
                saw_empty_page = True
            found.extend(self.result_ids(page["results"]))
            if cursor is None:
                break
        self.assertTrue(saw_empty_page)
        self.assertEqual(set(found), {self.ids["edition_one"], self.ids["edition_two"]})

    def test_revocation_during_read_discards_pending_body(self):
        original_read = core.read_bytes
        triggered = False

        def revoke_after_original(path, *args, **kwargs):
            nonlocal triggered
            result = original_read(path, *args, **kwargs)
            if not triggered and Path(path).parent.name == "originals":
                triggered = True
                Engine(self.state).revoke(self.ids["short"])
            return result

        with mock.patch.object(core, "read_bytes", side_effect=revoke_after_original):
            with self.assertRaises(MemoryError):
                self.engine.fetch(self.ids["short"])
        self.assertTrue(triggered)

    def test_original_changed_during_read_discards_pending_body(self):
        original_read = core.read_bytes
        triggered = False

        def change_after_original(path, *args, **kwargs):
            nonlocal triggered
            result = original_read(path, *args, **kwargs)
            if not triggered and Path(path).parent.name == "originals":
                triggered = True
                Path(path).write_bytes(result + b" ")
            return result

        with mock.patch.object(core, "read_bytes", side_effect=change_after_original):
            with self.assertRaises(MemoryError):
                self.engine.fetch(self.ids["short"])
        self.assertTrue(triggered)

    def test_derived_tampering_denies_body(self):
        self.engine.fetch(self.ids["short"])
        derived = self.state / "derived" / (self.ids["short"][3:] + ".json")
        derived.write_bytes(derived.read_bytes() + b" ")
        with self.assertRaises(MemoryError):
            self.engine.fetch(self.ids["short"])

    def test_approval_is_bound_to_exact_input_bytes(self):
        document = self.capsule("short")
        document["document_id"] = "approval-example"
        name = self.put(document)
        plan = self.engine.prepare_import(name)
        document["text"] += " Modified after preview."
        self.put(document)
        with self.assertRaises(MemoryError):
            self.engine.apply_import(name, plan["approval_sha256"])

    def test_unknown_fields_invalid_dates_and_missing_relation_rejected(self):
        for patch in ({"unexpected": "value"}, {"event_at": "2040-04-12"},
                      {"supersedes": "v1:" + "0" * 64}, {"corrects": ["v1:" + "0" * 64]},
                      {"representation": "verified_truth"}, {"text": "x" * 100_001},
                      {"text": ""}):
            document = self.capsule("short")
            document.update(patch)
            with self.subTest(fields=list(patch)), self.assertRaises(MemoryError):
                self.engine.prepare_import(self.put(document))

    def test_traversal_arbitrary_ids_and_unsupported_zip_rejected(self):
        for filename in ("../short.json", str(self.state / "inbox" / "short.json"), "sub/short.json", "archive.zip"):
            with self.subTest(filename=filename), self.assertRaises(MemoryError):
                self.engine.prepare_import(filename)
        for source_id in ("../../secret", str(self.state / "inbox" / "short.json"), "v1:" + "x" * 64):
            with self.subTest(source_id=source_id), self.assertRaises(MemoryError):
                self.engine.fetch(source_id)

    def test_symlink_input_and_parent_path_rejected(self):
        (self.state / "inbox" / "linked.json").symlink_to(self.state / "inbox" / "short.json")
        with self.assertRaises((MemoryError, OSError)):
            self.engine.prepare_import("linked.json")
        linked = self.root / "linked-state"
        linked.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises((MemoryError, OSError)):
            Engine(linked).status()

    def test_hardlinked_input_and_directory_source_rejected(self):
        os.link(self.state / "inbox" / "short.json", self.state / "inbox" / "hardlink.json")
        with self.assertRaises(MemoryError):
            self.engine.prepare_import("hardlink.json")
        (self.state / "inbox" / "directory.json").mkdir()
        with self.assertRaises(MemoryError):
            self.engine.prepare_import("directory.json")

    def test_credential_patterns_block_import_without_echoing_value(self):
        # Deliberately fabricated pattern, never an issued credential.
        fabricated = "sk-" + "proj-" + "X" * 40
        for field in ("text", "title"):
            document = self.capsule("short")
            document[field] = fabricated
            with self.subTest(field=field), self.assertRaises(MemoryError) as caught:
                self.engine.prepare_import(self.put(document))
            self.assertEqual(caught.exception.code, "credential_review_required")
            self.assertNotIn(fabricated, str(caught.exception))

    def test_json_escaped_credential_pattern_still_refused(self):
        # A fictional pattern encoded with JSON escapes is still credential-like.
        fabricated = "sk-" + "proj-" + "X" * 40
        document = self.capsule("short")
        document["text"] = fabricated
        raw = json.dumps(document).replace("-", "\\u002d").encode("utf-8")
        self.assertNotIn(b"sk-", raw)
        (self.state / "inbox" / "escaped.json").write_bytes(raw)
        with self.assertRaises(MemoryError) as caught:
            self.engine.prepare_import("escaped.json")
        self.assertEqual(caught.exception.code, "credential_review_required")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unavailable on this platform")
    def test_fifo_input_returns_without_waiting(self):
        os.mkfifo(self.state / "inbox" / "pipe.json")
        code = "from artemis_memory_core.core import Engine; import sys; Engine(sys.argv[1]).prepare_import('pipe.json')"
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.state)],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)

    def test_malformed_json_duplicate_keys_and_nonfinite_numbers_rejected(self):
        for raw in (b"not-json", b'{"schema":1,"schema":2}', b'{"value":NaN}', b"[1,2,3]"):
            (self.state / "inbox" / "bad.json").write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(MemoryError):
                self.engine.prepare_import("bad.json")

    def test_hostile_document_is_inert_and_sql_is_literal_text(self):
        result = self.engine.fetch(self.ids["hostile"])
        self.assertIn("touch SHOULD_NOT_EXIST", result["text"])
        self.assertTrue(result["untrusted_content"])
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())
        self.assertFalse((self.state / "SHOULD_NOT_EXIST").exists())
        document = self.capsule("short")
        document["document_id"] = "literal-sql"
        document["text"] = "SYNTHETIC DEMO — NOT REAL CONVERSATIONS\nlantern '); DROP TABLE documents; --"
        name = self.put(document)
        plan = self.engine.prepare_import(name)
        inserted = self.engine.apply_import(name, plan["approval_sha256"])["document_ids"][0]
        self.assertEqual(self.engine.fetch(inserted)["text"], document["text"])
        self.assertEqual(self.engine.fetch(self.ids["short"])["text"], self.capsule("short")["text"])

    def test_excerpt_invalid_windows_rejected(self):
        for values in ({"start": -1}, {"limit": 0}, {"limit": 6001}, {"start": True}, {"start": 10**9}):
            with self.subTest(values=values), self.assertRaises(MemoryError):
                self.engine.fetch(self.ids["short"], **values)

    def test_demo_refuses_unrelated_existing_state(self):
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("Retain this file.")
        with self.assertRaises((ValueError, OSError)):
            prepare_demo(unrelated)
        self.assertEqual((unrelated / "keep.txt").read_text(), "Retain this file.")

    def test_cli_search_fetch_and_error_never_emit_old_body(self):
        def run(*args):
            return subprocess.run([sys.executable, "-B", "-m", "artemis_memory_core", *args],
                                  cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
        search = run("search", "--state", str(self.state), "lantern", "--limit", "2")
        self.assertEqual(search.returncode, 0, search.stderr)
        self.assertEqual(len(json.loads(search.stdout)["results"]), 2)
        fetch = run("fetch", "--state", str(self.state), self.ids["short"])
        self.assertEqual(fetch.returncode, 0, fetch.stderr)
        self.assertEqual(json.loads(fetch.stdout)["text"], self.capsule("short")["text"])
        denied = run("fetch", "--state", str(self.state), self.ids["revoked"])
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(denied.stdout, "")
        self.assertEqual(json.loads(denied.stderr)["status"], "BLOCKED")
        self.assertNotIn("REVOKED-FICTIONAL-BODY", denied.stderr)


if __name__ == "__main__":
    unittest.main()
