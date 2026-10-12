"""Plano: calendário reverso, dias reservados, descanso semanal, sem data e depois da prova."""

from __future__ import annotations

import unittest
from datetime import date, datetime

from tests.fixtures import CONCEPTS, materia
from tutor.attempts import Attempt
from tutor.knowledge_map import Concept, KnowledgeMap
from tutor.learner import DEFAULT_PARAMS, estimate_concepts
from tutor.planner import build_plan, pace_capacity, render, study_days, trail_status

TODAY = date(2026, 3, 2)  # segunda-feira


def answer(qid: str) -> Attempt:
    return Attempt(seq=0, id=qid, at=datetime(2026, 3, 1, 10, 0), mode="treino", answer="A", dont_know=False,
                   confidence=3, hints=0, seconds=30, correct=True, after_reveal=False)


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
        self.assertFalse(days[0].get("diagnostico"), "iniciante começa aprendendo, sem diagnóstico")
        flat = [c for d in days for c in d["conceitos"]]
        self.assertEqual(flat, ["espaco-amostral", "prob-classica", "prob-condicional", "bayes"])
        self.assertEqual(plan["trilha"]["total"], 4)
        self.assertFalse(plan["apertado"])

    def test_diagnostic_only_for_non_beginners(self) -> None:
        for level in ("intermediario", "avancado"):
            plan = build_plan(materia("2026-03-22", nivel=level), kmap(), estimates(), False, TODAY)
            self.assertTrue(plan["dias"][0].get("diagnostico"), level)
        plan = build_plan(materia("2026-03-22", nivel="intermediario"), kmap(), estimates(), True, TODAY)
        self.assertFalse(plan["dias"][0].get("diagnostico"), "com tentativas, sem diagnóstico")

    def test_tight_plan_keeps_every_concept(self) -> None:
        many = KnowledgeMap({f"c{i:02d}": Concept(f"c{i:02d}", f"C{i}", "t", 1.0, (), "fontes") for i in range(20)})
        plan = build_plan(materia("2026-03-05"), many, estimates(many), True, TODAY)
        flat = [c for d in plan["dias"] for c in d["conceitos"]]
        self.assertEqual(sorted(flat), sorted(many.concepts), "nenhum conceito fica sem dia")
        self.assertEqual(flat, plan["trilha"]["ordem"])
        self.assertTrue(plan["apertado"])
        self.assertEqual(plan["ritmo_necessario"], 20)

    def test_count_distribution(self) -> None:
        seven = KnowledgeMap({f"c{i}": Concept(f"c{i}", f"C{i}", "t", 1.0, (), "fontes") for i in range(7)})
        plan = build_plan(materia("2026-03-07"), seven, estimates(seven), True, TODAY)  # 5 dias: 3 livres
        sizes = [len(d["conceitos"]) for d in plan["dias"] if d["tipo"] == "estudo"]
        self.assertEqual(sizes, [3, 2, 2])

    def test_exam_tomorrow_on_a_rest_day(self) -> None:
        sunday = date(2026, 3, 8)
        plan = build_plan(materia("2026-03-09", dias_por_semana=6), kmap(), estimates(), True, sunday)
        self.assertEqual([d["data"] for d in plan["dias"]], ["2026-03-08"])
        self.assertEqual(len(plan["dias"][0]["conceitos"]), 4, "sem dia livre, os conceitos vão para os dias reservados")

    def test_after_exam_keeps_the_trail(self) -> None:
        plan = build_plan(materia("2026-03-01"), kmap(), estimates(), True, TODAY)
        self.assertEqual(plan["modo"], "pos_prova")
        self.assertEqual(len(plan["trilha"]["pendentes"]), 4)
        self.assertIn("Teorema de Bayes", render(materia("2026-03-01"), kmap(), plan, estimates(), TODAY))

    def test_without_date_is_never_tight(self) -> None:
        many = KnowledgeMap({f"c{i}": Concept(f"c{i}", f"C{i}", "t", 1.0, (), "fontes") for i in range(40)})
        plan = build_plan(materia(None), many, estimates(many), True, TODAY)
        self.assertFalse(plan["apertado"])

    def test_pace_capacity(self) -> None:
        self.assertEqual([pace_capacity(materia(nivel=n, tempo_diario_min=60))
                          for n in ("iniciante", "intermediario", "avancado")], [2, 3, 4])
        self.assertEqual(pace_capacity(materia(tempo_diario_min=None)), 3)
        self.assertEqual(pace_capacity(materia(tempo_diario_min=10)), 1)
        self.assertEqual(pace_capacity(materia(nivel=None, tempo_diario_min=60)), 3)

    def test_trail_status(self) -> None:
        questions = {f"q{i}": {"id": f"q{i}", "conceitos": [cid], "dificuldade": 2}
                     for i, cid in enumerate(["espaco-amostral", "espaco-amostral", "prob-classica", "prob-classica",
                                              "prob-condicional", "prob-condicional", "bayes"])}
        history = [answer("q0"), answer("q1"), answer("q2"), answer("q4"), answer("q5")]
        studied = {"espaco-amostral": "2026-03-01", "prob-classica": "2026-03-01"}
        trail = trail_status(kmap(), questions, history, studied, DEFAULT_PARAMS)
        self.assertEqual(trail["concluidos"], ["espaco-amostral"], "estudado e com 2 respostas")
        self.assertIn("prob-classica", trail["pendentes"], "estudado, mas só 1 resposta")
        self.assertIn("prob-condicional", trail["pendentes"], "2 respostas, mas não estudado")
        self.assertEqual(trail["sem_questoes"], ["bayes"])
        text = render(materia("2026-03-22"), kmap(), build_plan(materia("2026-03-22"), kmap(), estimates(), True, TODAY,
                                                                trail=trail), estimates(), TODAY)
        self.assertIn("Faltam questões para concluir: Teorema de Bayes", text)
        self.assertIn("- [x] Espaço amostral (`espaco-amostral`): concluído", text)
        self.assertIn("Trilha: 1 de 4 conceitos concluídos", text)

    def test_short_horizon(self) -> None:
        plan = build_plan(materia("2026-03-06"), kmap(), estimates(), True, TODAY)
        self.assertEqual([d["tipo"] for d in plan["dias"]][-2:], ["simulado", "revisao-final"])
        self.assertFalse(plan["dias"][0].get("diagnostico"))

    def test_without_date_and_after_exam(self) -> None:
        plan = build_plan(materia(None), kmap(), estimates(), True, TODAY)
        self.assertEqual(plan["modo"], "sem_data")
        self.assertTrue(all(d["tipo"] == "estudo" for d in plan["dias"]))
        self.assertEqual(build_plan(materia("2026-03-01"), kmap(), estimates(), True, TODAY)["modo"], "pos_prova")

    def test_trail_done(self) -> None:
        trail = trail_status(kmap(), {}, [], set(), DEFAULT_PARAMS)
        done = {**trail, "concluidos": trail["ordem"], "pendentes": [], "proximos": [], "sem_questoes": [], "concluida": True}
        plan = build_plan(materia("2026-03-22"), kmap(), estimates(), True, TODAY, trail=done)
        self.assertTrue(all(not d["conceitos"] for d in plan["dias"]))
        self.assertIn("Trilha concluída", render(materia("2026-03-22"), kmap(), plan, estimates(), TODAY))

    def test_render(self) -> None:
        data = materia("2026-03-22")
        data["prova"]["data_confirmada"] = False
        plan = build_plan(data, kmap(), estimates(), False, TODAY)
        text = render(data, kmap(), plan, estimates(), TODAY)
        self.assertIn("| D-20 (seg) | 2026-03-02 |", text)
        self.assertIn("data provisória", text)
        self.assertIn("- [ ] Espaço amostral (`espaco-amostral`): a estudar; 0 de 2 respostas", text)
        self.assertIn("Trilha: 0 de 4 conceitos concluídos", text)
        for word in ("Priorize", "cortar", "cortes", "deixar de lado"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
