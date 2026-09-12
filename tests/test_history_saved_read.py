"""Recover saved historical decisions after the original input files are gone."""
import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_long_history as fixture

history, story = fixture.history, fixture.story


class HistorySavedReadTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.LongHistoryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.book = self.fixture.book

    def revision(self):
        return self.book.meta("revision")

    def snapshot(self):
        return self.revision(), tuple(self.book.db.iterdump()), self.book.path.read_bytes()

    def assert_code(self, code, call):
        with self.assertRaises(story.StoryError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def seed(self, delete=False):
        f = self.fixture
        f.add(1, change=True)
        f.dep(1)
        original = self.book.cards(["key"])["key"]
        entity = {"id": "envelope", "name": "信封", "kind": "item", "description": "封口完好"}
        story.world.save(self.book, {"entities": [entity]}, self.revision())
        started = f.start()
        decision = {"id": "key", "before_sha": story.digest(story.dumps(original)),
                    "after": None if delete else {**original, "text": "钥匙交给守门人。"},
                    "chapter": 1, "quote": "她交出钥匙", "note": "按本次候选稿核对最后去向。"}
        changes = {"entities": [{**entity, "description": "封口已拆开"}]}
        staged = history.branch_update(self.book, started["branch"], {
            "chapters": [f.candidate(1)], "state_changes": [decision], "world_changes": changes}, self.revision())
        review = {**staged["review_template"], "note": "本次逐段审查已保存。",
                  "state_review": "钥匙决定与最终原文相符。", "coverage_review": "已核对独立的一章及其状态。"}
        final = history.branch_update(self.book, started["branch"], {"semantic_review": review}, self.revision())
        self.expected = {"state_changes": [decision], "world_changes": changes, "semantic_review": review}
        self.branch = final["branch"]
        self.fixture.draft.unlink()
        return final

    def test_reopened_branch_recovers_exact_decisions_and_review_without_input_files(self):
        staged = self.seed()
        self.book.close()
        self.book = self.fixture.book = story.Book(self.fixture.root)
        before = self.snapshot()
        result = history.branch_saved(self.book, self.branch)
        self.assertEqual(result["saved"], self.expected)
        self.assertEqual(result["revision"], staged["revision"])
        self.assertEqual(result["current_revision"], self.revision())
        self.assertEqual(result["manifest_sha256"], staged["manifest_sha256"])
        self.assertEqual(result["candidate_chapters"], [1])
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(self.book.cards(["key"])["key"]["text"], "钥匙已经交出。")
        self.assertEqual(history.branch_inspect(self.book, self.branch, chapter=1)["candidate"]["text"], self.fixture.texts[1])
        self.assertEqual(self.snapshot(), before)

    def test_explicit_deletion_survives_readback_as_null(self):
        self.seed(delete=True)
        result = history.branch_saved(self.book, self.branch)
        self.assertEqual(result["saved"], self.expected)
        self.assertIsNone(result["saved"]["state_changes"][0]["after"])
        self.assertIn("key", self.book.cards(["key"]))

    def test_empty_and_invalidated_reviews_are_distinct_from_saved_review_text(self):
        self.fixture.add(1)
        started = self.fixture.start()
        result = history.branch_saved(self.book, started["branch"])
        self.assertEqual(result["saved"], {"state_changes": [], "world_changes": {}, "semantic_review": None})
        self.assertEqual(result["candidate_chapters"], [])
        self.fixture.stage(started)
        self.assertIsNotNone(history.branch_saved(self.book, started["branch"])["saved"]["semantic_review"])
        history.branch_update(self.book, started["branch"], {"chapters": [{"chapter": 1,
            "summary": "复核后修改了候选摘要。"}]}, self.revision())
        self.assertIsNone(history.branch_saved(self.book, started["branch"])["saved"]["semantic_review"])

    def test_stale_branch_still_returns_saved_values_without_refreshing_hashes(self):
        staged = self.seed()
        self.book.save_notes([{"id": "key", "text": "另一会话记录钥匙失踪。"}], self.revision())
        before = self.snapshot()
        result = history.branch_saved(self.book, self.branch)
        self.assertEqual(result["saved"], self.expected)
        self.assertEqual(result["revision"], staged["revision"])
        self.assertGreater(result["current_revision"], result["revision"])
        self.assertEqual(self.snapshot(), before)
        self.assert_code("stale_branch", lambda: history.branch_publish(self.book, self.branch, self.revision()))

    def test_published_branch_remains_readable_after_later_canonical_changes(self):
        self.seed()
        history.branch_publish(self.book, self.branch, self.revision())
        self.book.save_notes([{"id": "key", "text": "发布后又有新的去向。"}], self.revision())
        before = self.snapshot()
        result = history.branch_saved(self.book, self.branch)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["saved"], self.expected)
        self.assertEqual(self.snapshot(), before)

    def test_read_is_one_snapshot_during_concurrent_candidate_update(self):
        self.seed()
        expected = history.branch_saved(self.book, self.branch)
        self.book.db.execute("PRAGMA journal_mode=WAL")
        writer = story.Book(self.fixture.root)
        original_branch = history._branch
        changed = copy.deepcopy(self.expected["world_changes"])
        changed["entities"][0]["description"] = "封口另有候选改动"

        def read_then_write(book, bid):
            result = original_branch(book, bid)
            if book is self.book:
                history.branch_update(writer, bid, {"world_changes": changed}, writer.meta("revision"))
            return result

        try:
            with patch.object(history, "_branch", side_effect=read_then_write):
                result = history.branch_saved(self.book, self.branch)
            self.assertEqual(result, expected)
            following = history.branch_saved(self.book, self.branch)
            self.assertEqual(following["saved"]["world_changes"], changed)
            self.assertGreater(following["current_revision"], result["current_revision"])
            self.assertIsNone(following["saved"]["semantic_review"])
        finally:
            writer.close()

    def test_budget_failure_does_not_truncate_saved_decisions_or_change_state(self):
        self.seed()
        before = self.snapshot()
        error = self.assert_code("budget_exceeded", lambda: history.branch_saved(self.book, self.branch, budget=256))
        self.assertGreater(error.details["minimum_bytes"], 256)
        self.assertEqual(self.snapshot(), before)
        result = history.branch_saved(self.book, self.branch, budget=error.details["minimum_bytes"] + 64)
        self.assertEqual(result["saved"], self.expected)
        self.assertEqual(result["budget"]["used"], len(story.dumps(result).encode("utf-8")))
        self.assertEqual(self.snapshot(), before)

    def test_missing_branch_and_invalid_budget_never_create_or_modify_data(self):
        self.seed()
        before = self.snapshot()
        self.assert_code("branch_missing", lambda: history.branch_saved(self.book, "missing"))
        self.assert_code("invalid_input", lambda: history.branch_saved(self.book, self.branch, budget=255))
        self.assertEqual(self.snapshot(), before)

    def test_cli_reads_without_expect_or_input_and_rejects_mutation_flags(self):
        self.seed()
        before = self.snapshot()
        command = [sys.executable, "-B", str(fixture.TOOL), "history-saved", "--book", str(self.fixture.root),
                   "--branch", self.branch]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["saved"], self.expected)
        for flags in (["--expect", str(self.revision())], ["--input", "lost.json"]):
            rejected = subprocess.run(command + flags, text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_partial_edit_retains_other_recovered_decisions_and_requires_new_review(self):
        self.seed()
        restored = history.branch_saved(self.book, self.branch)
        decisions = restored["saved"]["state_changes"]
        decisions[0]["note"] = "恢复后重新核对了这项决定。"
        history.branch_update(self.book, self.branch, {"state_changes": decisions}, restored["current_revision"])
        current = history.branch_saved(self.book, self.branch)
        self.assertEqual(current["saved"]["world_changes"], self.expected["world_changes"])
        self.assertEqual(current["saved"]["state_changes"][0]["note"], decisions[0]["note"])
        self.assertIsNone(current["saved"]["semantic_review"])
        self.assert_code("review_incomplete", lambda: history.branch_publish(self.book, self.branch, self.revision()))


if __name__ == "__main__":
    unittest.main()
