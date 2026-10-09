"""Plano: calendário reverso, dias reservados, descanso semanal, sem data e depois da prova."""

from __future__ import annotations

import unittest
from datetime import date, datetime

from tests.fixtures import CONCEPTS, materia
from tutor.knowledge_map import Concept, KnowledgeMap
from tutor.learner import DEFAULT_PARAMS, estimate_concepts
from tutor.planner import build_plan, render, study_days

TODAY = date(2026, 3, 2)  # segunda-feira


def kmap() -> KnowledgeMap:
    return KnowledgeMap({
        c["id"]: Concept(c["id"], c["nome"], c["tema"], float(c["peso"]), tuple(c["prerequisitos"]), "fontes")
        for c in CONCEPTS
    })


def estimates(map_=None):
    return estimate_concepts(map_ or kmap(), {}, [], datetime(2026, 3, 2), DEFAULT_PARAMS)


class PlannerTest(unittest.TestCase):
    def test_rest_days(self) -> None:
        days = study_days(TODAY, date(2026, 3, 15), 6)
        self.assertEqual(len(days), 12)
        self.assertTrue(all(d.weekday() != 6 for d in days))
        self.assertEqual(len(study_days(TODAY, date(2026, 3, 15), 7)), 14)

    def test_reverse_calendar(self) -> None:
        plan = build_plan(materia("2026-03-22"), kmap(), estimates(), False, TODAY)
        days = plan["dias"]
        self.assertEqual(plan["modo"], "prova")
        self.assertEqual(days[-1]["data"], "2026-03-21")
        self.assertEqual([d["tipo"] for d in days[-3:]], ["simulado", "reforco", "revisao-final"])
        self.assertTrue(days[0].get("diagnostico"))
        flat = [c for d in days for c in d["conceitos"]]
        self.assertEqual(flat, ["espaco-amostral", "prob-classica", "prob-condicional", "bayes"])
        self.assertEqual(plan["cobertura"], 1.0)
        self.assertFalse(plan["apertado"])

    def test_short_horizon(self) -> None:
        plan = build_plan(materia("2026-03-06"), kmap(), estimates(), True, TODAY)
        self.assertEqual([d["tipo"] for d in plan["dias"]][-2:], ["simulado", "revisao-final"])
        self.assertFalse(plan["dias"][0].get("diagnostico"))

    def test_without_date_and_after_exam(self) -> None:
        plan = build_plan(materia(None), kmap(), estimates(), True, TODAY)
        self.assertEqual(plan["modo"], "sem_data")
        self.assertTrue(all(d["tipo"] == "estudo" for d in plan["dias"]))
        self.assertEqual(build_plan(materia("2026-03-01"), kmap(), estimates(), True, TODAY)["modo"], "pos_prova")

    def test_tight_plan_is_flagged(self) -> None:
        many = KnowledgeMap({f"c{i}": Concept(f"c{i}", f"C{i}", "t", 1.0, (), "fontes") for i in range(20)})
        plan = build_plan(materia("2026-03-05"), many, estimates(many), True, TODAY)
        self.assertTrue(plan["apertado"])

    def test_render(self) -> None:
        data = materia("2026-03-22")
        data["prova"]["data_confirmada"] = False
        plan = build_plan(data, kmap(), estimates(), False, TODAY)
        text = render(data, kmap(), plan, estimates(), TODAY)
        self.assertIn("| D-20 (seg) | 2026-03-02 |", text)
        self.assertIn("data provisória", text)
        self.assertIn("- [ ] Espaço amostral (`espaco-amostral`): sem tentativas", text)


if __name__ == "__main__":
    unittest.main()
