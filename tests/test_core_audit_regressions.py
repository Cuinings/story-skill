"""Concrete runtime regressions found during the full repository audit."""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_story as fixtures


story = fixtures.story


class CoreAuditRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-core-audit-")
        self.temp_root = Path(self.temp.name).resolve()
        self.root = self.temp_root / "中文书"
        story.Book.create(self.root, "审查样本", "long")
        self.book = story.Book(self.root)

    def tearDown(self):
        self.book.close()
        # Cleanup is restricted to the exact temporary directory created above.
        self.assertEqual(Path(self.temp.name).resolve(), self.temp_root)
        self.root.resolve().relative_to(self.temp_root)
        self.temp.cleanup()

    def test_recall_byte_omissions_are_incomplete_even_when_search_finished(self):
        self.book.save_notes([fixtures.card("clue", text="线索" * 500)], 0)
        packet = self.book.recall("线索", 1000)
        self.assertEqual(packet["matches"], [])
        self.assertEqual(packet["omitted"], 1)
        self.assertFalse(packet["complete"])
        self.assertFalse(packet["no_match_confirmed"])
        self.assertIn("budget_limit", packet["truncated_reasons"])
        self.assertEqual(packet["budget"]["used"], len(story.dumps(packet).encode("utf-8")))
        self.assertLessEqual(packet["budget"]["used"], 1000)
        full = self.book.recall("线索", 12000)
        self.assertTrue(full["complete"])
        self.assertEqual(full["omitted"], 0)
        self.assertNotIn("budget_limit", full["truncated_reasons"])

    def test_recall_card_and_match_share_a_snapshot_during_concurrent_update(self):
        self.book.db.execute("PRAGMA journal_mode=WAL")
        old = fixtures.card("clue", text="江棠持有钥匙。", tags=[])
        new = fixtures.card("clue", text="杜承安持有账本。", tags=[])
        self.book.save_notes([old], 0)
        original_query = story.search.query
        with closing(story.Book(self.root)) as writer:
            def queried(*args, **kwargs):
                result = original_query(*args, **kwargs)
                writer.save_notes([new], 1)
                return result
            with patch.object(story.search, "query", side_effect=queried):
                packet = self.book.recall("江棠")
        self.assertEqual(packet["matches"][0]["text"], old["text"])
        self.assertFalse(self.book.db.in_transaction)
        self.assertEqual(self.book.cards(["clue"])["clue"]["text"], new["text"])

    def test_world_read_payload_and_digest_share_a_snapshot_during_update(self):
        self.book.db.execute("PRAGMA journal_mode=WAL")
        old = {"id": "hero", "name": "江棠", "kind": "character", "description": "保管旧钥匙。"}
        new = {**old, "description": "交出旧钥匙。"}
        story.world.save(self.book, {"entities": [old]}, 0)
        old_sha = story.world.resolve_dependency(self.book, "entities", "hero")
        original_stored = story.world._stored
        updated = False
        with closing(story.Book(self.root)) as writer:
            def stored(book, *args, **kwargs):
                nonlocal updated
                value = original_stored(book, *args, **kwargs)
                if book is self.book and not updated:
                    updated = True
                    story.world.save(writer, {"entities": [new]}, 1)
                return value
            with patch.object(story.world, "_stored", side_effect=stored):
                packet = self.book.world_read("entities", "hero")
        self.assertEqual(packet["payload"]["entities"], [old])
        self.assertEqual(packet["record_sha256"], old_sha)
        self.assertFalse(self.book.db.in_transaction)
        self.assertNotEqual(story.world.resolve_dependency(self.book, "entities", "hero"), old_sha)

    def test_composite_readers_preserve_the_callers_transaction(self):
        with self.book.transaction():
            self.book.put_card(story.valid_card(fixtures.card("clue", text="江棠有钥匙。")))
            story.world.apply_in_transaction(self.book, {"entities": [
                {"id": "hero", "name": "江棠", "kind": "character", "description": "保管钥匙。"}]})
            self.assertTrue(self.book.recall("江棠")["matches"])
            self.assertTrue(self.book.db.in_transaction)
            self.assertTrue(self.book.world_read("entities", "hero")["record_sha256"])
            self.assertTrue(self.book.db.in_transaction)

    def test_nul_source_is_rejected_before_creating_truncated_chunks(self):
        source = self.root / "原文.txt"
        text = "第1章 入门\n她推开门。\x00门后有封信。\n"
        source.write_bytes(text.encode("utf-8"))
        with self.assertRaises(story.StoryError) as caught:
            self.book.ingest(source)
        self.assertEqual(caught.exception.code, "corrupt_text")
        self.assertEqual(self.book.meta("revision"), 0)
        self.assertEqual(self.book.db.execute("SELECT count(*) FROM sources").fetchone()[0], 0)
        self.assertEqual(source.read_bytes(), text.encode("utf-8"))

    def test_nul_adoption_is_rejected_before_exporting_a_broken_baseline(self):
        draft = self.root / "旧稿.md"
        draft.write_bytes("# 旧稿\n她推开门。\x00门后有封信。\n".encode("utf-8"))
        with self.assertRaises(story.StoryError) as caught:
            self.book.adopt(10, draft, "她推门发现来信。", 0)
        self.assertEqual(caught.exception.code, "corrupt_text")
        self.assertEqual(self.book.meta("revision"), 0)
        self.assertEqual(self.book.meta("last_chapter"), 0)
        self.assertFalse((self.root / "chapters").exists())

    def test_sqlite_integer_overflow_is_a_structured_cli_error(self):
        payload = self.root / "plan.json"
        payload.write_text(story.dumps(fixtures.plan(requires=[])), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(fixtures.TOOL), "plan",
            "--book", str(self.root), "--chapter", str(2**63), "--expect", "0", "--input", str(payload)],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "invalid_input")
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.book.meta("revision"), 0)


if __name__ == "__main__":
    unittest.main()
