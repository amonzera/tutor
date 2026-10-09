"""Wrapper bin/tutor.sh: dedução do alvo no WSL, escolha do Python e erro sem Python."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest

from tests.helpers import ROOT, available_shells

WRAPPER = "bin/tutor.sh"


def run_shell(shell: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shell, WRAPPER, *args], cwd=ROOT, env=env if env is not None else os.environ.copy(),
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


class WslTargetTest(unittest.TestCase):
    cases = {
        "//wsl.localhost/Ubuntu/home/aluno/tutor": "Ubuntu\t/home/aluno/tutor",
        "//wsl$/Debian/home/aluno/meu repo": "Debian\t/home/aluno/meu repo",
        "//wsl.localhost/Ubuntu-24.04": "Ubuntu-24.04\t/",
    }
    rejected = ["/home/aluno/tutor", "//servidor/compartilhado/tutor", "C:/Users/aluno/tutor", ""]

    def setUp(self) -> None:
        self.shells = available_shells()
        if not self.shells:
            self.skipTest("nenhum shell POSIX disponível")

    def test_parses_wsl_paths_in_every_shell(self) -> None:
        for shell in self.shells:
            for path, expected in self.cases.items():
                with self.subTest(shell=shell, path=path):
                    done = run_shell(shell, "--alvo-wsl", path)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertEqual(done.stdout.rstrip("\n"), expected)

    def test_rejects_other_paths(self) -> None:
        for shell in self.shells:
            for path in self.rejected:
                with self.subTest(shell=shell, path=path):
                    self.assertEqual(run_shell(shell, "--alvo-wsl", path).returncode, 1)


class PythonSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.shells = available_shells()
        if not self.shells:
            self.skipTest("nenhum shell POSIX disponível")

    def test_runs_engine_and_returns_json(self) -> None:
        for shell in self.shells:
            with self.subTest(shell=shell):
                env = {**os.environ, "TUTOR_PYTHON": sys.executable}
                done = run_shell(shell, "ambiente", env=env)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(json.loads(done.stdout)["status"], "ok")

    def test_invalid_tutor_python_falls_back(self) -> None:
        for shell in self.shells:
            with self.subTest(shell=shell):
                env = {**os.environ, "TUTOR_PYTHON": "/caminho/que/nao/existe/python"}
                done = run_shell(shell, "ambiente", env=env)
                self.assertEqual(done.returncode, 0, done.stderr)

    @unittest.skipIf(sys.platform == "win32", "PATH vazio não é reproduzível no Git Bash")
    def test_without_python_prints_json_error(self) -> None:
        shell = shutil.which("dash") or shutil.which("sh")
        if shell is None:
            self.skipTest("sem sh")
        env = {"PATH": "/caminho/inexistente"}
        done = run_shell(shell, "ambiente", env=env)
        self.assertEqual(done.returncode, 127)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["erro"], "python_nao_encontrado")
        self.assertIn("llm_directive", payload)

    @unittest.skipIf(sys.platform == "win32", "PATH vazio não é reproduzível no Git Bash")
    def test_hook_errors_go_to_stderr(self) -> None:
        shell = shutil.which("dash") or shutil.which("sh")
        if shell is None:
            self.skipTest("sem sh")
        done = run_shell(shell, "inicio-sessao", env={"PATH": "/caminho/inexistente"})
        self.assertEqual(done.stdout, "")
        self.assertIn("Python", done.stderr)


if __name__ == "__main__":
    unittest.main()
