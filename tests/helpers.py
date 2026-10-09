"""Utilidades dos testes: pasta de matérias temporária, relógio fixo e execução da CLI."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

from tutor import cli
from tutor.core import Clock, Context, Workspace, write_json

ROOT = Path(__file__).resolve().parent.parent
FIXED_NOW = datetime(2026, 3, 2, 10, 0, 0)


class TempWorkspaceCase(unittest.TestCase):
    """Cada teste ganha uma pasta `subjects/` própria e um relógio fixo."""

    now = FIXED_NOW

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.subjects = Path(self._tmp.name) / "subjects"
        self.subjects.mkdir()
        self.ctx = Context(Workspace(root=ROOT, subjects=self.subjects), Clock(self.now))

    def at(self, when: datetime) -> Context:
        return Context(self.ctx.workspace, Clock(when))

    def make_subject(self, slug: str, materia: dict[str, Any] | None = None, sources: int = 1) -> Path:
        folder = self.subjects / slug
        (folder / "fontes").mkdir(parents=True)
        for i in range(sources):
            (folder / "fontes" / f"nota-{i}.md").write_text(f"# Nota {i}\n", encoding="utf-8")
        if materia is not None:
            write_json(folder / "materia.json", {"schema_version": 1, "slug": slug, **materia})
        return folder

    def run_cli(self, *args: str, when: datetime | None = None) -> tuple[int, dict[str, Any]]:
        """Roda a CLI no próprio processo, com a pasta e o relógio do teste."""
        env = {
            "TUTOR_MATERIAS_DIR": str(self.subjects),
            "TUTOR_AGORA": (when or self.now).isoformat(),
        }
        out = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
            code = cli.main(list(args))
        return code, json.loads(out.getvalue())


def run_module(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Roda `python -m tutor` num processo separado (testa o contrato de saída real)."""
    full_env = {**os.environ, "PYTHONUTF8": "1", **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "tutor", *args],
        cwd=ROOT, env=full_env, capture_output=True, text=True, encoding="utf-8", check=False,
    )


def available_shells() -> list[str]:
    """Shells POSIX disponíveis para testar o wrapper (dash é o mais estrito)."""
    return [name for name in ("dash", "bash", "sh") if shutil.which(name)]
