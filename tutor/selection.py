"""Escolha das próximas questões e montagem do simulado.

Prioridade de uma questão (maior primeiro), a partir da última tentativa:
  errou: 3 (+1,5 se a confiança era 4 ou 5)  |  acertou com confiança 1-2: 2
  nunca vista: 1  |  acertou com confiança 3+: 0,5, crescendo até 1 depois de 7 dias
Multiplicadores: conceito fraco ou sem dados, peso do conceito, revisão vencida (x1,5),
pré-requisito ainda fraco (x0,3), acerto no mesmo dia (x0,2). A ordem final
intercala temas. Pesos e multiplicadores são heurísticos (veja docs/ARQUITETURA.md).
No treino de um conceito ainda não concluído na trilha, a ordem é outra: as questões
respondidas nas últimas 24 h por último, as do conceito como principal primeiro e,
entre elas, da mais fácil para a mais difícil.
A saída traz só ids: tema e conceitos ficam ocultos até a correção.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime
from typing import Any

from tutor import attempts as attempt_store
from tutor.attempts import REVEAL_WINDOW, Attempt
from tutor.bank import load_bank
from tutor.core import Context, SubjectPaths, TutorError, load_materia, resolve_subject
from tutor.knowledge_map import KnowledgeMap, load_map
from tutor.learner import ConceptEstimate, estimate_concepts, params_from, practice_counts, readiness
from tutor.planner import load_studied
from tutor.srs import is_due, load_items

MODES = ("treino", "quiz", "revisao", "diagnostico")
DEFAULT_N = {"treino": 3, "quiz": 5, "revisao": 3, "diagnostico": 4}


def _base_score(history: list[Attempt], today: date) -> float:
    if not history:
        return 1.0
    last = history[-1]
    if last.correct is None:
        return 1.5
    if not last.correct:
        return 3.0 + (1.5 if last.confidence >= 4 else 0.0)
    if last.confidence <= 2:
        score = 2.0
    else:
        score = 0.5 + 0.5 * min(1.0, (today - last.at.date()).days / 7.0)
    if last.at.date() == today:
        score *= 0.2
    return score


def score_questions(
    questions: dict[str, dict[str, Any]], kmap: KnowledgeMap, estimates: dict[str, ConceptEstimate],
    history: list[Attempt], due_concepts: set[str], today: date,
) -> dict[str, float]:
    by_question: dict[str, list[Attempt]] = {}
    for attempt in history:
        by_question.setdefault(attempt.id, []).append(attempt)
    scores = {}
    for qid, question in questions.items():
        concepts = [c for c in question.get("conceitos", []) if c in kmap.concepts]
        if not concepts:
            continue
        score = _base_score(by_question.get(qid, []), today)
        weakest = min(estimates[c].mean if estimates[c].attempts else 0.5 for c in concepts)
        score *= 1.0 + (1.0 - weakest)
        score *= 1.0 + max(estimates[c].weight for c in concepts)
        if any(c in due_concepts for c in concepts):
            score *= 1.5
        blocked = any(
            estimates[p].attempts >= 2 and estimates[p].mean < 0.5
            for c in concepts for p in kmap.concepts[c].prerequisites if p in estimates
        )
        if blocked:
            score *= 0.3
        scores[qid] = score
    return scores


def interleave(ranked: list[str], questions: dict[str, dict[str, Any]], n: int) -> list[str]:
    """Pega os melhores evitando o mesmo tema duas vezes seguidas quando há alternativa."""
    pool = list(ranked)
    picked: list[str] = []
    last_theme = None
    while pool and len(picked) < n:
        choice = next((q for q in pool if questions[q].get("tema") != last_theme), pool[0])
        picked.append(choice)
        pool.remove(choice)
        last_theme = questions[choice].get("tema")
    return picked


def _usable(question: dict[str, Any], exam: bool) -> bool:
    state = question.get("verificacao", "pendente")
    if state == "divergente":
        return False
    return state == "verificada" if exam else True


def _context(paths: SubjectPaths, now: datetime):
    materia = load_materia(paths)
    kmap = load_map(paths)
    questions = load_bank(paths)
    history = attempt_store.history(paths)
    estimates = estimate_concepts(kmap, questions, history, now, params_from(materia))
    return materia, kmap, questions, history, estimates


def next_questions(
    paths: SubjectPaths, mode: str, n: int | None, theme: str | None, concept: str | None,
    now: datetime, rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    materia, kmap, questions, history, estimates = _context(paths, now)
    today = now.date()
    exam_date = (materia.get("prova") or {}).get("data")
    exam_day = date.fromisoformat(exam_date) if exam_date else None
    due = {i["conceito"] for i in load_items(paths) if is_due(i, today, exam_day)}
    rng = rng or random.Random(f"{today.isoformat()}-{len(history)}")
    n = n or DEFAULT_N[mode]
    pool = {qid: q for qid, q in questions.items() if _usable(q, exam=False)}
    if theme:
        pool = {qid: q for qid, q in pool.items() if q.get("tema") == theme}
    if concept:
        pool = {qid: q for qid, q in pool.items() if concept in q.get("conceitos", [])}
    if mode == "revisao":
        pool = {qid: q for qid, q in pool.items() if set(q.get("conceitos", [])) & due} or pool
    if mode == "diagnostico":
        return [{"id": qid, "tipo": pool[qid].get("tipo", "multipla-escolha")}
                for qid in _diagnostic(pool, kmap, history, n, rng)]
    scores = score_questions(pool, kmap, estimates, history, due, today)
    if mode == "treino" and concept and not _concluded(paths, concept, questions, history, materia):
        recent = {a.id for a in history if now - a.at <= REVEAL_WINDOW}
        ordered = sorted(scores, key=lambda q: (
            q in recent, (pool[q].get("conceitos") or [None])[0] != concept,
            int(pool[q].get("dificuldade", 2)), -scores[q], rng.random(),
        ))
        return [{"id": qid, "tipo": pool[qid].get("tipo", "multipla-escolha")} for qid in ordered[:n]]
    ranked = sorted(scores, key=lambda q: (-scores[q], rng.random()))
    return [{"id": qid, "tipo": pool[qid].get("tipo", "multipla-escolha")} for qid in interleave(ranked, pool, n)]


def _concluded(paths: SubjectPaths, concept: str, questions: dict[str, dict[str, Any]], history: list[Attempt],
               materia: dict[str, Any]) -> bool:
    """Estudado (`trilha estudado`) e praticado com o mínimo de respostas."""
    needed = max(1, int(params_from(materia)["respostas_para_concluir"]))
    return concept in load_studied(paths) and practice_counts(questions, history).get(concept, 0) >= needed


def _diagnostic(
    pool: dict[str, dict[str, Any]], kmap: KnowledgeMap, history: list[Attempt], n: int, rng: random.Random,
) -> list[str]:
    """Uma questão inédita por conceito, começando pelas raízes e pelos de maior peso."""
    seen = {a.id for a in history}
    picked: list[str] = []
    for cid in kmap.topological_order():
        candidates = [q for q, data in pool.items() if cid in data.get("conceitos", []) and q not in seen and q not in picked]
        if not candidates:
            continue
        candidates.sort(key=lambda q: (abs(int(pool[q].get("dificuldade", 2)) - 2), rng.random()))
        picked.append(candidates[0])
        if len(picked) >= n:
            break
    return picked


def build_exam(
    paths: SubjectPaths, n: int | None, now: datetime, rng: random.Random | None = None,
) -> tuple[list[str], int, dict[str, Any]]:
    materia, kmap, questions, history, estimates = _context(paths, now)
    exam = materia.get("prova") or {}
    n_exam = int(exam.get("n_questoes") or 10)
    n = n or n_exam
    pool = {qid: q for qid, q in questions.items() if _usable(q, exam=True)}
    if len(pool) < n:
        raise TutorError(
            "banco_insuficiente",
            f"O simulado precisa de {n} questões verificadas; o banco tem {len(pool)}.",
            "Ofereça um simulado menor (--n) ou gerar e verificar mais questões antes.",
            verificadas=len(pool),
        )
    rng = rng or random.Random(f"simulado-{now.date().isoformat()}-{len(history)}")
    theme_weight: dict[str, float] = {}
    for qid, q in pool.items():
        theme = q.get("tema") or "geral"
        theme_weight.setdefault(theme, 0.0)
    for cid, est in estimates.items():
        theme = kmap.concepts[cid].theme
        if theme in theme_weight:
            theme_weight[theme] += est.weight
    total = sum(theme_weight.values()) or 1.0
    raw = {t: n * w / total for t, w in theme_weight.items()}
    quota = {t: int(v) for t, v in raw.items()}
    for theme in sorted(raw, key=lambda t: -(raw[t] - quota[t]))[: n - sum(quota.values())]:
        quota[theme] += 1
    scores = score_questions(pool, kmap, estimates, history, set(), now.date())
    chosen: list[str] = []
    for theme, k in sorted(quota.items()):
        members = [q for q in pool if (pool[q].get("tema") or "geral") == theme]
        members.sort(key=lambda q: (-scores.get(q, 0.0) * (0.75 + 0.5 * rng.random())))
        chosen += members[:k]
    if len(chosen) < n:  # tema com poucas questões: completa com as melhores restantes
        rest = sorted((q for q in pool if q not in chosen), key=lambda q: -scores.get(q, 0.0))
        chosen += rest[: n - len(chosen)]
    ordered = interleave(chosen, pool, n)
    limit = round(int(exam.get("duracao_min") or 120) * n / max(n_exam, 1))
    forecast = readiness(estimates, n, params_from(materia), seed=f"simulado-{now.date()}")
    return ordered, limit, forecast


# ---------------------------------------------------------------- subcomandos


def cmd_next(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    picks = next_questions(paths, args.modo, args.n, args.tema, args.conceito, ctx.clock.now())
    if not picks:
        return {
            "status": "ok", "questoes": [],
            "llm_directive": "Não há questões disponíveis com esse filtro. Ofereça outro tema ou gerar questões novas.",
        }
    directive = (
        "Apresente UMA questão por vez com `apresentar` (o tema fica oculto de propósito: reconhecer a ferramenta "
        "faz parte da prova). Peça resposta e confiança antes de ajudar; corrija com `corrigir`."
    )
    if args.modo == "diagnostico":
        directive = (
            "Diagnóstico: pré-teste para mapear o que o aluno já sabe. Explique que errar aqui é esperado e útil. "
            "Apresente cada questão com `apresentar --modo diagnostico`, peça resposta e confiança, corrija sem "
            "aula longa (explicação curta) e siga; o plano se ajusta depois."
        )
    return {"status": "ok", "modo": args.modo, "questoes": picks, "llm_directive": directive}


def cmd_exam_start(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    ids, limit, forecast = build_exam(paths, args.n, ctx.clock.now())
    attempt_store.start_exam(paths, ids, limit, forecast if forecast.get("disponivel") else None, ctx.clock.now())
    return {
        "status": "ok",
        "questoes": ids,
        "limite_min": limit,
        "previsao": forecast,
        "llm_directive": (
            f"Simulado de {len(ids)} questões em {limit} minutos, em condições de prova: sem consulta, sem dicas, sem "
            "feedback até o fim. Combine as regras com o aluno, apresente uma questão por vez com `apresentar`, "
            "registre cada resposta e confiança com `simulado responder` e, no fim (ou com o tempo esgotado), rode "
            "`simulado encerrar`."
        ),
    }


def cmd_exam_answer(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    answer = None if args.nao_sei else args.resposta
    if answer is None and not args.nao_sei:
        raise TutorError("sem_resposta", "Informe --resposta ou --nao-sei.")
    return attempt_store.answer_exam(
        paths, args.questao, answer, args.confianca, args.segundos, ctx.clock.now(), args.substituir,
    )


def cmd_exam_status(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return attempt_store.exam_status(resolve_subject(ctx, args.materia), ctx.clock.now())


def cmd_exam_finish(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    return attempt_store.finish_exam(resolve_subject(ctx, args.materia), ctx.clock.now())


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("proximas", help="próximas questões priorizadas e intercaladas (só ids)")
    p.add_argument("--materia")
    p.add_argument("--modo", choices=MODES, default="treino")
    p.add_argument("--n", type=int, help="quantas (padrão depende do modo)")
    p.add_argument("--tema")
    p.add_argument("--conceito")
    p.set_defaults(handler=cmd_next)

    group = sub.add_parser("simulado", help="prova completa cronometrada, com correção só no fim")
    actions = group.add_subparsers(dest="acao", metavar="<acao>", required=True, parser_class=type(group))
    p = actions.add_parser("iniciar", help="sorteia o simulado (estratificado, só questões verificadas)")
    p.add_argument("--materia")
    p.add_argument("--n", type=int, help="número de questões (padrão: o da prova)")
    p.set_defaults(handler=cmd_exam_start)
    p = actions.add_parser("responder", help="guarda resposta e confiança sem corrigir")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    attempt_store.add_answer_args(p)
    p.add_argument("--substituir", action="store_true")
    p.set_defaults(handler=cmd_exam_answer)
    p = actions.add_parser("estado", help="tempo decorrido e questões que faltam (retomada)")
    p.add_argument("--materia")
    p.set_defaults(handler=cmd_exam_status)
    p = actions.add_parser("encerrar", help="corrige tudo, registra e compara com a previsão")
    p.add_argument("--materia")
    p.set_defaults(handler=cmd_exam_finish)
