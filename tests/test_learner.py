"""Modelo do aluno: domínio com decaimento, calibração e preparo (com teste do aluno sintético)."""

from __future__ import annotations

import itertools
import random
import unittest
from datetime import datetime, timedelta

from tutor.attempts import Attempt
from tutor.knowledge_map import Concept, KnowledgeMap
from tutor.learner import DEFAULT_PARAMS, calibration, estimate_concepts, readiness

NOW = datetime(2026, 3, 2, 10, 0)
_SEQ = itertools.count(1)


def kmap(n: int = 4) -> KnowledgeMap:
    return KnowledgeMap({f"c{i}": Concept(f"c{i}", f"Conceito {i}", "tema", 1.0, (), "fontes") for i in range(n)})


def bank(n_concepts: int = 4, per_concept: int = 5) -> dict:
    questions = {}
    for c in range(n_concepts):
        for k in range(per_concept):
            questions[f"q{c}-{k}"] = {"id": f"q{c}-{k}", "tipo": "multipla-escolha",
                                     "alternativas": {x: x for x in "ABCDE"}, "conceitos": [f"c{c}"]}
    return questions


def attempt(qid: str, correct: bool, days_ago: float = 0, confidence: int = 3, hints: int = 0,
            after_reveal: bool = False) -> Attempt:
    return Attempt(seq=next(_SEQ), id=qid, at=NOW - timedelta(days=days_ago), mode="treino", answer="A", dont_know=False,
                   confidence=confidence, hints=hints, seconds=30, correct=correct, after_reveal=after_reveal)


class EstimateTest(unittest.TestCase):
    def test_no_data(self) -> None:
        est = estimate_concepts(kmap(), bank(), [], NOW, DEFAULT_PARAMS)
        self.assertTrue(all(e.status == "sem_dados" for e in est.values()))
        self.assertAlmostEqual(est["c0"].mean, 0.5)

    def test_status_follows_evidence(self) -> None:
        good = [attempt(f"q0-{k % 5}", True, days_ago=k * 0.1) for k in range(8)]
        bad = [attempt(f"q1-{k}", False) for k in range(4)]
        est = estimate_concepts(kmap(), bank(), good + bad, NOW, DEFAULT_PARAMS)
        self.assertEqual(est["c0"].status, "dominado")
        self.assertEqual(est["c1"].status, "fraco")
        self.assertGreaterEqual(est["c1"].mean, 0.2, "piso de chute com 5 alternativas")
        self.assertLessEqual(est["c0"].low, est["c0"].mean)
        self.assertLessEqual(est["c0"].mean, est["c0"].high)

    def test_old_evidence_weighs_less(self) -> None:
        recent_wrong_old_right = [attempt("q0-0", True, days_ago=90) for _ in range(5)] + [attempt("q0-1", False)]
        est = estimate_concepts(kmap(), bank(), recent_wrong_old_right, NOW, DEFAULT_PARAMS)
        no_decay = dict(DEFAULT_PARAMS, meia_vida_dias=10_000)
        est_flat = estimate_concepts(kmap(), bank(), recent_wrong_old_right, NOW, no_decay)
        self.assertLess(est["c0"].mean, est_flat["c0"].mean)

    def test_heavy_hints_count_as_error_and_reveal_is_ignored(self) -> None:
        helped = [attempt("q0-0", True, hints=3) for _ in range(5)]
        est = estimate_concepts(kmap(), bank(), helped, NOW, DEFAULT_PARAMS)
        self.assertLess(est["c0"].mean, 0.5)
        revealed = [attempt("q1-0", True, after_reveal=True) for _ in range(5)]
        est = estimate_concepts(kmap(), bank(), revealed, NOW, DEFAULT_PARAMS)
        self.assertEqual(est["c1"].attempts, 0)


class CalibrationTest(unittest.TestCase):
    def test_overconfidence_is_detected(self) -> None:
        pool = [attempt("q0-0", k % 2 == 0, confidence=5) for k in range(20)]
        result = calibration(pool)
        self.assertGreater(result["vies"], 0.3)
        self.assertIn("superconfiante", result["leitura"])
        self.assertEqual(result["erros_com_confianca_alta"], 10)

    def test_excludes_hints_and_reveals(self) -> None:
        pool = [attempt("q0-0", True, confidence=4), attempt("q0-1", False, hints=2), attempt("q0-2", True, after_reveal=True)]
        self.assertEqual(calibration(pool)["n"], 1)
        self.assertEqual(calibration([])["n"], 0)

    def test_well_calibrated(self) -> None:
        rng = random.Random(7)
        pool = []
        for level, probability in {1: 0.2, 3: 0.6, 5: 0.95}.items():
            pool += [attempt("q0-0", rng.random() < probability, confidence=level) for _ in range(200)]
        result = calibration(pool)
        self.assertLess(abs(result["vies"]), 0.05)
        self.assertEqual(result["leitura"], "calibrado")


class ReadinessTest(unittest.TestCase):
    def test_needs_coverage(self) -> None:
        est = estimate_concepts(kmap(), bank(), [attempt("q0-0", True)], NOW, DEFAULT_PARAMS)
        result = readiness(est, 10, DEFAULT_PARAMS)
        self.assertFalse(result["disponivel"])
        self.assertTrue(result["praticar_primeiro"])

    def test_deterministic_and_bounded(self) -> None:
        history = [attempt(f"q{c}-{k}", (c + k) % 3 != 0) for c in range(4) for k in range(3)]
        est = estimate_concepts(kmap(), bank(), history, NOW, DEFAULT_PARAMS)
        first = readiness(est, 10, DEFAULT_PARAMS, seed="x")
        self.assertEqual(first, readiness(est, 10, DEFAULT_PARAMS, seed="x"))
        self.assertTrue(first["disponivel"])
        low, high = first["faixa_80"]
        self.assertTrue(0 <= low <= first["mediana"] <= high <= 10)
        self.assertIn("Não é previsão de nota", first["aviso"])

    def test_synthetic_student_interval_coverage(self) -> None:
        """A faixa de 80% deve conter a nota real de um aluno sintético em cerca de 80% dos casos."""
        rng = random.Random(2026)
        concepts, questions = kmap(5), bank(5, 6)
        n_exam, hits, students = 12, 0, 150
        for s in range(students):
            truth = {f"c{c}": rng.uniform(0.2, 0.95) for c in range(5)}
            history = []
            for c in range(5):
                for k in range(rng.randint(3, 8)):
                    history.append(attempt(f"q{c}-{k % 6}", rng.random() < truth[f"c{c}"], days_ago=rng.uniform(0, 10)))
            est = estimate_concepts(concepts, questions, history, NOW, DEFAULT_PARAMS)
            result = readiness(est, n_exam, DEFAULT_PARAMS, seed=f"aluno-{s}")
            self.assertTrue(result["disponivel"])
            drawn = rng.choices(list(truth), k=n_exam)
            score = sum(1 for c in drawn if rng.random() < truth[c])
            low, high = result["faixa_80"]
            hits += low <= score <= high
        coverage = hits / students
        self.assertGreaterEqual(coverage, 0.70, f"cobertura {coverage:.2f}")
        self.assertLessEqual(coverage, 0.97, f"cobertura {coverage:.2f}")


if __name__ == "__main__":
    unittest.main()
