"""Banco de questões (sem respostas) e gabarito (protegido), importação e verificação cega.

- `questoes.json`: enunciado, alternativas, conceitos, tema, status de verificação.
- `gabarito.json`: resposta, conceito decisivo, solução e por que cada distrator é
  tentador. Gravado codificado (veja `core.write_protected`); só o motor o lê.
- Rascunhos (`banco/rascunhos/<lote>.json`) trazem questão e gabarito juntos; o
  `banco importar` separa os dois e apaga o rascunho.
- O verificador resolve às cegas e grava cada resposta com `banco registrar-verificacao`;
  `banco comparar` confronta com o gabarito e escreve `verificacao.md` sem letras.
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from tutor.core import (
    SCHEMA_VERSION,
    Context,
    SubjectPaths,
    TutorError,
    check_schema,
    ensure_inside,
    load_materia,
    mark_step,
    read_json,
    read_protected,
    resolve_subject,
    write_json,
    write_protected,
    write_text,
)
from tutor.knowledge_map import KnowledgeMap, load_map

QUESTION_TYPES = ("multipla-escolha", "numerica", "aberta")
VERIFICATION_STATES = ("pendente", "verificada", "divergente", "aviso")
VERIFIER_ALERTS = ("ambigua", "sem-resposta", "enunciado-defeituoso", "depende-de-figura")
ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LETTER_KEYS = "ABCDEFGHIJ"
FORBIDDEN_KEYS = ("resposta", "gabarito", "correta", "solucao", "distratores", "answer")
LEAK_MARKERS = re.compile(
    r"(gabarito|resposta\s+correta|alternativa\s+correta|\(\s*correta\s*\)|\bcorreta\s*:|(?<![A-Za-z0-9$\\])\[x\]|\u2713|\u2714)",
    re.IGNORECASE,
)
DEFAULT_REL_TOLERANCE = 0.01


# ---------------------------------------------------------------- leitura


def load_bank(paths: SubjectPaths, required: bool = True) -> dict[str, dict[str, Any]]:
    data = read_json(paths.questoes)
    if data is None:
        if required:
            raise TutorError(
                "sem_banco", "A matéria ainda não tem banco de questões.",
                f"O banco é criado pelo /nova-materia {paths.slug} (etapa banco).",
            )
        return {}
    check_schema(data, paths.questoes)
    return {q["id"]: q for q in data.get("questoes", []) if isinstance(q, dict) and "id" in q}


def save_bank(paths: SubjectPaths, questions: dict[str, dict[str, Any]], removed: list[str] | None = None) -> None:
    previous = read_json(paths.questoes) or {}
    removed_ids = sorted(set(previous.get("ids_removidos", [])) | set(removed or []))
    data: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "materia": paths.slug, "questoes": list(questions.values())}
    if removed_ids:
        data["ids_removidos"] = removed_ids
    write_json(paths.questoes, data)


def load_key(paths: SubjectPaths) -> dict[str, dict[str, Any]]:
    payload = read_protected(paths.gabarito, {"respostas": {}})
    return dict(payload.get("respostas", {}))


def save_key(paths: SubjectPaths, answers: dict[str, dict[str, Any]]) -> None:
    write_protected(paths.gabarito, paths.slug, {"respostas": answers})


def public_view(question: dict[str, Any]) -> dict[str, Any]:
    """O que o aluno pode ver antes de responder: sem tema, conceitos nem origem."""
    view: dict[str, Any] = {"id": question["id"], "tipo": question.get("tipo", "multipla-escolha")}
    if question.get("contexto_compartilhado"):
        view["contexto_compartilhado"] = question["contexto_compartilhado"]
    view["enunciado"] = question["enunciado"]
    if question.get("alternativas"):
        view["alternativas"] = question["alternativas"]
    if question.get("unidade"):
        view["unidade"] = question["unidade"]
    figure = question.get("figura")
    if isinstance(figure, dict) and figure.get("descricao"):
        view["figura"] = figure["descricao"]
    return view


# ---------------------------------------------------------------- conferência de respostas


def normalize_letter(raw: str, valid: list[str]) -> str:
    text = raw.strip().upper()
    text = re.sub(r"^(LETRA|ALTERNATIVA|OP[CÇ][AÃ]O)\s+", "", text)
    text = text.strip("()[]{}.:) ")
    if text in valid:
        return text
    raise TutorError(
        "resposta_invalida",
        f"Resposta {raw!r} não é uma das alternativas ({', '.join(valid)}).",
        "Peça ao aluno a letra de uma das alternativas e tente de novo.",
    )


NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?", re.IGNORECASE)


def parse_number(raw: str) -> float:
    """Aceita 0,25 · 0.25 · 1/4 · 25% · -1,5e-3 (com ou sem unidade depois)."""
    text = raw.strip().replace("−", "-").replace(" ", "")
    percent = text.endswith("%")
    text = text.rstrip("%")
    fraction = re.fullmatch(r"([-+]?\d+(?:[.,]\d+)?)/(\d+(?:[.,]\d+)?)", text)
    try:
        if fraction:
            value = float(fraction.group(1).replace(",", ".")) / float(fraction.group(2).replace(",", "."))
        else:
            match = NUMBER.match(text)
            if not match:
                raise ValueError(raw)
            value = float(match.group(0).replace(",", "."))
    except (ValueError, ZeroDivisionError) as exc:
        raise TutorError(
            "resposta_invalida", f"Não entendi o número {raw!r}.",
            "Peça ao aluno o valor numérico (ex.: 0,25 ou 1/4) e tente de novo.",
        ) from exc
    return value / 100 if percent else value


def check_answer(question: dict[str, Any], entry: dict[str, Any], answer: str | None) -> dict[str, Any]:
    """Compara a resposta do aluno com o gabarito. `answer=None` significa "não sei"."""
    kind = question.get("tipo", "multipla-escolha")
    result: dict[str, Any] = {"tipo": kind}
    if kind == "multipla-escolha":
        valid = sorted((question.get("alternativas") or {}).keys())
        correct_letter = entry["resposta"]
        result["resposta_correta"] = correct_letter
        if answer is None:
            result.update(resposta_aluno=None, correta=False)
            return result
        letter = normalize_letter(answer, valid)
        result.update(resposta_aluno=letter, correta=letter == correct_letter)
        if letter != correct_letter:
            result["por_que_tentadora"] = (entry.get("distratores") or {}).get(letter)
        return result
    if kind == "numerica":
        spec = entry["resposta"]
        expected = float(spec["valor"])
        result["resposta_correta"] = spec["valor"]
        if spec.get("unidade") or question.get("unidade"):
            result["unidade"] = spec.get("unidade") or question.get("unidade")
        if answer is None:
            result.update(resposta_aluno=None, correta=False)
            return result
        value = parse_number(answer)
        tolerance = max(
            float(spec.get("tolerancia_abs") or 0.0),
            float(spec.get("tolerancia_rel", DEFAULT_REL_TOLERANCE)) * abs(expected),
            1e-12,
        )
        result.update(resposta_aluno=value, correta=abs(value - expected) <= tolerance)
        if not result["correta"]:
            for known in entry.get("erros_comuns") or []:
                if abs(value - float(known["valor"])) <= tolerance:
                    result["por_que_tentadora"] = known.get("explicacao")
                    break
        return result
    # aberta: o motor não corrige; devolve a rubrica para o tutor (ou o corretor) avaliar
    result.update(resposta_aluno=answer, correta=None if answer is not None else False, rubrica=entry.get("rubrica") or [])
    return result


# ---------------------------------------------------------------- validação


CONTROL_CHARS = re.compile(r"[\x00-\x09\x0b-\x1f]")
DISPLAY_MATH = re.compile(r"\$\$.*?\$\$", re.DOTALL)
INLINE_MATH = re.compile(r"\$[^$]*\$")


def _latex_problems(where: str, text: Any) -> list[str]:
    """LaTeX com barra invertida simples no JSON vira caractere de controle sem erro: \\frac, \\theta, \\beta, \\nu..."""
    if not isinstance(text, str):
        return []
    if CONTROL_CHARS.search(text):
        return [f"{where}: caractere de controle ou tabulação no texto (LaTeX no JSON precisa de barra dupla: \\\\frac)"]
    inline = INLINE_MATH.findall(DISPLAY_MATH.sub("", text.replace("R$", "")))
    if any("\n" in segment for segment in inline):
        return [f"{where}: quebra de linha dentro de $...$ (LaTeX no JSON precisa de barra dupla: \\\\nu)"]
    return []


def _lint_text(where: str, text: Any) -> list[str]:
    problems = _latex_problems(where, text)
    if isinstance(text, str) and LEAK_MARKERS.search(text):
        problems.append(f"{where}: possível marca de resposta no texto ({LEAK_MARKERS.search(text).group(0)!r})")
    return problems


def validate_question(q: dict[str, Any], kmap: KnowledgeMap | None, where: str) -> list[str]:
    problems: list[str] = []
    qid = q.get("id")
    if qid is not None and (not isinstance(qid, str) or not ID_PATTERN.fullmatch(qid)):
        problems.append(f"{where}: id inválido {qid!r}")
    kind = q.get("tipo", "multipla-escolha")
    if kind not in QUESTION_TYPES:
        problems.append(f"{where}: tipo deve ser um de {', '.join(QUESTION_TYPES)}")
    if not str(q.get("enunciado") or "").strip():
        problems.append(f"{where}: falta enunciado")
    alternatives = q.get("alternativas")
    if kind == "multipla-escolha":
        if not isinstance(alternatives, dict) or len(alternatives) < 2:
            problems.append(f"{where}: múltipla escolha precisa de ao menos 2 alternativas")
        else:
            keys = list(alternatives)
            if keys != list(LETTER_KEYS[: len(keys)]):
                problems.append(f"{where}: alternativas devem ser A, B, C... em ordem")
            for key, text in alternatives.items():
                if not str(text or "").strip():
                    problems.append(f"{where}: alternativa {key} vazia")
                problems += _lint_text(f"{where}, alternativa {key}", text)
    elif alternatives:
        problems.append(f"{where}: só múltipla escolha tem alternativas")
    for key in FORBIDDEN_KEYS:
        if key in q:
            problems.append(f"{where}: o banco não pode ter o campo {key!r} (resposta vai no gabarito)")
    concepts = q.get("conceitos")
    if not isinstance(concepts, list) or not concepts:
        problems.append(f"{where}: 'conceitos' deve listar ao menos um conceito do mapa")
    elif kmap is not None:
        for cid in concepts:
            if cid not in kmap.concepts:
                problems.append(f"{where}: conceito inexistente no mapa: {cid!r}")
    difficulty = q.get("dificuldade", 2)
    if difficulty not in (1, 2, 3):
        problems.append(f"{where}: 'dificuldade' deve ser 1, 2 ou 3")
    if q.get("verificacao", "pendente") not in VERIFICATION_STATES:
        problems.append(f"{where}: 'verificacao' deve ser um de {', '.join(VERIFICATION_STATES)}")
    figure = q.get("figura")
    if figure is not None:
        if not isinstance(figure, dict) or not str(figure.get("descricao") or "").strip():
            problems.append(f"{where}: 'figura' precisa de 'descricao' em texto")
        else:
            problems += _lint_text(f"{where}, figura", figure.get("descricao"))
    problems += _lint_text(f"{where}, enunciado", q.get("enunciado"))
    problems += _lint_text(f"{where}, contexto", q.get("contexto_compartilhado"))
    return problems


def validate_entry(q: dict[str, Any], entry: Any, where: str) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{where}: gabarito ausente"]
    problems: list[str] = []
    kind = q.get("tipo", "multipla-escolha")
    answer = entry.get("resposta")
    if kind == "multipla-escolha":
        letters = list((q.get("alternativas") or {}).keys())
        if answer not in letters:
            problems.append(f"{where}: a resposta precisa ser exatamente uma das alternativas")
        else:
            wrong = [k for k in letters if k != answer]
            distractors = entry.get("distratores") or {}
            missing = [k for k in wrong if not str(distractors.get(k) or "").strip()]
            if missing:
                problems.append(f"{where}: explique por que cada alternativa errada é tentadora (faltam {', '.join(missing)})")
            if answer in distractors:
                problems.append(f"{where}: a alternativa correta não pode estar em 'distratores'")
    elif kind == "numerica":
        if not isinstance(answer, dict) or not isinstance(answer.get("valor"), (int, float)):
            problems.append(f"{where}: resposta numérica precisa de {{'valor': número}}")
    elif not entry.get("rubrica"):
        problems.append(f"{where}: questão aberta precisa de 'rubrica' (lista de critérios)")
    for field in ("conceito_decisivo", "solucao"):
        if not str(entry.get(field) or "").strip():
            problems.append(f"{where}: falta '{field}' no gabarito")
        problems += _latex_problems(f"{where}, {field}", entry.get(field))
    for key, text in (entry.get("distratores") or {}).items() if isinstance(entry.get("distratores"), dict) else ():
        problems += _latex_problems(f"{where}, distrator {key}", text)
    return problems


def validate_bank(paths: SubjectPaths, kmap: KnowledgeMap | None) -> list[str]:
    questions = load_bank(paths)
    key = load_key(paths)
    problems: list[str] = []
    for qid, question in questions.items():
        problems += validate_question(question, kmap, f"questão {qid}")
        problems += validate_entry(question, key.get(qid), f"gabarito de {qid}")
    extra = sorted(set(key) - set(questions))
    if extra:
        problems.append(f"gabarito com ids que não existem no banco: {', '.join(extra)}")
    return problems


# ---------------------------------------------------------------- importação de rascunhos


def _id_prefix(slug: str) -> str:
    parts = [p for p in slug.split("-") if p]
    prefix = "".join(p[0] for p in parts) if len(parts) > 1 else slug[:3]
    return prefix or "q"


QUESTION_FIELDS = {
    "id", "tipo", "enunciado", "alternativas", "conceitos", "tema", "dificuldade", "unidade", "figura",
    "contexto_compartilhado", "origem",
}


def _removed_ids(paths: SubjectPaths) -> list[str]:
    data = read_json(paths.questoes) or {}
    return list(data.get("ids_removidos", []))


def _drop_verification(paths: SubjectPaths, qids: set[str]) -> None:
    """Questão trocada ou removida perde as rodadas antigas do verificador (não herda 'verificada')."""
    if not qids or not paths.verificacao.exists():
        return
    data = read_protected(paths.verificacao, {"rodadas": []})
    data["rodadas"] = [r for r in data.get("rodadas", []) if r.get("id") not in qids]
    write_protected(paths.verificacao, paths.slug, data)


def _next_id(prefix: str, taken: set[str]) -> str:
    numbers = [int(m.group(1)) for qid in taken if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", qid))]
    number = max(numbers, default=0) + 1
    while f"{prefix}-{number:03d}" in taken:
        number += 1
    return f"{prefix}-{number:03d}"


def import_draft(paths: SubjectPaths, draft: Path, now: datetime, replace: bool = False) -> dict[str, Any]:
    draft = ensure_inside(paths.rascunhos, draft if draft.is_absolute() else paths.root / draft)
    data = read_json(draft)
    if data is None:
        raise TutorError("rascunho_inexistente", f"Rascunho não encontrado: {draft.name}.")
    check_schema(data, draft)
    kmap = load_map(paths, required=False)
    questions = load_bank(paths, required=False)
    key = load_key(paths)
    batch = str(data.get("lote") or draft.stem)
    incoming = data.get("questoes")
    if not isinstance(incoming, list) or not incoming:
        raise TutorError("rascunho_vazio", "O rascunho não tem questões.")
    prefix = _id_prefix(paths.slug)
    taken = set(questions) | set(key) | set(_removed_ids(paths))
    problems: list[str] = []
    staged: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for index, raw in enumerate(incoming, start=1):
        if not isinstance(raw, dict):
            problems.append(f"questão {index} do rascunho: deve ser um objeto")
            continue
        item = dict(raw)
        entry = item.pop("gabarito", None)
        unknown = sorted(set(item) - QUESTION_FIELDS)
        if unknown:
            problems.append(
                f"questão {index}: campos não permitidos no banco ({', '.join(unknown)}); explicações e soluções vão no gabarito"
            )
        qid = item.get("id")
        if qid and qid in questions and not replace:
            problems.append(f"questão {index}: id {qid!r} já existe (use --substituir para trocar)")
            continue
        if not qid:
            qid = _next_id(prefix, taken)
            item["id"] = qid
        taken.add(qid)
        item.setdefault("tipo", "multipla-escolha")
        item.setdefault("dificuldade", 2)
        item.setdefault("origem", {"tipo": "gerada", "lote": batch})
        if not item.get("tema") and kmap is not None and item.get("conceitos"):
            first = kmap.concepts.get(item["conceitos"][0])
            if first is not None:
                item["tema"] = first.theme
        item["verificacao"] = "pendente"
        item.pop("aviso", None)
        where = f"questão {index} ({qid})"
        problems += validate_question(item, kmap, where)
        problems += validate_entry(item, entry, f"gabarito da {where}")
        staged.append((item, entry or {}))
    if problems:
        raise TutorError(
            "rascunho_invalido",
            f"O rascunho {draft.name} tem problemas; nada foi importado.",
            "Corrija o rascunho (sem copiar respostas para o banco) e importe de novo.",
            problemas=problems,
        )
    replaced = {item["id"] for item, _ in staged if item["id"] in questions}
    for item, entry in staged:
        questions[item["id"]] = item
        key[item["id"]] = entry
    save_bank(paths, questions)
    save_key(paths, key)
    _drop_verification(paths, replaced)
    for item, _ in staged:  # recorte antigo não vale para o texto novo; recortes vêm depois da importação
        (paths.figuras / f"{item['id']}.png").unlink(missing_ok=True)
    mark_step(paths, "banco", False)  # questões novas precisam de verificação antes de a etapa fechar
    draft.unlink()
    if paths.figuras_temp.is_dir():
        shutil.rmtree(paths.figuras_temp, ignore_errors=True)
    return {"importadas": [item["id"] for item, _ in staged], "lote": batch}


# ---------------------------------------------------------------- verificação cega


def record_verification(
    paths: SubjectPaths, qid: str, answer: str, confidence: int, saw_mark: bool,
    alert: str | None, notes: str | None, now: datetime,
) -> None:
    questions = load_bank(paths)
    if qid not in questions:
        raise TutorError("questao_inexistente", f"Questão {qid!r} não existe no banco.")
    if not 1 <= confidence <= 5:
        raise TutorError("confianca_invalida", "A confiança deve ser de 1 a 5.")
    if alert is not None and alert not in VERIFIER_ALERTS:
        raise TutorError("alerta_invalido", f"Alerta deve ser um de {', '.join(VERIFIER_ALERTS)}.")
    question = questions[qid]
    kind = question.get("tipo", "multipla-escolha")
    if kind == "multipla-escolha" and alert not in ("ambigua", "sem-resposta"):
        answer = normalize_letter(answer, sorted(question.get("alternativas") or {}))
    elif kind == "numerica" and alert is None:
        parse_number(answer)
    data = read_protected(paths.verificacao, {"rodadas": []})
    data.setdefault("rodadas", []).append(
        {
            "id": qid, "resposta": answer, "confianca": confidence, "viu_marca_oficial": saw_mark,
            "alerta": alert, "observacoes": notes or "", "em": now.isoformat(),
        }
    )
    write_protected(paths.verificacao, paths.slug, data)


def compare_verification(paths: SubjectPaths, now: datetime) -> dict[str, Any]:
    questions = load_bank(paths)
    key = load_key(paths)
    rounds = read_protected(paths.verificacao, {"rodadas": []}).get("rodadas", [])
    latest: dict[str, dict[str, Any]] = {}
    confirmations: dict[str, dict[str, Any]] = {}
    for record in rounds:
        if "confirmacao" in record:
            confirmations[record["id"]] = record
        else:
            latest[record["id"]] = record
    summary = {state: [] for state in VERIFICATION_STATES}
    rows = []
    for qid, question in questions.items():
        record = latest.get(qid)
        entry = key.get(qid)
        note = ""
        if question.get("tipo") == "aberta" and qid in confirmations and entry is not None:
            confirmed = confirmations[qid]["confirmacao"] == "certo"
            state = "verificada" if confirmed else "divergente"
            note = "" if confirmed else "resposta independente não atende à rubrica"
        elif record is None or entry is None:
            state = "pendente"
        elif record.get("alerta"):
            state, note = "aviso", f"verificador marcou: {record['alerta']}"
        else:
            try:
                verdict = check_answer(question, entry, str(record["resposta"]))
            except TutorError:
                verdict = {"correta": False, "ilegivel": True}
            if verdict.get("ilegivel"):
                state, note = "aviso", "resposta do verificador ilegível; verifique de novo"
            elif verdict["correta"] is None:
                state, note = "pendente", "questão aberta: conferir com `banco conferir-aberta` e `banco confirmar`"
            elif verdict["correta"]:
                state = "verificada" if int(record["confianca"]) >= 3 else "aviso"
                note = "" if state == "verificada" else "verificador concordou com baixa confiança"
            else:
                state, note = "divergente", "verificador chegou a outra resposta"
        if record is not None and record.get("viu_marca_oficial"):
            note = (note + "; " if note else "") + "verificador viu a marca oficial"
        question["verificacao"] = state
        if note and state != "verificada":
            question["aviso"] = note
        else:
            question.pop("aviso", None)
        summary[state].append(qid)
        rows.append((qid, state, note))
    save_bank(paths, questions)
    lines = [
        "# Verificação do banco",
        "",
        f"> Gerado por `banco comparar` em {now.strftime('%Y-%m-%d %H:%M')}. Sem letras de resposta, de propósito.",
        "",
        "`verificada` = um verificador independente chegou à mesma resposta sem ver o gabarito. "
        "Não é garantia de que a questão está certa.",
        "",
        "| Questão | Status | Observação |",
        "|---|---|---|",
    ]
    lines += [f"| {qid} | {state} | {note or '-'} |" for qid, state, note in rows]
    write_text(paths.verificacao_md, "\n".join(lines))
    return {state: ids for state, ids in summary.items()}


def _require_setup_phase(paths: SubjectPaths) -> None:
    """Conferir abertas revela a rubrica: só durante a preparação do banco, nunca numa sessão de estudo."""
    materia = read_json(paths.materia) or {}
    if (materia.get("etapas") or {}).get("banco") == "ok":
        raise TutorError(
            "fora_da_preparacao",
            "A conferência de questões abertas só acontece enquanto a etapa 'banco' está pendente.",
            "Isso faz parte do /nova-materia (ou da criação de questões novas), não da sessão de estudo.",
        )


def open_review(paths: SubjectPaths, qid: str) -> dict[str, Any]:
    """Para conferir uma questão aberta: rubrica, solução e a resposta independente do verificador."""
    _require_setup_phase(paths)
    question = load_bank(paths).get(qid)
    if question is None or question.get("tipo") != "aberta":
        raise TutorError("nao_e_aberta", f"{qid!r} não é uma questão aberta do banco.")
    entry = load_key(paths).get(qid) or {}
    rounds = read_protected(paths.verificacao, {"rodadas": []}).get("rodadas", [])
    answers = [r for r in rounds if r.get("id") == qid and "confirmacao" not in r]
    if not answers:
        raise TutorError("sem_verificacao", f"O verificador ainda não respondeu {qid}.")
    return {
        "questao": public_view(question),
        "rubrica": entry.get("rubrica") or [],
        "solucao": entry.get("solucao"),
        "resposta_verificador": answers[-1]["resposta"],
        "confianca_verificador": answers[-1]["confianca"],
    }


def confirm_open(paths: SubjectPaths, qid: str, mark: str, notes: str | None, now: datetime) -> None:
    if mark not in ("certo", "errado"):
        raise TutorError("nota_invalida", "Use certo ou errado.")
    open_review(paths, qid)  # valida que é aberta e que o verificador já respondeu
    data = read_protected(paths.verificacao, {"rodadas": []})
    data.setdefault("rodadas", []).append(
        {"id": qid, "confirmacao": mark, "observacoes": notes or "", "em": now.isoformat()}
    )
    write_protected(paths.verificacao, paths.slug, data)


# ---------------------------------------------------------------- subcomandos


def cmd_import(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    result = import_draft(paths, Path(args.arquivo), ctx.clock.now(), replace=args.substituir)
    return {
        "status": "ok",
        **result,
        "llm_directive": (
            "Questões importadas com verificação 'pendente'. Não repita respostas na conversa. "
            "Próximo passo: o verificador resolve cada uma às cegas e depois rode `banco comparar`."
        ),
    }


def cmd_record_verification(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    record_verification(
        paths, args.questao, args.resposta, args.confianca, args.viu_marca == "sim",
        args.alerta, args.obs, ctx.clock.now(),
    )
    return {
        "status": "ok",
        "questao": args.questao,
        "llm_directive": "Resposta registrada. Siga para a próxima questão; não diga se concordou com o gabarito (você não o conhece).",
    }


def cmd_compare(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    summary = compare_verification(paths, ctx.clock.now())
    return {
        "status": "ok",
        "resumo": {state: len(ids) for state, ids in summary.items()},
        "divergentes": summary["divergente"],
        "avisos": summary["aviso"],
        "pendentes": summary["pendente"],
        "llm_directive": (
            "Questões divergentes ficam fora de uso; avisos ficam fora do simulado. Relate os números ao "
            "aluno sem revelar respostas. Para divergentes, ofereça regenerar a questão ou removê-la."
        ),
    }


def cmd_open_review(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    return {
        "status": "ok",
        **open_review(paths, args.questao),
        "llm_directive": (
            "Só na preparação da matéria, nunca com o aluno presente: julgue se a resposta do verificador atende "
            "à rubrica (ou passe os três ao agente corretor) e registre com `banco confirmar --nota certo|errado`."
        ),
    }


def cmd_confirm(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    confirm_open(paths, args.questao, args.nota, args.obs, ctx.clock.now())
    return {"status": "ok", "questao": args.questao, "llm_directive": "Registrado. Rode `banco comparar` para atualizar os status."}


def cmd_remove(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    questions = load_bank(paths)
    if args.questao not in questions:
        raise TutorError("questao_inexistente", f"Questão {args.questao!r} não existe no banco.")
    key = load_key(paths)
    del questions[args.questao]
    key.pop(args.questao, None)
    save_bank(paths, questions, removed=[args.questao])
    save_key(paths, key)
    _drop_verification(paths, {args.questao})
    return {
        "status": "ok", "removida": args.questao,
        "llm_directive": "Questão removida do banco e do gabarito. O id não será reaproveitado.",
    }


def cmd_export(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    load_materia(paths)
    dest = Path(args.para).expanduser()
    if dest.exists() and not args.forcar:
        raise TutorError("destino_existe", f"{dest} já existe. Use --forcar para sobrescrever.")
    questions = load_bank(paths)
    key = load_key(paths)
    merged = [{**q, "gabarito": key.get(qid)} for qid, q in questions.items()]
    write_json(dest, {"schema_version": SCHEMA_VERSION, "materia": paths.slug, "questoes": merged})
    return {
        "status": "ok",
        "arquivo": str(dest),
        "llm_directive": "Este comando é para o aluno rodar no próprio terminal. Não leia o arquivo gerado.",
    }


def add_commands(sub: argparse._SubParsersAction) -> None:
    bank = sub.add_parser("banco", help="importa rascunhos, verifica às cegas, remove ou exporta questões")
    bank_sub = bank.add_subparsers(dest="acao", metavar="<acao>", required=True, parser_class=type(bank))

    p = bank_sub.add_parser("importar", help="separa um rascunho em banco + gabarito e apaga o rascunho")
    p.add_argument("--materia")
    p.add_argument("--arquivo", required=True, help="banco/rascunhos/<lote>.json")
    p.add_argument("--substituir", action="store_true", help="permite trocar questões com o mesmo id")
    p.set_defaults(handler=cmd_import)

    p = bank_sub.add_parser("registrar-verificacao", help="resposta do verificador para uma questão (às cegas)")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.add_argument("--resposta", required=True)
    p.add_argument("--confianca", type=int, required=True)
    p.add_argument("--viu-marca", choices=("sim", "nao"), default="nao", help="viu a marca oficial da resposta?")
    p.add_argument("--alerta", choices=VERIFIER_ALERTS)
    p.add_argument("--obs", help="observação curta, sem repetir o enunciado")
    p.set_defaults(handler=cmd_record_verification)

    p = bank_sub.add_parser("comparar", help="confronta o verificador com o gabarito e atualiza os status")
    p.add_argument("--materia")
    p.set_defaults(handler=cmd_compare)

    p = bank_sub.add_parser("conferir-aberta", help="rubrica e resposta do verificador de uma questão aberta (preparação)")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.set_defaults(handler=cmd_open_review)

    p = bank_sub.add_parser("confirmar", help="registra se a resposta independente de uma questão aberta atende à rubrica")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.add_argument("--nota", required=True, choices=("certo", "errado"))
    p.add_argument("--obs")
    p.set_defaults(handler=cmd_confirm)

    p = bank_sub.add_parser("remover", help="remove uma questão do banco e do gabarito")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.set_defaults(handler=cmd_remove)

    p = bank_sub.add_parser("exportar", help="gera cópia legível do gabarito (para o aluno, no terminal dele)")
    p.add_argument("--materia")
    p.add_argument("--para", required=True)
    p.add_argument("--forcar", action="store_true")
    p.set_defaults(handler=cmd_export)
