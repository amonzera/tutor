"""Painel e caderno de erros."""

from __future__ import annotations

import json
import unittest

from tests.fixtures import answer_of, build_subject, qid, wrong_of
from tests.helpers import TempWorkspaceCase
from tutor import attempts
from tutor.report import build_error_notebook, render_error_notebook


class ReportTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now)
        for index, correct, confidence in [(3, False, 5), (4, False, 4), (1, True, 2), (5, True, 3)]:
            attempts.present(self.paths, qid(index), "treino", self.now)
            attempts.check(self.paths, qid(index), answer_of(index) if correct else wrong_of(index), confidence, 0, 40, self.now)
        attempts.classify(self.paths, qid(3), "conceito", self.now)
        attempts.classify(self.paths, qid(4), "conceito", self.now)

    def test_dashboard(self) -> None:
        code, out = self.run_cli("painel", "--materia", "prob", "--escrever")
        self.assertEqual(code, 0, out)
        for key in ("conceitos", "por_tema", "tipos_de_erro", "calibracao", "preparo", "proximas_acoes", "revisoes"):
            self.assertIn(key, out)
        self.assertEqual(out["tipos_de_erro"], {"conceito": 2})
        classic = next(c for c in out["conceitos"] if c["conceito"] == "prob-classica")
        self.assertEqual(classic["estado"], "fraco")
        self.assertTrue(any("confiança alta" in a for a in out["proximas_acoes"]))
        text = self.paths.dominio.read_text(encoding="utf-8")
        self.assertIn("## Domínio por conceito", text)
        self.assertFalse(out["preparo"]["disponivel"])
        self.assertIn("Preparo estimado: indisponível (poucos dados", text)

    def test_error_notebook_never_shows_answers(self) -> None:
        notebook = build_error_notebook(self.paths)
        text = render_error_notebook(notebook, self.now) + json.dumps(notebook, ensure_ascii=False)
        self.assertEqual(notebook["conceitos"][0]["conceito"], "prob-classica")
        self.assertIn("erro de conceito repetido", notebook["conceitos"][0]["recorrente"])
        self.assertIn(f"equívoco típico {wrong_of(3)} (3)", text)
        self.assertNotIn("solução comentada", text)
        self.assertNotIn("resposta_correta", text)


if __name__ == "__main__":
    unittest.main()
