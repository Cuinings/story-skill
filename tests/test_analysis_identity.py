import copy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_story as fixtures


story = fixtures.story
TOOL = fixtures.TOOL


class AnalysisIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-analysis-identity-")
        self.root = Path(self.temp.name) / "分析身份"
        story.Book.create(self.root, "往来的信", "analysis")
        self.book = story.Book(self.root)
        source = self.root / "原文.txt"
        source.write_bytes(("第1章 来信\n她收到一封信。\n第2章 回信\n她决定回信。\n"
                            "第3章 送信\n信送到了。\n").encode("utf-8"))
        self.sid = self.book.ingest(source, "partial")["source"]
        self.chunks = self.book.next_chunks(self.sid, limit=10)["chunks"]

    def tearDown(self):
        self.book.close()
        self.temp.cleanup()

    def payload(self, ordinal, **extra):
        chunk = self.chunks[ordinal - 1]
        quote = chunk["text"].strip().splitlines()[-1]
        return {"chunk_sha256": chunk["sha"], "summary": "本块提供信件往来的可见行动。",
                "findings": [{"kind": "事件", "claim": "人物行动有精确文本可核对。", "quote": quote}], **extra}

    def saved(self, ordinal):
        return self.book.db.execute("SELECT analysis FROM chunks WHERE source=? AND ordinal=?",
                                    (self.sid, ordinal)).fetchone()[0]

    def state(self):
        return {"revision": self.book.meta("revision"), "coverage": self.book.coverage(self.sid),
                "analyses": [self.saved(ordinal) for ordinal in range(1, 4)],
                "events": [tuple(row) for row in self.book.db.execute("SELECT * FROM events ORDER BY seq")]}

    def legacy_record(self, ordinal, embedded_chunk):
        # v0.1.1 accepted additional fields without checking this redundant ID.
        payload = self.payload(ordinal, chunk=embedded_chunk)
        with self.book.transaction():
            self.book.db.execute("UPDATE chunks SET analysis=? WHERE source=? AND ordinal=?",
                                 (story.dumps(payload), self.sid, ordinal))
            self.book.event("analysis", {"source": self.sid, "chunk": ordinal,
                                         "before": None, "after": payload})

    def cli(self, command, *args):
        result = subprocess.run([sys.executable, str(TOOL), command, "--book", str(self.root),
                                 "--source", self.sid, *map(str, args)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        return json.loads(result.stdout)

    def test_legacy_wrong_chunk_is_displayed_with_database_identity_without_rewriting(self):
        self.legacy_record(1, 999)
        before = self.state()
        result = self.book.findings(self.sid)
        self.assertEqual(result["results"][0]["chunk"], 1)
        self.assertEqual(result["results"][0]["chunk_sha256"], self.chunks[0]["sha"])
        self.assertEqual(self.state(), before)
        self.assertEqual(json.loads(self.saved(1))["chunk"], 999)

    def test_cli_record_uses_actual_chunk_number_across_finding_pages(self):
        for ordinal in (3, 1):
            payload = self.payload(ordinal, chunk=ordinal)
            file = self.root / f"analysis-{ordinal}.json"
            file.write_text(story.dumps(payload), encoding="utf-8")
            result = self.cli("record", "--chunk", ordinal, "--input", file)
            self.assertEqual(result["recorded"], ordinal)
        first = self.cli("findings", "--offset", 0, "--limit", 1)
        second = self.cli("findings", "--offset", first["next_offset"], "--limit", 1)
        self.assertEqual(first["results"][0]["chunk"], 1)
        self.assertEqual(second["results"][0]["chunk"], 3)
        self.assertEqual(second["next_offset"], second["total"])
        self.assertEqual(self.book.coverage(self.sid)["next_chunk"], 2)
        self.assertNotIn("chunk", json.loads(self.saved(1)))
        self.assertNotIn("chunk", json.loads(self.saved(3)))

    def test_copied_findings_can_be_revised_and_retried_idempotently(self):
        self.book.record(self.sid, 1, self.payload(1))
        copied = self.book.findings(self.sid)["results"][0]
        revision = self.book.meta("revision")
        unchanged = self.book.record(self.sid, 1, copied)
        self.assertTrue(unchanged["idempotent"])
        self.assertEqual(self.book.meta("revision"), revision)
        copied["summary"] = "信件抵达改变了人物掌握的信息。"
        caller_input = copy.deepcopy(copied)
        result = self.book.record(self.sid, 1, copied, replace=True)
        self.assertFalse(result["idempotent"])
        self.assertEqual(copied, caller_input, "Input normalization must not mutate the caller's object")
        revised = self.book.findings(self.sid)["results"][0]
        self.assertEqual(revised["chunk"], 1)
        self.assertEqual(revised["summary"], copied["summary"])
        revision = self.book.meta("revision")
        retried = self.book.record(self.sid, 1, revised, replace=True)
        self.assertTrue(retried["idempotent"])
        self.assertEqual(self.book.meta("revision"), revision)
        self.assertNotIn("chunk", json.loads(self.saved(1)))

    def test_correctly_read_legacy_record_can_be_retried_without_a_new_revision(self):
        self.legacy_record(1, 999)
        before = self.state()
        copied = self.book.findings(self.sid)["results"][0]
        result = self.book.record(self.sid, 1, copied)
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["recorded"], 1)
        self.assertEqual(self.state(), before)

    def test_conflicting_chunk_rejects_both_new_records_and_replacements_without_changes(self):
        self.book.record(self.sid, 1, self.payload(1))
        for ordinal, embedded, replace in ((2, 1, False), (1, 2, True)):
            with self.subTest(ordinal=ordinal, replace=replace):
                before = self.state()
                payload = self.payload(ordinal, chunk=embedded, summary="这份分析不应保存。")
                with self.assertRaises(story.StoryError) as result:
                    self.book.record(self.sid, ordinal, payload, replace=replace)
                self.assertEqual(result.exception.code, "chunk_mismatch")
                self.assertEqual(self.state(), before)

    def test_embedded_chunk_requires_a_positive_integer_without_mutating_state(self):
        for embedded in (True, "1", 1.0, 0, -1, None):
            with self.subTest(embedded=embedded):
                before = self.state()
                with self.assertRaises(story.StoryError) as result:
                    self.book.record(self.sid, 1, self.payload(1, chunk=embedded))
                self.assertEqual(result.exception.code, "invalid_input")
                self.assertEqual(self.state(), before)

    def test_record_receipt_reports_its_committed_snapshot_when_another_writer_follows(self):
        original_transaction = self.book.transaction

        @contextmanager
        def another_writer_after_commit():
            with original_transaction():
                yield
            other = story.Book(self.root)
            try:
                other.record(self.sid, 2, self.payload(2))
            finally:
                other.close()

        with patch.object(self.book, "transaction", side_effect=another_writer_after_commit):
            result = self.book.record(self.sid, 1, self.payload(1))
        self.assertEqual(result["recorded"], 1)
        self.assertEqual(result["analyzed"], 1)
        self.assertEqual(result["pending"], 2)
        self.assertEqual(result["next_chunk"], 2)
        self.assertEqual(self.book.coverage(self.sid)["analyzed"], 2)


if __name__ == "__main__":
    unittest.main()
