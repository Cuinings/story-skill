import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_story as fixtures


story = fixtures.story


class AnalysisBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-analysis-baseline-")
        self.root = Path(self.temp.name) / "分析基线"
        story.Book.create(self.root, "往来的信", "analysis")
        self.book = story.Book(self.root)
        self.other = story.Book(self.root)
        source = self.root / "原文.txt"
        source.write_text("第1章 来信\n她收到一封信。\n第2章 回信\n她写下明天回家。\n", encoding="utf-8")
        self.sid = self.book.ingest(source, "partial")["source"]
        self.chunks = self.book.next_chunks(self.sid)["chunks"]
        self.report_file = self.root / "待提交报告.md"

    def tearDown(self):
        self.other.close()
        self.book.close()
        self.temp.cleanup()

    def payload(self, ordinal):
        chunk = self.chunks[ordinal - 1]
        return {"chunk_sha256": chunk["sha"], "summary": "信件改变人物所处的情境。",
                "findings": [{"kind": "事实", "claim": "人物行动有可定位的文字。",
                              "quote": chunk["text"].strip().splitlines()[-1]}]}

    def finish(self):
        for ordinal in (1, 2):
            self.book.record(self.sid, ordinal, self.payload(ordinal))
        return self.book.findings(self.sid)

    def write_report(self, suffix="尚不能据此认定返乡已经实际发生。"):
        self.report_file.write_text(
            "本报告仅分析实际导入的两章。人物收到来信后写下明天回家的话，文本提供了信件往来与人物表达，"
            "但没有展示回家行动的完成。" + suffix, encoding="utf-8")

    def snapshot(self):
        return {"revision": self.book.meta("revision"), "findings": self.book.findings(self.sid),
                "coverage": self.book.coverage(self.sid),
                "events": [tuple(row) for row in self.book.db.execute("SELECT * FROM events ORDER BY seq")]}

    def assert_error(self, code, operation):
        with self.assertRaises(story.StoryError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)

    def test_stale_record_cannot_overwrite_another_connections_correction(self):
        self.finish()
        stale = self.book.findings(self.sid)["results"][0]
        current = copy.deepcopy(stale)
        current["findings"][0]["claim"] = "来信到达是事实，信件内容仍未交代。"
        self.other.record(self.sid, 1, current, replace=True)
        stale["summary"] = "本会话只调整摘要，但持有旧结论。"
        before = self.snapshot()
        self.assert_error("stale_analysis", lambda: self.book.record(self.sid, 1, stale, replace=True))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(before["findings"]["results"][0]["findings"], current["findings"])

    def test_missing_record_baseline_is_rejected_but_exact_retry_keeps_working(self):
        self.finish()
        changed = self.payload(1)
        changed["summary"] = "新的摘要尚未绑定所读记录。"
        before = self.snapshot()
        self.assert_error("analysis_baseline_required", lambda: self.book.record(self.sid, 1, changed, replace=True))
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.book.record(self.sid, 1, self.payload(1), replace=True)["idempotent"])

    def test_retry_uses_old_baseline_only_while_same_content_is_still_current(self):
        self.finish()
        edited = self.book.findings(self.sid)["results"][0]
        edited["summary"] = "用户核对后的摘要。"
        original_input = copy.deepcopy(edited)
        self.book.record(self.sid, 1, edited, replace=True)
        before = self.snapshot()
        self.assertTrue(self.book.record(self.sid, 1, edited, replace=True)["idempotent"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(edited, original_input)
        stored = json.loads(self.book.db.execute("SELECT analysis FROM chunks WHERE source=? AND ordinal=1", (self.sid,)).fetchone()[0])
        self.assertNotIn("analysis_sha256", stored)
        later = self.other.findings(self.sid)["results"][0]
        later["summary"] = "随后又核对了一项变化。"
        self.other.record(self.sid, 1, later, replace=True)
        before = self.snapshot()
        self.assert_error("stale_analysis", lambda: self.book.record(self.sid, 1, edited, replace=True))
        self.assertEqual(self.snapshot(), before)

    def test_snapshot_covers_pending_completion_and_records_outside_requested_page(self):
        pending = self.book.findings(self.sid, limit=1)
        self.book.record(self.sid, 1, self.payload(1))
        first = self.book.findings(self.sid, limit=1)
        self.other.record(self.sid, 2, self.payload(2))
        complete = self.book.findings(self.sid, limit=1)
        self.assertNotEqual(pending["analysis_sha256"], first["analysis_sha256"])
        self.assertNotEqual(first["analysis_sha256"], complete["analysis_sha256"])
        self.assertEqual(first["results"], complete["results"])
        later_page = self.other.findings(self.sid, offset=1, limit=1)
        self.assertEqual(later_page["analysis_sha256"], complete["analysis_sha256"])
        edited = later_page["results"][0]
        edited["summary"] = "第二块的新核对结果。"
        self.other.record(self.sid, 2, edited, replace=True)
        updated = self.book.findings(self.sid, limit=1)
        self.assertNotEqual(complete["analysis_sha256"], updated["analysis_sha256"])
        self.assertEqual(complete["results"], updated["results"])

    def test_unrelated_source_does_not_invalidate_the_analysis_snapshot(self):
        before = self.finish()
        second = self.root / "另一作品.txt"
        second.write_text("序章\n另一个人等来了天亮。\n", encoding="utf-8")
        other_sid = self.other.ingest(second, "complete")["source"]
        self.assertEqual(self.book.findings(self.sid)["analysis_sha256"], before["analysis_sha256"])
        self.assertNotEqual(self.book.findings(other_sid)["analysis_sha256"], before["analysis_sha256"])

    def test_findings_keeps_page_and_fingerprint_in_one_concurrent_read_snapshot(self):
        original = self.finish()
        self.book.db.execute("PRAGMA journal_mode=WAL")
        changed = self.other.findings(self.sid)["results"][1]
        changed["summary"] = "另一连接在分页读取期间改了本块。"
        snapshot_sha = self.book._analysis_snapshot_sha

        def change_before_fingerprinting(sid):
            self.other.record(sid, 2, changed, replace=True)
            return snapshot_sha(sid)

        with patch.object(self.book, "_analysis_snapshot_sha", change_before_fingerprinting):
            page = self.book.findings(self.sid)
        self.assertEqual(page, original)
        current = self.book.findings(self.sid)
        self.assertNotEqual(current["analysis_sha256"], page["analysis_sha256"])
        self.assertEqual(current["results"][1]["summary"], changed["summary"])

    def test_findings_preserves_the_callers_transaction_and_rollback(self):
        self.finish()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "caller rollback"):
            with self.book.transaction():
                self.book.set_meta("analysis_read_marker", "uncommitted")
                self.book.findings(self.sid)
                self.assertTrue(self.book.db.in_transaction)
                self.assertEqual(self.book.meta("analysis_read_marker"), "uncommitted")
                self.assertIsNone(self.other.db.execute("SELECT value FROM meta WHERE key='analysis_read_marker'").fetchone())
                raise RuntimeError("caller rollback")
        self.assertIsNone(self.book.db.execute("SELECT value FROM meta WHERE key='analysis_read_marker'").fetchone())
        self.assertEqual(self.snapshot(), before)

    def test_record_fingerprint_cannot_be_borrowed_from_another_chunk(self):
        packet = self.finish()
        edited = packet["results"][1]
        edited["summary"] = "本块修改不能借用另一块的基线。"
        edited["analysis_sha256"] = packet["results"][0]["analysis_sha256"]
        before = self.snapshot()
        self.assert_error("stale_analysis", lambda: self.book.record(self.sid, 2, edited, replace=True))
        self.assertEqual(self.snapshot(), before)

    def test_new_report_requires_the_baseline_used_for_aggregation(self):
        self.finish()
        self.write_report()
        before = self.snapshot()
        self.assert_error("analysis_baseline_required", lambda: self.book.report(self.sid, self.report_file))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.book.coverage(self.sid)["report_path"])

    def test_stale_report_is_not_finalized_and_records_remain_editable(self):
        old = self.finish()
        self.write_report("这里保留第一次聚合时的结论。")
        revised = self.other.findings(self.sid)["results"][1]
        revised["findings"][0]["claim"] = "人物写下回家的话，实际行程尚未发生。"
        self.other.record(self.sid, 2, revised, replace=True)
        before = self.snapshot()
        self.assert_error("stale_analysis", lambda: self.book.report(self.sid, self.report_file, old["analysis_sha256"]))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.book.coverage(self.sid)["report_path"])
        self.assertFalse((self.root / ".story/analysis" / self.sid / "report.md").exists())
        reviewed = self.book.findings(self.sid)
        self.write_report("重新核对后，报告保留表达意愿与实际返乡的区别。")
        final = self.book.report(self.sid, self.report_file, reviewed["analysis_sha256"])
        self.assertTrue(final["finalized"] and final["exports_complete"])
        before = self.snapshot()
        # The already accepted report is immutable and exact retries are safe.
        self.assertTrue(self.book.report(self.sid, self.report_file, old["analysis_sha256"])["finalized"])
        self.assertEqual(self.snapshot(), before)
        revised["summary"] = "定稿后改变记录应被拒绝。"
        self.assert_error("report_already_final", lambda: self.book.record(self.sid, 2, revised, replace=True))
        self.write_report("另一份报告不能覆盖已经接受的定稿。")
        self.assert_error("report_exists", lambda: self.book.report(self.sid, self.report_file, reviewed["analysis_sha256"]))

    def test_pending_snapshot_cannot_finalize_after_new_records_complete(self):
        incomplete = self.book.findings(self.sid)
        self.finish()
        self.write_report()
        before = self.snapshot()
        self.assert_error("stale_analysis", lambda: self.book.report(self.sid, self.report_file, incomplete["analysis_sha256"]))
        self.assertEqual(self.snapshot(), before)

    def test_failed_export_resumes_without_regenerating_or_refinalizing_report(self):
        baseline = self.finish()["analysis_sha256"]
        self.write_report()
        with patch.object(story, "atomic_write", side_effect=OSError("temporary report export failure")):
            result = self.book.report(self.sid, self.report_file, baseline)
        self.assertTrue(result["finalized"])
        self.assertFalse(result["exports_complete"])
        self.book.close()
        self.book = story.Book(self.root)
        status = self.book.status()
        self.assertIn(result["report_path"], status["pending_exports"])
        self.assertFalse(Path(result["report"]).exists())
        before = self.snapshot()
        recovered = self.book.export(safe_only=True)
        self.assertTrue(recovered["exports_complete"])
        self.assertTrue(Path(result["report"]).is_file())
        self.assertEqual(self.snapshot(), before)

    def test_cli_report_uses_captured_fingerprint_and_rejects_stale_input(self):
        old = self.finish()
        self.write_report()
        changed = self.other.findings(self.sid)["results"][0]
        changed["summary"] = "独立连接已改变分析。"
        self.other.record(self.sid, 1, changed, replace=True)
        args = [sys.executable, "-B", str(fixtures.TOOL), "report", "--book", str(self.root),
                "--source", self.sid, "--file", str(self.report_file), "--expect-analysis"]
        result = subprocess.run(args + [old["analysis_sha256"]], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "stale_analysis")
        reviewed = self.book.findings(self.sid)
        self.write_report("此稿已按照另一连接保存的分析重新核对。")
        result = subprocess.run(args + [reviewed["analysis_sha256"]], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["exports_complete"])


if __name__ == "__main__":
    unittest.main()
