"""Tentativas: compromisso antes da correção, idempotência, revelação recente e simulado adiado."""

from __future__ import annotations

import unittest
from datetime import timedelta

from tests.fixtures import answer_of, build_subject, mc_draft_item, qid, wrong_of
from tests.helpers import TempWorkspaceCase
from tutor import attempts
from tutor.core import TutorError, read_json, read_jsonl


class PracticeFlowTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now)

    def test_check_requires_presentation(self) -> None:
        with self.assertRaises(TutorError) as caught:
            attempts.check(self.paths, qid(1), answer_of(1), 3, 0, None, self.now)
        self.assertEqual(caught.exception.code, "questao_nao_apresentada")

    def test_check_records_before_revealing(self) -> None:
        shown = attempts.present(self.paths, qid(1), "treino", self.now)
        self.assertNotIn("tema", shown["questao"])
        later = self.now + timedelta(seconds=95)
        result = attempts.check(self.paths, qid(1), wrong_of(1), 5, 1, None, later)
        self.assertFalse(result["correta"])
        self.assertEqual(result["resposta_correta"], answer_of(1))
        self.assertIn("equívoco típico", result["por_que_tentadora"])
        self.assertEqual(result["pendente"], "classificar")
        self.assertIn("confiança alta", result["alerta"])
        record = read_jsonl(self.paths.tentativas)[-1]
        self.assertEqual((record["confianca"], record["dicas"], record["segundos"]), (5, 1, 95))
        self.assertEqual(read_json(self.paths.sessao)["abertas"], {})

    def test_verification_mode_does_not_open_attempt(self) -> None:
        shown = attempts.present(self.paths, qid(1), "verificacao", self.now)
        self.assertEqual(shown["modo"], "verificacao")
        self.assertNotIn("tema", shown["questao"])
        self.assertEqual((read_json(self.paths.sessao) or {}).get("abertas", {}), {})
        with self.assertRaises(TutorError):
            attempts.check(self.paths, qid(1), answer_of(1), 3, 0, None, self.now)

    def test_validation_of_confidence_and_hints(self) -> None:
        attempts.present(self.paths, qid(1), "treino", self.now)
        for confidence, hints in [(0, 0), (6, 0), (3, -1), (3, 5)]:
            with self.subTest(confidence=confidence, hints=hints), self.assertRaises(TutorError):
                attempts.check(self.paths, qid(1), "A", confidence, hints, None, self.now)

    def test_repeated_call_is_idempotent(self) -> None:
        attempts.present(self.paths, qid(2), "treino", self.now)
        first = attempts.check(self.paths, qid(2), answer_of(2), 4, 0, 30, self.now)
        again = attempts.check(self.paths, qid(2), answer_of(2), 4, 0, 30, self.now + timedelta(minutes=2))
        self.assertTrue(again["repetida"])
        self.assertEqual(first["correta"], again["correta"])
        self.assertEqual(len(read_jsonl(self.paths.tentativas)), 1)
        with self.assertRaises(TutorError):
            attempts.check(self.paths, qid(2), answer_of(2), 4, 0, 30, self.now + timedelta(minutes=20))

    def test_after_reveal_flag(self) -> None:
        attempts.present(self.paths, qid(3), "treino", self.now)
        attempts.check(self.paths, qid(3), wrong_of(3), 3, 0, 20, self.now)
        soon = self.now + timedelta(hours=2)
        attempts.present(self.paths, qid(3), "treino", soon)
        self.assertTrue(attempts.check(self.paths, qid(3), answer_of(3), 3, 0, 20, soon)["apos_revelacao"])
        much_later = self.now + timedelta(days=3)
        attempts.present(self.paths, qid(3), "treino", much_later)
        self.assertNotIn("apos_revelacao", attempts.check(self.paths, qid(3), answer_of(3), 3, 0, 20, much_later))
        flags = [a.after_reveal for a in attempts.history(self.paths)]
        self.assertEqual(flags, [False, True, False])

    def test_attempts_in_the_same_second_do_not_collide(self) -> None:
        for _ in range(2):
            attempts.present(self.paths, qid(6), "treino", self.now)
            attempts.check(self.paths, qid(6), wrong_of(6), 3, 0, 5, self.now)
        attempts.classify(self.paths, qid(6), "conta", self.now)
        history = attempts.history(self.paths)
        self.assertEqual([a.seq for a in history], [1, 2])
        self.assertEqual([a.error_type for a in history], [None, "conta"])

    def test_dont_know_is_not_an_error_to_classify(self) -> None:
        attempts.present(self.paths, qid(4), "treino", self.now)
        result = attempts.check(self.paths, qid(4), None, 1, 4, None, self.now)
        self.assertFalse(result["correta"])
        self.assertNotIn("pendente", result)
        self.assertEqual(attempts.pending(attempts.history(self.paths))["classificar"], [])

    def test_classification(self) -> None:
        attempts.present(self.paths, qid(5), "treino", self.now)
        attempts.check(self.paths, qid(5), wrong_of(5), 2, 0, 10, self.now)
        self.assertEqual(attempts.pending(attempts.history(self.paths))["classificar"], [qid(5)])
        with self.assertRaises(TutorError):
            attempts.classify(self.paths, qid(5), "preguica", self.now)
        attempts.classify(self.paths, qid(5), "sinal", self.now)
        history = attempts.history(self.paths)
        self.assertEqual(history[-1].error_type, "sinal")
        self.assertEqual(attempts.pending(history)["classificar"], [])
        with self.assertRaises(TutorError):
            attempts.classify(self.paths, qid(6), "conta", self.now)

    def test_divergent_question_is_out_of_use(self) -> None:
        bank = read_json(self.paths.questoes)
        bank["questoes"][0]["verificacao"] = "divergente"
        from tutor.core import write_json

        write_json(self.paths.questoes, bank)
        with self.assertRaises(TutorError) as caught:
            attempts.present(self.paths, qid(1), "treino", self.now)
        self.assertEqual(caught.exception.code, "questao_fora_de_uso")


