"""Plano de estudo: trilha completa em ordem de prioridade e calendário reverso até a prova.

Regras (heurísticas, ajustáveis pelo replanejamento):
- a trilha tem todos os conceitos do mapa: pré-requisitos antes; entre os prontos, o que mais cai na
  prova (peso) primeiro e, entre empatados, o mais difícil; nada sai da trilha;
- um conceito está concluído quando foi estudado (`trilha estudado`, depois da explicação) e
  praticado com pelo menos `respostas_para_concluir` respostas; a trilha só termina com todos;
- 1º dia de estudo: diagnóstico, se ainda não houver tentativas e o aluno não for iniciante;
- com 7 ou mais dias: simulado completo em D-3, reforço pelos erros em D-2 e
  simulado leve + revisão geral em D-1; com 3 a 6 dias: simulado em D-2 e revisão em D-1;
- os conceitos pendentes são distribuídos por contagem pelos dias livres (sem dias livres, por
  todos os dias); o ritmo necessário é comparado com o recomendado para o tempo e o nível;
- folga diária para as revisões vencidas, que vêm sempre antes do conteúdo novo.
`plano.md` é gerado a partir dos dados; o estado não mora no arquivo.
"""

from __future__ import annotations

import argparse
import math
from datetime import date, datetime, timedelta
from typing import Any

from tutor import attempts as attempt_store
from tutor.attempts import Attempt
from tutor.bank import load_bank
from tutor.core import (
    SCHEMA_VERSION,
    Context,
    SubjectPaths,
    TutorError,
    load_materia,
    mark_step,
    parse_date,
    read_json,
    resolve_subject,
    write_json,
    write_text,
)
from tutor.knowledge_map import KnowledgeMap, load_map
from tutor.learner import ConceptEstimate, estimate_concepts, params_from, practice_counts

WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
NO_EXAM_HORIZON = 14
REST_ORDER = (6, 5, 4, 3, 2, 1, 0)  # domingo primeiro, depois sábado...
MINUTES_PER_NEW_CONCEPT = {"iniciante": 30, "intermediario": 20, "avancado": 15}
DEFAULT_PACE = 3


def study_days(start: date, end: date, days_per_week: int) -> list[date]:
    rest = set(REST_ORDER[: max(0, 7 - max(1, min(7, days_per_week)))])
    days, current = [], start
    while current <= end:
        if current.weekday() not in rest:
            days.append(current)
        current += timedelta(days=1)
    return days


# ---------------------------------------------------------------- trilha


def _usable(question: dict[str, Any]) -> bool:
    return question.get("verificacao", "pendente") != "divergente"


