"""Núcleo: JSONL resistente a quedas, caminhos seguros, slugs, codificação em repouso e versões."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tutor.core import (
    TutorError, append_jsonl, check_schema, decode_protected, encode_protected, ensure_inside, read_jsonl,
    read_protected, slugify, validate_slug, write_protected,
)


class JsonlTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "estado" / "registro.jsonl"

    def test_truncated_line_does_not_break_future_writes(self) -> None:
        append_jsonl(self.path, {"n": 1})
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write('{"n": 2, "corta')  # queda no meio da escrita
        append_jsonl(self.path, {"n": 3})
        append_jsonl(self.path, {"n": 4})
        self.assertEqual([r["n"] for r in read_jsonl(self.path)], [1, 3, 4])

    def test_missing_file_is_empty(self) -> None:
        self.assertEqual(read_jsonl(self.path), [])


class PathsTest(unittest.TestCase):
    def test_ensure_inside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "materia"
            (base / "banco").mkdir(parents=True)
            self.assertEqual(ensure_inside(base, base / "banco"), (base / "banco").resolve())
            for bad in (base / ".." / "fora", Path("/etc/passwd")):
                with self.subTest(bad=str(bad)), self.assertRaises(TutorError):
                    ensure_inside(base, bad)

    def test_slugs(self) -> None:
        self.assertEqual(slugify("Cálculo 2 (turma B)"), "calculo-2-turma-b")
        self.assertEqual(slugify("!!!"), "materia")
        self.assertEqual(validate_slug("calculo-2"), "calculo-2")
        for bad in ("Cálculo", "calculo 2", "../x", "-x", "a" * 41, ""):
            with self.subTest(bad=bad), self.assertRaises(TutorError):
                validate_slug(bad)


class ProtectedTest(unittest.TestCase):
    def test_roundtrip_and_not_readable(self) -> None:
        payload = {"respostas": {"q1": {"resposta": "C", "solucao": "condicionar ao evento"}}}
        blob = encode_protected(payload)
        self.assertEqual(decode_protected(blob), payload)
        self.assertNotIn("condicionar", blob)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gabarito.json"
            write_protected(path, "x", payload)
            self.assertNotIn("condicionar", path.read_text(encoding="utf-8"))
            self.assertEqual(read_protected(path), payload)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["conteudo"] = "isto não é base64!"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(TutorError):
                read_protected(path)

    def test_newer_schema_is_refused(self) -> None:
        with self.assertRaises(TutorError) as caught:
            check_schema({"schema_version": 99}, Path("materia.json"))
        self.assertEqual(caught.exception.code, "versao_mais_nova")
        with self.assertRaises(TutorError):
            check_schema({"sem": "versao"}, Path("materia.json"))


if __name__ == "__main__":
    unittest.main()
