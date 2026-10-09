"""Painel de progresso e caderno de erros.

O painel junta domínio por conceito (com faixa de incerteza), acerto por tema, tipos
de erro, calibração, preparo estimado e o histórico dos simulados (previsto x real).
O caderno de erros agrupa erros recorrentes por conceito, tipo e distrator escolhido,
sem nunca mostrar a letra correta (a mesma questão pode voltar).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from tutor import attempts as attempt_store
from tutor.bank import load_bank, load_key
from tutor.core import Context, SubjectPaths, load_materia, parse_date, read_jsonl, resolve_subject, write_text
from tutor.knowledge_map import load_map
from tutor.learner import calibration, estimate_concepts, params_from, readiness
from tutor.srs import is_due, load_items

STATUS_LABEL = {"dominado": "dominado", "em_progresso": "em progresso", "fraco": "fraco", "sem_dados": "sem dados"}


def build_dashboard(paths: SubjectPaths, now: datetime) -> dict[str, Any]:
    materia = load_materia(paths)
    kmap = load_map(paths)
    questions = load_bank(paths, required=False)
    history = attempt_store.history(paths)
    params = params_from(materia)
    estimates = estimate_concepts(kmap, questions, history, now, params)
    exam = materia.get("prova") or {}
    exam_date = parse_date(exam.get("data"))
    by_theme: dict[str, list[float]] = defaultdict(list)
    errors: Counter[str] = Counter()
    for attempt in history:
        question = questions.get(attempt.id)
        if question is None or attempt.score is None:
            continue
        by_theme[question.get("tema") or "geral"].append(attempt.score)
        if attempt.score < 1 and attempt.error_type:
            errors[attempt.error_type] += 1
    items = load_items(paths)
    today = now.date()
    exams = [
        {"em": r["em"][:10], "acertos": r["acertos"], "total": r["total"],
         "previsto": (r.get("previsao") or {}).get("mediana"), "faixa_prevista": (r.get("previsao") or {}).get("faixa_80")}
        for r in read_jsonl(paths.simulados)
    ]
    pend = attempt_store.pending(history)
    dashboard = {
        "materia": paths.slug,
        "nome": materia.get("nome"),
        "dias_ate_prova": (exam_date - today).days if exam_date else None,
        "resumo": {
            "tentativas": len(history),
            "questoes_distintas": len({a.id for a in history}),
            "banco": len(questions),
            "verificadas": sum(1 for q in questions.values() if q.get("verificacao") == "verificada"),
            "dias_com_estudo": len({a.at.date() for a in history}),
        },
        "conceitos": [estimates[cid].as_dict() for cid in kmap.topological_order()],
        "por_tema": [
            {"tema": theme, "tentativas": len(scores), "acerto": round(sum(scores) / len(scores), 2)}
            for theme, scores in sorted(by_theme.items())
        ],
        "tipos_de_erro": dict(errors.most_common()),
        "calibracao": calibration(history),
        "preparo": readiness(estimates, int(exam.get("n_questoes") or 10), params, seed=f"painel-{today}"),
        "simulados": exams,
        "revisoes": {"agendadas": len(items), "vencidas": sum(1 for i in items if is_due(i, today, exam_date))},
        "pendencias": pend,
    }
    dashboard["proximas_acoes"] = _next_actions(dashboard, estimates, history, today)
    return dashboard


def _next_actions(dashboard, estimates, history, today) -> list[str]:
    actions = []
    if dashboard["pendencias"]["classificar"]:
        actions.append(f"Classificar erros pendentes: {', '.join(dashboard['pendencias']['classificar'][:5])}.")
    recent_overconfident = {a.id for a in history if a.correct is False and a.confidence >= 4 and (today - a.at.date()).days <= 7}
    if recent_overconfident:
        actions.append("Rever concepções: houve erro com confiança alta nos últimos 7 dias (questões "
                       + ", ".join(sorted(recent_overconfident)[:5]) + ").")
    tried = [e for e in estimates.values() if e.attempts]
    if tried:
        weakest = max(tried, key=lambda e: e.weight * (1 - e.mean))
        if weakest.status != "dominado":
            actions.append(f"Praticar o conceito mais fraco considerando o peso: {weakest.name} (/quiz).")
    untouched = sorted((e for e in estimates.values() if not e.attempts), key=lambda e: -e.weight)
    if untouched:
        actions.append(f"Começar conceitos sem tentativas, pelo de maior peso: {untouched[0].name}.")
    if dashboard["calibracao"].get("vies", 0) > 0.1 and dashboard["calibracao"].get("n", 0) >= 10:
        actions.append("Treinar calibração: antes de dar confiança 4 ou 5, diga em uma frase por que tem certeza.")
    return actions[:5]


def render_dashboard(d: dict[str, Any], now: datetime) -> str:
    lines = [f"# Painel: {d.get('nome') or d['materia']}", "",
             f"> Gerado por `bash bin/tutor.sh painel` em {now.strftime('%Y-%m-%d %H:%M')}. Não edite à mão.", ""]
    s = d["resumo"]
    days = d["dias_ate_prova"]
    lines.append(f"- Prova: {'sem data' if days is None else (f'em {days} dia(s)' if days >= 0 else 'já passou')}")
    lines.append(f"- Tentativas: {s['tentativas']} em {s['dias_com_estudo']} dia(s); questões distintas: "
                 f"{s['questoes_distintas']} de {s['banco']} ({s['verificadas']} verificadas)")
    lines.append(f"- Revisões: {d['revisoes']['vencidas']} vencida(s) de {d['revisoes']['agendadas']} agendada(s)")
    prep = d["preparo"]
    if prep.get("disponivel"):
        lines.append(f"- Preparo estimado: {prep['mediana']} de {prep['questoes']} (faixa de 80%: "
                     f"{prep['faixa_80'][0]} a {prep['faixa_80'][1]}). {prep['aviso']}")
    else:
        lines.append(f"- Preparo estimado: indisponível ({prep.get('motivo')}).")
    lines += ["", "## Domínio por conceito", "", "| Conceito | Tema | Tentativas | Acerto estimado | Faixa 80% | Estado |",
              "|---|---|---:|---:|---|---|"]
    for c in d["conceitos"]:
        estimate = "-" if c["tentativas"] == 0 else f"{round(100 * c['p_acerto'])}%"
        band = "-" if c["tentativas"] == 0 else f"{round(100 * c['faixa_80'][0])}% a {round(100 * c['faixa_80'][1])}%"
        lines.append(f"| {c['nome']} | {c['tema']} | {c['tentativas']} | {estimate} | {band} | {STATUS_LABEL[c['estado']]} |")
    lines += ["", "## Acerto por tema", "", "| Tema | Tentativas | Acerto |", "|---|---:|---:|"]
    lines += [f"| {t['tema']} | {t['tentativas']} | {round(100 * t['acerto'])}% |" for t in d["por_tema"]] or ["| - | 0 | - |"]
    lines += ["", "## Tipos de erro", ""]
    lines += [f"- {kind}: {count}" for kind, count in d["tipos_de_erro"].items()] or ["- nenhum erro classificado"]
    cal = d["calibracao"]
    lines += ["", "## Calibração (confiança x acerto)", ""]
    if cal.get("n"):
        lines.append(f"- {cal['n']} respostas sem dica; Brier {cal['brier']} (0 é perfeito); leitura: {cal['leitura']}.")
        lines += ["", "| Confiança | Respostas | Acerto | Esperado |", "|---:|---:|---:|---:|"]
        lines += [f"| {r['confianca']} | {r['n']} | {round(100 * r['acerto'])}% | {round(100 * r['esperado'])}% |"
                  for r in cal["por_confianca"]]
    else:
        lines.append("- Sem dados ainda.")
    if d["simulados"]:
        lines += ["", "## Simulados (previsto x real)", "", "| Data | Acertos | Previsto | Faixa prevista |", "|---|---:|---:|---|"]
        for e in d["simulados"]:
            band = f"{e['faixa_prevista'][0]} a {e['faixa_prevista'][1]}" if e.get("faixa_prevista") else "-"
            lines.append(f"| {e['em']} | {e['acertos']:g}/{e['total']} | {e['previsto'] if e['previsto'] is not None else '-'} | {band} |")
    lines += ["", "## Próximas ações", ""]
    lines += [f"- {a}" for a in d["proximas_acoes"]] or ["- Seguir o plano."]
    return "\n".join(lines)


def build_error_notebook(paths: SubjectPaths) -> dict[str, Any]:
    kmap = load_map(paths)
    questions = load_bank(paths, required=False)
    key = load_key(paths)
    groups: dict[str, dict[str, Any]] = {}
    for attempt in attempt_store.history(paths):
        question = questions.get(attempt.id)
        if question is None or attempt.score is None or attempt.score >= 1:
            continue
        entry = key.get(attempt.id) or {}
        tempting = None
        if question.get("tipo", "multipla-escolha") == "multipla-escolha" and attempt.answer:
            tempting = (entry.get("distratores") or {}).get(attempt.answer)
        for cid in question.get("conceitos", []):
            group = groups.setdefault(cid, {"erros": 0, "tipos": Counter(), "equivocos": Counter(), "questoes": set(), "ultima": None})
            group["erros"] += 1
            if attempt.error_type:
                group["tipos"][attempt.error_type] += 1
            if tempting:
                group["equivocos"][tempting] += 1
            group["questoes"].add(attempt.id)
            day = attempt.at.date().isoformat()
            group["ultima"] = max(group["ultima"] or day, day)
    concepts = []
    for cid, group in sorted(groups.items(), key=lambda kv: -kv[1]["erros"]):
        name = kmap.concepts[cid].name if cid in kmap.concepts else cid
        recurring = [m for m, n in group["equivocos"].items() if n >= 2] + [
            f"erro de {t} repetido" for t, n in group["tipos"].items() if n >= 2
        ]
        concepts.append(
            {"conceito": cid, "nome": name, "erros": group["erros"], "tipos": dict(group["tipos"]),
             "equivocos": [m for m, _ in group["equivocos"].most_common()], "recorrente": recurring,
             "questoes": sorted(group["questoes"]), "ultima": group["ultima"]}
        )
    return {"conceitos": concepts}


def render_error_notebook(notebook: dict[str, Any], now: datetime) -> str:
    lines = ["# Caderno de erros", "",
             f"> Gerado por `bash bin/tutor.sh erros` em {now.strftime('%Y-%m-%d %H:%M')}. Sem letras de resposta, "
             "de propósito: as questões voltam. Não edite à mão; anote reflexões em notas/.", ""]
    if not notebook["conceitos"]:
        return "\n".join(lines + ["Nenhum erro registrado ainda."])
    for c in notebook["conceitos"]:
        lines += [f"## {c['nome']}", "", f"- Erros: {c['erros']} (última vez em {c['ultima']}); questões: {', '.join(c['questoes'])}"]
        if c["tipos"]:
            lines.append("- Tipos: " + ", ".join(f"{t} ({n})" for t, n in c["tipos"].items()))
        if c["recorrente"]:
            lines.append("- Padrão recorrente: " + "; ".join(c["recorrente"]))
        for misconception in c["equivocos"][:3]:
            lines.append(f"- Armadilha em que você caiu: {misconception}")
        lines.append("")
    return "\n".join(lines)


def cmd_dashboard(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    now = ctx.clock.now()
    dashboard = build_dashboard(paths, now)
    if args.escrever:
        write_text(paths.dominio, render_dashboard(dashboard, now))
    return {
        "status": "ok",
        **dashboard,
        "llm_directive": (
            "Mostre o painel de forma curta: conceitos mais fracos (com a faixa de incerteza), tipo de erro dominante, "
            "calibração e o preparo estimado com a faixa e o aviso. Nunca transforme o preparo em promessa de nota. "
            "Termine com as próximas ações."
        ),
    }


def cmd_errors(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    notebook = build_error_notebook(paths)
    if args.escrever:
        write_text(paths.caderno, render_error_notebook(notebook, ctx.clock.now()))
    return {
        "status": "ok",
        **notebook,
        "llm_directive": (
            "Mostre os padrões recorrentes primeiro. Para cada um, peça que o aluno explique por que a armadilha "
            "engana e como reconhecê-la; depois ofereça questões do conceito (/quiz). Não revele respostas."
        ),
    }


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("painel", help="domínio, acertos, erros, calibração e preparo (com --escrever, gera dominio.md)")
    p.add_argument("--materia")
    p.add_argument("--escrever", action="store_true")
    p.set_defaults(handler=cmd_dashboard)
    p = sub.add_parser("erros", help="caderno de erros (com --escrever, gera caderno-de-erros.md)")
    p.add_argument("--materia")
    p.add_argument("--escrever", action="store_true")
    p.set_defaults(handler=cmd_errors)
