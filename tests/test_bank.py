"""Banco e gabarito: separação, codificação em repouso, importação, conferência e verificação cega."""

from __future__ import annotations

import json
import unittest

from tests.fixtures import answer_of, build_subject, mc_draft_item, qid, wrong_of
from tests.helpers import TempWorkspaceCase
from tutor.bank import (
    check_answer, compare_verification, import_draft, load_bank, load_key, normalize_letter, parse_number,
    public_view, record_verification,
)
from tutor.core import TutorError, write_json


class ImportTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now, verify=False)

    def test_answer_key_is_separate_and_encoded(self) -> None:
        questions = load_bank(self.paths)
        self.assertEqual(len(questions), 8)
        raw_bank = self.paths.questoes.read_text(encoding="utf-8")
        for key in ("resposta", "gabarito", "solucao", "distratores"):
            self.assertNotIn(f'"{key}"', raw_bank)
        raw_key = self.paths.gabarito.read_text(encoding="utf-8")
        self.assertNotIn("solução comentada", raw_key)
        self.assertNotIn("equívoco típico", raw_key)
        self.assertEqual(json.loads(raw_key)["codificacao"], "zlib+base64")
        self.assertEqual(load_key(self.paths)[qid(3)]["resposta"], answer_of(3))
        self.assertFalse((self.paths.rascunhos / "lote-01.json").exists(), "rascunho deve ser apagado")
        self.assertTrue(all(q["verificacao"] == "pendente" for q in questions.values()))
        self.assertEqual(questions[qid(1)]["tema"], "fundamentos", "tema herdado do conceito")

    def _draft(self, items, name="lote-02.json"):
        path = self.paths.rascunhos / name
        write_json(path, {"schema_version": 1, "lote": "lote-02", "questoes": items})
        return path

    def test_invalid_draft_imports_nothing(self) -> None:
        good = mc_draft_item("bayes", "A", 90)
        leaky = mc_draft_item("bayes", "B", 91)
        leaky["alternativas"]["B"] = "Esta é a alternativa (correta)"
        no_distractors = mc_draft_item("bayes", "C", 92)
        no_distractors["gabarito"]["distratores"] = {}
        unknown = mc_draft_item("conceito-que-nao-existe", "D", 93)
        answer_in_bank = mc_draft_item("bayes", "E", 94, resposta="E")
        with self.assertRaises(TutorError) as caught:
            import_draft(self.paths, self._draft([good, leaky, no_distractors, unknown, answer_in_bank]), self.now)
        problems = " | ".join(caught.exception.extra["problemas"])
        for expected in ["marca de resposta", "por que cada alternativa errada", "conceito inexistente", "'resposta'"]:
            self.assertIn(expected, problems)
        self.assertEqual(len(load_bank(self.paths)), 8)
        self.assertTrue((self.paths.rascunhos / "lote-02.json").exists(), "rascunho inválido fica para correção")

    def test_latex_in_drafts(self) -> None:
        good = mc_draft_item("bayes", "A", 95)
        good["enunciado"] = "Calcule $\\frac{1}{2} \\cdot \\theta$, a concentração $[X]$ e o preço de R$ 10,00."
        good["gabarito"]["solucao"] = "Como $\\beta = \\frac{a}{b}$, a resposta segue."
        import_draft(self.paths, self._draft([good]), self.now)
        self.assertEqual(len(load_bank(self.paths)), 9, "LaTeX bem escapado entra")
        broken = [mc_draft_item("bayes", "B", n) for n in (96, 97, 98)]
        broken[0]["enunciado"] = "Calcule $" + "\x0c" + "rac{1}{2}$."  # \frac com barra simples no JSON
        broken[1]["alternativas"]["A"] = "$" + "\t" + "heta$ vale 30 graus"  # \theta
        broken[2]["gabarito"]["solucao"] = "Use $" + "\n" + "u$ aqui."  # \nu
        with self.assertRaises(TutorError) as caught:
            import_draft(self.paths, self._draft(broken), self.now)
        self.assertEqual(" | ".join(caught.exception.extra["problemas"]).count("barra dupla"), 3)

    def test_leak_lint_ignores_math_notation(self) -> None:
        from tutor.bank import LEAK_MARKERS

        self.assertIsNone(LEAK_MARKERS.search("Quanto vale E[X] para essa variável?"))
        self.assertIsNone(LEAK_MARKERS.search("A concentração $[X]$ dobra."))
        self.assertIsNotNone(LEAK_MARKERS.search("[x] B) 1/2"))
        self.assertIsNotNone(LEAK_MARKERS.search("B) 1/2 \u2713"))

    def test_duplicate_id_needs_replace_flag(self) -> None:
        item = mc_draft_item("bayes", "A", 95, id=qid(1))
        with self.assertRaises(TutorError):
            import_draft(self.paths, self._draft([item]), self.now)
        crop = self.paths.figuras / f"{qid(1)}.png"
        crop.parent.mkdir(parents=True)
        crop.write_bytes(b"\x89PNG\r\n\x1a\n")
        result = import_draft(self.paths, self._draft([item]), self.now, replace=True)
        self.assertEqual(result["importadas"], [qid(1)])
        self.assertEqual(load_key(self.paths)[qid(1)]["resposta"], "A")
        self.assertFalse(crop.exists(), "o recorte da questão antiga não vale para a nova")

    def test_unknown_fields_are_refused(self) -> None:
        item = mc_draft_item("bayes", "A", 97, explicacao="a resposta é A porque...")
        with self.assertRaises(TutorError) as caught:
            import_draft(self.paths, self._draft([item]), self.now)
        self.assertIn("campos não permitidos", " ".join(caught.exception.extra["problemas"]))

    def test_replace_and_remove_reset_verification(self) -> None:
        record_verification(self.paths, qid(1), answer_of(1), 5, False, None, None, self.now)
        self.assertIn(qid(1), compare_verification(self.paths, self.now)["verificada"])
        import_draft(self.paths, self._draft([mc_draft_item("bayes", "A", 98, id=qid(1))]), self.now, replace=True)
        self.assertIn(qid(1), compare_verification(self.paths, self.now)["pendente"], "questão trocada não herda verificação")
        code, out = self.run_cli("banco", "remover", "--materia", "prob", "--questao", qid(8))
        self.assertEqual(code, 0, out)
        result = import_draft(self.paths, self._draft([mc_draft_item("bayes", "B", 99)]), self.now)
        self.assertEqual(result["importadas"], [qid(9)], "id removido não é reaproveitado")

    def test_draft_must_live_in_drafts_folder(self) -> None:
        outside = self.paths.root / "fora.json"
        write_json(outside, {"schema_version": 1, "questoes": [mc_draft_item("bayes", "A", 96)]})
        with self.assertRaises(TutorError):
            import_draft(self.paths, outside, self.now)

    def test_public_view_hides_theme_and_concepts(self) -> None:
        view = public_view(load_bank(self.paths)[qid(1)])
        self.assertEqual(set(view), {"id", "tipo", "enunciado", "alternativas"})


