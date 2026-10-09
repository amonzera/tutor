"""Linha de comando do motor: `python -m tutor <subcomando>` (via `bash bin/tutor.sh`).

Toda saída é um objeto JSON. Erros esperados viram `{"status": "erro", ...}`.
Subcomandos de contexto (usados por hooks e skills) sempre saem com código 0,
porque uma injeção `!` que falha aborta a skill inteira.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from tutor import __version__, subjects
from tutor.core import Context, TutorError, Workspace, clock_from_env

Handler = Callable[[argparse.Namespace, Context], "dict[str, Any] | None"]

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 70


class _Parser(argparse.ArgumentParser):
    """Erros de uso também saem como JSON, em português."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise TutorError(
            "uso_invalido",
            f"Uso inválido: {message}",
            "Confira os argumentos com `bash bin/tutor.sh <subcomando> --help` e tente de novo.",
        )


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="tutor",
        description="Motor do tutor de estudo guiado. Saída sempre em JSON.",
    )
    parser.add_argument("--versao", action="version", version=f"tutor {__version__}")
    sub = parser.add_subparsers(dest="subcomando", metavar="<subcomando>", parser_class=_Parser)
    subjects.add_commands(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except TutorError as exc:
        emit(exc.payload())
        return EXIT_USAGE
    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_USAGE
    always_zero = bool(getattr(args, "always_zero", False))
    try:
        ctx = Context(workspace=Workspace.from_env(), clock=clock_from_env())
        payload = handler(args, ctx)
    except TutorError as exc:
        emit(exc.payload())
        return EXIT_OK if always_zero else EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - até o erro inesperado sai em JSON
        emit(
            {
                "status": "erro",
                "erro": "erro_interno",
                "mensagem": f"{type(exc).__name__}: {exc}",
                "llm_directive": "Erro inesperado no motor. Mostre a mensagem ao aluno e não tente contornar.",
            }
        )
        return EXIT_OK if always_zero else EXIT_INTERNAL
    if payload is not None:
        emit(payload)
    return EXIT_OK
