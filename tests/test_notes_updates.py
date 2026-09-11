"""Partial notes updates preserve the constraints recalled for the next chapter."""
from pathlib import Path
import tempfile
import unittest

import test_story as fixtures

story = fixtures.story


class NotesUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-notes-update-")
        self.root = Path(self.temp.name).resolve() / "测试书"
        story.Book.create(self.root, "约束更新", "long")
        self.book = story.Book(self.root)
        self.rule = {"id": "door-rule", "kind": "world", "critical": True,
                     "scope": "global", "tags": ["门禁"], "due": 3,
                     "text": "禁用隔空开门术。", "source": "作者设定"}
        self.book.save_notes([self.rule], 0)
        self.book.save_plan(1, fixtures.plan(requires=[], tags=[]), 1)

    def tearDown(self):
        self.book.close()
        self.temp.cleanup()

    def test_text_update_keeps_hard_constraint_in_context_and_retry_is_noop(self):
        update = {"id": "door-rule", "text": "夜间禁用隔空开门术。", "source": "作者补充"}
        result = self.book.save_notes([update], 2)
        packet = self.book.context(1)
        self.assertEqual(packet["required_cards"], [story.valid_card({**self.rule, **update})])
        retry = self.book.save_notes([update], result["revision"])
        self.assertEqual(retry, {"updated": 0, "revision": result["revision"]})

    def test_explicit_release_clears_constraint_without_erasing_other_fields(self):
        self.book.save_notes([{"id": "door-rule", "critical": False, "tags": [],
                               "due": None, "status": "resolved"}], 2)
        self.assertEqual(self.book.context(1)["required_cards"], [])
        saved = self.book.cards()["door-rule"]
        self.assertEqual(saved["text"], self.rule["text"])
        self.assertEqual(saved["source"], self.rule["source"])
        self.assertEqual(saved["kind"], "world")
        self.assertEqual(saved["tags"], [])
        self.assertIsNone(saved["due"])

    def test_invalid_new_card_rolls_back_entire_update(self):
        with self.assertRaises(story.StoryError) as caught:
            self.book.save_notes([{"id": "door-rule", "critical": False}, {"id": "new-rule"}], 2)
        self.assertEqual(caught.exception.code, "invalid_input")
        self.assertEqual(self.book.meta("revision"), 2)
        self.assertEqual(self.book.cards(), {"door-rule": story.valid_card(self.rule)})

    def test_stale_update_cannot_restore_an_old_constraint(self):
        other = story.Book(self.root)
        try:
            other.save_notes([{"id": "door-rule", "critical": False}], 2)
            with self.assertRaises(story.StoryError) as caught:
                self.book.save_notes([{"id": "door-rule", "text": "旧会话的新说明。"}], 2)
            self.assertEqual(caught.exception.code, "stale_revision")
            self.assertFalse(self.book.cards()["door-rule"]["critical"])
            self.assertEqual(self.book.cards()["door-rule"]["text"], self.rule["text"])
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
