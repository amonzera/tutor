"""Mapa de conhecimento: conceitos, pré-requisitos, pesos e onde cada um aparece nas fontes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tutor.core import SLUG_PATTERN, SubjectPaths, TutorError, check_schema, read_json

ORIGINS = ("fontes", "conhecimento-geral")


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    theme: str
    weight: float
    prerequisites: tuple[str, ...]
    origin: str
    misconceptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KnowledgeMap:
    concepts: dict[str, Concept]

    def topological_order(self) -> list[str]:
        """Pré-requisitos antes; entre independentes, maior peso primeiro (estável por id)."""
        order: list[str] = []
        done: set[str] = set()
        pending = sorted(self.concepts.values(), key=lambda c: (-c.weight, c.id))
        while pending:
            ready = [c for c in pending if all(p in done for p in c.prerequisites)]
            if not ready:  # só acontece com ciclo, que validate() já recusa
                ready = pending[:1]
            for concept in ready:
                order.append(concept.id)
                done.add(concept.id)
            pending = [c for c in pending if c.id not in done]
        return order

    def trail_order(self, difficulty: dict[str, float] | None = None, practicable: set[str] | None = None) -> list[str]:
        """Ordem da trilha: pré-requisitos antes; entre os conceitos prontos, a maior prioridade primeiro.

        A prioridade efetiva de um conceito é o maior peso entre ele e tudo o que ele libera, para que um
        pré-requisito leve de um conceito pesado não fique para o fim. Desempates: peso próprio, conceitos com
        questões antes dos sem questões, o mais difícil antes e, por fim, o id.
        """
        difficulty = difficulty or {}
        effective = {cid: c.weight for cid, c in self.concepts.items()}
        dependents: dict[str, list[str]] = {cid: [] for cid in self.concepts}
        for concept in self.concepts.values():
            for prereq in concept.prerequisites:
                if prereq in dependents:
                    dependents[prereq].append(concept.id)
        for cid in reversed(self.topological_order()):
            for child in dependents[cid]:
                effective[cid] = max(effective[cid], effective[child])

        def key(c: Concept) -> tuple:
            without_questions = practicable is not None and c.id not in practicable
            return (-effective[c.id], -c.weight, without_questions, -difficulty.get(c.id, 2.0), c.id)

        order: list[str] = []
        placed: set[str] = set()
        remaining = dict(self.concepts)
        while remaining:
            ready = [c for c in remaining.values()
                     if all(p in placed or p not in self.concepts for p in c.prerequisites)]
            best = min(ready or remaining.values(), key=key)  # sem prontos só com ciclo, que validate() recusa
            order.append(best.id)
            placed.add(best.id)
            del remaining[best.id]
        return order

    def roots(self) -> list[str]:
        return [cid for cid in self.topological_order() if not self.concepts[cid].prerequisites]

    def weights(self) -> dict[str, float]:
        total = sum(c.weight for c in self.concepts.values()) or 1.0
        return {cid: c.weight / total for cid, c in self.concepts.items()}


def validate_map_data(data: Any, paths: SubjectPaths) -> list[str]:
    """Problemas do mapa, em português. Lista vazia = válido."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["o mapa deve ser um objeto JSON"]
    concepts = data.get("conceitos")
    if not isinstance(concepts, list) or not concepts:
        return ["'conceitos' deve ser uma lista não vazia"]
    ids: list[str] = []
    for index, item in enumerate(concepts, start=1):
        where = f"conceito {index}"
        if not isinstance(item, dict):
            problems.append(f"{where}: deve ser um objeto")
            continue
        cid = item.get("id")
        if not isinstance(cid, str) or not SLUG_PATTERN.fullmatch(cid):
            problems.append(f"{where}: id inválido {cid!r} (use minúsculas sem acento e hífens)")
        else:
            where = f"conceito {cid}"
            ids.append(cid)
        if not str(item.get("nome") or "").strip():
            problems.append(f"{where}: falta 'nome'")
        if not str(item.get("tema") or "").strip():
            problems.append(f"{where}: falta 'tema'")
        weight = item.get("peso", 1)
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not 1 <= weight <= 5:
            problems.append(f"{where}: 'peso' deve ser número de 1 a 5")
        origin = item.get("origem", "fontes")
        if origin not in ORIGINS:
            problems.append(f"{where}: 'origem' deve ser {' ou '.join(ORIGINS)}")
        sources = item.get("fontes") or []
        if origin == "fontes":
            if not sources:
                problems.append(f"{where}: origem 'fontes' exige ao menos uma referência em 'fontes'")
            for ref in sources:
                name = ref.get("arquivo") if isinstance(ref, dict) else None
                if not name:
                    problems.append(f"{where}: referência sem 'arquivo'")
                elif not (paths.fontes / name).is_file():
                    problems.append(f"{where}: arquivo de fonte inexistente: {name}")
        if not isinstance(item.get("prerequisitos", []), list):
            problems.append(f"{where}: 'prerequisitos' deve ser uma lista")
    duplicated = sorted({cid for cid in ids if ids.count(cid) > 1})
    if duplicated:
        problems.append(f"ids repetidos: {', '.join(duplicated)}")
    known = set(ids)
    graph = {
        item["id"]: [p for p in item.get("prerequisitos", []) if isinstance(p, str)]
        for item in concepts
        if isinstance(item, dict) and item.get("id") in known
    }
    for cid, prereqs in graph.items():
        for prereq in prereqs:
            if prereq not in known:
                problems.append(f"conceito {cid}: pré-requisito inexistente {prereq!r}")
            elif prereq == cid:
                problems.append(f"conceito {cid}: não pode ser pré-requisito de si mesmo")
    cycle = _find_cycle(graph)
    if cycle:
        problems.append("ciclo de pré-requisitos: " + " -> ".join(cycle))
    return problems


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if state.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for start in sorted(graph):
        if state.get(start) is None:
            found = visit(start)
            if found:
                return found
    return None


def load_map(paths: SubjectPaths, required: bool = True) -> KnowledgeMap | None:
    data = read_json(paths.mapa)
    if data is None:
        if required:
            raise TutorError(
                "sem_mapa",
                "A matéria ainda não tem mapa-conhecimento.json.",
                f"Rode /nova-materia {paths.slug} para gerar o mapa.",
            )
        return None
    check_schema(data, paths.mapa)
    problems = validate_map_data(data, paths)
    if problems:
        raise TutorError(
            "mapa_invalido",
            "mapa-conhecimento.json tem problemas.",
            "Corrija os problemas listados (ou peça ao ingestor para regenerar o mapa) e valide de novo.",
            problemas=problems,
        )
    concepts = {}
    for item in data["conceitos"]:
        concepts[item["id"]] = Concept(
            id=item["id"],
            name=item["nome"],
            theme=item["tema"],
            weight=float(item.get("peso", 1)),
            prerequisites=tuple(item.get("prerequisitos", [])),
            origin=item.get("origem", "fontes"),
            misconceptions=tuple(item.get("equivocos", [])),
        )
    return KnowledgeMap(concepts)
