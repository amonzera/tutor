"""Contrato da linha de comando: JSON sempre, erros em português, códigos de saída."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import unittest
from unittest import mock

from tests.helpers import TempWorkspaceCase, run_module
from tutor import cli
from tutor.cli import build_parser


class CliContractTest(unittest.TestCase):
    def test_unknown_subcommand_is_json_usage_error(self) -> None:
        done = run_module("nao-existe")
        self.assertEqual(done.returncode, 2)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["status"], "erro")
        self.assertEqual(payload["erro"], "uso_invalido")
        self.assertIn("llm_directive", payload)

    def test_output_is_utf8_json(self) -> None:
        done = run_module("materias", env={"TUTOR_MATERIAS_DIR": "/caminho/que/nao/existe"})
        self.assertEqual(done.returncode, 0)
        payload = json.loads(done.stdout)
        self.assertIn("matérias", payload["llm_directive"])

    def test_invalid_frozen_clock_is_reported(self) -> None:
        done = run_module("materias", env={"TUTOR_HOJE": "09/10/2026"})
        payload = json.loads(done.stdout)
        self.assertEqual(payload["erro"], "data_invalida")
        self.assertEqual(done.returncode, 0, "materias é subcomando de contexto: sai sempre com 0")



class EverySubcommandTest(TempWorkspaceCase):
    """Nenhum subcomando deixa escapar exceção: sempre JSON, com status ou no formato de hook."""

    def commands(self) -> list[list[str]]:
        parser = build_parser()
        top = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        found = []
        for name, subparser in top.choices.items():
            nested = [a for a in subparser._actions if isinstance(a, argparse._SubParsersAction)]
            found += [[name, child] for child in nested[0].choices] if nested else [[name]]
        return found

    def test_all_subcommands_answer_json(self) -> None:
        commands = self.commands()
        self.assertGreaterEqual(len(commands), 30)
        for command in commands:
            with self.subTest(command=" ".join(command)), mock.patch("sys.stdin", io.StringIO("")):
                env = {"TUTOR_MATERIAS_DIR": str(self.subjects), "TUTOR_AGORA": self.now.isoformat()}
                out = io.StringIO()
                with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                    code = cli.main(command)
                self.assertIn(code, (0, 1, 2))
                text = out.getvalue()
                if command == ["guarda"]:
                    self.assertEqual(text, "")
                    continue
                payload = json.loads(text)
                self.assertTrue("status" in payload or "hookSpecificOutput" in payload, payload)
                if payload.get("status") == "erro":
                    self.assertIn("mensagem", payload)


if __name__ == "__main__":
    unittest.main()
