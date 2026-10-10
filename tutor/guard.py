"""Guarda do tutor: política do hook PreToolUse (chamada por bin/guarda.sh).

Lê o evento do hook (JSON na entrada padrão) e, quando a chamada viola uma regra,
responde com `permissionDecision: "deny"` e o motivo. Sem violação, não imprime
nada e a permissão segue o fluxo normal do Claude Code.

Regras:
1. O agente `verificador` resolve às cegas: só usa o motor para `apresentar`, `calc`
   e `banco registrar-verificacao`, sem operadores de shell.
2. Texto da área protegida (`texto --protegido`) e páginas renderizadas (`renderizar`)
   só para o agente `ingestor-de-fontes`.
3. `banco exportar` é para o aluno rodar no próprio terminal, nunca para um agente.
4. Fora do motor, nenhum comando toca arquivos protegidos (gabarito, respostas do
   verificador, tentativas, área protegida, provas, rascunhos).
5. Nenhuma busca recursiva (grep -r, rg, git grep, find -exec...) alcança subjects/
   ou examples/: use `bash bin/tutor.sh buscar`, que pula a área protegida.

É uma camada a mais, não um cofre: variações de comando podem escapar. A proteção
principal é estrutural (arquivos codificados, correção que exige a resposta).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from typing import Any

from tutor.core import Context

VERIFIER = "verificador"
INGESTOR = "ingestor-de-fontes"
WRITERS = {INGESTOR, "escritor-de-questoes"}
VERIFIER_SUBCOMMANDS = (("apresentar",), ("calc",), ("banco", "registrar-verificacao"))
PROTECTED_MARKERS = (
    "gabarito.json", "verificacao.json", "tentativas.jsonl", "ingestao/protegido", "fontes/provas",
    "banco/rascunhos", "figuras-temp",
)
WRITER_MARKERS = ("banco/rascunhos", "figuras-temp")
OPERATORS = {";", "&", "&&", "|", "||", "|&", ";;", "(", ")", "<", ">", ">>", "<<", "&>"}
SHELL_PREFIXES = {"do", "then", "else", "elif", "if", "while", "until", "!", "time", "command", "exec", "env", "{"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
FILE_READERS = {"cat", "head", "tail", "less", "more", "grep", "egrep", "rg", "awk", "sed", "strings", "xxd", "od", "base64"}

REASON_VERIFIER = (
    "O verificador resolve às cegas: só pode rodar `bash bin/tutor.sh apresentar`, `calc` e "
    "`banco registrar-verificacao`, sem operadores de shell."
)
REASON_INGESTOR = "Texto protegido e páginas renderizadas são só para o agente ingestor-de-fontes."
REASON_EXPORT = "`banco exportar` é para o aluno rodar no próprio terminal, não para o tutor."
REASON_PROTECTED = (
    "Este comando toca um arquivo protegido (gabarito, respostas do verificador, tentativas, provas ou rascunhos). "
    "Use os subcomandos do motor (`apresentar`, `corrigir`, `painel`...)."
)
REASON_SEARCH = (
    "Busca recursiva em subjects/ ou examples/ pode expor arquivos protegidos. Use `bash bin/tutor.sh buscar "
    "--materia <slug> --termo <termo>` ou restrinja a busca a pastas como tutor/ e docs/."
)


def _tokens(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list[str]) -> list[list[str]]:
    segments, current = [], []
    for token in tokens:
        if token in OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _strip_prefixes(segment: list[str]) -> list[str]:
    """Remove palavras-chave do shell e atribuições de variável do início do segmento."""
    index = 0
    while index < len(segment) and (segment[index] in SHELL_PREFIXES or ASSIGNMENT.fullmatch(segment[index])):
        index += 1
    return segment[index:]


def _engine_args(segment: list[str]) -> list[str] | None:
    """Argumentos depois de `bash bin/tutor.sh` (ou de `./bin/tutor.sh` chamado direto)."""
    segment = _strip_prefixes(segment)
    if len(segment) >= 2 and segment[0] in ("bash", "sh") and segment[1].replace("\\", "/").endswith("bin/tutor.sh"):
        return segment[2:]
    if segment and segment[0].replace("\\", "/").endswith("bin/tutor.sh"):
        return segment[1:]
    return None


def _is_recursive_search(segment: list[str]) -> bool:
    program = segment[0].rsplit("/", 1)[-1]
    if program in ("rg", "ag", "ack", "ack-grep"):
        return True
    if program in ("grep", "egrep", "fgrep", "zgrep"):
        for token in segment[1:]:
            if token in ("-r", "-R", "--recursive", "--dereference-recursive") or token.startswith("--directories=rec"):
                return True
            if token.startswith("-") and not token.startswith("--") and any(ch in "rR" for ch in token[1:]):
                return True
        return False
    if program == "git" and len(segment) > 1 and segment[1] == "grep":
        return True
    if program == "find" and any(t in ("-exec", "-execdir", "-ok") for t in segment):
        return True
    if program == "xargs" and any(t.rsplit("/", 1)[-1] in FILE_READERS for t in segment[1:]):
        return True
    return False


def _reaches_data(scope: list[str], cwd: str) -> bool:
    cwd = cwd.replace("\\", "/")
    inside = "/subjects" in cwd or "/examples" in cwd
    if not scope:
        return True  # sem caminho: diretório atual (raiz ou dentro de subjects/)
    for token in scope:
        path = token.replace("\\", "/")
        if path in (".", "./", "*", "..", "../") or path.startswith(("subjects", "./subjects", "examples", "./examples")):
            return True
        if "/subjects" in path or "/examples" in path:
            return True
        if inside and not path.startswith("/"):
            return True
    return False


def _search_scope(segment: list[str]) -> list[str]:
    program = segment[0].rsplit("/", 1)[-1]
    args = segment[2:] if program == "git" else segment[1:]
    if program == "find":
        return [t for t in args if not t.startswith("-")][:1]
    positional = [t for t in args if not t.startswith("-")]
    uses_e = any(t in ("-e", "--regexp", "-f", "--file") for t in args)
    return positional if uses_e else positional[1:]


def decide(event: dict[str, Any]) -> str | None:
    """Motivo da negação, ou None quando a chamada pode seguir o fluxo normal."""
    tool = event.get("tool_name") or ""
    agent = event.get("agent_type") or ""
    data = event.get("tool_input") or {}
    if agent == VERIFIER:
        if tool != "Bash":
            return REASON_VERIFIER
        command = str(data.get("command") or "")
        tokens = _tokens(command)
        if tokens is None or "`" in command or "$(" in command or "${" in command:
            return REASON_VERIFIER
        segments = _segments(tokens)
        if len(segments) != 1 or any(t in OPERATORS for t in tokens):
            return REASON_VERIFIER
        args = _engine_args(segments[0])
        if args is None or not any(tuple(args[: len(s)]) == s for s in VERIFIER_SUBCOMMANDS):
            return REASON_VERIFIER
        return None
    if tool == "Read":
        path = str(data.get("file_path") or "").replace("\\", "/")
        if any(m in path for m in WRITER_MARKERS) and agent not in WRITERS:
            return REASON_PROTECTED
        return None
    if tool != "Bash":
        return None
    command = str(data.get("command") or "")
    tokens = _tokens(command)
    normalized = command.replace("\\", "/")
    if tokens is None:
        return REASON_PROTECTED if any(m in normalized for m in PROTECTED_MARKERS) else None
    for segment in _segments(tokens):
        args = _engine_args(segment)
        if args is not None:
            if args[:1] == ["renderizar"] or (args[:1] == ["texto"] and "--protegido" in args):
                if agent != INGESTOR:
                    return REASON_INGESTOR
            if args[:2] == ["banco", "exportar"]:
                return REASON_EXPORT
            continue
        segment = _strip_prefixes(segment)
        if not segment:
            continue
        text = " ".join(segment).replace("\\", "/")
        program = segment[0].rsplit("/", 1)[-1]
        for marker in PROTECTED_MARKERS:
            if marker not in text:
                continue
            if marker in WRITER_MARKERS and agent in WRITERS:
                continue
            if program in ("ls", "mkdir"):
                continue
            if program == "mv" and len(segment) >= 3 and "fontes/provas" in segment[-1].replace("\\", "/") and not any(
                m in " ".join(segment[1:-1]).replace("\\", "/") for m in PROTECTED_MARKERS
            ):
                continue  # mover material PARA a área protegida é permitido
            return REASON_PROTECTED
        if _is_recursive_search(segment) and _reaches_data(_search_scope(segment), str(event.get("cwd") or "")):
            return REASON_SEARCH
    return None


def cmd_guard(args: argparse.Namespace, ctx: Context) -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return None
    reason = decide(event if isinstance(event, dict) else {})
    if reason:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False) + "\n")
    return None


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("guarda", help="política do hook PreToolUse (lê o evento JSON na entrada padrão)")
    p.set_defaults(handler=cmd_guard, always_zero=True)
