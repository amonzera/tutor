"""Modelo do aluno: domínio por conceito, calibração e preparo estimado.

Domínio = probabilidade de acertar uma questão nova do conceito, estimada por uma
Beta-Bernoulli: cada tentativa soma acerto/erro com peso que cai pela metade a
cada `meia_vida_dias` (evidência antiga vale menos). O piso é a chance de acerto
no chute (1/nº de alternativas). Escolha deliberadamente simples: com poucas
tentativas por aluno, modelos com muitos parâmetros só repetiriam os valores
iniciais. Todos os limiares abaixo são heurísticos e ajustáveis em `materia.json`
(chave `modelo_aluno`); nenhum vem de estudo específico.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tutor.attempts import Attempt
from tutor.knowledge_map import KnowledgeMap

CONFIDENCE_PROBABILITY = {1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 0.95}
DEFAULT_PARAMS = {
    "meia_vida_dias": 21.0,
    "limiar_dominado": 0.85,
    "limiar_inferior_dominado": 0.7,
    "evidencia_minima_dominado": 3.0,
    "limiar_fraco": 0.6,
    "cobertura_minima_preparo": 0.5,
    "tentativas_para_cobertura": 2,
}
SAMPLES = 2000


def params_from(materia: dict[str, Any] | None) -> dict[str, float]:
    params = dict(DEFAULT_PARAMS)
    overrides = (materia or {}).get("modelo_aluno") or {}
    for key, value in overrides.items():
        if key in params and isinstance(value, (int, float)) and not isinstance(value, bool):
            params[key] = float(value)
    return params


def guess_probability(question: dict[str, Any]) -> float:
    alternatives = question.get("alternativas") or {}
    if question.get("tipo", "multipla-escolha") == "multipla-escolha" and alternatives:
        return 1.0 / len(alternatives)
    return 0.0


@dataclass(frozen=True)
class ConceptEstimate:
    id: str
    name: str
    theme: str
    weight: float
    attempts: int
    evidence: float
    mean: float
    low: float
    high: float
    status: str
    last_seen: str | None
    alpha: float
    beta: float
    guess: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "conceito": self.id,
            "nome": self.name,
            "tema": self.theme,
            "peso": round(self.weight, 3),
            "tentativas": self.attempts,
            "p_acerto": round(self.mean, 2),
            "faixa_80": [round(self.low, 2), round(self.high, 2)],
            "estado": self.status,
            "ultima_vez": self.last_seen,
        }


def _seed(*parts: Any) -> int:
    text = "|".join(str(p) for p in parts)
    return sum((i + 1) * ord(ch) for i, ch in enumerate(text)) % (2**31)


def estimate_concepts(
    kmap: KnowledgeMap, questions: dict[str, dict[str, Any]], attempts: list[Attempt],
    now: datetime, params: dict[str, float],
) -> dict[str, ConceptEstimate]:
    half_life = max(params["meia_vida_dias"], 0.1)
    weights = kmap.weights()
    alpha = defaultdict(lambda: 1.0)
    beta = defaultdict(lambda: 1.0)
    evidence: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    last_seen: dict[str, datetime] = {}
    guesses: dict[str, list[float]] = defaultdict(list)
    for qid, question in questions.items():
        for cid in question.get("conceitos", []):
            guesses[cid].append(guess_probability(question))
    for attempt in attempts:
        question = questions.get(attempt.id)
        score = attempt.independent_score
        if question is None or score is None or attempt.after_reveal:
            continue
        age_days = max((now - attempt.at).total_seconds() / 86400.0, 0.0)
        weight = 0.5 ** (age_days / half_life)
        for cid in question.get("conceitos", []):
            alpha[cid] += weight * score
            beta[cid] += weight * (1.0 - score)
            evidence[cid] += weight
            counts[cid] += 1
            if cid not in last_seen or attempt.at > last_seen[cid]:
                last_seen[cid] = attempt.at
    estimates = {}
    for cid, concept in kmap.concepts.items():
        a, b = alpha[cid], beta[cid]
        guess = min(guesses[cid]) if guesses[cid] else 0.0
        rng = random.Random(_seed(cid, round(a, 6), round(b, 6)))
        samples = sorted(max(guess, rng.betavariate(a, b)) for _ in range(SAMPLES))
        mean = max(guess, a / (a + b))
        low, high = samples[int(0.1 * SAMPLES)], samples[int(0.9 * SAMPLES) - 1]
        if counts[cid] == 0:
            status = "sem_dados"
        elif mean < params["limiar_fraco"]:
            status = "fraco"
        elif (
            mean >= params["limiar_dominado"] and low >= params["limiar_inferior_dominado"]
            and evidence[cid] >= params["evidencia_minima_dominado"]
        ):
            status = "dominado"
        else:
            status = "em_progresso"
        estimates[cid] = ConceptEstimate(
            id=cid, name=concept.name, theme=concept.theme, weight=weights[cid], attempts=counts[cid],
            evidence=evidence[cid], mean=mean, low=low, high=high, status=status,
            last_seen=last_seen[cid].date().isoformat() if cid in last_seen else None,
            alpha=a, beta=b, guess=guess,
        )
    return estimates


def calibration(attempts: list[Attempt]) -> dict[str, Any]:
    """Só tentativas comprometidas antes de qualquer dica e sem revelação recente."""
    pool = [a for a in attempts if not a.after_reveal and a.hints == 0 and not a.dont_know and a.score is not None]
    if not pool:
        return {"n": 0, "leitura": "sem dados"}
    probabilities = [CONFIDENCE_PROBABILITY.get(a.confidence, 0.6) for a in pool]
    scores = [float(a.score) for a in pool]
    brier = statistics.fmean((p - s) ** 2 for p, s in zip(probabilities, scores))
    bias = statistics.fmean(probabilities) - statistics.fmean(scores)
    table = []
    for level in range(1, 6):
        rows = [s for a, s in zip(pool, scores) if a.confidence == level]
        if rows:
            table.append(
                {"confianca": level, "n": len(rows), "acerto": round(statistics.fmean(rows), 2),
                 "esperado": CONFIDENCE_PROBABILITY[level]}
            )
    if len(pool) < 10:
        reading = "poucos dados (menos de 10 respostas)"
    elif bias > 0.1:
        reading = "superconfiante: a confiança costuma passar do acerto"
    elif bias < -0.1:
        reading = "subconfiante: acerta mais do que acha"
    else:
        reading = "calibrado"
    return {
        "n": len(pool),
        "brier": round(brier, 3),
        "vies": round(bias, 3),
        "leitura": reading,
        "por_confianca": table,
        "erros_com_confianca_alta": sum(1 for a, s in zip(pool, scores) if s == 0 and a.confidence >= 4),
        "acertos_com_confianca_baixa": sum(1 for a, s in zip(pool, scores) if s == 1 and a.confidence <= 2),
    }


def readiness(
    estimates: dict[str, ConceptEstimate], n_questions: int, params: dict[str, float], seed: Any = "preparo",
) -> dict[str, Any]:
    """Distribuição da nota num simulado de `n_questions` questões, com a incerteza declarada."""
    if not estimates or n_questions <= 0:
        return {"disponivel": False, "motivo": "sem conceitos ou sem número de questões da prova"}
    needed = int(params["tentativas_para_cobertura"])
    coverage = sum(e.weight for e in estimates.values() if e.attempts >= needed)
    if coverage < params["cobertura_minima_preparo"]:
        missing = sorted((e for e in estimates.values() if e.attempts < needed), key=lambda e: -e.weight)
        return {
            "disponivel": False,
            "cobertura": round(coverage, 2),
            "motivo": f"poucos dados: só {round(100 * coverage)}% do conteúdo (por peso) tem {needed}+ tentativas",
            "praticar_primeiro": [e.name for e in missing[:5]],
        }
    rng = random.Random(_seed(seed, n_questions, *(round(e.alpha, 4) for e in estimates.values())))
    ids = list(estimates)
    weights = [estimates[c].weight for c in ids]
    scores = []
    for _ in range(SAMPLES):
        theta = {c: max(estimates[c].guess, rng.betavariate(estimates[c].alpha, estimates[c].beta)) for c in ids}
        drawn = rng.choices(ids, weights=weights, k=n_questions)
        scores.append(sum(1 for c in drawn if rng.random() < theta[c]))
    scores.sort()
    p10, p50, p90 = scores[int(0.1 * SAMPLES)], scores[SAMPLES // 2], scores[int(0.9 * SAMPLES) - 1]
    return {
        "disponivel": True,
        "questoes": n_questions,
        "mediana": p50,
        "faixa_80": [p10, p90],
        "cobertura": round(coverage, 2),
        "aviso": (
            "Estimativa grosseira a partir das suas tentativas, supondo uma prova parecida com o banco. "
            "Não é previsão de nota."
        ),
    }
