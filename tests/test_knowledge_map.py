"""Mapa de conhecimento: validação (ids, pré-requisitos, ciclos, fontes) e ordem de estudo."""

from __future__ import annotations

import copy
import unittest

from tests.fixtures import CONCEPTS
from tests.helpers import TempWorkspaceCase
from tutor.core import SubjectPaths, TutorError, write_json
from tutor.knowledge_map import Concept, KnowledgeMap, load_map, validate_map_data


class KnowledgeMapTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        folder = self.make_subject("prob", {"nome": "Probabilidade"})
        self.paths = SubjectPaths(folder)
        (folder / "fontes" / "apostila.md").write_text("# Apostila\n", encoding="utf-8")
        self.concepts = [{**c, "fontes": [{"arquivo": "apostila.md"}]} for c in CONCEPTS]

    def data(self, concepts=None):
        return {"schema_version": 1, "conceitos": concepts if concepts is not None else self.concepts}

    def test_valid_map(self) -> None:
        self.assertEqual(validate_map_data(self.data(), self.paths), [])

    def test_problems_are_reported(self) -> None:
        broken = copy.deepcopy(self.concepts)
        broken[1]["id"] = "Espaço Amostral"
        broken[2]["prerequisitos"] = ["nao-existe"]
        broken[3]["peso"] = 9
        broken.append({"id": "bayes", "nome": "Repetido", "tema": "x", "peso": 1, "fontes": [{"arquivo": "apostila.md"}]})
        broken.append({"id": "sem-fonte", "nome": "Sem fonte", "tema": "x", "peso": 1})
        broken.append({"id": "fonte-errada", "nome": "Errada", "tema": "x", "peso": 1, "fontes": [{"arquivo": "nao.pdf"}]})
        problems = " | ".join(validate_map_data(self.data(broken), self.paths))
        for expected in ["id inválido", "pré-requisito inexistente", "'peso'", "ids repetidos: bayes",
                         "exige ao menos uma referência", "arquivo de fonte inexistente: nao.pdf"]:
            self.assertIn(expected, problems)

    def test_general_knowledge_needs_no_source(self) -> None:
        concepts = self.concepts + [{"id": "extra", "nome": "Extra", "tema": "x", "peso": 1, "origem": "conhecimento-geral"}]
        self.assertEqual(validate_map_data(self.data(concepts), self.paths), [])

    def test_cycle_is_detected(self) -> None:
        concepts = copy.deepcopy(self.concepts)
        concepts[0]["prerequisitos"] = ["bayes"]
        problems = validate_map_data(self.data(concepts), self.paths)
        self.assertTrue(any("ciclo" in p for p in problems), problems)

    def test_topological_order_and_weights(self) -> None:
        concepts = self.concepts + [
            {"id": "independente-leve", "nome": "Leve", "tema": "x", "peso": 1, "fontes": [{"arquivo": "apostila.md"}]},
            {"id": "independente-pesado", "nome": "Pesado", "tema": "x", "peso": 5, "fontes": [{"arquivo": "apostila.md"}]},
        ]
        write_json(self.paths.mapa, self.data(concepts))
        kmap = load_map(self.paths)
        order = kmap.topological_order()
        for before, after in [("espaco-amostral", "prob-classica"), ("prob-classica", "prob-condicional"),
                              ("prob-condicional", "bayes"), ("independente-pesado", "independente-leve")]:
            self.assertLess(order.index(before), order.index(after))
        self.assertAlmostEqual(sum(kmap.weights().values()), 1.0)

    def test_trail_order(self) -> None:
        def concept(cid: str, weight: float, *prereqs: str) -> Concept:
            return Concept(cid, cid.upper(), "t", float(weight), prereqs, "fontes")

        inverted = KnowledgeMap({"a": concept("a", 1), "b": concept("b", 5, "a"), "c": concept("c", 3), "d": concept("d", 3)})
        self.assertEqual(inverted.trail_order(), ["a", "b", "c", "d"], "o pré-requisito leve herda o peso de quem ele libera")
        tied = KnowledgeMap({"x": concept("x", 3), "y": concept("y", 3), "z": concept("z", 3)})
        self.assertEqual(tied.trail_order({"x": 1.0, "y": 3.0, "z": 2.0}), ["y", "z", "x"], "mais difícil antes")
        self.assertEqual(tied.trail_order(), ["x", "y", "z"], "sem dificuldade, desempata pelo id")
        self.assertEqual(tied.trail_order(practicable={"y", "z"}), ["y", "z", "x"], "sem questões fica por último")
        chain = KnowledgeMap({"base": concept("base", 1), "topo": concept("topo", 2, "base"), "solto": concept("solto", 5)})
        self.assertEqual(chain.trail_order(), ["solto", "base", "topo"], "peso manda, pré-requisito sempre antes")

    def test_load_map_rejects_invalid(self) -> None:
        write_json(self.paths.mapa, self.data([{"id": "x"}]))
        with self.assertRaises(TutorError) as caught:
            load_map(self.paths)
        self.assertEqual(caught.exception.code, "mapa_invalido")
        self.assertTrue(caught.exception.extra["problemas"])


if __name__ == "__main__":
    unittest.main()