def concept_difficulty(kmap: KnowledgeMap, questions: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Média da `dificuldade` (1 a 3) das questões utilizáveis de cada conceito; 2 sem questões."""
    sums: dict[str, float] = {cid: 0.0 for cid in kmap.concepts}
    counts: dict[str, int] = {cid: 0 for cid in kmap.concepts}
    for question in questions.values():
        if not _usable(question):
            continue
        for cid in question.get("conceitos", []):
            if cid in sums:
                sums[cid] += float(question.get("dificuldade", 2))
                counts[cid] += 1
    return {cid: sums[cid] / counts[cid] if counts[cid] else 2.0 for cid in kmap.concepts}


def usable_counts(kmap: KnowledgeMap, questions: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {cid: 0 for cid in kmap.concepts}
    for question in questions.values():
        if _usable(question):
            for cid in question.get("conceitos", []):
                if cid in counts:
                    counts[cid] += 1
    return counts


def load_studied(paths: SubjectPaths) -> dict[str, str]:
    """Conceitos já explicados ao aluno (`trilha estudado`), com a data."""
    data = read_json(paths.trilha, {}) or {}
    studied = data.get("estudados") if isinstance(data, dict) else None
    return dict(studied) if isinstance(studied, dict) else {}


def trail_status(
    kmap: KnowledgeMap, questions: dict[str, dict[str, Any]], history: list[Attempt],
    studied: dict[str, str] | set[str], params: dict[str, float],
) -> dict[str, Any]:
    needed = max(1, int(params.get("respostas_para_concluir", 2)))
    usable = usable_counts(kmap, questions)
    practicable = {cid for cid, n in usable.items() if n >= needed}
    order = kmap.trail_order(concept_difficulty(kmap, questions), practicable)
    practice = practice_counts(questions, history)
    done = [c for c in order if c in studied and practice.get(c, 0) >= needed]
    finished = set(done)
    pending = [c for c in order if c not in finished]
    return {
        "ordem": order,
        "concluidos": done,
        "pendentes": pending,
        "proximos": pending[:3],
        "sem_questoes": [c for c in pending if usable[c] < needed],
        "total": len(order),
        "concluida": not pending,
        "respostas_para_concluir": needed,
        "progresso": {
            c: {"estudado": c in studied, "respostas": practice.get(c, 0), "questoes": usable[c]} for c in order
        },
    }


def _unknown_trail(kmap: KnowledgeMap) -> dict[str, Any]:
    """Trilha sem dados de banco nem de tentativas: tudo pendente, sem acusar falta de questões."""
    order = kmap.trail_order()
    return {"ordem": order, "concluidos": [], "pendentes": order, "proximos": order[:3], "sem_questoes": [],
            "total": len(order), "concluida": not order, "respostas_para_concluir": 2,
            "progresso": {c: {"estudado": False, "respostas": 0, "questoes": None} for c in order}}


def pace_capacity(materia: dict[str, Any]) -> int:
    """Conceitos novos por dia recomendados para o tempo diário e o nível (heurística)."""
    minutes = materia.get("tempo_diario_min")
    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes <= 0:
        return DEFAULT_PACE
    level = materia.get("nivel") if materia.get("nivel") in MINUTES_PER_NEW_CONCEPT else "intermediario"
    return max(1, int(minutes // MINUTES_PER_NEW_CONCEPT[level]))


# ---------------------------------------------------------------- calendário


def build_plan(
    materia: dict[str, Any], kmap: KnowledgeMap, estimates: dict[str, ConceptEstimate],
    has_attempts: bool, today: date, *, trail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trail = trail or _unknown_trail(kmap)
    capacity = pace_capacity(materia)
    exam = parse_date((materia.get("prova") or {}).get("data"))
    if exam is not None and exam <= today:
        return {"modo": "pos_prova", "prova": exam.isoformat(), "dias_de_estudo": 0, "dias": [], "trilha": trail,
                "ritmo_recomendado": capacity, "ritmo_necessario": 0, "apertado": False}
    end = exam - timedelta(days=1) if exam else today + timedelta(days=NO_EXAM_HORIZON - 1)
    days = study_days(today, end, int(materia.get("dias_por_semana") or 6)) or [today]
    plan_days: list[dict[str, Any]] = [
        {"data": d.isoformat(), "dia_semana": WEEKDAYS[d.weekday()],
         "rotulo": f"D-{(exam - d).days}" if exam else f"dia {i + 1}", "conceitos": []}
        for i, d in enumerate(days)
    ]
    reserved: dict[int, tuple[str, str]] = {}
    if exam and len(plan_days) >= 7:
        reserved[len(plan_days) - 3] = ("simulado", "Simulado completo em tempo de prova (/simulado)")
        reserved[len(plan_days) - 2] = ("reforco", "Reforço pelos erros do simulado e pelos erros com confiança alta")
        reserved[len(plan_days) - 1] = ("revisao-final", "Simulado leve + revisão geral; dormir bem")
    elif exam and len(plan_days) >= 3:
        reserved[len(plan_days) - 2] = ("simulado", "Simulado (pode ser reduzido) em tempo de prova")
        reserved[len(plan_days) - 1] = ("revisao-final", "Revisão geral e pontos fracos")
    elif exam:
        reserved[len(plan_days) - 1] = ("revisao-final", "Revisão geral e pontos fracos")
    if not has_attempts and 0 not in reserved and materia.get("nivel") != "iniciante":
        plan_days[0]["diagnostico"] = True
    pending = list(trail["pendentes"])
    free = [i for i in range(len(plan_days)) if i not in reserved] or list(range(len(plan_days)))
    base, extra = divmod(len(pending), len(free))
    start = 0
    for position, index in enumerate(free):
        size = base + (1 if position < extra else 0)
        plan_days[index]["conceitos"] = pending[start:start + size]
        start += size
    for index, (kind, text) in reserved.items():
        plan_days[index]["tipo"] = kind
        plan_days[index]["atividade"] = text
    for day in plan_days:
        day.setdefault("tipo", "estudo")
        if day["tipo"] == "estudo":
            parts = ["Revisões vencidas"]
            if day.get("diagnostico"):
                parts.append("diagnóstico (/diagnostico)")
            if day["conceitos"]:
                parts.append("conceitos do dia na ordem da trilha: explicação, exemplo resolvido e questões")
                parts.append("ensinar de volta")
            else:
                parts.append("questões intercaladas dos pontos fracos (/quiz)")
            day["atividade"] = " → ".join(parts)
    needed = math.ceil(len(pending) / len(free)) if pending else 0
    return {
        "modo": "prova" if exam else "sem_data",
        "prova": exam.isoformat() if exam else None,
        "dias_de_estudo": len(plan_days),
        "dias": plan_days,
        "trilha": trail,
        "ritmo_recomendado": capacity,
        "ritmo_necessario": needed,
        "apertado": bool(exam) and needed > capacity,
    }


def today_entry(plan: dict[str, Any], today: date) -> dict[str, Any] | None:
    return next((d for d in plan.get("dias", []) if d["data"] == today.isoformat()), None)


def _trail_lines(kmap: KnowledgeMap, trail: dict[str, Any]) -> list[str]:
    needed = trail["respostas_para_concluir"]
    lines = ["## Trilha, em ordem de prioridade", "",
             "O que mais cai na prova vem primeiro; entre empatados, o mais difícil; sempre depois dos pré-requisitos. "
             "A trilha só termina quando todos os conceitos forem estudados e praticados.", ""]
    finished = set(trail["concluidos"])
    for cid in trail["ordem"]:
        progress = trail["progresso"][cid]
        if cid in finished:
            detail = "concluído"
        else:
            detail = ("estudado" if progress["estudado"] else "a estudar") + f"; {min(progress['respostas'], needed)} de {needed} respostas"
            if progress["questoes"] is not None and progress["questoes"] < needed:
                detail += "; faltam questões no banco"
        lines.append(f"- [{'x' if cid in finished else ' '}] {kmap.concepts[cid].name} (`{cid}`): {detail}")
    return lines


def render(materia: dict[str, Any], kmap: KnowledgeMap, plan: dict[str, Any],
           estimates: dict[str, ConceptEstimate], today: date) -> str:
    name = materia.get("nome") or materia.get("slug")
    trail = plan["trilha"]
    progress = f"- Trilha: {len(trail['concluidos'])} de {trail['total']} conceitos concluídos (estudados e praticados com pelo menos {trail['respostas_para_concluir']} respostas)."
    lines = [f"# Plano de estudo: {name}", "",
             f"> Gerado por `bash bin/tutor.sh plano` em {today.isoformat()}. Não edite à mão: para mudar datas, "
             "pesos ou ordem, use `/plano`, que ajusta os dados e gera este arquivo de novo.", ""]
    if plan["modo"] == "pos_prova":
        lines += [f"A prova foi em {plan['prova']}. Use `/plano` para informar a próxima data ou siga em modo "
                  "manutenção (revisões espaçadas sem teto).", "", progress]
        if not trail["concluida"]:
            lines += ["", *_trail_lines(kmap, trail)]
        return "\n".join(lines)
    exam = plan.get("prova")
    minutes = materia.get("tempo_diario_min")
    summary = [f"- Prova: {exam}" if exam else "- Prova: sem data informada (plano de 14 dias, sem simulados)"]
    if exam and not (materia.get("prova") or {}).get("data_confirmada"):
        summary.append("- Atenção: data provisória. Confirme com `/plano` quando souber a data certa.")
    summary.append(f"- Dias de estudo até a véspera: {plan['dias_de_estudo']}" + (f", {minutes} min por dia" if minutes else ""))
    summary.append(progress)
    if trail["pendentes"]:
        summary.append(f"- Ritmo: {plan['ritmo_necessario']} conceito(s) novo(s) por dia de estudo "
                       f"(recomendado para o seu tempo e nível: {plan['ritmo_recomendado']}).")
    if plan["apertado"]:
        summary.append("- Plano apertado: o ritmo necessário passa do recomendado. Nada sai da trilha: aumente o tempo "
                       "diário ou os dias de estudo por semana com `/plano`.")
    if trail["sem_questoes"]:
        names = ", ".join(kmap.concepts[c].name for c in trail["sem_questoes"])
        summary.append(f"- Faltam questões para concluir: {names}. O tutor gera e verifica questões para eles.")
    if trail["concluida"]:
        summary.append("- Trilha concluída: o foco agora é revisão, pontos fracos e simulados.")
    lines += summary + ["", "## Calendário", "", "| Dia | Data | Foco | Conceitos | Atividade |", "|---|---|---|---|---|"]
    for day in plan["dias"]:
        concepts = ", ".join(kmap.concepts[c].name for c in day["conceitos"]) or "-"
        focus = {"simulado": "Simulado", "reforco": "Reforço", "revisao-final": "Revisão final"}.get(day["tipo"], "Estudo")
        lines.append(f"| {day['rotulo']} ({day['dia_semana']}) | {day['data']} | {focus} | {concepts} | {day['atividade']} |")
    lines += ["", *_trail_lines(kmap, trail)]
    lines += ["", "## Como cada sessão funciona", "",
              "1. Revisões vencidas primeiro, de memória.",
              "2. Os próximos conceitos da trilha: explicação curta e exemplo resolvido quando o conceito é novo "
              "(sempre, para quem é iniciante); se você já domina o básico, problema primeiro.",
              "3. Em cada questão: sua resposta e sua confiança antes de qualquer ajuda; \"não sei\" também vale.",
              "4. No fim, você explica o conceito com as suas palavras (ensinar de volta).",
              "5. Checkpoint: o que foi feito e o próximo passo ficam registrados; o que não terminou continua na "
              "próxima sessão."]
    return "\n".join(lines)


def compute(paths: SubjectPaths, today: date) -> tuple[dict[str, Any], str]:
    materia = load_materia(paths)
    kmap = load_map(paths)
    questions = load_bank(paths, required=False)
    history = attempt_store.history(paths)
    now = datetime.combine(today, datetime.min.time())
    params = params_from(materia)
    estimates = estimate_concepts(kmap, questions, history, now, params)
    trail = trail_status(kmap, questions, history, load_studied(paths), params)
    plan = build_plan(materia, kmap, estimates, bool(history), today, trail=trail)
    return plan, render(materia, kmap, plan, estimates, today)


# ---------------------------------------------------------------- subcomandos


def cmd_plan(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    plan, text = compute(paths, ctx.clock.today())
    if args.escrever:
        write_text(paths.plano, text)
        mark_step(paths, "plano", True)
    directive = (
        "Resuma o plano em poucas linhas: trilha (concluídos de total), foco de hoje e dos próximos dias, simulados. "
        "Nada sai da trilha: ela segue a ordem de prioridade e só termina com todos os conceitos estudados e praticados. "
        "Se estiver apertado, diga com franqueza o ritmo necessário e sugira mais tempo por dia ou mais dias de estudo."
    )
    if plan["trilha"]["sem_questoes"]:
        directive += (" Conceitos em `trilha.sem_questoes` não têm questões suficientes: acione o agente "
                      "escritor-de-questoes para eles e depois o verificador, `banco comparar` e `validar --etapa banco`.")
    return {
        "status": "ok",
        **plan,
        "arquivo": str(paths.plano) if args.escrever else None,
        "llm_directive": directive,
    }


def cmd_trail_studied(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    kmap = load_map(paths)
    if args.conceito not in kmap.concepts:
        raise TutorError("conceito_inexistente", f"Conceito {args.conceito!r} não existe no mapa.",
                         "Use um id de `trilha.ordem` (saída de `plano`).")
    data = read_json(paths.trilha, {}) or {}
    studied = load_studied(paths)
    studied.setdefault(args.conceito, ctx.clock.today().isoformat())
    write_json(paths.trilha, {**(data if isinstance(data, dict) else {}), "schema_version": SCHEMA_VERSION,
                              "estudados": studied})
    params = params_from(load_materia(paths))
    needed = max(1, int(params["respostas_para_concluir"]))
    answers = practice_counts(load_bank(paths, required=False), attempt_store.history(paths)).get(args.conceito, 0)
    missing = max(0, needed - answers)
    return {
        "status": "ok",
        "conceito": args.conceito,
        "estudado_em": studied[args.conceito],
        "respostas": answers,
        "faltam_respostas": missing,
        "llm_directive": (
            f"Conceito marcado como estudado. Agora as questões dele, da mais fácil para a mais difícil "
            f"(`proximas --conceito {args.conceito}`): faltam {missing} resposta(s) para concluí-lo na trilha."
            if missing else "Conceito estudado e praticado: concluído na trilha. Siga para o próximo conceito do dia."
        ),
    }


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("plano", help="trilha e calendário reverso até a prova (com --escrever, gera plano.md)")
    p.add_argument("--materia")
    p.add_argument("--escrever", action="store_true")
    p.set_defaults(handler=cmd_plan)

    group = sub.add_parser("trilha", help="trilha de estudo: conceitos em ordem de prioridade")
    actions = group.add_subparsers(dest="acao", metavar="<acao>", required=True, parser_class=type(group))
    p = actions.add_parser("estudado", help="marca que o conceito foi explicado ao aluno (idempotente)")
    p.add_argument("--materia")
    p.add_argument("--conceito", required=True)
    p.set_defaults(handler=cmd_trail_studied)
