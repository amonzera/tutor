"""Matérias: listagem, estado, resumo de início de sessão e diagnóstico do ambiente."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from tutor import __version__
from tutor.core import Context, TutorError, is_valid_slug, parse_date, read_json, slugify

SOURCES_DIR = "fontes"
SESSION_START_MAX_CHARS = 1800
SESSION_START_MAX_SUBJECTS = 12


def _count_sources(folder: Path) -> int:
    base = folder / SOURCES_DIR
    if not base.is_dir():
        return 0
    return sum(1 for p in base.rglob("*") if p.is_file() and not p.name.startswith("."))


def _due_reviews(folder: Path, today: date) -> int:
    data = read_json(folder / "estado" / "revisoes.json", {}) or {}
    due = 0
    for item in data.get("itens", []):
        next_date = parse_date(item.get("proxima"))
        if next_date is not None and next_date <= today:
            due += 1
    return due


def subject_summary(folder: Path, today: date) -> dict[str, Any]:
    """Resumo de uma pasta de `subjects/`, sem levantar erro por matéria malformada."""
    info: dict[str, Any] = {"pasta": folder.name}
    if not is_valid_slug(folder.name):
        info.update(estado="nome_invalido", sugestao=slugify(folder.name))
        return info
    info["fontes"] = _count_sources(folder)
    try:
        materia = read_json(folder / "materia.json")
    except TutorError as exc:
        info.update(estado="com_erro", erro=exc.message)
        return info
    if materia is None:
        info["estado"] = "nova"
        return info
    exam = parse_date((materia.get("prova") or {}).get("data"))
    info["nome"] = materia.get("nome") or folder.name
    info["data_prova"] = exam.isoformat() if exam else None
    info["data_confirmada"] = bool((materia.get("prova") or {}).get("data_confirmada")) if exam else False
    info["dias_ate_prova"] = (exam - today).days if exam else None
    pending = [step for step, state in (materia.get("etapas") or {}).items() if state != "ok"]
    if pending:
        info["estado"] = "configurando"
        info["etapas_pendentes"] = pending
    elif exam is not None and exam < today:
        info["estado"] = "prova_passou"
    else:
        info["estado"] = "ativa"
    info["revisoes_vencidas"] = _due_reviews(folder, today)
    info["ultima_sessao"] = materia.get("ultima_sessao")
    return info


def list_subjects(ctx: Context) -> list[dict[str, Any]]:
    base = ctx.workspace.subjects
    if not base.is_dir():
        return []
    today = ctx.clock.today()
    return [
        subject_summary(folder, today)
        for folder in sorted(base.iterdir())
        if folder.is_dir() and not folder.name.startswith(".")
    ]


def last_subject(ctx: Context) -> str | None:
    data = read_json(ctx.workspace.local_state_file, {}) or {}
    slug = data.get("ultima_materia")
    return slug if isinstance(slug, str) and is_valid_slug(slug) else None


# ---------------------------------------------------------------- subcomandos


def cmd_subjects(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    items = list_subjects(ctx)
    if items:
        directive = (
            "Mostre uma tabela curta: matéria, estado, dias até a prova e revisões vencidas. "
            "Estado 'nova': sugira /nova-materia <pasta>. 'configurando': /nova-materia <pasta> retoma "
            "de onde parou. 'nome_invalido': sugira renomear a pasta para o valor de 'sugestao'. "
            "'ativa' ou 'prova_passou': /estudar <pasta>."
        )
    else:
        directive = (
            "Ainda não há matérias. Explique: criar subjects/<nome>/fontes/, colocar o material e rodar "
            "/nova-materia <nome>. Para experimentar antes, sugira `bash bin/tutor.sh exemplo`."
        )
    return {"status": "ok", "materias": items, "ultima_materia": last_subject(ctx), "llm_directive": directive}


def _describe(item: dict[str, Any]) -> str:
    state = item.get("estado")
    name = item["pasta"]
    if state == "nova":
        return f"- {name}: nova, {item.get('fontes', 0)} arquivo(s) em fontes/, ainda não inicializada."
    if state == "nome_invalido":
        return f"- {name}: nome de pasta inválido (sugestão: {item.get('sugestao')})."
    if state == "com_erro":
        return f"- {name}: materia.json com erro."
    if state == "configurando":
        return f"- {name}: configuração incompleta ({', '.join(item.get('etapas_pendentes', []))})."
    days = item.get("dias_ate_prova")
    exam = "sem data de prova" if days is None else (f"prova em {days} dia(s)" if days >= 0 else "prova já passou")
    return f"- {name}: {exam}, {item.get('revisoes_vencidas', 0)} revisão(ões) vencida(s)."


def session_start_texts(ctx: Context) -> tuple[str, str]:
    """Devolve (contexto para o Claude, mensagem curta para o aluno)."""
    items = list_subjects(ctx)
    if not items:
        context = (
            "[Tutor] Nenhuma matéria em subjects/. Se o aluno quiser começar, explique como criar "
            "subjects/<nome>/fontes/ e rodar /nova-materia <nome>, ou sugira `bash bin/tutor.sh exemplo`."
        )
        return context, "Tutor: nenhuma matéria ainda. Veja subjects/README.md ou rode: bash bin/tutor.sh exemplo"
    lines = ["[Tutor] Estado das matérias no início da sessão:"]
    lines += [_describe(item) for item in items[:SESSION_START_MAX_SUBJECTS]]
    if len(items) > SESSION_START_MAX_SUBJECTS:
        lines.append(f"- ... e mais {len(items) - SESSION_START_MAX_SUBJECTS} matéria(s) (veja /materias).")
    last = last_subject(ctx)
    if last:
        lines.append(f"Última matéria usada: {last}.")
    lines.append(
        "Não comece uma sessão de estudo sem o aluno pedir. Se ele quiser estudar, use /estudar "
        "(ou /materias para ver tudo)."
    )
    context = "\n".join(lines)[:SESSION_START_MAX_CHARS]
    due = sum(int(item.get("revisoes_vencidas") or 0) for item in items)
    message = f"Tutor: {len(items)} matéria(s), {due} revisão(ões) vencida(s) hoje. Use /estudar ou /materias."
    return context, message


def cmd_session_start(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    try:
        context, message = session_start_texts(ctx)
    except TutorError as exc:
        context = f"[Tutor] Não consegui ler as matérias: {exc.message}"
        message = "Tutor: erro ao ler as matérias (rode /materias para detalhes)."
    return {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
        "systemMessage": message,
    }


def _tool_version(executable: str) -> str | None:
    try:
        done = subprocess.run([executable, "-v"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stderr or done.stdout or "").strip().splitlines()
    return lines[0] if lines else None


def cmd_environment(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    pdftotext = shutil.which("pdftotext")
    return {
        "status": "ok",
        "tutor": __version__,
        "python": platform.python_version(),
        "sistema": platform.platform(),
        "raiz": str(ctx.workspace.root),
        "pasta_materias": str(ctx.workspace.subjects),
        "pdftotext": {"disponivel": pdftotext is not None, "versao": _tool_version(pdftotext) if pdftotext else None},
        "pdftoppm": shutil.which("pdftoppm") is not None,
        "codificacao_saida": getattr(sys.stdout, "encoding", None),
        "llm_directive": (
            "Diagnóstico do ambiente. Sem pdftotext, PDFs não podem ser lidos: oriente instalar o poppler "
            "(Linux: poppler-utils; macOS: brew install poppler) ou converter o material para .txt/.md."
        ),
    }


def add_commands(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("materias", help="lista as matérias e o estado de cada uma")
    parser.set_defaults(handler=cmd_subjects, always_zero=True)
    parser = sub.add_parser("inicio-sessao", help="resumo para o hook SessionStart (JSON de hook)")
    parser.set_defaults(handler=cmd_session_start, always_zero=True)
    parser = sub.add_parser("ambiente", help="mostra Python, pdftotext e as pastas em uso")
    parser.set_defaults(handler=cmd_environment, always_zero=True)
