"""Listagem de matérias e resumo do hook de início de sessão."""

from __future__ import annotations

import json
import unittest

from tests.helpers import TempWorkspaceCase
from tutor.core import write_json


class SubjectsListTest(TempWorkspaceCase):
    def test_empty_folder(self) -> None:
        code, out = self.run_cli("materias")
        self.assertEqual(code, 0)
        self.assertEqual(out["materias"], [])
        self.assertIn("/nova-materia", out["llm_directive"])

    def test_states(self) -> None:
        self.make_subject("calculo-2", sources=2)
        self.make_subject(
            "fisica-3",
            {"nome": "Física 3", "prova": {"data": "2026-03-12", "data_confirmada": True}, "etapas": {"mapa": "ok"}},
        )
        self.make_subject("quimica", {"nome": "Química", "etapas": {"mapa": "ok", "banco": "pendente"}})
        self.make_subject("historia", {"nome": "História", "prova": {"data": "2026-02-01"}})
        (self.subjects / "Álgebra Linear").mkdir()
        (self.subjects / ".oculta").mkdir()

        code, out = self.run_cli("materias")
        self.assertEqual(code, 0)
        by_name = {item["pasta"]: item for item in out["materias"]}
        self.assertNotIn(".oculta", by_name)
        self.assertEqual(by_name["calculo-2"]["estado"], "nova")
        self.assertEqual(by_name["calculo-2"]["fontes"], 2)
        self.assertEqual(by_name["fisica-3"]["estado"], "ativa")
        self.assertEqual(by_name["fisica-3"]["dias_ate_prova"], 10)
        self.assertEqual(by_name["quimica"]["estado"], "configurando")
        self.assertEqual(by_name["quimica"]["etapas_pendentes"], ["banco"])
        self.assertEqual(by_name["historia"]["estado"], "prova_passou")
        self.assertEqual(by_name["Álgebra Linear"]["estado"], "nome_invalido")
        self.assertEqual(by_name["Álgebra Linear"]["sugestao"], "algebra-linear")

    def test_corrupted_materia_does_not_break_listing(self) -> None:
        folder = self.make_subject("calculo-2")
        (folder / "materia.json").write_text("{ isto não é json", encoding="utf-8")
        code, out = self.run_cli("materias")
        self.assertEqual(code, 0)
        self.assertEqual(out["materias"][0]["estado"], "com_erro")

    def test_due_reviews_count(self) -> None:
        folder = self.make_subject("calculo-2", {"nome": "Cálculo 2"})
        write_json(
            folder / "estado" / "revisoes.json",
            {"schema_version": 1, "itens": [{"proxima": "2026-03-01"}, {"proxima": "2026-03-02"}, {"proxima": "2026-03-09"}]},
        )
        _, out = self.run_cli("materias")
        self.assertEqual(out["materias"][0]["revisoes_vencidas"], 2)


class SessionStartTest(TempWorkspaceCase):
    def test_hook_payload_shape(self) -> None:
        self.make_subject("calculo-2", {"nome": "Cálculo 2", "prova": {"data": "2026-03-20"}})
        write_json(self.subjects / ".local.json", {"ultima_materia": "calculo-2"})
        code, out = self.run_cli("inicio-sessao")
        self.assertEqual(code, 0)
        self.assertEqual(set(out), {"hookSpecificOutput", "systemMessage"})
        hook = out["hookSpecificOutput"]
        self.assertEqual(hook["hookEventName"], "SessionStart")
        self.assertIn("calculo-2: prova em 18 dia(s)", hook["additionalContext"])
        self.assertIn("Última matéria usada: calculo-2", hook["additionalContext"])
        self.assertLessEqual(len(hook["additionalContext"]), 1800)

    def test_hook_with_many_subjects_stays_short(self) -> None:
        for i in range(40):
            self.make_subject(f"materia-{i:02d}", {"nome": f"Matéria {i}"})
        _, out = self.run_cli("inicio-sessao")
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(context), 1800)
        self.assertIn("e mais 28", context)

    def test_hook_never_fails_on_broken_local_state(self) -> None:
        (self.subjects / ".local.json").write_text("{quebrado", encoding="utf-8")
        code, out = self.run_cli("inicio-sessao")
        self.assertEqual(code, 0)
        self.assertIn("hookSpecificOutput", out)
        json.dumps(out)


if __name__ == "__main__":
    unittest.main()
