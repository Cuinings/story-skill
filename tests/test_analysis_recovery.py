import json
from pathlib import Path
import tempfile
import unittest

import test_story as fixtures


story = fixtures.story


class AnalysisRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-analysis-recovery-")
        self.root = Path(self.temp.name) / "空白块分析"
        story.Book.create(self.root, "门后的信", "analysis")
        self.book = story.Book(self.root)

    def tearDown(self):
        self.book.close()
        self.temp.cleanup()

    def chunk_rows(self, sid):
        return [dict(row) for row in self.book.db.execute(
            "SELECT * FROM chunks WHERE source=? ORDER BY ordinal", (sid,))]

    def analysis_for(self, text, sha):
        return {
            "chunk_sha256": sha,
            "summary": "可见文字给出人物行动或场景信息。",
            "findings": [{
                "kind": "文本证据",
                "claim": "本块包含可定位的文字，仍须经过逐块分析。",
                "quote": text.strip()[:120],
            }],
        }

    def assert_lossless(self, sid, original):
        rows = self.chunk_rows(sid)
        self.assertEqual(self.book.source(sid)["text"], original)
        self.assertEqual(rows[0]["start"], 0)
        self.assertEqual(rows[-1]["end"], len(original))
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(rows, rows[1:])))
        self.assertEqual("".join(original[r["start"]:r["end"]] for r in rows), original)
        for row in rows:
            self.assertEqual(row["sha"], story.digest(original[row["start"]:row["end"]]))
        self.assertTrue(self.book.coverage(sid)["text_coverage_contiguous"])

    def finish_and_report(self, sid):
        total = self.book.coverage(sid)["chunks_total"]
        for _ in range(total + 1):
            chunks = self.book.next_chunks(sid, limit=2)["chunks"]
            if not chunks:
                break
            for chunk in chunks:
                self.assertTrue(chunk["text"].strip(), "Whitespace must not block manual analysis")
                self.book.record(sid, chunk["ordinal"], self.analysis_for(chunk["text"], chunk["sha"]))
        else:
            self.fail("Analysis did not make progress through the saved chunks")
        coverage = self.book.coverage(sid)
        self.assertEqual(coverage["pending"], 0)
        self.assertEqual(coverage["analyzed"], total)
        self.assertTrue(coverage["complete_for_imported_text"])
        report = self.root / "报告草稿.md"
        report.write_text(
            "本报告仅覆盖实际导入的文字。人物推门与发现信件构成可见的信息变化；"
            "空白范围作为排版信息保留，不被描述成故事事件，也不代替正文片段的人工分析。",
            encoding="utf-8",
        )
        result = self.book.report(sid, report)
        self.assertTrue(result["exports_complete"])
        self.assertTrue(Path(result["report"]).is_file())

    def check_new_source(self, text):
        source = self.root / "原文.txt"
        source.write_bytes(text.encode("utf-8"))
        result = self.book.ingest(source, "partial", chunk_chars=256)
        sid = result["source"]
        self.assert_lossless(sid, text)
        rows = self.chunk_rows(sid)
        blank = [row for row in rows if not text[row["start"]:row["end"]].strip()]
        content = [row for row in rows if text[row["start"]:row["end"]].strip()]
        self.assertTrue(blank, "Fixture must exercise a standalone whitespace chunk")
        self.assertTrue(content)
        self.assertEqual(result["pending"], len(content))
        for row in blank:
            self.assertIsNotNone(row["analysis"], "New whitespace chunks must have completion evidence")
            self.assertEqual(json.loads(row["analysis"])["chunk_sha256"], row["sha"])
        for row in content:
            self.assertIsNone(row["analysis"], "Narrative text must never be automatically analyzed")
        saved = self.book.findings(sid, limit=100, budget=100000)["results"]
        self.assertEqual({item["chunk"] for item in saved}, {row["ordinal"] for row in blank})
        self.finish_and_report(sid)
        self.assert_lossless(sid, text)
        self.assertEqual(source.read_bytes(), text.encode("utf-8"))

    def test_leading_blank_lines_complete_without_losing_source(self):
        self.check_new_source("\r\n\t \r\n第1章 入门\r\n她推开门。\r\n")

    def test_trailing_whitespace_chunks_complete_without_losing_source(self):
        self.check_new_source("第1章 入门\n她推开门。\n" + " \t\r\n" * 300)

    def test_middle_whitespace_chunks_preserve_later_chapter(self):
        self.check_new_source("第1章 入门\n她推开门。\n" + " \t\r\n" * 300 + "第2章 留信\n门后有封信。\n")

    def test_whitespace_longer_than_maximum_chunk_size_completes(self):
        self.check_new_source(" " * 12000 + "\n第1章 入门\n她推开门。\n")

    def test_unheaded_source_with_blank_chunks_completes(self):
        self.check_new_source("她推开门。\n" + " \t\r\n" * 300 + "门后有封信。\n")

    def test_nonempty_text_is_not_automatically_completed(self):
        source = self.root / "正文.txt"
        text = "第1章 入门\n她推开门。\n第2章 留信\n门后有封信。\n"
        source.write_bytes(text.encode("utf-8"))
        result = self.book.ingest(source)
        sid = result["source"]
        self.assertEqual(result["analyzed"], 0)
        self.assertEqual(result["pending"], result["chunks_total"])
        self.assertEqual(len(self.book.next_chunks(sid)["chunks"]), result["chunks_total"])
        self.assertTrue(all(row["analysis"] is None for row in self.chunk_rows(sid)))
        self.assertFalse(self.book.coverage(sid)["complete_for_imported_text"])

    def test_whitespace_only_source_still_rejects_empty_input(self):
        source = self.root / "空白原文.txt"
        source.write_bytes((" \t\r\n" * 500).encode("utf-8"))
        with self.assertRaises(story.StoryError) as result:
            self.book.ingest(source)
        self.assertEqual(result.exception.code, "empty_source")
        self.assertEqual(self.book.list_sources()["total"], 0)

    def test_legacy_pending_blanks_resume_without_rebuilding_or_losing_analysis(self):
        # Construct a pre-fix SQLite checkpoint directly: calling today's ingest
        # would normalize whitespace and would not exercise existing databases.
        pieces = ["\r\n\r\n", "第1章 入门\r\n她推开门。\r\n", " \t" * 100 + "\r\n",
                  "第2章 留信\r\n门后有封信。\r\n", "\r\n\t \r\n"]
        original = "".join(pieces)
        sid = story.digest(original)
        old_analysis = self.analysis_for(pieces[1], story.digest(pieces[1]))
        with self.book.transaction():
            self.book.db.execute("INSERT INTO sources VALUES (?,?,?,?,?)",
                                 (sid, str(self.root / "已经导入的原文.txt"), original, "partial", "utf-8-sig"))
            start = 0
            for ordinal, piece in enumerate(pieces, 1):
                self.book.db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?)",
                                     (sid, ordinal, start, start + len(piece), f"原始块 {ordinal}",
                                      story.digest(piece), story.dumps(old_analysis) if ordinal == 2 else None))
                start += len(piece)
            self.book.event("ingest", {"source": sid, "chunks": len(pieces), "coverage": "partial"})
            self.book.event("analysis", {"source": sid, "chunk": 2, "before": None, "after": old_analysis})
        immutable = [tuple(row[key] for key in ("ordinal", "start", "end", "title", "sha"))
                     for row in self.chunk_rows(sid)]
        old_events = [tuple(row) for row in self.book.db.execute("SELECT seq,revision,kind,data FROM events ORDER BY seq")]
        old_saved = self.chunk_rows(sid)[1]["analysis"]
        book_id = self.book.meta("id")
        self.book.close()
        self.book = story.Book(self.root)
        packet = self.book.next_chunks(sid, limit=1)
        self.assertEqual([chunk["ordinal"] for chunk in packet["chunks"]], [4])
        self.assertEqual(self.book.meta("id"), book_id)
        self.assertEqual(self.book.coverage(sid)["pending"], 1)
        self.assertEqual(self.book.coverage(sid)["analyzed"], 4)
        self.assertEqual(self.chunk_rows(sid)[1]["analysis"], old_saved)
        self.assertEqual(immutable, [tuple(row[key] for key in ("ordinal", "start", "end", "title", "sha"))
                                     for row in self.chunk_rows(sid)])
        self.assertEqual(old_events, [tuple(row) for row in self.book.db.execute(
            "SELECT seq,revision,kind,data FROM events WHERE seq<=? ORDER BY seq", (old_events[-1][0],))])
        for row in self.chunk_rows(sid):
            if not original[row["start"]:row["end"]].strip():
                self.assertEqual(json.loads(row["analysis"])["chunk_sha256"], row["sha"])
        revision = self.book.meta("revision")
        self.book.next_chunks(sid, limit=1)
        self.assertEqual(self.book.meta("revision"), revision, "Reopening a checkpoint must not duplicate recovery events")
        self.assert_lossless(sid, original)
        self.finish_and_report(sid)
        self.assertEqual(self.chunk_rows(sid)[1]["analysis"], old_saved)
        self.assert_lossless(sid, original)

    def test_repeated_ingest_and_next_leave_noncontent_evidence_unchanged(self):
        source = self.root / "原文.txt"
        source.write_bytes("\n\n第1章 入门\n她推开门。\n".encode("utf-8"))
        result = self.book.ingest(source, "partial")
        sid = result["source"]
        before = self.chunk_rows(sid)
        self.assertIsNotNone(before[0]["analysis"])
        revision = self.book.meta("revision")
        self.assertTrue(self.book.ingest(source, "partial")["idempotent"])
        self.book.next_chunks(sid)
        self.book.next_chunks(sid)
        self.assertEqual(self.chunk_rows(sid), before)
        self.assertEqual(self.book.meta("revision"), revision)


if __name__ == "__main__":
    unittest.main()
