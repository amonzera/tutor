"""Revisão espaçada: SM-2, limite pela prova, triagem diária e orçamento entre matérias."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.fixtures import build_subject
from tests.helpers import TempWorkspaceCase
from tutor import srs
from tutor.core import TutorError, read_json, write_json


class SM2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.scheduler = srs.SM2Scheduler()

    def run_grades(self, grades):
        item = {}
        intervals = []
        for grade in grades:
            item.update(self.scheduler.next_state(item, grade))
            intervals.append(item["intervalo"])
        return item, intervals

    def test_classic_sequence(self) -> None:
        item, intervals = self.run_grades(["bom", "bom", "bom"])
        self.assertEqual(intervals, [1, 6, 15])
        self.assertEqual(item["ef"], 2.5)

    def test_ease_factor_moves_with_grade(self) -> None:
        self.assertAlmostEqual(self.run_grades(["facil"])[0]["ef"], 2.6)
        self.assertAlmostEqual(self.run_grades(["dificil"])[0]["ef"], 2.36)
        item, intervals = self.run_grades(["bom", "bom", "esqueci"])
        self.assertEqual((item["repeticoes"], item["lapsos"], intervals[-1]), (0, 1, 1))
        self.assertAlmostEqual(item["ef"], 1.96)
        floor, _ = self.run_grades(["esqueci"] * 6)
        self.assertEqual(floor["ef"], 1.3)

    def test_fixed_ladder(self) -> None:
        ladder = srs.FixedLadderScheduler()
        item, intervals = {}, []
        for grade in ["bom", "bom", "bom", "bom", "esqueci"]:
            item.update(ladder.next_state(item, grade))
            intervals.append(item["intervalo"])
        self.assertEqual(intervals, [2, 4, 7, 7, 1])


class ScheduleDateTest(unittest.TestCase):
    today = date(2026, 3, 2)

    def test_without_exam(self) -> None:
        self.assertEqual(srs.schedule_date(15, self.today, None, 0.25), date(2026, 3, 17))

    def test_fraction_of_remaining_days(self) -> None:
        exam = self.today + timedelta(days=40)
        self.assertEqual(srs.schedule_date(30, self.today, exam, 0.5), self.today + timedelta(days=20))
        near = self.today + timedelta(days=3)
        self.assertEqual(srs.schedule_date(30, self.today, near, 0.5, repetitions=0), self.today + timedelta(days=1))
        self.assertEqual(srs.schedule_date(30, self.today, near, 0.5, repetitions=3), self.today + timedelta(days=2))

    def test_never_after_the_eve(self) -> None:
        exam = self.today + timedelta(days=5)
        due = srs.schedule_date(15, self.today, exam, 1.0)
        self.assertEqual(due, exam - timedelta(days=1))
        self.assertIsNone(srs.schedule_date(1, self.today, self.today + timedelta(days=1), 0.25))

    def test_after_exam_no_cap(self) -> None:
        self.assertEqual(srs.schedule_date(6, self.today, self.today - timedelta(days=3), 0.25), self.today + timedelta(days=6))


class AgendaTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now)
        self.today = self.now.date()

    def test_schedule_is_idempotent_and_validates(self) -> None:
        first = srs.schedule(self.paths, ["prob-classica", "bayes"], self.today)
        again = srs.schedule(self.paths, ["prob-classica"], self.today)
        self.assertEqual(first["agendados"], ["prob-classica", "bayes"])
        self.assertEqual(again["ja_existiam"], ["prob-classica"])
        self.assertEqual(len(srs.load_items(self.paths)), 2)
        with self.assertRaises(TutorError):
            srs.schedule(self.paths, ["nao-existe"], self.today)
        with self.assertRaises(TutorError):
            srs.review(self.paths, "espaco-amostral", "bom", self.today)

    def test_review_cycle_respects_exam(self) -> None:
        srs.schedule(self.paths, ["prob-classica"], self.today)
        day = self.today + timedelta(days=1)
        self.assertEqual([i["conceito"] for i in srs.due_today(self.paths, day)["hoje"]], ["prob-classica"])
        exam = date(2026, 3, 30)
        seen = []
        for _ in range(8):
            result = srs.review(self.paths, "prob-classica", "facil", day)
            if result["proxima"] is None:
                self.assertTrue(result["concluido_ate_a_prova"])
                break
            next_day = date.fromisoformat(result["proxima"])
            self.assertLess(next_day, exam, "nenhuma revisão depois da véspera")
            seen.append(next_day)
            day = next_day
        self.assertEqual(seen[-1], exam - timedelta(days=1))

    def test_daily_limit_and_triage(self) -> None:
        materia = read_json(self.paths.materia)
        materia["revisao"]["max_por_dia"] = 2
        write_json(self.paths.materia, materia)
        srs.schedule(self.paths, ["espaco-amostral", "prob-classica", "prob-condicional", "bayes"], self.today)
        items = srs.load_items(self.paths)
        items[3]["lapsos"] = 2
        srs.save_items(self.paths, items)
        result = srs.due_today(self.paths, self.today + timedelta(days=1))
        self.assertEqual(len(result["hoje"]), 2)
        self.assertEqual(result["excedentes"], 2)
        self.assertEqual(result["hoje"][0]["conceito"], "bayes", "mais lapsos primeiro")

    def test_after_exam_items_return(self) -> None:
        srs.schedule(self.paths, ["bayes"], self.today)
        items = srs.load_items(self.paths)
        items[0]["proxima"] = None
        srs.save_items(self.paths, items)
        self.assertEqual(srs.due_today(self.paths, date(2026, 3, 29))["hoje"], [])
        self.assertEqual(len(srs.due_today(self.paths, date(2026, 4, 2))["hoje"]), 1)


class BalanceTest(unittest.TestCase):
    def test_budget_is_split_by_urgency(self) -> None:
        allocation = srs.balance({"a": 20, "b": 20, "c": 1}, {"a": 2, "b": 30, "c": None}, 15)
        self.assertEqual(sum(allocation.values()), 15)
        self.assertGreater(allocation["a"], allocation["b"])
        self.assertEqual(allocation["c"], 1)
        self.assertTrue(all(allocation[s] <= n for s, n in {"a": 20, "b": 20, "c": 1}.items()))

    def test_small_budget_keeps_minimum(self) -> None:
        self.assertEqual(srs.balance({"a": 5, "b": 5}, {"a": 1, "b": 1}, 3), {"a": 2, "b": 2})


class ReviewCommandsTest(TempWorkspaceCase):
    def test_all_subjects_listing(self) -> None:
        build_subject(self.subjects, self.now, slug="prob")
        build_subject(self.subjects, self.now, slug="estatistica", exam="2026-03-10")
        for slug in ("prob", "estatistica"):
            code, _ = self.run_cli("revisao", "agendar", "--materia", slug, "--conceito", "bayes", "--conceito", "prob-classica")
            self.assertEqual(code, 0)
        code, out = self.run_cli("revisao", "listar", "--todas", when=self.now + timedelta(days=1))
        self.assertEqual(code, 0, out)
        self.assertEqual(set(out["materias"]), {"prob", "estatistica"})


if __name__ == "__main__":
    unittest.main()
