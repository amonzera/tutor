"""Seleção: prioridades, intercalação, exclusão de não verificadas no simulado e diagnóstico."""

from __future__ import annotations

import random
import unittest
from datetime import timedelta

from tests.fixtures import answer_of, build_subject, mc_draft_item, qid, wrong_of
from tests.helpers import TempWorkspaceCase
from tutor import attempts, selection
from tutor.bank import load_bank, save_bank
from tutor.core import TutorError


class SelectionTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now)

    def answer(self, index: int, correct: bool, confidence: int, when=None) -> None:
        when = when or self.now
        attempts.present(self.paths, qid(index), "treino", when)
        attempts.check(self.paths, qid(index), answer_of(index) if correct else wrong_of(index), confidence, 0, 30, when)

    def pick(self, n=8, mode="treino", when=None, **filters):
        when = when or self.now + timedelta(days=1)
        return [q["id"] for q in selection.next_questions(self.paths, mode, n, filters.get("tema"), filters.get("conceito"),
                                                          when, random.Random(1))]

    def test_output_hides_theme(self) -> None:
        picks = selection.next_questions(self.paths, "treino", 3, None, None, self.now, random.Random(1))
        self.assertEqual(len(picks), 3)
        self.assertTrue(all(set(p) == {"id", "tipo"} for p in picks))

    def test_priorities(self) -> None:
        self.answer(3, False, 5)  # erro com confiança alta
        self.answer(5, False, 2)  # erro com confiança baixa
        self.answer(1, True, 1)   # acerto sem confiança
        self.answer(2, True, 5)   # acerto confiante
        order = self.pick()
        self.assertEqual(order[0], qid(3))
        self.assertLess(order.index(qid(5)), order.index(qid(2)))
        self.assertLess(order.index(qid(1)), order.index(qid(2)))
        self.assertGreaterEqual(order.index(qid(2)), 6, "acerto confiante fica entre os últimos")

    def test_interleaving_avoids_repeating_theme(self) -> None:
        bank = load_bank(self.paths)
        order = self.pick(n=6)
        themes = [bank[q]["tema"] for q in order]
        repeats = sum(1 for a, b in zip(themes, themes[1:]) if a == b)
        self.assertLessEqual(repeats, 1, themes)

    def test_filters(self) -> None:
        bank = load_bank(self.paths)
        self.assertTrue(all(bank[q]["tema"] == "condicional" for q in self.pick(tema="condicional")))
        self.assertTrue(all("bayes" in bank[q]["conceitos"] for q in self.pick(conceito="bayes")))

    def test_unverified_allowed_in_practice_not_in_exam(self) -> None:
        bank = load_bank(self.paths)
        for index in range(1, 9):
            bank[qid(index)]["verificacao"] = "pendente" if index > 2 else "verificada"
        bank[qid(2)]["verificacao"] = "divergente"
        save_bank(self.paths, bank)
        self.assertNotIn(qid(2), self.pick())
        self.assertIn(qid(5), self.pick())
        with self.assertRaises(TutorError) as caught:
            selection.build_exam(self.paths, 4, self.now)
        self.assertEqual(caught.exception.code, "banco_insuficiente")

    def test_exam_is_stratified_and_timed(self) -> None:
        ids, limit, forecast = selection.build_exam(self.paths, 4, self.now, random.Random(3))
        bank = load_bank(self.paths)
        themes = sorted(bank[q]["tema"] for q in ids)
        self.assertEqual(themes, ["condicional", "condicional", "fundamentos", "fundamentos"])
        self.assertEqual(limit, 40)
        self.assertFalse(forecast["disponivel"])

    def test_diagnostic_covers_concepts_in_order(self) -> None:
        order = self.pick(mode="diagnostico", n=4)
        bank = load_bank(self.paths)
        concepts = [bank[q]["conceitos"][0] for q in order]
        self.assertEqual(concepts, ["espaco-amostral", "prob-classica", "prob-condicional", "bayes"])

    def test_diagnostic_default_size(self) -> None:
        picks = selection.next_questions(self.paths, "diagnostico", None, None, None, self.now, random.Random(1))
        self.assertEqual(len(picks), 4)

    def test_new_concept_starts_easy_and_leaves_recent_for_last(self) -> None:
        extra = [mc_draft_item("espaco-amostral", "A", 9, dificuldade=1), mc_draft_item("espaco-amostral", "B", 10, dificuldade=3)]
        paths = build_subject(self.subjects, self.now, slug="dif", extra_questions=extra)

        def picks(when):
            return [q["id"] for q in selection.next_questions(paths, "treino", 4, None, "espaco-amostral", when,
                                                              random.Random(1))]

        order = picks(self.now)
        self.assertEqual(order[0], qid(9, "dif"), "a mais fácil primeiro")
        self.assertEqual(order[-1], qid(10, "dif"), "a mais difícil por último")
        attempts.present(paths, qid(9, "dif"), "treino", self.now)
        attempts.check(paths, qid(9, "dif"), "A", 3, 0, 30, self.now)
        self.assertEqual(picks(self.now + timedelta(hours=1))[-1], qid(9, "dif"), "respondida há pouco vai para o fim")

    def scores(self):
        materia, kmap, questions, history, estimates = selection._context(self.paths, self.now)
        return selection.score_questions(questions, kmap, estimates, history, set(), self.now.date())

    def test_weak_prerequisite_lowers_priority(self) -> None:
        before = self.scores()
        self.assertAlmostEqual(before[qid(5)] / before[qid(7)], 1.3 / 1.2, places=3)
        for _ in range(2):
            for index in (3, 4):
                self.answer(index, False, 3, when=self.now - timedelta(days=3))
        after = self.scores()
        self.assertLess(after[qid(5)], after[qid(7)] * 0.5, "condicional depende de clássica, que está fraca")
        self.assertGreater(after[qid(3)], after[qid(1)], "o próprio conceito fraco sobe")


if __name__ == "__main__":
    unittest.main()
