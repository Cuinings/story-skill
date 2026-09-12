"""Behavioral regressions for ambiguous story order and resource baselines."""
import unittest

from test_long_world import FixtureBook, entity, plan, planned, world


class WorldAuditFixes(unittest.TestCase):
    def fixture(self):
        book = FixtureBook()
        self.addCleanup(book.db.close)
        text = ("甲先在东屋等候，不知钥匙藏处，后来去了西屋并读信获知。"
                "钥匙先在甲手中，后来交给乙。甲有一百枚铜钱，另有四十枚收支和七十枚支出。")
        evidence = [book.chapter(1, text), book.chapter(2, text)]
        world.save(book, {"entities": [entity("actor", "甲"), entity("other", "乙"),
                    entity("east", "东屋", "place"), entity("west", "西屋", "place"),
                    entity("key", "钥匙", "item"), entity("coin", "铜钱", "resource")]},
                   book.meta("revision"))
        return book, evidence

    def save(self, book, **payload):
        return world.save(book, payload, book.meta("revision"))

    def transfer(self, rid, at, evidence, **fields):
        return {"id": rid, "resource": "coin", "sender": "actor", "amount": "40",
                "quantity_text": "四十枚铜钱", "at": at, "evidence": evidence, **fields}

    def ledger(self, book, evidence, at, opening_id, transfer_id, reverse=False, incoming=False):
        opening = self.transfer(opening_id, 0, evidence, sender=None, receiver="actor",
                                amount="100", quantity_text="一百枚铜钱", opening=True)
        endpoints = {"sender": None, "receiver": "actor"} if incoming else {}
        transfer = self.transfer(transfer_id, at, evidence, **endpoints)
        rows = [opening, transfer]
        self.save(book, transfers=rows[::-1] if reverse else rows)

    def test_unknown_time_transfer_cannot_be_reset_by_opening(self):
        for opening_id, transfer_id in (("a", "z"), ("z", "a")):
            for reverse in (False, True):
                for incoming in (False, True):
                    with self.subTest(ids=(opening_id, transfer_id), reverse=reverse, incoming=incoming):
                        book, evidence = self.fixture()
                        self.ledger(book, evidence[0], None, opening_id, transfer_id, reverse, incoming)
                        resource = world.context(book, plan(["actor"], at=10), 3)["resources"][0]
                        self.assertFalse(resource["known"])
                        self.assertIsNone(resource["amount"])
                        self.save(book, transfers=[self.transfer("next", 10, planned(), amount="70")])
                        check = world.check(book, plan(["actor"], at=10), 3)
                        self.assertFalse(check["blockers"])
                        self.assertIn("resource_baseline_unknown", {w["code"] for w in check["warnings"]})

    def test_known_time_transfer_keeps_exact_balance_and_overdraft_check(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                book, evidence = self.fixture()
                self.ledger(book, evidence[0], 1, "z", "a", reverse)
                resource = world.context(book, plan(["actor"], at=10), 3)["resources"][0]
                self.assertTrue(resource["known"])
                self.assertEqual(resource["amount"], "60")
                self.save(book, transfers=[self.transfer("next", 10, planned(), amount="70")])
                check = world.check(book, plan(["actor"], at=10), 3)
                self.assertEqual([w["code"] for w in check["blockers"]], ["resource_overdraft"])
                self.assertEqual(check["blockers"][0]["available"], "60")

    def test_planned_undated_transfer_does_not_change_observed_balance(self):
        book, evidence = self.fixture()
        self.save(book, transfers=[self.transfer("opening", 0, evidence[0], sender=None,
                  receiver="actor", amount="100", opening=True), self.transfer("later", None, planned())])
        resource = world.context(book, plan(["actor"], at=10), 3)["resources"][0]
        self.assertTrue(resource["known"])
        self.assertEqual(resource["amount"], "100")
        check = world.check(book, plan(["actor"], at=10), 3)
        self.assertIn("quantity_or_time_unknown", {w["code"] for w in check["warnings"]})

    def test_current_chapter_transfer_check_keeps_undated_balance_unknown(self):
        book, _ = self.fixture()
        evidence = book.chapter(3, "甲开账记有一百枚铜钱，另有日期不明的四十枚支出，再付出七十枚。")
        transfers = [self.transfer("opening", 0, evidence, sender=None, receiver="actor",
                                  amount="100", opening=True),
                     self.transfer("undated", None, evidence),
                     self.transfer("next", 10, evidence, amount="70")]
        self.save(book, transfers=transfers)
        check = world.check_transition(book, plan(["actor"], at=0, end=10), 3, {"transfers": transfers})
        self.assertFalse(check["blockers"])
        self.assertIn("resource_baseline_unknown", {w["code"] for w in check["warnings"]})

    def transfer_batch_check(self, mode, ids, reverse=False, opening="0", income="10",
                             spending=("10",), income_at=10, spending_at=10, later=None):
        book, evidence = self.fixture()
        self.save(book, transfers=[self.transfer("opening", 0, evidence[0], sender=None,
                  receiver="actor", amount=opening, opening=True)])
        ev = planned() if mode == "planned" else book.chapter(3, "甲有几笔同刻度的明确收支，先后未详。")
        rows = [self.transfer(ids[0], income_at, ev, sender=None, receiver="actor", amount=income)]
        rows.extend(self.transfer(rid, spending_at, ev, amount=amount)
                    for rid, amount in zip(ids[1:], spending))
        if later:
            rows.append(self.transfer("later", 12, ev, amount=later))
        if reverse:
            rows.reverse()
        self.save(book, transfers=rows)
        selected = plan(["actor"], at=10, end=12)
        if mode == "planned":
            return world.check(book, selected, 3)
        return world.check_transition(book, selected, 3, {"transfers": rows})

    def test_same_tick_income_and_spending_need_order_evidence(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                for reverse in (False, True):
                    with self.subTest(mode=mode, ids=ids, reverse=reverse):
                        check = self.transfer_batch_check(mode, ids, reverse)
                        self.assertFalse(check["blockers"])
                        self.assertIn("resource_order_ambiguous", {w["code"] for w in check["warnings"]})

    def test_same_tick_unavoidable_shortfall_still_blocks(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "m", "z"), ("z", "m", "a")):
                for reverse in (False, True):
                    with self.subTest(mode=mode, ids=ids, reverse=reverse):
                        check = self.transfer_batch_check(mode, ids, reverse, spending=("7", "7"))
                        self.assertFalse(check["ok"])
                        self.assertEqual([b["code"] for b in check["blockers"]], ["resource_overdraft"])
                        self.assertEqual(check["blockers"][0]["available"], "10")
                        self.assertEqual(check["blockers"][0]["required"], "14")

    def test_same_tick_sufficient_baseline_needs_no_order_warning(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                with self.subTest(mode=mode, ids=ids):
                    check = self.transfer_batch_check(mode, ids, opening="10")
                    self.assertTrue(check["ok"])
                    self.assertFalse(check["warnings"])

    def test_known_tick_order_controls_when_income_can_cover_spending(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                for income_at, spending_at in ((10, 11), (11, 10)):
                    with self.subTest(mode=mode, ids=ids, income_at=income_at):
                        check = self.transfer_batch_check(mode, ids, income_at=income_at, spending_at=spending_at)
                        self.assertEqual(check["ok"], income_at < spending_at)
                        self.assertNotIn("resource_order_ambiguous", {w["code"] for w in check["warnings"]})

    def test_ambiguous_batch_net_balance_is_known_at_next_tick(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                with self.subTest(mode=mode, ids=ids):
                    check = self.transfer_batch_check(mode, ids, later="1")
                    self.assertIn("resource_order_ambiguous", {w["code"] for w in check["warnings"]})
                    self.assertEqual([b["id"] for b in check["blockers"]], ["later"])
                    self.assertEqual(check["blockers"][0]["available"], "0")

    def test_observed_same_tick_income_does_not_prove_it_preceded_new_spending(self):
        for mode in ("planned", "actual"):
            book, evidence = self.fixture()
            self.save(book, transfers=[self.transfer("opening", 0, evidence[0], sender=None,
                      receiver="actor", amount="0", opening=True),
                      self.transfer("income", 10, evidence[0], sender=None, receiver="actor", amount="10")])
            ev = planned() if mode == "planned" else book.chapter(3, "甲在同一刻度支出十枚铜钱。")
            rows = [self.transfer("spending", 10, ev, amount="10")]
            self.save(book, transfers=rows)
            check = (world.check(book, plan(["actor"], at=10), 3) if mode == "planned" else
                     world.check_transition(book, plan(["actor"], at=10), 3, {"transfers": rows}))
            self.assertFalse(check["blockers"])
            self.assertIn("resource_order_ambiguous", {w["code"] for w in check["warnings"]})

    def test_same_tick_circular_transfers_need_initial_funds_or_order_evidence(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                for reverse in (False, True):
                    with self.subTest(mode=mode, ids=ids, reverse=reverse):
                        book, evidence = self.fixture()
                        self.save(book, transfers=[self.transfer("opening-" + holder, 0, evidence[0],
                                  sender=None, receiver=holder, amount="0", opening=True)
                                  for holder in ("actor", "other")])
                        ev = planned() if mode == "planned" else book.chapter(3, "同一刻度甲交乙十枚，乙又交甲十枚。")
                        rows = [self.transfer(ids[0], 10, ev, receiver="other", amount="10"),
                                self.transfer(ids[1], 10, ev, sender="other", receiver="actor", amount="10")]
                        if reverse:
                            rows.reverse()
                        self.save(book, transfers=rows)
                        selected = plan(["actor", "other"], at=10)
                        check = (world.check(book, selected, 3) if mode == "planned" else
                                 world.check_transition(book, selected, 3, {"transfers": rows}))
                        self.assertFalse(check["blockers"])
                        self.assertEqual({w["holder"] for w in check["warnings"]
                                          if w["code"] == "resource_order_ambiguous"}, {"actor", "other"})

    def unknown_batch_check(self, mode, ids, reverse=False, incoming=False, observed_unknown=False):
        book, evidence = self.fixture()
        self.save(book, transfers=[self.transfer("opening", 0, evidence[0], sender=None,
                  receiver="actor", amount="5", opening=True)])
        ev = planned() if mode == "planned" else book.chapter(3, "甲明确支出六枚，另有金额未明的收支。")
        endpoints = {"sender": None, "receiver": "actor"} if incoming else {}
        unknown = self.transfer(ids[1], 10, evidence[0] if observed_unknown else ev,
                                amount=None, quantity_text="金额未明", **endpoints)
        rows = [self.transfer(ids[0], 10, ev, amount="6"), unknown]
        if reverse:
            rows.reverse()
        self.save(book, transfers=rows)
        payload = [row for row in rows if not observed_unknown or row["id"] != unknown["id"]]
        check = (world.check(book, plan(["actor"], at=10), 3) if mode == "planned" else
                 world.check_transition(book, plan(["actor"], at=10), 3, {"transfers": payload}))
        return book, check

    def test_unknown_same_tick_expense_cannot_hide_minimum_shortfall(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                for reverse in (False, True):
                    for observed_unknown in (False, True):
                        with self.subTest(mode=mode, ids=ids, reverse=reverse, observed=observed_unknown):
                            book, check = self.unknown_batch_check(mode, ids, reverse,
                                                                  observed_unknown=observed_unknown)
                            self.assertEqual([b["code"] for b in check["blockers"]], ["resource_overdraft"])
                            self.assertEqual(check["blockers"][0]["available"], "5")
                            self.assertEqual(check["blockers"][0]["required"], "6")
                            self.assertTrue(check["blockers"][0]["required_is_minimum"])
                            balance = world.context(book, plan(["actor"], at=11), 4)["resources"][0]
                            if mode == "actual" or observed_unknown:
                                self.assertFalse(balance["known"])
                                self.assertIsNone(balance["amount"])
                            else:
                                self.assertTrue(balance["known"])
                                self.assertEqual(balance["amount"], "5")

    def test_unknown_same_tick_income_keeps_shortfall_unverified(self):
        for mode in ("planned", "actual"):
            for ids in (("a", "z"), ("z", "a")):
                for reverse in (False, True):
                    for observed_unknown in (False, True):
                        with self.subTest(mode=mode, ids=ids, reverse=reverse, observed=observed_unknown):
                            _, check = self.unknown_batch_check(mode, ids, reverse, incoming=True,
                                                               observed_unknown=observed_unknown)
                            self.assertFalse(check["blockers"])
                            self.assertIn("resource_baseline_unknown", {w["code"] for w in check["warnings"]})

    def test_unknown_flows_do_not_cross_holder_or_resource_boundaries(self):
        for mode in ("planned", "actual"):
            book, evidence = self.fixture()
            self.save(book, entities=[entity("grain", "米", "resource")],
                      transfers=[self.transfer("opening", 0, evidence[0], sender=None,
                                 receiver="actor", amount="5", opening=True)])
            ev = planned() if mode == "planned" else book.chapter(3, "甲付六枚铜钱；米与乙的铜钱另有未明收支。")
            rows = [self.transfer("known", 10, ev, amount="6"),
                    self.transfer("grain-income", 10, ev, resource="grain", sender=None,
                                  receiver="actor", amount=None, quantity_text="米量未明"),
                    self.transfer("other-income", 10, ev, sender=None, receiver="other",
                                  amount=None, quantity_text="乙的收入未明")]
            self.save(book, transfers=rows)
            selected = plan(["actor", "other"], at=10)
            check = (world.check(book, selected, 3) if mode == "planned" else
                     world.check_transition(book, selected, 3, {"transfers": rows}))
            self.assertEqual([(b["holder"], b["resource"], b["available"])
                              for b in check["blockers"]], [("actor", "coin", "5")])

    def test_opening_after_dated_unknown_flow_sets_only_its_own_baseline(self):
        for mode in ("planned", "actual"):
            book, evidence = self.fixture()
            self.save(book, transfers=[self.transfer("before-opening", 1, evidence[0], amount=None,
                  quantity_text="开账前支出未明"), self.transfer("opening", 2, evidence[0], sender=None,
                  receiver="actor", amount="5", opening=True)])
            before = world.context(book, plan(["actor"], at=3), 3)["resources"][0]
            self.assertTrue(before["known"])
            self.assertEqual(before["amount"], "5")
            ev = planned() if mode == "planned" else book.chapter(3, "甲在开账后支出六枚铜钱。")
            rows = [self.transfer("spending", 10, ev, amount="6")]
            self.save(book, transfers=rows)
            check = (world.check(book, plan(["actor"], at=10), 3) if mode == "planned" else
                     world.check_transition(book, plan(["actor"], at=10), 3, {"transfers": rows}))
            self.assertEqual([b["code"] for b in check["blockers"]], ["resource_overdraft"])
            self.assertEqual(check["blockers"][0]["available"], "5")

    def state_rows(self, book, evidence, kind, ids, ticks=(10, 10)):
        if kind == "facts":
            return [{"id": rid, "subject": "key", "predicate": "持有人", "value": value,
                     "entities": ["actor"], "start": tick, "evidence": ev}
                    for rid, value, tick, ev in zip(ids, ("甲", "乙"), ticks, evidence)]
        if kind == "knowledge":
            self.save(book, facts=[{"id": "proposition", "subject": "key", "predicate": "藏处",
                      "value": "门后", "start": 0, "evidence": evidence[0]}])
            return [{"id": rid, "actor": "actor", "fact": "proposition", "state": value,
                     "at": tick, "channel": "读信前后的明确交代", "evidence": ev}
                    for rid, value, tick, ev in zip(ids, ("unknown", "knows"), ticks, evidence)]
        return [{"id": rid, "line": "home", "place": value, "at": tick,
                 "summary": "甲在" + value, "unfinished": "等候下一步", "evidence": ev}
                for rid, value, tick, ev in zip(ids, ("east", "west"), ticks, evidence)]

    def check_tied_states(self, kind):
        for ids in (("a", "z"), ("z", "a")):
            for reverse in (False, True):
                for separate_chapters in (False, True):
                    with self.subTest(kind=kind, ids=ids, reverse=reverse, separate_chapters=separate_chapters):
                        book, evidence = self.fixture()
                        refs = evidence if separate_chapters else [evidence[0], evidence[0]]
                        rows = self.state_rows(book, refs, kind, ids)
                        self.save(book, **{kind: rows[::-1] if reverse else rows})
                        packet = world.context(book, plan(["actor"], at=11, line="home"), 3)
                        if kind == "lines":
                            self.assertIsNone(packet["line"])
                            selected = packet["line_candidates"]
                        else:
                            selected = packet[kind]
                        self.assertEqual({r["id"] for r in selected}, set(ids))
                        self.assertTrue(all(r.get("order_uncertain") for r in selected))
                        self.assertTrue(any(w["code"] == "world_order_ambiguous" and w["kind"] == kind
                                            for w in packet["warnings"]))

    def test_tied_facts_preserve_candidates_without_id_or_publication_order(self):
        self.check_tied_states("facts")

    def test_tied_knowledge_preserves_candidates_without_id_or_publication_order(self):
        self.check_tied_states("knowledge")

    def test_tied_lines_preserve_candidates_without_id_or_publication_order(self):
        self.check_tied_states("lines")

    def test_distinct_story_ticks_keep_latest_state_despite_publication_order(self):
        for kind in ("facts", "knowledge", "lines"):
            with self.subTest(kind=kind):
                book, evidence = self.fixture()
                rows = self.state_rows(book, evidence[::-1], kind, ("z", "a"), ticks=(10, 11))
                self.save(book, **{kind: rows})
                packet = world.context(book, plan(["actor"], at=12, line="home"), 3)
                selected = [packet["line"]] if kind == "lines" else packet[kind]
                self.assertEqual([r["id"] for r in selected], ["a"])
                self.assertNotIn("order_uncertain", selected[0])

    def test_expired_fact_interval_no_longer_creates_a_tie(self):
        book, evidence = self.fixture()
        rows = self.state_rows(book, evidence, "facts", ("z", "a"))
        rows[0]["end"] = 11
        self.save(book, facts=rows)
        tied = world.context(book, plan(["actor"], at=10), 3)
        self.assertEqual({r["id"] for r in tied["facts"]}, {"a", "z"})
        self.assertTrue(all(r["order_uncertain"] for r in tied["facts"]))
        after = world.context(book, plan(["actor"], at=11), 3)
        self.assertEqual([r["id"] for r in after["facts"]], ["a"])
        self.assertNotIn("world_order_ambiguous", {w["code"] for w in after["warnings"]})

    def test_planned_cognition_ties_do_not_override_observed_knowledge(self):
        book, evidence = self.fixture()
        rows = self.state_rows(book, [evidence[0], planned()], "knowledge", ("observed", "future-a"))
        rows[0]["state"] = "knows"
        rows[1]["state"] = "unknown"
        rows.append({**rows[1], "id": "future-z", "state": "suspects"})
        self.save(book, knowledge=rows)
        packet = world.context(book, plan(["actor"], at=11), 3)
        self.assertEqual([r["state"] for r in packet["knowledge"]], ["knows"])
        self.assertNotIn("order_uncertain", packet["knowledge"][0])
        self.assertEqual({r["state"] for r in packet["planned"]["knowledge"]}, {"unknown", "suspects"})
        self.assertTrue(all(r["order_uncertain"] for r in packet["planned"]["knowledge"]))

    def test_ambiguous_fact_does_not_confirm_rule_prerequisite(self):
        book, evidence = self.fixture()
        rows = self.state_rows(book, [evidence[0], evidence[0]], "facts", ("a", "z"))
        self.save(book, facts=rows, rules=[{"id": "rule-v1", "rule": "unlock", "version": 1,
                  "start": 0, "description": "持有钥匙才能开锁", "hard": True,
                  "entities": ["actor"], "requires": ["z"], "evidence": evidence[0]}],
                  uses=[{"id": "next", "actor": "actor", "rule": "unlock", "at": 11,
                         "evidence": planned()}])
        check = world.check(book, plan(["actor"], at=11), 3)
        self.assertIn("rule_prerequisite_unverified", {w["code"] for w in check["warnings"]})


if __name__ == "__main__":
    unittest.main()
