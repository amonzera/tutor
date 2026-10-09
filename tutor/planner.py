"""Plano de estudo: calendário reverso a partir da data da prova.

Regras (heurísticas, ajustáveis pelo replanejamento):
- 1º dia de estudo: diagnóstico, se ainda não houver tentativas;
- com 7 ou mais dias: simulado completo em D-3, reforço pelos erros em D-2 e
  simulado leve + revisão geral em D-1; com 3 a 6 dias: simulado em D-2 e revisão em D-1;
- conceitos ainda não dominados em ordem de pré-requisito (entre independentes, maior
  peso primeiro), distribuídos pelos dias livres equilibrando a soma dos pesos;
- folga diária para as revisões vencidas, que vêm sempre antes do conteúdo novo.
`plano.md` é gerado a partir dos dados; o estado não mora no arquivo.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from typing import Any

from tutor import attempts as attempt_store
from tutor.bank import load_bank
from tutor.core import Context, SubjectPaths, load_materia, mark_step, parse_date, resolve_subject, write_text
from tutor.knowledge_map import KnowledgeMap, load_map
from tutor.learner import ConceptEstimate, estimate_concepts, params_from

WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
NO_EXAM_HORIZON = 14
REST_ORDER = (6, 5, 4, 3, 2, 1, 0)  # domingo primeiro, depois sábado...


def study_days(start: date, end: date, days_per_week: int) -> list[date]:
    rest = set(REST_ORDER[: max(0, 7 - max(1, min(7, days_per_week)))])
    days, current = [], start
    while current <= end:
        if current.weekday() not in rest:
            days.append(current)
        current += timedelta(days=1)
    return days


def build_plan(
    materia: dict[str, Any], kmap: KnowledgeMap, estimates: dict[str, ConceptEstimate],
    has_attempts: bool, today: date,
) -> dict[str, Any]:
    exam = parse_date((materia.get("prova") or {}).get("data"))
    if exam is not None and exam <= today:
        return {"modo": "pos_prova", "prova": exam.isoformat(), "dias": [], "cobertura": 1.0, "apertado": False}
    end = exam - timedelta(days=1) if exam else today + timedelta(days=NO_EXAM_HORIZON - 1)
    days = study_days(today, end, int(materia.get("dias_por_semana") or 6))
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
    elif exam and plan_days:
        reserved[len(plan_days) - 1] = ("revisao-final", "Revisão geral e pontos fracos")
    if not has_attempts and plan_days and 0 not in reserved:
        plan_days[0]["diagnostico"] = True
    to_study = [cid for cid in kmap.topological_order() if estimates[cid].status != "dominado"]
    free = [i for i in range(len(plan_days)) if i not in reserved]
    if free and to_study:
        loads = {cid: kmap.concepts[cid].weight * (1.5 - estimates[cid].mean) for cid in to_study}
        target = sum(loads.values()) / len(free)
        slot, acc = 0, 0.0
        for cid in to_study:
            if acc >= target and slot < len(free) - 1:
                slot, acc = slot + 1, 0.0
            plan_days[free[slot]]["conceitos"].append(cid)
            acc += loads[cid]
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
                parts.append("conceitos do dia com questões (tenta-primeiro)")
                parts.append("ensinar de volta")
            else:
                parts.append("questões intercaladas dos pontos fracos (/quiz)")
            day["atividade"] = " → ".join(parts)
    scheduled = {cid for day in plan_days for cid in day["conceitos"]}
    tight = bool(to_study) and (not free or len(to_study) / max(len(free), 1) > 3)
    return {
        "modo": "prova" if exam else "sem_data",
        "prova": exam.isoformat() if exam else None,
        "dias_de_estudo": len(plan_days),
        "dias": plan_days,
        "conceitos_a_estudar": to_study,
        "dominados": [cid for cid in kmap.topological_order() if estimates[cid].status == "dominado"],
        "cobertura": round(len(scheduled) / len(to_study), 2) if to_study else 1.0,
        "apertado": tight,
    }


def today_entry(plan: dict[str, Any], today: date) -> dict[str, Any] | None:
    return next((d for d in plan.get("dias", []) if d["data"] == today.isoformat()), None)


def render(materia: dict[str, Any], kmap: KnowledgeMap, plan: dict[str, Any],
           estimates: dict[str, ConceptEstimate], today: date) -> str:
    name = materia.get("nome") or materia.get("slug")
    lines = [f"# Plano de estudo: {name}", "",
             f"> Gerado por `bash bin/tutor.sh plano` em {today.isoformat()}. Não edite à mão: para mudar datas, "
             "pesos ou ordem, use `/plano`, que ajusta os dados e gera este arquivo de novo.", ""]
    if plan["modo"] == "pos_prova":
        lines += [f"A prova foi em {plan['prova']}. Use `/plano` para informar a próxima data ou siga em modo "
                  "manutenção (revisões espaçadas sem teto)."]
        return "\n".join(lines)
    exam = plan.get("prova")
    minutes = materia.get("tempo_diario_min")
    summary = [f"- Prova: {exam}" if exam else "- Prova: sem data informada (plano de 14 dias, sem simulados)"]
    if exam and not (materia.get("prova") or {}).get("data_confirmada"):
        summary.append("- Atenção: data provisória. Confirme com `/plano` quando souber a data certa.")
    summary.append(f"- Dias de estudo até a véspera: {plan['dias_de_estudo']}" + (f", {minutes} min por dia" if minutes else ""))
    summary.append(f"- Conceitos a estudar: {len(plan['conceitos_a_estudar'])}; já dominados: {len(plan['dominados'])}")
    if plan["apertado"]:
        summary.append("- Plano apertado: mais de 3 conceitos por dia livre. Priorize os de maior peso e considere aumentar o tempo diário.")
    lines += summary + ["", "## Calendário", "", "| Dia | Data | Foco | Conceitos | Atividade |", "|---|---|---|---|---|"]
    for day in plan["dias"]:
        concepts = ", ".join(kmap.concepts[c].name for c in day["conceitos"]) or "-"
        focus = {"simulado": "Simulado", "reforco": "Reforço", "revisao-final": "Revisão final"}.get(day["tipo"], "Estudo")
        lines.append(f"| {day['rotulo']} ({day['dia_semana']}) | {day['data']} | {focus} | {concepts} | {day['atividade']} |")
    lines += ["", "## Conceitos em ordem de estudo", ""]
    for cid in kmap.topological_order():
        est = estimates[cid]
        mark = "x" if est.status == "dominado" else " "
        detail = "sem tentativas" if est.attempts == 0 else f"acerto estimado {round(100 * est.mean)}%, {est.status.replace('_', ' ')}"
        lines.append(f"- [{mark}] {kmap.concepts[cid].name} (`{cid}`): {detail}")
    lines += ["", "## Como cada sessão funciona", "",
              "1. Revisões vencidas primeiro, de memória.",
              "2. Conceito do dia: se você ainda é iniciante nele, um exemplo resolvido e depois questões com dicas que "
              "vão sumindo; se já domina o básico, problema primeiro.",
              "3. Em cada questão: sua resposta e sua confiança antes de qualquer ajuda.",
              "4. No fim, você explica o conceito com as suas palavras (ensinar de volta).",
              "5. Checkpoint: o que foi feito e o próximo passo ficam registrados para a próxima sessão."]
    return "\n".join(lines)


def compute(paths: SubjectPaths, today: date) -> tuple[dict[str, Any], str]:
    materia = load_materia(paths)
    kmap = load_map(paths)
    questions = load_bank(paths, required=False)
    history = attempt_store.history(paths)
    now = datetime.combine(today, datetime.min.time())
    estimates = estimate_concepts(kmap, questions, history, now, params_from(materia))
    plan = build_plan(materia, kmap, estimates, bool(history), today)
    return plan, render(materia, kmap, plan, estimates, today)


def cmd_plan(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    plan, text = compute(paths, ctx.clock.today())
    if args.escrever:
        write_text(paths.plano, text)
        mark_step(paths, "plano", True)
    return {
        "status": "ok",
        **plan,
        "arquivo": str(paths.plano) if args.escrever else None,
        "llm_directive": (
            "Resuma o plano em poucas linhas: dias até a prova, foco de hoje e dos próximos dias, simulados. "
            "Se estiver apertado, diga com franqueza e proponha prioridades; não prometa cobrir tudo."
        ),
    }


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("plano", help="calendário reverso até a prova (com --escrever, gera plano.md)")
    p.add_argument("--materia")
    p.add_argument("--escrever", action="store_true")
    p.set_defaults(handler=cmd_plan)
