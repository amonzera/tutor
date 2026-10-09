"""Contrato da linha de comando: JSON sempre, erros em português, códigos de saída."""

from __future__ import annotations

import json
import unittest

from tests.helpers import run_module


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


if __name__ == "__main__":
    unittest.main()