class CheckAnswerTest(unittest.TestCase):
    mc = {"id": "q", "tipo": "multipla-escolha", "alternativas": {k: k for k in "ABCDE"}}
    mc_entry = {"resposta": "C", "distratores": {"A": "confundiu P(A|B) com P(B|A)"}}

    def test_letter_normalization(self) -> None:
        for raw in ["c", "C", "(c)", "c)", "letra C", "Alternativa c", " C. "]:
            self.assertEqual(normalize_letter(raw, list("ABCDE")), "C")
        with self.assertRaises(TutorError):
            normalize_letter("F", list("ABCDE"))

    def test_multiple_choice(self) -> None:
        self.assertTrue(check_answer(self.mc, self.mc_entry, "c")["correta"])
        wrong = check_answer(self.mc, self.mc_entry, "A")
        self.assertFalse(wrong["correta"])
        self.assertEqual(wrong["por_que_tentadora"], "confundiu P(A|B) com P(B|A)")
        self.assertFalse(check_answer(self.mc, self.mc_entry, None)["correta"])

    def test_numeric(self) -> None:
        question = {"id": "n", "tipo": "numerica"}
        entry = {"resposta": {"valor": 0.25}, "erros_comuns": [{"valor": 0.5, "explicacao": "esqueceu de condicionar"}]}
        for raw in ["0,25", "0.25", "1/4", "25%", "0,2501"]:
            self.assertTrue(check_answer(question, entry, raw)["correta"], raw)
        wrong = check_answer(question, entry, "0,5")
        self.assertFalse(wrong["correta"])
        self.assertEqual(wrong["por_que_tentadora"], "esqueceu de condicionar")
        self.assertFalse(check_answer(question, entry, "0,3")["correta"])
        with self.assertRaises(TutorError):
            check_answer(question, entry, "um quarto")
        self.assertAlmostEqual(parse_number("-1,5e-3"), -0.0015)

    def test_open_question_returns_rubric(self) -> None:
        result = check_answer({"id": "o", "tipo": "aberta"}, {"rubrica": ["define evento", "dá exemplo"]}, "resposta")
        self.assertIsNone(result["correta"])
        self.assertEqual(result["rubrica"], ["define evento", "dá exemplo"])
        self.assertFalse(check_answer({"id": "o", "tipo": "aberta"}, {"rubrica": ["x"]}, None)["correta"])


class VerificationTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now, verify=False)

    def test_statuses(self) -> None:
        record_verification(self.paths, qid(1), answer_of(1), 5, False, None, None, self.now)
        record_verification(self.paths, qid(2), wrong_of(2), 4, False, None, None, self.now)
        record_verification(self.paths, qid(3), answer_of(3), 2, False, None, None, self.now)
        record_verification(self.paths, qid(4), "A", 3, False, "ambigua", "duas alternativas valem", self.now)
        record_verification(self.paths, qid(5), answer_of(5), 4, True, None, None, self.now)
        summary = compare_verification(self.paths, self.now)
        self.assertEqual(summary["divergente"], [qid(2)])
        self.assertIn(qid(1), summary["verificada"])
        self.assertIn(qid(5), summary["verificada"])
        self.assertEqual(sorted(summary["aviso"]), [qid(3), qid(4)])
        self.assertEqual(sorted(summary["pendente"]), [qid(i) for i in range(6, 9)])
        bank = load_bank(self.paths)
        self.assertIn("ambigua", bank[qid(4)]["aviso"])
        report = self.paths.verificacao_md.read_text(encoding="utf-8")
        self.assertIn("viu a marca oficial", report)
        self.assertNotIn("Alternativa", report)
        raw = self.paths.verificacao.read_text(encoding="utf-8")
        self.assertNotIn("duas alternativas valem", raw, "respostas do verificador também ficam codificadas")

    def test_open_question_needs_confirmation(self) -> None:
        open_item = {"tipo": "aberta", "enunciado": "Explique o que é um evento.", "conceitos": ["espaco-amostral"],
                     "gabarito": {"rubrica": ["subconjunto do espaço amostral"], "conceito_decisivo": "evento",
                                  "solucao": "subconjunto"}}
        paths = build_subject(self.subjects, self.now, slug="aberta", verify=False, extra_questions=[open_item])
        record_verification(paths, qid(9, "aberta"), "um subconjunto dos resultados", 4, False, None, None, self.now)
        self.assertIn(qid(9, "aberta"), compare_verification(paths, self.now)["pendente"])
        from tutor.bank import confirm_open, open_review

        review = open_review(paths, qid(9, "aberta"))
        self.assertEqual(review["resposta_verificador"], "um subconjunto dos resultados")
        self.assertEqual(review["rubrica"], ["subconjunto do espaço amostral"])
        confirm_open(paths, qid(9, "aberta"), "certo", None, self.now)
        self.assertIn(qid(9, "aberta"), compare_verification(paths, self.now)["verificada"])
        confirm_open(paths, qid(9, "aberta"), "errado", "faltou o espaço amostral", self.now)
        self.assertIn(qid(9, "aberta"), compare_verification(paths, self.now)["divergente"])
        with self.assertRaises(TutorError):
            open_review(paths, qid(1, "aberta"))
        from tutor.core import mark_step

        mark_step(paths, "banco", True)
        with self.assertRaises(TutorError) as caught:
            open_review(paths, qid(9, "aberta"))
        self.assertEqual(caught.exception.code, "fora_da_preparacao", "fora da preparação a rubrica não sai")

    def test_latest_round_wins(self) -> None:
        record_verification(self.paths, qid(1), wrong_of(1), 4, False, None, None, self.now)
        record_verification(self.paths, qid(1), answer_of(1), 4, False, None, None, self.now)
        self.assertIn(qid(1), compare_verification(self.paths, self.now)["verificada"])

    def test_input_validation(self) -> None:
        with self.assertRaises(TutorError):
            record_verification(self.paths, "nao-existe", "A", 4, False, None, None, self.now)
        with self.assertRaises(TutorError):
            record_verification(self.paths, qid(1), "A", 9, False, None, None, self.now)
        with self.assertRaises(TutorError):
            record_verification(self.paths, qid(1), "Z", 4, False, None, None, self.now)

    def test_numeric_verifier_answer_is_validated(self) -> None:
        numeric = {"tipo": "numerica", "enunciado": "Quanto vale 1/2 + 1/4?", "conceitos": ["prob-classica"],
                   "gabarito": {"resposta": {"valor": 0.75}, "conceito_decisivo": "soma", "solucao": "3/4"}}
        paths = build_subject(self.subjects, self.now, slug="num", verify=False, extra_questions=[numeric])
        with self.assertRaises(TutorError):
            record_verification(paths, qid(9, "num"), "três quartos", 4, False, None, None, self.now)
        record_verification(paths, qid(9, "num"), "0,75", 4, False, None, None, self.now)
        self.assertIn(qid(9, "num"), compare_verification(paths, self.now)["verificada"])


class BankCommandsTest(TempWorkspaceCase):
    def test_export_and_remove(self) -> None:
        build_subject(self.subjects, self.now)
        target = self.subjects.parent / "gabarito-legivel.json"
        code, out = self.run_cli("banco", "exportar", "--materia", "prob", "--para", str(target))
        self.assertEqual(code, 0, out)
        exported = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(exported["questoes"][0]["gabarito"]["resposta"], answer_of(1))
        code, out = self.run_cli("banco", "exportar", "--materia", "prob", "--para", str(target))
        self.assertEqual(out["erro"], "destino_existe")
        code, out = self.run_cli("banco", "remover", "--materia", "prob", "--questao", qid(8))
        self.assertEqual(code, 0)
        code, out = self.run_cli("validar", "--materia", "prob", "--etapa", "banco")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
