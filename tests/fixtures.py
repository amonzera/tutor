"""Matéria sintética para os testes: mapa com 4 conceitos e banco importado pelo fluxo real."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from tutor.bank import compare_verification, import_draft, record_verification
from tutor.core import SCHEMA_VERSION, SubjectPaths, mark_step, write_json

CONCEPTS = [
    {"id": "espaco-amostral", "nome": "Espaço amostral", "tema": "fundamentos", "peso": 2, "prerequisitos": []},
    {"id": "prob-classica", "nome": "Probabilidade clássica", "tema": "fundamentos", "peso": 3,
     "prerequisitos": ["espaco-amostral"]},
    {"id": "prob-condicional", "nome": "Probabilidade condicional", "tema": "condicional", "peso": 3,
     "prerequisitos": ["prob-classica"]},
    {"id": "bayes", "nome": "Teorema de Bayes", "tema": "condicional", "peso": 2,
     "prerequisitos": ["prob-condicional"]},
]

# (conceito, resposta correta) de cada questão de múltipla escolha, na ordem dos ids gerados
MC_QUESTIONS = [
    ("espaco-amostral", "B"), ("espaco-amostral", "D"), ("prob-classica", "C"), ("prob-classica", "A"),
    ("prob-condicional", "E"), ("prob-condicional", "B"), ("bayes", "C"), ("bayes", "D"),
]


def materia(exam: str | None = "2026-03-30", **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "slug": "prob", "nome": "Probabilidade", "objetivo": "passar na prova",
        "nivel": "iniciante", "idioma": "pt-BR", "tempo_diario_min": 40, "dias_por_semana": 7,
        "prova": {"data": exam, "data_confirmada": exam is not None, "formato": "multipla-escolha",
                  "duracao_min": 80, "n_questoes": 8, "n_alternativas": 5},
        "revisao": {"algoritmo": "sm2-prova", "max_por_dia": 15, "fracao_max_intervalo": 0.5},
        "etapas": {s: "ok" for s in ("inventario", "perguntas", "ingestao", "mapa", "plano", "banco", "contrato")},
        **extra,
    }


def mc_draft_item(concept: str, answer: str, number: int, **extra: Any) -> dict[str, Any]:
    alternatives = {k: f"Alternativa {k} da questão {number}" for k in "ABCDE"}
    return {
        "enunciado": f"Enunciado fictício número {number} sobre {concept}.",
        "alternativas": alternatives,
        "conceitos": [concept],
        "gabarito": {
            "resposta": answer,
            "conceito_decisivo": f"conceito decisivo {number}",
            "solucao": f"solução comentada {number}",
            "distratores": {k: f"equívoco típico {k} ({number})" for k in "ABCDE" if k != answer},
        },
        **extra,
    }


def build_subject(subjects_dir: Path, now: datetime, slug: str = "prob", verify: bool = True,
                  exam: str | None = "2026-03-30", extra_questions: list[dict[str, Any]] | None = None) -> SubjectPaths:
    folder = subjects_dir / slug
    (folder / "fontes").mkdir(parents=True)
    (folder / "fontes" / "apostila.md").write_text("# Apostila\n## Seção\nTexto fictício.\n", encoding="utf-8")
    paths = SubjectPaths(folder)
    write_json(paths.materia, {**materia(exam), "slug": slug})
    concepts = [{**c, "fontes": [{"arquivo": "apostila.md", "local": "seção 1"}]} for c in CONCEPTS]
    write_json(paths.mapa, {"schema_version": SCHEMA_VERSION, "materia": slug, "conceitos": concepts})
    items = [mc_draft_item(c, a, i + 1) for i, (c, a) in enumerate(MC_QUESTIONS)] + (extra_questions or [])
    paths.rascunhos.mkdir(parents=True)
    write_json(paths.rascunhos / "lote-01.json", {"schema_version": SCHEMA_VERSION, "lote": "lote-01", "questoes": items})
    import_draft(paths, paths.rascunhos / "lote-01.json", now)
    if verify:
        for index, (_, answer) in enumerate(MC_QUESTIONS, start=1):
            record_verification(paths, f"{_prefix(slug)}-{index:03d}", answer, 4, False, None, None, now)
        compare_verification(paths, now)
        if not extra_questions:
            mark_step(paths, "banco", True)  # como o `validar` faria numa matéria pronta
    return paths


def _prefix(slug: str) -> str:
    parts = slug.split("-")
    return "".join(p[0] for p in parts) if len(parts) > 1 else slug[:3]


def qid(index: int, slug: str = "prob") -> str:
    return f"{_prefix(slug)}-{index:03d}"


def answer_of(index: int) -> str:
    return MC_QUESTIONS[index - 1][1]


def wrong_of(index: int) -> str:
    return next(k for k in "ABCDE" if k != answer_of(index))
