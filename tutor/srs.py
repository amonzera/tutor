"""Revisão espaçada de conceitos, limitada pela data da prova.

Itens são conceitos do mapa (não questões: revisar a mesma questão ensina a letra,
não a ideia). A revisão é recordação livre ("explique de memória") ou uma questão
nova do conceito.

Agendador padrão `sm2-prova`: SM-2 (fator de facilidade por item; lapso volta ao
início) com duas adaptações para prova marcada, ambas heurísticas declaradas:
  1. o intervalo não passa de `fracao_max_intervalo` (padrão 0,5) dos dias que faltam,
     com piso de 2 dias para item já estabelecido (2+ acertos seguidos): perto da prova
     os intervalos se fecham sem virar revisão diária. Inspirado na ideia de que o
     espaçamento ótimo depende do horizonte de retenção; os números são escolha nossa,
     calibrada por simulação (4 a 9 revisões para provas de 1 semana a 2 meses);
  2. nenhuma revisão cai depois da véspera da prova.
Outras diferenças em relação à descrição original (Wozniak, 1990): quatro notas em vez
de seis; o fator também é atualizado nos lapsos; o intervalo é arredondado para o
inteiro mais próximo; conceitos com nota abaixo de 4 não voltam no mesmo dia.
O limite diário e o orçamento entre matérias são aplicados na leitura (triagem),
sem reagendar nada.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

from tutor.core import (
    SCHEMA_VERSION,
    Context,
    SubjectPaths,
    TutorError,
    is_valid_slug,
    load_materia,
    parse_date,
    read_json,
    resolve_subject,
    write_json,
)
from tutor.knowledge_map import load_map

GRADES = ("esqueci", "dificil", "bom", "facil")
DEFAULT_DAILY_LIMIT = 15
DEFAULT_TOTAL_LIMIT = 30
DEFAULT_INTERVAL_FRACTION = 0.5
ESTABLISHED_MIN_INTERVAL = 2
MIN_PER_SUBJECT = 2


class Scheduler(Protocol):
    name: str

    def next_state(self, item: dict[str, Any], grade: str) -> dict[str, Any]:
        """Novo estado (ef, repeticoes, intervalo, lapsos) depois de uma revisão."""


@dataclass(frozen=True)
class SM2Scheduler:
    name: str = "sm2-prova"
    quality: dict[str, int] = field(default_factory=lambda: {"esqueci": 1, "dificil": 3, "bom": 4, "facil": 5})

    def next_state(self, item: dict[str, Any], grade: str) -> dict[str, Any]:
        q = self.quality[grade]
        ef = float(item.get("ef", 2.5))
        repetitions = int(item.get("repeticoes", 0))
        interval = int(item.get("intervalo", 0))
        lapses = int(item.get("lapsos", 0))
        ef = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
        if q < 3:
            repetitions, interval, lapses = 0, 1, lapses + 1
        else:
            repetitions += 1
            interval = 1 if repetitions == 1 else 6 if repetitions == 2 else max(1, round(interval * ef))
        return {"ef": round(ef, 3), "repeticoes": repetitions, "intervalo": interval, "lapsos": lapses}


@dataclass(frozen=True)
class FixedLadderScheduler:
    """Escada fixa (como no formato antigo). Útil para migração e como dublê nos testes."""

    name: str = "escada-fixa"
    steps: tuple[int, ...] = (1, 2, 4, 7)

    def next_state(self, item: dict[str, Any], grade: str) -> dict[str, Any]:
        repetitions = int(item.get("repeticoes", 0))
        lapses = int(item.get("lapsos", 0))
        if grade == "esqueci":
            return {"ef": item.get("ef", 2.5), "repeticoes": 0, "intervalo": self.steps[0], "lapsos": lapses + 1}
        repetitions += 1
        interval = self.steps[min(repetitions, len(self.steps) - 1)]
        return {"ef": item.get("ef", 2.5), "repeticoes": repetitions, "intervalo": interval, "lapsos": lapses}


SCHEDULERS: dict[str, Scheduler] = {"sm2-prova": SM2Scheduler(), "escada-fixa": FixedLadderScheduler()}


def schedule_date(
    interval: int, today: date, exam: date | None, fraction: float, repetitions: int = 0,
) -> date | None:
    """Próxima revisão respeitando a prova. None = não cabe outra revisão antes dela."""
    if exam is None or exam <= today:
        return today + timedelta(days=max(1, interval))
    eve = exam - timedelta(days=1)
    if eve <= today:
        return None
    days_left = (exam - today).days
    floor = ESTABLISHED_MIN_INTERVAL if repetitions >= 2 else 1
    interval = min(max(1, interval), max(floor, int(fraction * days_left)))
    return min(today + timedelta(days=interval), eve)


# ---------------------------------------------------------------- dados


def _settings(materia: dict[str, Any]) -> tuple[Scheduler, date | None, float, int]:
    config = materia.get("revisao") or {}
    name = config.get("algoritmo", "sm2-prova")
    if name not in SCHEDULERS:
        raise TutorError("algoritmo_desconhecido", f"Algoritmo de revisão desconhecido: {name!r}.")
    exam = parse_date((materia.get("prova") or {}).get("data"))
    fraction = float(config.get("fracao_max_intervalo", DEFAULT_INTERVAL_FRACTION))
    limit = int(config.get("max_por_dia", DEFAULT_DAILY_LIMIT))
    return SCHEDULERS[name], exam, fraction, limit


def load_items(paths: SubjectPaths) -> list[dict[str, Any]]:
    data = read_json(paths.revisoes, {}) or {}
    return list(data.get("itens", []))


def save_items(paths: SubjectPaths, items: list[dict[str, Any]]) -> None:
    write_json(paths.revisoes, {"schema_version": SCHEMA_VERSION, "itens": items})


def is_due(item: dict[str, Any], today: date, exam: date | None) -> bool:
    next_date = parse_date(item.get("proxima"))
    if next_date is None:
        return exam is None or exam <= today  # depois da prova, volta a revisar
    return next_date <= today


def triage(items: list[dict[str, Any]], today: date, exam: date | None) -> list[dict[str, Any]]:
    """Vencidos em ordem de urgência: mais lapsos, mais atrasados (relativo ao intervalo), mais difíceis."""
    due = [item for item in items if is_due(item, today, exam)]

    def urgency(item: dict[str, Any]) -> tuple:
        next_date = parse_date(item.get("proxima")) or today
        overdue = (today - next_date).days / max(1, int(item.get("intervalo", 1)))
        return (-int(item.get("lapsos", 0)), -overdue, float(item.get("ef", 2.5)), item["conceito"])

    return sorted(due, key=urgency)


def schedule(paths: SubjectPaths, concept_ids: list[str], today: date) -> dict[str, list[str]]:
    materia = load_materia(paths)
    _, exam, fraction, _ = _settings(materia)
    kmap = load_map(paths, required=False)
    items = load_items(paths)
    known = {item["conceito"] for item in items}
    added, existing = [], []
    for cid in concept_ids:
        if kmap is not None and cid not in kmap.concepts:
            raise TutorError("conceito_inexistente", f"Conceito {cid!r} não existe no mapa.")
        if cid in known:
            existing.append(cid)
            continue
        next_date = schedule_date(1, today, exam, fraction)
        items.append(
            {
                "conceito": cid,
                "nome": kmap.concepts[cid].name if kmap else cid,
                "ef": 2.5, "repeticoes": 0, "intervalo": 0, "lapsos": 0,
                "proxima": next_date.isoformat() if next_date else None,
                "ultima": None, "criado_em": today.isoformat(), "historico": [],
            }
        )
        known.add(cid)
        added.append(cid)
    save_items(paths, items)
    return {"agendados": added, "ja_existiam": existing}


def review(paths: SubjectPaths, concept_id: str, grade: str, today: date) -> dict[str, Any]:
    if grade not in GRADES:
        raise TutorError("nota_invalida", f"A nota deve ser uma de: {', '.join(GRADES)}.")
    materia = load_materia(paths)
    scheduler, exam, fraction, _ = _settings(materia)
    items = load_items(paths)
    item = next((i for i in items if i["conceito"] == concept_id), None)
    if item is None:
        raise TutorError(
            "conceito_nao_agendado", f"O conceito {concept_id!r} não está na agenda.",
            "Agende com `revisao agendar` (conceitos aprendidos entram na agenda no fim da sessão).",
        )
    item.update(scheduler.next_state(item, grade))
    next_date = schedule_date(int(item["intervalo"]), today, exam, fraction, int(item["repeticoes"]))
    item["proxima"] = next_date.isoformat() if next_date else None
    item["ultima"] = today.isoformat()
    item.setdefault("historico", []).append({"em": today.isoformat(), "nota": grade, "intervalo": item["intervalo"]})
    save_items(paths, items)
    return {
        "conceito": concept_id,
        "nota": grade,
        "proxima": item["proxima"],
        "lapsos": item["lapsos"],
        "concluido_ate_a_prova": next_date is None,
    }


def due_today(paths: SubjectPaths, today: date) -> dict[str, Any]:
    materia = load_materia(paths)
    _, exam, _, limit = _settings(materia)
    ordered = triage(load_items(paths), today, exam)
    return {
        "hoje": [
            {"conceito": i["conceito"], "nome": i.get("nome", i["conceito"]), "lapsos": i.get("lapsos", 0),
             "dias_de_atraso": (today - (parse_date(i.get("proxima")) or today)).days}
            for i in ordered[:limit]
        ],
        "excedentes": max(0, len(ordered) - limit),
        "limite_diario": limit,
        "dias_ate_prova": (exam - today).days if exam else None,
    }


def balance(due_counts: dict[str, int], days_to_exam: dict[str, int | None], total: int) -> dict[str, int]:
    """Divide o orçamento diário entre matérias: um mínimo para cada uma, o resto por urgência."""
    allocation = {s: min(n, MIN_PER_SUBJECT) for s, n in due_counts.items()}
    left = total - sum(allocation.values())
    if left <= 0:
        return allocation
    urgency = {
        s: (1.0 / max(days_to_exam[s], 1) if days_to_exam.get(s) is not None and days_to_exam[s] >= 0 else 1 / 60)
        * max(due_counts[s] - allocation[s], 0)
        for s in due_counts
    }
    weight_sum = sum(urgency.values())
    if weight_sum == 0:
        return allocation
    shares = {s: left * u / weight_sum for s, u in urgency.items()}
    extra = {s: min(int(shares[s]), due_counts[s] - allocation[s]) for s in due_counts}
    remainder = left - sum(extra.values())
    for s in sorted(due_counts, key=lambda s: -(shares[s] - int(shares[s]))):
        if remainder <= 0:
            break
        if allocation[s] + extra[s] < due_counts[s]:
            extra[s] += 1
            remainder -= 1
    return {s: allocation[s] + extra[s] for s in due_counts}


# ---------------------------------------------------------------- subcomandos


def cmd_list(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    today = ctx.clock.today()
    if not args.todas:
        paths = resolve_subject(ctx, args.materia)
        result = due_today(paths, today)
        return {
            "status": "ok",
            "materia": paths.slug,
            **result,
            "llm_directive": (
                "Faça as revisões ANTES de conteúdo novo, na ordem dada: peça que o aluno explique cada conceito de "
                "memória (recordação livre), sem consultar. Depois registre com `revisao registrar --nota "
                "esqueci|dificil|bom|facil`."
                if result["hoje"] else "Nenhuma revisão vencida hoje. Siga com o plano."
            ),
        }
    base = ctx.workspace.subjects
    per_subject: dict[str, dict[str, Any]] = {}
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        if not folder.is_dir() or not is_valid_slug(folder.name) or not (folder / "materia.json").is_file():
            continue
        try:
            per_subject[folder.name] = due_today(SubjectPaths(folder), today)
        except TutorError:
            continue
    prefs = read_json(base / "preferencias.json", {}) or {}
    total = int(prefs.get("max_revisoes_dia_total", DEFAULT_TOTAL_LIMIT))
    counts = {s: len(r["hoje"]) for s, r in per_subject.items()}
    allocation = balance(counts, {s: r["dias_ate_prova"] for s, r in per_subject.items()}, total)
    return {
        "status": "ok",
        "orcamento_total": total,
        "materias": {
            s: {"hoje": r["hoje"][: allocation.get(s, 0)], "adiadas": counts[s] - allocation.get(s, 0) + r["excedentes"],
                "dias_ate_prova": r["dias_ate_prova"]}
            for s, r in per_subject.items()
        },
        "llm_directive": "Mostre quantas revisões cabem hoje em cada matéria; comece pela matéria com prova mais próxima.",
    }


def cmd_review(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    result = review(paths, args.conceito, args.nota, ctx.clock.today())
    directive = (
        "Esqueceu: explique de novo de forma breve (com uma pergunta antes da resposta) e peça que o aluno reformule."
        if args.nota == "esqueci" else "Registrado. Siga para a próxima revisão."
    )
    return {"status": "ok", **result, "llm_directive": directive}


def cmd_schedule(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    result = schedule(paths, args.conceito, ctx.clock.today())
    return {"status": "ok", **result, "llm_directive": "Conceitos na agenda de revisão (o primeiro retorno é amanhã)."}


def add_commands(sub: argparse._SubParsersAction) -> None:
    group = sub.add_parser("revisao", help="revisões espaçadas dos conceitos (limitadas pela prova)")
    actions = group.add_subparsers(dest="acao", metavar="<acao>", required=True, parser_class=type(group))

    p = actions.add_parser("listar", help="revisões vencidas hoje (com limite diário)")
    p.add_argument("--materia")
    p.add_argument("--todas", action="store_true", help="todas as matérias, dividindo o orçamento diário")
    p.set_defaults(handler=cmd_list)

    p = actions.add_parser("registrar", help="resultado de uma revisão: esqueci, dificil, bom ou facil")
    p.add_argument("--materia")
    p.add_argument("--conceito", required=True)
    p.add_argument("--nota", required=True, choices=GRADES)
    p.set_defaults(handler=cmd_review)

    p = actions.add_parser("agendar", help="coloca conceitos aprendidos na agenda (idempotente)")
    p.add_argument("--materia")
    p.add_argument("--conceito", required=True, action="append", help="id do conceito (pode repetir)")
    p.set_defaults(handler=cmd_schedule)
