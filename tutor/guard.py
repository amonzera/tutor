"""Guarda do tutor: política do hook PreToolUse (chamada por bin/guarda.sh).

Lê o evento do hook (JSON na entrada padrão) e, quando a chamada viola uma regra,
responde com `permissionDecision: "deny"` e o motivo. Sem violação, não imprime
nada e a permissão segue o fluxo normal do Claude Code.

Regras:
1. O agente `verificador` resolve às cegas: só roda, literalmente,
   `bash bin/tutor.sh apresentar ... --modo verificacao`, `bash bin/tutor.sh calc ...` e
   `bash bin/tutor.sh banco registrar-verificacao ...`, sem operadores, variáveis,
   comentários nem quebras de linha (lista fechada sobre o comando inteiro).
2. Texto da área protegida (`texto --protegido`), páginas renderizadas (`renderizar`) e
   recortes de figura (`recortar`) só para o agente `ingestor-de-fontes`.
3. `banco exportar` é para o aluno rodar no próprio terminal, nunca para um agente.
4. `banco registrar-verificacao` só para o verificador.
5. Chamadas ao motor com variáveis de ambiente na frente são negadas (exceto o relógio
   de testes, TUTOR_HOJE e TUTOR_AGORA): `BASH_ENV=...` ou `PYTHONPATH=...` executariam código.
6. Fora do motor, nenhum comando toca arquivos protegidos (gabarito, respostas do
   verificador, tentativas, área protegida, provas, rascunhos, figuras). Rascunhos e
   figuras ficam abertos aos agentes que escrevem o banco, também para leitura.
7. Nenhuma busca recursiva (grep -r, rg, git grep, find -exec, ferramenta Grep...)
   alcança subjects/ ou examples/: use `bash bin/tutor.sh buscar`.

É uma camada a mais, não um cofre: variações de comando podem escapar. A proteção
principal é estrutural (arquivos codificados, correção que exige a resposta).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from tutor.core import Context, repo_root

VERIFIER = "verificador"
INGESTOR = "ingestor-de-fontes"
WRITERS = {INGESTOR, "escritor-de-questoes"}
VERIFIER_COMMAND = re.compile(
    r"bash (?:\./)?bin/tutor\.sh "
    r"(?:apresentar(?= [^\n]*--modo verificacao(?: |$))|calc|banco registrar-verificacao)"
    r"(?: [^\n\r#;&|<>$`\\]*)?"
)
PROTECTED_MARKERS = (
    "gabarito.json", "verificacao.json", "tentativas.jsonl", "ingestao/protegido", "fontes/provas",
    "banco/rascunhos", "figuras-temp", "banco/figuras",
)
WRITER_MARKERS = ("banco/rascunhos", "figuras-temp", "banco/figuras")
OPERATOR_CHARS = set("();<>|&")
SHELL_PREFIXES = {"do", "then", "else", "elif", "if", "while", "until", "!", "time", "command", "exec", "env", "{"}
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=.*")
SAFE_VARIABLES = {"TUTOR_HOJE", "TUTOR_AGORA", "TUTOR_MATERIAS_DIR"}
DANGEROUS_VARIABLES = {
    "BASH_ENV", "ENV", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTHONINSPECT", "PYTHONUSERBASE",
    "TUTOR_PYTHON", "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH",
    "PATH", "SHELLOPTS", "BASHOPTS", "PS4", "PROMPT_COMMAND",
}
EXPORTERS = {"export", "declare", "typeset", "readonly", "local"}
FILE_READERS = {"cat", "head", "tail", "less", "more", "grep", "egrep", "rg", "awk", "sed", "strings", "xxd", "od", "base64"}
ENGINE_SCRIPT_NAMES = {"bin/tutor.sh", "./bin/tutor.sh"}
WSL_UNC = re.compile(r"//(?:wsl\.localhost|wsl\$)/[^/]+(/.*)?", re.IGNORECASE)

REASON_VERIFIER = (
    "O verificador resolve às cegas: só pode rodar `bash bin/tutor.sh apresentar ... --modo verificacao`, "
    "`bash bin/tutor.sh calc ...` e `bash bin/tutor.sh banco registrar-verificacao ...`, sem operadores de shell, "
    "variáveis, comentários ou quebras de linha."
)
REASON_INGESTOR = "Texto protegido, páginas renderizadas e recortes de figura são só para o agente ingestor-de-fontes."
REASON_EXPORT = "`banco exportar` é para o aluno rodar no próprio terminal, não para o tutor."
REASON_REGISTER = "Só o agente verificador registra respostas às cegas (`banco registrar-verificacao`)."
REASON_ENV = (
    "Chamadas ao motor não podem levar variáveis de ambiente na frente (exceto TUTOR_HOJE, TUTOR_AGORA e "
    "TUTOR_MATERIAS_DIR), e variáveis que executam código (BASH_ENV, PYTHONPATH, PATH...) não podem ser definidas."
)
REASON_PROTECTED = (
    "Este comando toca um arquivo protegido (gabarito, respostas do verificador, tentativas, provas, rascunhos ou "
    "figuras de prova). "
    "Use os subcomandos do motor (`apresentar`, `corrigir`, `painel`...)."
)
REASON_SEARCH = (
    "Busca recursiva em subjects/ ou examples/ pode expor arquivos protegidos. Use `bash bin/tutor.sh buscar "
    "--materia <slug> --termo <termo>` ou restrinja a busca a pastas como tutor/ e docs/."
)


def _tokens(command: str) -> list[str] | None:
    """Tokeniza como o shell: quebra de linha separa comandos e `#` no meio da palavra não é comentário."""
    text = command.replace("\r", "\n").replace("\n", " ; ")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _is_operator(token: str) -> bool:
    return bool(token) and set(token) <= OPERATOR_CHARS


def _segments(tokens: list[str]) -> list[list[str]]:
    segments, current = [], []
    for token in tokens:
        if _is_operator(token):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _prefixes(segment: list[str]) -> tuple[list[str], list[str]]:
    """Separa (variáveis atribuídas no início, resto do segmento), pulando palavras-chave do shell."""
    index, assigned = 0, []
    while index < len(segment):
        token = segment[index]
        match = ASSIGNMENT.fullmatch(token)
        if match:
            assigned.append(match.group(1))
        elif token not in SHELL_PREFIXES:
            break
        index += 1
    return assigned, segment[index:]


def _is_engine_script(token: str) -> bool:
    normalized = token.replace("\\", "/")
    if normalized in ENGINE_SCRIPT_NAMES:
        return True
    if not normalized.endswith("bin/tutor.sh"):
        return False
    try:
        return Path(token).resolve() == (repo_root() / "bin" / "tutor.sh").resolve()
    except OSError:
        return False


def _engine_args(segment: list[str]) -> list[str] | None:
    """Argumentos depois de `bash bin/tutor.sh` (o script real do repositório), ou None."""
    if len(segment) >= 2 and segment[0] in ("bash", "sh") and _is_engine_script(segment[1]):
        return segment[2:]
    if segment and _is_engine_script(segment[0]):
        return segment[1:]
    return None


def _is_recursive_search(segment: list[str]) -> bool:
    program = segment[0].rsplit("/", 1)[-1]
    if program in ("rg", "ag", "ack", "ack-grep"):
        return True
    if program in ("grep", "egrep", "fgrep", "zgrep"):
        for index, token in enumerate(segment[1:], start=1):
            if token in ("-r", "-R", "--recursive", "--dereference-recursive") or token.startswith("--directories=rec"):
                return True
            if token in ("-d", "--directories") and index + 1 < len(segment) and segment[index + 1].startswith("rec"):
                return True
            if token.startswith("-") and not token.startswith("--") and any(ch in "rR" for ch in token[1:]):
                return True
        return False
    if program == "git" and len(segment) > 1 and segment[1] == "grep":
        return True
    if program == "find" and any(t in ("-exec", "-execdir", "-ok", "-okdir") for t in segment):
        return True
    if program == "xargs" and any(t.rsplit("/", 1)[-1] in FILE_READERS for t in segment[1:]):
        return True
    return False


def _native(text: str) -> str:
    """Troca barras invertidas e o prefixo UNC do WSL, que o aplicativo do Windows usa, pelo caminho local."""
    text = text.replace("\\", "/")
    match = WSL_UNC.fullmatch(text)
    if match and os.name != "nt":
        text = match.group(1) or "/"
    return os.path.expanduser(text)


def _local_path(token: str, cwd: str) -> Path | None:
    """Caminho absoluto do token no sistema onde o motor roda, ou None quando não dá para saber."""
    path = Path(_native(token))
    if not path.is_absolute():
        base = Path(_native(cwd)) if cwd else None
        if base is None or not base.is_absolute():
            return None
        path = base / path
    return path


def _covers_data(token: str, cwd: str) -> bool:
    """O caminho é a raiz do repositório ou uma pasta acima dela (logo, inclui subjects/ e examples/)."""
    path = _local_path(token, cwd)
    if path is None:
        return False
    try:
        root, target = repo_root().resolve(), path.resolve()
    except (OSError, RuntimeError):
        return False
    return target == root or target in root.parents


def _reaches_data(scope: list[str], cwd: str) -> bool:
    lowered_cwd = cwd.replace("\\", "/").lower()
    inside = "/subjects" in lowered_cwd or "/examples" in lowered_cwd
    if not scope:
        return True  # sem caminho: diretório atual (raiz ou dentro de subjects/)
    for token in scope:
        path = token.replace("\\", "/").lower()
        if path in (".", "./", "*", "..", "../") or path.startswith(("subjects", "./subjects", "examples", "./examples")):
            return True
        if "/subjects" in path or "/examples" in path:
            return True
        if inside and not path.startswith("/"):
            return True
        if _covers_data(token, cwd):
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


def _decide_verifier(tool: str, data: dict[str, Any]) -> str | None:
    if tool != "Bash":
        return REASON_VERIFIER
    command = str(data.get("command") or "").strip()
    return None if VERIFIER_COMMAND.fullmatch(command) else REASON_VERIFIER


def _decide_engine(args: list[str], assigned: list[str], agent: str) -> str | None:
    if any(name not in SAFE_VARIABLES for name in assigned):
        return REASON_ENV
    if args[:1] in (["renderizar"], ["recortar"]) or (args[:1] == ["texto"] and "--protegido" in args):
        if agent != INGESTOR:
            return REASON_INGESTOR
    if args[:2] == ["banco", "exportar"]:
        return REASON_EXPORT
    if args[:2] == ["banco", "registrar-verificacao"] and agent != VERIFIER:
        return REASON_REGISTER
    return None


def _decide_bash(command: str, agent: str, cwd: str) -> str | None:
    tokens = _tokens(command)
    lowered = command.replace("\\", "/").lower()
    if tokens is None:
        return REASON_PROTECTED if any(m in lowered for m in PROTECTED_MARKERS) else None
    for raw in _segments(tokens):
        assigned, segment = _prefixes(raw)
        if any(name in DANGEROUS_VARIABLES for name in assigned):
            return REASON_ENV
        if segment and segment[0] in EXPORTERS and any(
            (match := ASSIGNMENT.fullmatch(token)) and match.group(1) in DANGEROUS_VARIABLES for token in segment[1:]
        ):
            return REASON_ENV
        if not segment:
            continue
        args = _engine_args(segment)
        if args is not None:
            reason = _decide_engine(args, assigned, agent)
            if reason:
                return reason
            continue
        text = " ".join(segment).replace("\\", "/").lower()
        program = segment[0].rsplit("/", 1)[-1]
        for marker in PROTECTED_MARKERS:
            if marker not in text:
                continue
            if marker in WRITER_MARKERS and agent in WRITERS:
                continue
            if program in ("ls", "mkdir"):
                continue
            target = segment[-1].replace("\\", "/").lower()
            sources = " ".join(segment[1:-1]).replace("\\", "/").lower()
            if program == "mv" and len(segment) >= 3 and "fontes/provas" in target and not any(m in sources for m in PROTECTED_MARKERS):
                continue  # mover material PARA a área protegida é permitido
            return REASON_PROTECTED
        if _is_recursive_search(segment) and _reaches_data(_search_scope(segment), cwd):
            return REASON_SEARCH
    return None


def decide(event: dict[str, Any]) -> str | None:
    """Motivo da negação, ou None quando a chamada pode seguir o fluxo normal."""
    tool = event.get("tool_name") or ""
    agent = event.get("agent_type") or ""
    data = event.get("tool_input") or {}
    cwd = str(event.get("cwd") or "")
    if agent == VERIFIER:
        return _decide_verifier(tool, data)
    if tool == "Read":
        path = str(data.get("file_path") or "").replace("\\", "/").lower()
        if any(m in path for m in WRITER_MARKERS) and agent not in WRITERS:
            return REASON_PROTECTED
        return None
    if tool == "Grep":
        path = str(data.get("path") or "")
        return REASON_SEARCH if _reaches_data([path] if path else [], cwd) else None
    if tool == "Bash":
        return _decide_bash(str(data.get("command") or ""), agent, cwd)
    return None


def cmd_guard(args: argparse.Namespace, ctx: Context | None) -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
        reason = decide(event if isinstance(event, dict) else {})
    except Exception:  # noqa: BLE001 - a guarda falha aberta e em silêncio
        return None
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
    p.set_defaults(handler=cmd_guard, always_zero=True, needs_context=False)