class OpenQuestionTest(TempWorkspaceCase):
    def test_open_question_is_graded_later(self) -> None:
        open_item = {"tipo": "aberta", "enunciado": "Explique o que é um evento.", "conceitos": ["espaco-amostral"],
                     "gabarito": {"rubrica": ["define evento como subconjunto"], "conceito_decisivo": "evento",
                                  "solucao": "subconjunto do espaço amostral"}}
        paths = build_subject(self.subjects, self.now, extra_questions=[open_item])
        attempts.present(paths, qid(9), "treino", self.now)
        result = attempts.check(paths, qid(9), "um subconjunto", 3, 0, None, self.now)
        self.assertIsNone(result["correta"])
        self.assertEqual(result["pendente"], "avaliar")
        self.assertEqual(attempts.pending(attempts.history(paths))["avaliar"], [qid(9)])
        attempts.grade(paths, qid(9), "parcial", "conceito", self.now)
        last = attempts.history(paths)[-1]
        self.assertEqual((last.grade, last.score, last.error_type), ("parcial", 0.5, "conceito"))


class ExamTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.paths = build_subject(self.subjects, self.now)
        self.ids = [qid(1), qid(3), qid(5)]
        attempts.start_exam(self.paths, self.ids, 30, {"mediana": 2, "faixa_80": [1, 3]}, self.now)

    def test_feedback_only_at_the_end(self) -> None:
        with self.assertRaises(TutorError) as caught:
            attempts.check(self.paths, qid(1), "A", 3, 0, None, self.now)
        self.assertEqual(caught.exception.code, "questao_de_simulado")
        shown = attempts.present(self.paths, qid(1), "treino", self.now)
        self.assertEqual(shown["modo"], "simulado")
        status = attempts.answer_exam(self.paths, qid(1), answer_of(1).lower(), 4, 60, self.now + timedelta(minutes=3))
        self.assertNotIn("correta", status)
        self.assertEqual(status["proxima"], qid(3))
        with self.assertRaises(TutorError):
            attempts.answer_exam(self.paths, qid(1), "A", 4, 60, self.now)
        attempts.answer_exam(self.paths, qid(3), wrong_of(3), 5, 60, self.now + timedelta(minutes=6))
        self.assertEqual(attempts.exam_status(self.paths, self.now + timedelta(minutes=40))["tempo_esgotado"], True)
        result = attempts.finish_exam(self.paths, self.now + timedelta(minutes=40))
        self.assertEqual((result["acertos"], result["total"]), (1, 3))
        self.assertEqual(result["erros_com_confianca_alta"], [qid(3)])
        blank = next(r for r in result["questoes"] if r["questao"] == qid(5))
        self.assertTrue(blank["em_branco"])
        self.assertFalse(self.paths.simulado.exists())
        self.assertEqual(read_jsonl(self.paths.simulados)[-1]["previsao"]["mediana"], 2)
        modes = {a.mode for a in attempts.history(self.paths)}
        self.assertEqual(modes, {"simulado"})

    def test_numeric_answer_is_validated_when_given(self) -> None:
        numeric = {"tipo": "numerica", "enunciado": "Quanto vale 1/2 + 1/4?", "conceitos": ["prob-classica"],
                   "gabarito": {"resposta": {"valor": 0.75}, "conceito_decisivo": "soma", "solucao": "3/4"}}
        paths = build_subject(self.subjects, self.now, slug="num", extra_questions=[numeric])
        attempts.start_exam(paths, [qid(9, "num")], 10, None, self.now)
        with self.assertRaises(TutorError):
            attempts.answer_exam(paths, qid(9, "num"), "A", 3, None, self.now)
        attempts.answer_exam(paths, qid(9, "num"), "3/4", 3, None, self.now)
        self.assertEqual(attempts.finish_exam(paths, self.now)["acertos"], 1)

    def test_only_one_exam_at_a_time(self) -> None:
        with self.assertRaises(TutorError):
            attempts.start_exam(self.paths, self.ids, 30, None, self.now)


if __name__ == "__main__":
    unittest.main()
