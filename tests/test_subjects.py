"""Listagem de matérias e resumo do hook de início de sessão."""

from __future__ import annotations

import json
import unittest

from tests.helpers import ROOT, TempWorkspaceCase
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



class CreateAndConfigureTest(TempWorkspaceCase):
    def test_create_reports_missing_fields(self) -> None:
        code, out = self.run_cli("iniciar", "--materia", "calculo-2")
        self.assertEqual(out["erro"], "materia_inexistente")
        self.make_subject("calculo-2")
        code, out = self.run_cli("iniciar", "--materia", "calculo-2", "--nome", "Cálculo 2")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["criada"])
        self.assertIn("objetivo", out["faltando"]["obrigatorios"])
        self.assertEqual(out["etapas"]["inventario"], "ok")
        self.assertEqual(out["etapas"]["perguntas"], "pendente")
        code, out = self.run_cli(
            "configurar", "--materia", "calculo-2", "--objetivo", "passar", "--nivel", "intermediario",
            "--idioma", "pt-BR", "--tempo-diario", "45", "--formato", "multipla-escolha", "--data-prova", "2026-04-10",
            "--questoes", "10", "--duracao", "120", "--observacao", "Calculadora simples permitida.",
            "--provas-marcam-resposta", "sim",
        )
        self.assertEqual(out["faltando"], {"obrigatorios": [], "recomendados": []})
        self.assertEqual(out["etapas"]["perguntas"], "ok")
        contract = (self.subjects / "calculo-2" / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("# Matéria: Cálculo 2", contract)
        self.assertIn("Calculadora simples permitida.", contract)
        self.assertIn("resposta marcada na página", contract)
        self.assertNotIn("{{", contract)

    def test_rename_invalid_folder(self) -> None:
        (self.subjects / "Álgebra Linear" / "fontes").mkdir(parents=True)
        code, out = self.run_cli("iniciar", "--materia", "algebra-linear", "--renomear-de", "Álgebra Linear")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.subjects / "algebra-linear" / "materia.json").is_file())

    def test_empty_sources_keep_inventory_pending(self) -> None:
        self.make_subject("vazia", sources=0)
        _, out = self.run_cli("iniciar", "--materia", "vazia", "--nome", "Vazia")
        self.assertEqual(out["etapas"]["inventario"], "pendente")


class SessionFlowTest(TempWorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        from tests.fixtures import build_subject

        self.paths = build_subject(self.subjects, self.now)

    def test_validate_marks_steps(self) -> None:
        code, out = self.run_cli("plano", "--materia", "prob", "--escrever")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("validar", "--materia", "prob")
        self.assertEqual(code, 0, out)
        materia = json.loads(self.paths.materia.read_text(encoding="utf-8"))
        self.assertTrue(all(v == "ok" for v in materia["etapas"].values()))

    def test_validate_reports_problems(self) -> None:
        write_json(self.paths.mapa, {"schema_version": 1, "conceitos": []})
        code, out = self.run_cli("validar", "--materia", "prob", "--etapa", "mapa")
        self.assertEqual(code, 1)
        self.assertEqual(out["erro"], "validacao_falhou")
        self.assertIn("mapa", out["problemas"])

    def test_first_session_context(self) -> None:
        code, out = self.run_cli("contexto")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["primeira_sessao"])
        self.assertIn("diagnóstico", out["llm_directive"])
        self.assertIn("# Matéria", out["contrato"] or "# Matéria")
        self.assertEqual(json.loads((self.subjects / ".local.json").read_text(encoding="utf-8"))["ultima_materia"], "prob")

    def test_checkpoint_and_resume(self) -> None:
        from tests.fixtures import qid, wrong_of
        from tutor import attempts

        attempts.present(self.paths, qid(3), "treino", self.now)
        attempts.check(self.paths, qid(3), wrong_of(3), 4, 0, 50, self.now)
        code, out = self.run_cli("checkpoint", "--materia", "prob")
        self.assertEqual(code, 0, out)
        self.assertIn("proximo-passo.md", out["aviso"])
        self.paths.proximo.write_text("- Revisar probabilidade clássica.\n", encoding="utf-8")
        code, out = self.run_cli("checkpoint", "--materia", "prob")
        self.assertNotIn("aviso", out)
        self.assertIn("Questões: 1 (0 certas)", out["registro"])
        self.assertIn("classificar ['pro-003']", out["registro"])
        diary = self.paths.diario.read_text(encoding="utf-8")
        self.assertEqual(diary.count("## 2026-03-02"), 2)
        self.assertTrue(self.paths.plano.is_file() and self.paths.dominio.is_file())
        code, out = self.run_cli("contexto", "--materia", "prob", when=self.now.replace(day=3))
        self.assertFalse(out["primeira_sessao"])
        self.assertEqual(out["pendencias"]["classificar"], [qid(3)])
        self.assertIn("Revisar probabilidade clássica", out["proximo_passo"])
        self.assertEqual(len(out["diario_recente"]), 2)


class ExampleInstallTest(TempWorkspaceCase):
    def test_install_example(self) -> None:
        if not (ROOT / "examples" / "probabilidade-basica" / "materia.json").is_file():
            self.skipTest("exemplo ausente")
        code, out = self.run_cli("exemplo")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["prova"], "2026-03-23", "prova fictícia 21 dias depois de hoje")
        folder = self.subjects / "probabilidade-basica"
        materia = json.loads((folder / "materia.json").read_text(encoding="utf-8"))
        self.assertTrue(all(v == "ok" for v in materia["etapas"].values()))
        self.assertTrue(materia["prova"]["data_confirmada"])
        self.assertTrue((folder / "plano.md").is_file())
        self.assertFalse((folder / "estado" / "sessao.json").exists(), "estado começa vazio")
        questions = json.loads((folder / "banco" / "questoes.json").read_text(encoding="utf-8"))["questoes"]
        self.assertGreaterEqual(len(questions), 20)
        self.assertTrue(all(q["verificacao"] == "verificada" for q in questions))
        code, out = self.run_cli("exemplo")
        self.assertEqual(out["erro"], "exemplo_ja_instalado")
        code, out = self.run_cli("contexto")
        self.assertTrue(out["primeira_sessao"])


if __name__ == "__main__":
    unittest.main()
