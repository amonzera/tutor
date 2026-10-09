"""Matérias: criação, configuração, estado, retomada de sessão, checkpoint e validação.

É o módulo que orquestra os outros: os subcomandos daqui são os primeiros que as
skills chamam (`materias`, `contexto`) e os últimos (`checkpoint`).
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tutor import __version__
from tutor import attempts as attempt_store
from tutor.bank import load_bank, validate_bank
from tutor.core import (
    SCHEMA_VERSION,
    Context,
    SubjectPaths,
    TutorError,
    is_valid_slug,
    SETUP_STEPS as STEPS,
    load_materia,
    mark_step,
    parse_date,
    read_json,
    read_local_state,
    remember_subject,
    resolve_subject,
    slugify,
    validate_slug,
    write_json,
    write_text,
)
from tutor.knowledge_map import load_map, validate_map_data

SOURCES_DIR = "fontes"
SESSION_START_MAX_CHARS = 1800
SESSION_START_MAX_SUBJECTS = 12
REQUIRED_FIELDS = ("nome", "objetivo", "nivel", "idioma", "tempo_diario_min", "prova.formato")
RECOMMENDED_FIELDS = ("prova.data", "prova.duracao_min", "prova.n_questoes")
LEVELS = ("iniciante", "intermediario", "avancado")
FORMATS = ("multipla-escolha", "discursiva", "mista", "numerica")
MIN_VERIFIED_FOR_BANK_STEP = 3
EXAMPLE_SLUG = "probabilidade-basica"
EXAMPLE_EXAM_IN_DAYS = 21


# ---------------------------------------------------------------- listagem


def _count_sources(folder: Path) -> int:
    base = folder / SOURCES_DIR
    if not base.is_dir():
        return 0
    return sum(1 for p in base.rglob("*") if p.is_file() and not p.name.startswith("."))


def _due_reviews(folder: Path, today: date, exam: date | None) -> int:
    from tutor.srs import is_due  # noqa: PLC0415 - evita importar o agendador na listagem rápida

    data = read_json(folder / "estado" / "revisoes.json", {}) or {}
    return sum(1 for item in data.get("itens", []) if is_due(item, today, exam))


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
    info["revisoes_vencidas"] = _due_reviews(folder, today, exam)
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
    slug = read_local_state(ctx).get("ultima_materia")
    return slug if isinstance(slug, str) and is_valid_slug(slug) else None


# ---------------------------------------------------------------- criação e configuração


def _get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def missing_fields(materia: dict[str, Any]) -> dict[str, list[str]]:
    empty = lambda v: v is None or v == "" or v == []  # noqa: E731
    return {
        "obrigatorios": [f for f in REQUIRED_FIELDS if empty(_get(materia, f))],
        "recomendados": [f for f in RECOMMENDED_FIELDS if empty(_get(materia, f))],
    }


def _yes(value: str | None) -> bool | None:
    return None if value is None else value == "sim"


def apply_config(materia: dict[str, Any], args: argparse.Namespace) -> None:
    prova = materia.setdefault("prova", {})
    simple = {"nome": args.nome, "objetivo": args.objetivo, "nivel": args.nivel, "idioma": args.idioma,
              "tempo_diario_min": args.tempo_diario, "dias_por_semana": args.dias_semana}
    for key, value in simple.items():
        if value is not None:
            materia[key] = value
    if args.data_prova is not None:
        if args.data_prova in ("", "nenhuma", "sem-data"):
            prova["data"] = None
            prova["data_confirmada"] = False
        else:
            prova["data"] = parse_date(args.data_prova).isoformat()
            prova.setdefault("data_confirmada", True)
    if args.data_confirmada is not None:
        prova["data_confirmada"] = args.data_confirmada == "sim"
    for key, value in {"formato": args.formato, "duracao_min": args.duracao, "n_questoes": args.questoes,
                       "n_alternativas": args.alternativas}.items():
        if value is not None:
            prova[key] = value
    if args.observacao:
        prova["observacoes"] = list(dict.fromkeys((prova.get("observacoes") or []) + args.observacao))
    if args.preferencia:
        materia["preferencias"] = list(dict.fromkeys((materia.get("preferencias") or []) + args.preferencia))
    if args.tipo_erro_extra:
        materia["tipos_erro_extra"] = list(dict.fromkeys((materia.get("tipos_erro_extra") or []) + args.tipo_erro_extra))
    if args.provas_marcam_resposta is not None:
        materia["provas_marcam_resposta"] = _yes(args.provas_marcam_resposta)
    if args.max_revisoes_dia is not None:
        materia.setdefault("revisao", {})["max_por_dia"] = args.max_revisoes_dia


def render_contract(root: Path, materia: dict[str, Any]) -> str:
    template = (root / "templates" / "materia" / "CLAUDE.md").read_text(encoding="utf-8")
    prova = materia.get("prova") or {}
    parts = [str(prova.get("formato") or "formato não informado")]
    if prova.get("n_questoes"):
        parts.append(f"{prova['n_questoes']} questões")
    if prova.get("n_alternativas"):
        parts.append(f"{prova['n_alternativas']} alternativas")
    if prova.get("duracao_min"):
        parts.append(f"{prova['duracao_min']} minutos")
    date_text = prova.get("data") or "data ainda não informada"
    if prova.get("data") and not prova.get("data_confirmada"):
        date_text += " (provisória)"
    parts.append(date_text)
    rules = [
        "- Tenta primeiro: resposta e confiança (1 a 5) antes de qualquer ajuda; questões só por `apresentar`.",
        "- Erros classificados como conceito, metodo, sinal, conta ou chute"
        + (f", ou: {', '.join(materia['tipos_erro_extra'])}." if materia.get("tipos_erro_extra") else "."),
    ]
    if materia.get("provas_marcam_resposta"):
        rules.append("- As provas antigas desta matéria trazem a resposta marcada na página (por exemplo, em vermelho). "
                     "Nunca abra nem mostre imagens dessas páginas; use só o texto de `apresentar`.")
    for note in prova.get("observacoes") or []:
        rules.append(f"- Na prova: {note}")
    for pref in materia.get("preferencias") or []:
        rules.append(f"- Preferência do aluno: {pref}")
    values = {
        "nome": materia.get("nome") or materia.get("slug", ""),
        "objetivo": materia.get("objetivo") or "não informado",
        "prova": ", ".join(parts),
        "nivel": materia.get("nivel") or "não informado",
        "tempo_diario": f"{materia['tempo_diario_min']} min por dia" if materia.get("tempo_diario_min") else "não informado",
        "idioma": materia.get("idioma") or "pt-BR",
        "regras": "\n".join(rules),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def configure(ctx: Context, args: argparse.Namespace, create: bool) -> dict[str, Any]:
    from tutor.ingest import inventory  # noqa: PLC0415

    slug = args.materia
    if create and args.renomear_de:
        source = ctx.workspace.subjects / args.renomear_de
        if not source.is_dir():
            raise TutorError("pasta_inexistente", f"Pasta {args.renomear_de!r} não existe em subjects/.")
        target = ctx.workspace.subject_dir(validate_slug(slug))
        if target.exists():
            raise TutorError("destino_existe", f"Já existe uma pasta {slug!r}.")
        source.rename(target)
    if create:
        folder = ctx.workspace.subject_dir(slug)
        if not folder.is_dir():
            raise TutorError(
                "materia_inexistente", f"Crie primeiro subjects/{slug}/fontes/ com o material.",
                "Explique ao aluno como criar a pasta e colocar o material em fontes/.",
            )
        paths = SubjectPaths(folder)
    else:
        paths = resolve_subject(ctx, slug)
    now = ctx.clock.now()
    materia = read_json(paths.materia)
    created = materia is None
    if materia is None:
        if not create:
            raise TutorError("materia_nao_inicializada", "A matéria ainda não foi criada.", f"Use /nova-materia {paths.slug}.")
        materia = {
            "schema_version": SCHEMA_VERSION, "slug": paths.slug, "idioma": "pt-BR", "dias_por_semana": 6,
            "prova": {"data": None, "data_confirmada": False, "n_alternativas": 5},
            "revisao": {"algoritmo": "sm2-prova", "max_por_dia": 15, "fracao_max_intervalo": 0.5},
            "etapas": {s: "pendente" for s in STEPS}, "criado_em": now.isoformat(), "ultima_sessao": None,
        }
    apply_config(materia, args)
    for folder in (paths.estado, paths.banco, paths.rascunhos, paths.notas):
        folder.mkdir(parents=True, exist_ok=True)
    found = inventory(paths)
    steps = materia.setdefault("etapas", {s: "pendente" for s in STEPS})
    steps["inventario"] = "ok" if not found["vazio"] and not found["problemas"] else "pendente"
    missing = missing_fields(materia)
    steps["perguntas"] = "ok" if not missing["obrigatorios"] else "pendente"
    write_json(paths.materia, materia)
    write_text(paths.contrato, render_contract(ctx.workspace.root, materia))
    mark_step(paths, "contrato", True)
    remember_subject(ctx, paths.slug)
    directive = (
        "Pergunte ao aluno SÓ os campos de 'faltando' (use AskUserQuestion; no modo não interativo, peça em texto) "
        "e grave com `configurar`. Depois siga para a próxima etapa pendente."
        if missing["obrigatorios"] else "Configuração completa. Siga para a próxima etapa pendente."
    )
    return {
        "status": "ok", "materia": paths.slug, "criada": created, "faltando": missing,
        "etapas": read_json(paths.materia)["etapas"], "llm_directive": directive,
    }


# ---------------------------------------------------------------- validação


def validate(paths: SubjectPaths, step: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if step in ("mapa", "tudo"):
        data = read_json(paths.mapa)
        problems = ["falta mapa-conhecimento.json"] if data is None else validate_map_data(data, paths)
        results["mapa"] = problems
        mark_step(paths, "mapa", not problems)
    if step in ("banco", "tudo"):
        try:
            kmap = load_map(paths, required=False)
            problems = validate_bank(paths, kmap)
            questions = load_bank(paths)
        except TutorError as exc:
            problems, questions = [exc.message] + list(exc.extra.get("problemas", [])), {}
        verified = sum(1 for q in questions.values() if q.get("verificacao") == "verificada")
        pending = sorted(qid for qid, q in questions.items() if q.get("verificacao") == "pendente")
        if not problems and verified < MIN_VERIFIED_FOR_BANK_STEP:
            problems.append(f"o banco precisa de ao menos {MIN_VERIFIED_FOR_BANK_STEP} questões verificadas (tem {verified})")
        if not problems and pending:
            problems.append(f"questões ainda sem verificação: {', '.join(pending)}")
        results["banco"] = problems
        mark_step(paths, "banco", not problems)
    if step in ("plano", "tudo"):
        results["plano"] = [] if paths.plano.is_file() else ["falta plano.md (rode `plano --escrever`)"]
        mark_step(paths, "plano", not results["plano"])
    if any(results.values()):
        raise TutorError(
            "validacao_falhou", "A validação encontrou problemas.",
            "Corrija os problemas listados e valide de novo; não avance de etapa antes.",
            problemas={k: v for k, v in results.items() if v},
        )
    return {"status": "ok", "validado": sorted(results), "llm_directive": "Etapa validada. Siga para a próxima."}


# ---------------------------------------------------------------- sessão


def _diary_entries(paths: SubjectPaths, count: int) -> list[str]:
    if not paths.diario.is_file():
        return []
    text = paths.diario.read_text(encoding="utf-8")
    entries = ["## " + chunk.strip() for chunk in text.split("\n## ")[1:]]
    return entries[-count:]


def session_context(ctx: Context, slug: str | None) -> dict[str, Any]:
    from tutor import planner, report  # noqa: PLC0415
    from tutor.srs import due_today  # noqa: PLC0415

    paths = resolve_subject(ctx, slug)
    remember_subject(ctx, paths.slug)
    today = ctx.clock.today()
    summary = subject_summary(paths.root, today)
    if summary["estado"] == "nova":
        return {"status": "ok", "materia": paths.slug, "estado": "nova",
                "llm_directive": f"Matéria ainda não preparada. Sugira /nova-materia {paths.slug}."}
    out: dict[str, Any] = {"status": "ok", "materia": summary}
    out["contrato"] = paths.contrato.read_text(encoding="utf-8") if paths.contrato.is_file() else None
    out["proximo_passo"] = paths.proximo.read_text(encoding="utf-8").strip() if paths.proximo.is_file() else None
    out["diario_recente"] = _diary_entries(paths, 2)
    gaps = []
    try:
        out["revisoes"] = due_today(paths, today)
    except TutorError as exc:
        gaps.append(exc.message)
    history = attempt_store.history(paths)
    out["pendencias"] = attempt_store.pending(history)
    if paths.simulado.is_file():
        out["simulado_em_andamento"] = attempt_store.exam_status(paths, ctx.clock.now())
    try:
        dashboard = report.build_dashboard(paths, ctx.clock.now())
        weak = [c for c in dashboard["conceitos"] if c["estado"] in ("fraco", "em_progresso")]
        weak.sort(key=lambda c: -c["peso"] * (1 - c["p_acerto"]))
        out["painel"] = {
            "conceitos_fracos": [{"nome": c["nome"], "p_acerto": c["p_acerto"], "faixa_80": c["faixa_80"]} for c in weak[:3]],
            "calibracao": dashboard["calibracao"].get("leitura"),
            "preparo": dashboard["preparo"],
        }
        plan, _ = planner.compute(paths, today)
        out["plano_hoje"] = planner.today_entry(plan, today)
    except TutorError as exc:
        gaps.append(exc.message)
    out["primeira_sessao"] = not history
    if gaps:
        out["faltando"] = gaps
    steps = summary.get("etapas_pendentes") or []
    if steps:
        directive = f"A preparação da matéria não terminou (etapas: {', '.join(steps)}). Sugira /nova-materia {paths.slug}."
    elif out.get("simulado_em_andamento"):
        directive = "Há um simulado em andamento: ofereça retomar (sem feedback) ou encerrar com `simulado encerrar`."
    elif not history:
        directive = (
            "Primeira sessão: explique em 3 linhas como o tutor funciona (tenta primeiro, confiança, dicas em escada) "
            "e comece pelo diagnóstico (`proximas --modo diagnostico`)."
        )
    else:
        directive = (
            "Retome pelo proximo_passo e pelo diário. Ordem: pendências de classificação, revisões vencidas, foco do "
            "dia no plano (ou conceito mais fraco), questões no modo tenta-primeiro, ensinar de volta e checkpoint."
        )
    out["llm_directive"] = directive
    return out


def checkpoint(ctx: Context, slug: str | None) -> dict[str, Any]:
    from tutor import planner, report  # noqa: PLC0415
    from tutor.srs import load_items  # noqa: PLC0415

    paths = resolve_subject(ctx, slug)
    materia = load_materia(paths)
    today = ctx.clock.today()
    questions = load_bank(paths, required=False)
    kmap = load_map(paths, required=False)
    todays = [a for a in attempt_store.history(paths) if a.at.date() == today]
    correct = sum(1 for a in todays if a.correct)
    awaiting = sum(1 for a in todays if a.correct is None)
    concepts = sorted({c for a in todays for c in (questions.get(a.id) or {}).get("conceitos", [])})
    names = [kmap.concepts[c].name if kmap and c in kmap.concepts else c for c in concepts]
    errors: dict[str, int] = {}
    for a in todays:
        if a.correct is False and a.error_type:
            errors[a.error_type] = errors.get(a.error_type, 0) + 1
    reviews = [h for item in load_items(paths) for h in item.get("historico", []) if h.get("em") == today.isoformat()]
    forgotten = sum(1 for h in reviews if h.get("nota") == "esqueci")
    pend = attempt_store.pending(attempt_store.history(paths))
    next_text = paths.proximo.read_text(encoding="utf-8").strip() if paths.proximo.is_file() else ""
    digest = hashlib.sha256(next_text.encode("utf-8")).hexdigest()
    session = read_json(paths.sessao, {}) or {}
    stale = not next_text or session.get("proximo_passo_sha") == digest
    first_line = next(
        (line.strip("-# ").strip() for line in next_text.splitlines() if line.strip("-# ").strip()), "não registrado"
    )
    lines = [
        f"## {today.isoformat()}",
        "",
        f"- Questões: {len(todays)} ({correct} certas"
        + (f", {awaiting} aguardando avaliação" if awaiting else "") + ")"
        + (f"; conceitos: {', '.join(names)}" if names else ""),
    ]
    if errors:
        lines.append("- Erros: " + ", ".join(f"{k} ({v})" for k, v in sorted(errors.items())))
    lines.append(f"- Revisões: {len(reviews)}" + (f" ({forgotten} esquecida(s))" if forgotten else ""))
    if pend["classificar"] or pend["avaliar"]:
        lines.append(f"- Pendências: classificar {pend['classificar'] or '-'}; avaliar {pend['avaliar'] or '-'}")
    lines.append(f"- Próximo passo: {first_line}")
    previous = paths.diario.read_text(encoding="utf-8") if paths.diario.is_file() else "# Diário de estudo\n"
    write_text(paths.diario, previous.rstrip("\n") + "\n\n" + "\n".join(lines))
    session["proximo_passo_sha"] = digest
    write_json(paths.sessao, {**session, "schema_version": SCHEMA_VERSION})
    materia["ultima_sessao"] = today.isoformat()
    write_json(paths.materia, materia)
    try:
        _, plan_text = planner.compute(paths, today)
        write_text(paths.plano, plan_text)
        write_text(paths.dominio, report.render_dashboard(report.build_dashboard(paths, ctx.clock.now()), ctx.clock.now()))
    except TutorError:
        pass
    out = {"status": "ok", "registro": "\n".join(lines), "pendencias": pend}
    if stale:
        out["aviso"] = "proximo-passo.md não foi atualizado nesta sessão."
        out["llm_directive"] = (
            "Escreva estado/proximo-passo.md (o que fazer na próxima sessão, dúvidas em aberto, 3 a 6 linhas) e rode "
            "`checkpoint` de novo."
        )
    else:
        out["llm_directive"] = "Checkpoint feito. Diga ao aluno o foco da próxima sessão e quando ela deveria acontecer."
    return out


# ---------------------------------------------------------------- hook de início


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


# ---------------------------------------------------------------- exemplo


def install_example(ctx: Context, force: bool) -> dict[str, Any]:
    from tutor import planner  # noqa: PLC0415
    from tutor.ingest import ingest  # noqa: PLC0415

    source = ctx.workspace.root / "examples" / EXAMPLE_SLUG
    if not (source / "materia.json").is_file():
        raise TutorError("exemplo_ausente", "A matéria de exemplo não está em examples/.")
    target = ctx.workspace.subjects / EXAMPLE_SLUG
    if target.exists():
        if not force:
            raise TutorError(
                "exemplo_ja_instalado", f"subjects/{EXAMPLE_SLUG} já existe.",
                "Para reinstalar do zero (apaga o histórico de estudo do exemplo), rode `exemplo --forcar`.",
            )
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns("estado", "ingestao", "__pycache__", ".*")
    shutil.copytree(source, target, ignore=ignore)
    paths = SubjectPaths(target)
    paths.estado.mkdir(exist_ok=True)
    today = ctx.clock.today()
    materia = read_json(paths.materia)
    materia["prova"]["data"] = (today + timedelta(days=EXAMPLE_EXAM_IN_DAYS)).isoformat()
    materia["prova"]["data_confirmada"] = True
    materia["criado_em"] = ctx.clock.now().isoformat()
    materia["ultima_sessao"] = None
    materia["etapas"] = {step: "ok" for step in STEPS}
    write_json(paths.materia, materia)
    write_text(paths.contrato, render_contract(ctx.workspace.root, materia))
    warnings = []
    try:
        result = ingest(paths, ctx.clock.now())
        warnings += [f"{f['arquivo']}: {f['erro']}" for f in result["falhas"]]
    except TutorError as exc:
        warnings.append(exc.message)
    _, text = planner.compute(paths, today)
    write_text(paths.plano, text)
    remember_subject(ctx, EXAMPLE_SLUG)
    return {
        "status": "ok",
        "materia": EXAMPLE_SLUG,
        "prova": materia["prova"]["data"],
        "avisos": warnings,
        "llm_directive": f"Matéria de exemplo instalada (prova fictícia em {EXAMPLE_EXAM_IN_DAYS} dias). Sugira /estudar {EXAMPLE_SLUG}.",
    }


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


def cmd_create(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return configure(ctx, args, create=True)


def cmd_configure(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return configure(ctx, args, create=False)


def cmd_context(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return session_context(ctx, args.materia)


def cmd_checkpoint(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return checkpoint(ctx, args.materia)


def cmd_validate(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return validate(resolve_subject(ctx, args.materia), args.etapa)


def cmd_example(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return install_example(ctx, args.forcar)


def _config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--nome", help="nome da matéria (com acentos)")
    parser.add_argument("--objetivo")
    parser.add_argument("--nivel", choices=LEVELS)
    parser.add_argument("--idioma", help="ex.: pt-BR, en, es")
    parser.add_argument("--data-prova", help="AAAA-MM-DD (ou 'sem-data')")
    parser.add_argument("--data-confirmada", choices=("sim", "nao"))
    parser.add_argument("--formato", choices=FORMATS)
    parser.add_argument("--duracao", type=int, help="duração da prova em minutos")
    parser.add_argument("--questoes", type=int, help="número de questões da prova")
    parser.add_argument("--alternativas", type=int, help="alternativas por questão (múltipla escolha)")
    parser.add_argument("--tempo-diario", type=int, help="minutos de estudo por dia")
    parser.add_argument("--dias-semana", type=int, help="dias de estudo por semana (1 a 7)")
    parser.add_argument("--observacao", action="append", help="regra da prova (pode repetir)")
    parser.add_argument("--preferencia", action="append", help="preferência do aluno (pode repetir)")
    parser.add_argument("--tipo-erro-extra", action="append", help="tipo de erro próprio da matéria (pode repetir)")
    parser.add_argument("--provas-marcam-resposta", choices=("sim", "nao"), help="as provas antigas vêm com a resposta marcada?")
    parser.add_argument("--max-revisoes-dia", type=int)


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("materias", help="lista as matérias e o estado de cada uma")
    p.set_defaults(handler=cmd_subjects, always_zero=True)
    p = sub.add_parser("inicio-sessao", help="resumo para o hook SessionStart (JSON de hook)")
    p.set_defaults(handler=cmd_session_start, always_zero=True)
    p = sub.add_parser("ambiente", help="mostra Python, pdftotext e as pastas em uso")
    p.set_defaults(handler=cmd_environment, always_zero=True)

    p = sub.add_parser("iniciar", help="cria materia.json numa pasta de subjects/ (diz o que falta perguntar)")
    p.add_argument("--materia", required=True)
    p.add_argument("--renomear-de", help="pasta atual com nome inválido, a renomear para --materia")
    _config_args(p)
    p.set_defaults(handler=cmd_create)
    p = sub.add_parser("configurar", help="altera a configuração da matéria (data da prova, tempo diário...)")
    p.add_argument("--materia")
    _config_args(p)
    p.set_defaults(handler=cmd_configure)

    p = sub.add_parser("contexto", help="tudo para retomar a sessão: contrato, checkpoint, revisões, pendências")
    p.add_argument("--materia")
    p.set_defaults(handler=cmd_context, always_zero=True)
    p = sub.add_parser("checkpoint", help="fecha a sessão: diário com os números do dia, plano e painel atualizados")
    p.add_argument("--materia")
    p.set_defaults(handler=cmd_checkpoint)
    p = sub.add_parser("validar", help="valida mapa, banco ou plano e marca a etapa como concluída")
    p.add_argument("--materia")
    p.add_argument("--etapa", choices=("mapa", "banco", "plano", "tudo"), default="tudo")
    p.set_defaults(handler=cmd_validate)
    p = sub.add_parser("exemplo", help=f"instala a matéria de exemplo ({EXAMPLE_SLUG}) em subjects/")
    p.add_argument("--forcar", action="store_true", help="reinstala do zero (apaga o histórico do exemplo)")
    p.set_defaults(handler=cmd_example)
