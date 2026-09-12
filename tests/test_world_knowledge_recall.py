"""Recall a character's current knowledge through a related item or place."""
import unittest

from test_long_world import FixtureBook, WorldError, entity, fact, plan, planned, world


class KnowledgeRecallTests(unittest.TestCase):
    def setUp(self):
        self.book = FixtureBook()
        self.ev1 = self.book.chapter(1, "甲得知钥匙藏在东屋，乙只听见一句传闻。")
        self.ev2 = self.book.chapter(2, "甲受伤后忘了钥匙藏处。")
        self.save(entities=[entity("a", "甲"), entity("b", "乙"), entity("key", "钥匙", "item"),
                            entity("letter", "信件", "item")],
                  facts=[fact("where", "key", "东屋", self.ev1), fact("letter-where", "letter", "西屋", self.ev1)])
        self.save(knowledge=[self.knowledge("known", "knows", 0, entities=["key"], evidence=self.ev1)])

    def tearDown(self):
        self.book.db.close()

    def save(self, **payload):
        world.save(self.book, payload, self.book.meta("revision"))

    def knowledge(self, rid, state, at, **overrides):
        return {"id": rid, "actor": "a", "fact": "where", "state": state, "at": at,
                "channel": "正文明确交代认知变化", "evidence": self.ev2, **overrides}

    def context(self, entities=None, at=20, chapter=3):
        return world.context(self.book, plan(entities or ["key"], at=at), chapter)

    def test_item_and_actor_queries_agree_after_memory_loss(self):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", 10)])
        for entities in (["key"], ["a"], ["a", "key"]):
            with self.subTest(entities=entities):
                packet = self.context(entities)
                self.assertEqual([(r["id"], r["state"]) for r in packet["knowledge"]], [("forgotten", "unknown")])
                self.assertEqual([r["id"] for r in packet["propositions"]], ["where"])
                # Forgetting is not a change to where the key actually is.
                if "key" in entities:
                    self.assertEqual(packet["facts"][0]["value"], "东屋")

    def test_flashback_and_publication_horizon_keep_prior_knowledge(self):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", 10)])
        for at, chapter in ((5, 3), (20, 2)):
            with self.subTest(at=at, chapter=chapter):
                self.assertEqual([r["state"] for r in self.context(at=at, chapter=chapter)["knowledge"]], ["knows"])

    def assert_uncertain(self, at, code):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", at)])
        packet = self.context()
        self.assertEqual({r["state"] for r in packet["knowledge"]}, {"knows", "unknown"})
        self.assertIn(code, {r["code"] for r in packet["warnings"]})

    def test_unknown_time_remains_unordered_through_item_query(self):
        self.assert_uncertain(None, "world_time_unknown")

    def test_same_time_remains_unordered_through_item_query(self):
        self.assert_uncertain(0, "world_order_ambiguous")

    def test_proposed_memory_loss_stays_separate_from_observed_knowledge(self):
        self.save(knowledge=[self.knowledge("proposed-loss", "unknown", 10, evidence=planned())])
        packet = self.context()
        self.assertEqual([r["state"] for r in packet["knowledge"]], ["knows"])
        self.assertEqual([r["state"] for r in packet["planned"]["knowledge"]], ["unknown"])

    def test_unrelated_actors_propositions_and_clocks_do_not_join_selected_slot(self):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", 10),
                             self.knowledge("other-actor", "believes", 12, actor="b"),
                             self.knowledge("other-fact", "knows", 12, fact="letter-where"),
                             self.knowledge("other-clock", "knows", 12, clock="dream")])
        self.assertEqual([r["id"] for r in self.context()["knowledge"]], ["forgotten"])

    def test_new_knowledge_evidence_is_checked_through_item_query(self):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", 10)])
        world.invalidate_chapters(self.book, [2])
        with self.assertRaises(WorldError) as caught:
            self.context()
        self.assertEqual(caught.exception.code, "stale_world_evidence")
        self.assertEqual(caught.exception.details["id"], "forgotten")

    def test_retired_association_does_not_recall_unrelated_knowledge(self):
        self.save(knowledge=[self.knowledge("forgotten", "unknown", 10)])
        correction = self.book.chapter(3, "此前记错了人物，甲从未得知钥匙藏处。")
        with self.book.transaction(self.book.meta("revision")):
            world.invalidate_chapters(self.book, [1])
            world.apply_in_transaction(self.book, {"retirements": [{"kind": "knowledge", "id": "known",
                "reason": "旧认知记录人物有误", "evidence": correction}]}, repair=True)
        # The proposition is still linked through key and needs separate repair.
        # Restrict this assertion to knowledge recall, avoiding invalid facts.
        with self.book.transaction(self.book.meta("revision")):
            world.apply_in_transaction(self.book, {"facts": [fact("where", "key", "东屋", self.ev1)]}, repair=True)
        self.assertEqual(self.context(chapter=4)["knowledge"], [])


if __name__ == "__main__":
    unittest.main()
