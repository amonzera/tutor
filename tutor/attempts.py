"""Tentativas: o compromisso do aluno vem antes da correção, por construção.

Máquina de estados de uma questão:
  apresentar  -> abre a tentativa (marca o horário; o tema continua oculto)
  corrigir    -> exige resposta (ou "não sei"), confiança e nº de dicas; grava e só então revela
  classificar -> tipo de erro, depois de conversar com o aluno
  avaliar     -> nota de questão aberta, depois da rubrica

`tentativas.jsonl` é só de acréscimo: cada tentativa tem um número sequencial (`seq`);
classificações e avaliações viram registros novos que apontam para ele (`ref_seq`).

No simulado, as respostas ficam em `simulado-atual.json` (retomável) e a correção
só acontece no `simulado encerrar`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from tutor.bank import check_answer, load_bank, load_key, normalize_letter, public_view
from tutor.core import (
    SCHEMA_VERSION,
    Context,
    SubjectPaths,
    TutorError,
    append_jsonl,
    load_materia,
    read_json,
    read_jsonl,
    resolve_subject,
    write_json,
)
from tutor.knowledge_map import load_map

ERROR_TYPES = ("conceito", "metodo", "sinal", "conta", "chute")
PRACTICE_MODES = ("treino", "quiz", "revisao", "diagnostico")
GRADES = {"certo": 1.0, "parcial": 0.5, "errado": 0.0}
MAX_HINTS = 4
REVEAL_WINDOW = timedelta(hours=24)
REPEAT_WINDOW = timedelta(minutes=10)
MAX_SECONDS = 3 * 3600


@dataclass
class Attempt:
    """Tentativa já com classificação e avaliação aplicadas."""

    seq: int
    id: str
    at: datetime
    mode: str
    answer: Any
    dont_know: bool
    confidence: int
    hints: int
    seconds: int | None
    correct: bool | None
    after_reveal: bool
    error_type: str | None = None
    grade: str | None = None

    @property
    def score(self) -> float | None:
        """1 certo, 0 errado, 0,5 parcial (aberta); None se ainda não avaliada."""
        if self.grade is not None:
            return GRADES[self.grade]
        if self.correct is None:
            return None
        return 1.0 if self.correct else 0.0

    @property
    def independent_score(self) -> float | None:
        """Acerto sem ajuda decisiva: com 3 ou mais dicas (primeiro passo ou solução) conta como erro."""
        score = self.score
        if score is None:
            return None
        return 0.0 if self.hints >= 3 else score


def history(paths: SubjectPaths) -> list[Attempt]:
    attempts: dict[int, Attempt] = {}
    for record in read_jsonl(paths.tentativas):
        kind = record.get("tipo")
        if kind == "tentativa":
            seq = int(record.get("seq") or len(attempts) + 1)
            attempts[seq] = Attempt(
                seq=seq,
                id=record["id"],
                at=datetime.fromisoformat(record["em"]),
                mode=record.get("modo", "treino"),
                answer=record.get("resposta"),
                dont_know=bool(record.get("nao_sei")),
                confidence=int(record.get("confianca", 3)),
                hints=int(record.get("dicas", 0)),
                seconds=record.get("segundos"),
                correct=record.get("correta"),
                after_reveal=bool(record.get("apos_revelacao")),
                error_type=record.get("tipo_erro"),
            )
        elif kind in ("classificacao", "avaliacao"):
            target = attempts.get(int(record.get("ref_seq") or 0))
            if target is None or target.id != record.get("id"):
                continue
            if record.get("tipo_erro"):
                target.error_type = record["tipo_erro"]
            if kind == "avaliacao":
                target.grade = record["nota"]
                target.correct = record["nota"] == "certo"
    return [attempts[seq] for seq in sorted(attempts)]


def _next_seq(paths: SubjectPaths) -> int:
    return 1 + max((int(r.get("seq") or 0) for r in read_jsonl(paths.tentativas) if r.get("tipo") == "tentativa"), default=0)


def pending(attempts: list[Attempt]) -> dict[str, list[str]]:
    """Erros sem classificação e abertas sem avaliação (o `contexto` cobra na sessão seguinte)."""
    classify = sorted({a.id for a in attempts if a.correct is False and a.error_type is None and not a.dont_know})
    grade = sorted({a.id for a in attempts if a.correct is None and a.grade is None})
    return {"classificar": classify, "avaliar": grade}


# ---------------------------------------------------------------- estado da sessão


def _session(paths: SubjectPaths) -> dict[str, Any]:
    data = read_json(paths.sessao, {}) or {}
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("abertas", {})
    return data


def _active_exam(paths: SubjectPaths) -> dict[str, Any] | None:
    return read_json(paths.simulado)


def present(paths: SubjectPaths, qid: str, mode: str, now: datetime) -> dict[str, Any]:
    questions = load_bank(paths)
    question = questions.get(qid)
    if question is None:
        raise TutorError("questao_inexistente", f"Questão {qid!r} não existe no banco.")
    if question.get("verificacao") == "divergente":
        raise TutorError(
            "questao_fora_de_uso",
            f"A questão {qid} está fora de uso (o verificador chegou a outra resposta).",
            "Escolha outra questão com `proximas`.",
        )
    exam = _active_exam(paths)
    if exam is not None and qid in exam.get("questoes", []):
        mode = "simulado"
    elif mode == "simulado":
        raise TutorError("fora_do_simulado", f"A questão {qid} não faz parte do simulado em andamento.")
    if mode != "simulado":
        session = _session(paths)
        session["abertas"][qid] = {"em": now.isoformat(), "modo": mode}
        write_json(paths.sessao, session)
    view = public_view(question)
    out: dict[str, Any] = {"status": "ok", "modo": mode, "questao": view}
    if question.get("verificacao") in ("pendente", "aviso"):
        out["verificacao"] = question["verificacao"]
        out["aviso"] = question.get("aviso") or "Questão ainda não verificada de forma independente."
    if mode == "simulado":
        out["llm_directive"] = (
            "Simulado: mostre só o enunciado e as alternativas. Peça a resposta e a confiança (1 a 5) e registre "
            "com `simulado responder`. Não comente se está certo, não dê dicas."
        )
    else:
        out["llm_directive"] = (
            "Mostre o enunciado e as alternativas em texto (descreva a figura, se houver; nunca imagem de página "
            "de prova). Não revele tema nem conceito. Peça a resposta E a confiança (1 a 5) antes de qualquer ajuda. "
            "Se o aluno não souber, suba UM degrau da escada de dicas por vez (conceito, ferramenta, primeiro passo, "
            "solução) e conte as dicas dadas. Corrija com `corrigir`."
            + (" Avise que a questão ainda não foi verificada." if "verificacao" in out else "")
        )
    return out


def _alert(correct: bool | None, confidence: int) -> str | None:
    if correct is False and confidence >= 4:
        return "errou com confiança alta: provável concepção errada, prioridade máxima"
    if correct is True and confidence <= 2:
        return "acertou com confiança baixa: peça o porquê para consolidar"
    return None


def _result_payload(
    paths: SubjectPaths, question: dict[str, Any], entry: dict[str, Any], verdict: dict[str, Any],
    confidence: int, repeated: bool = False,
) -> dict[str, Any]:
    kmap = load_map(paths, required=False)
    names = [kmap.concepts[c].name if kmap and c in kmap.concepts else c for c in question.get("conceitos", [])]
    out: dict[str, Any] = {
        "status": "ok",
        "questao": question["id"],
        "correta": verdict["correta"],
        "resposta_aluno": verdict.get("resposta_aluno"),
        "resposta_correta": verdict.get("resposta_correta"),
        "conceito_decisivo": entry.get("conceito_decisivo"),
        "solucao": entry.get("solucao"),
        "conceitos": names,
        "tema": question.get("tema"),
    }
    if verdict.get("por_que_tentadora"):
        out["por_que_tentadora"] = verdict["por_que_tentadora"]
    if verdict.get("rubrica"):
        out["rubrica"] = verdict["rubrica"]
    if question.get("verificacao") != "verificada":
        out["verificacao"] = question.get("verificacao", "pendente")
    alert = _alert(verdict["correta"], confidence)
    if alert:
        out["alerta"] = alert
    if repeated:
        out["repetida"] = True
    if verdict["correta"] is None:
        out["pendente"] = "avaliar"
        out["llm_directive"] = (
            "Questão aberta: compare a resposta do aluno com a rubrica (ou chame o agente corretor), explique o que "
            "faltou e registre com `avaliar --nota certo|parcial|errado`."
        )
    elif verdict["correta"]:
        out["llm_directive"] = (
            "Acertou. Peça que explique por que as outras alternativas falham (ou o raciocínio, se não houver "
            "alternativas). Feedback sobre o processo, não sobre a pessoa."
        )
    else:
        out["pendente"] = "classificar"
        out["llm_directive"] = (
            "Errou. Antes de explicar, pergunte o que ele pensou. Use `por_que_tentadora` para tratar o distrator "
            "escolhido, depois a solução. Classifique o erro com `classificar` (conceito, metodo, sinal, conta ou chute)."
        )
    return out


def check(
    paths: SubjectPaths, qid: str, answer: str | None, confidence: int, hints: int,
    seconds: int | None, now: datetime,
) -> dict[str, Any]:
    if not 1 <= confidence <= 5:
        raise TutorError("confianca_invalida", "A confiança deve ser de 1 a 5.", "Pergunte a confiança ao aluno.")
    if not 0 <= hints <= MAX_HINTS:
        raise TutorError("dicas_invalidas", f"O número de dicas vai de 0 a {MAX_HINTS}.")
    exam = _active_exam(paths)
    if exam is not None and qid in exam.get("questoes", []):
        raise TutorError(
            "questao_de_simulado",
            "Esta questão está no simulado em andamento.",
            "Registre com `simulado responder`; a correção sai no `simulado encerrar`.",
        )
    questions = load_bank(paths)
    question = questions.get(qid)
    if question is None:
        raise TutorError("questao_inexistente", f"Questão {qid!r} não existe no banco.")
    entry = load_key(paths).get(qid)
    if entry is None:
        raise TutorError("sem_gabarito", f"A questão {qid} não tem gabarito.", "Escolha outra questão.")
    session = _session(paths)
    opened = session["abertas"].get(qid)
    previous = [a for a in history(paths) if a.id == qid]
    if opened is None:
        last = previous[-1] if previous else None
        if (
            last is not None and now - last.at <= REPEAT_WINDOW
            and last.confidence == confidence and last.dont_know == (answer is None)
        ):
            verdict = check_answer(question, entry, None if last.dont_know else str(answer))
            if verdict.get("resposta_aluno") == last.answer:
                return _result_payload(paths, question, entry, verdict, confidence, repeated=True)
        raise TutorError(
            "questao_nao_apresentada",
            f"A questão {qid} não foi apresentada nesta sessão.",
            "Apresente com `apresentar` (o aluno precisa ver o enunciado e se comprometer) e só depois corrija.",
        )
    verdict = check_answer(question, entry, answer)
    opened_at = datetime.fromisoformat(opened["em"])
    if seconds is None:
        seconds = int(min(max((now - opened_at).total_seconds(), 0), MAX_SECONDS))
    after_reveal = any(now - a.at <= REVEAL_WINDOW for a in previous)
    append_jsonl(
        paths.tentativas,
        {
            "v": SCHEMA_VERSION,
            "tipo": "tentativa",
            "seq": _next_seq(paths),
            "id": qid,
            "em": now.isoformat(),
            "apresentada_em": opened["em"],
            "modo": opened.get("modo", "treino"),
            "resposta": verdict.get("resposta_aluno"),
            "nao_sei": answer is None,
            "confianca": confidence,
            "dicas": hints,
            "segundos": seconds,
            "correta": verdict["correta"],
            "apos_revelacao": after_reveal,
        },
    )
    del session["abertas"][qid]
    write_json(paths.sessao, session)
    payload = _result_payload(paths, question, entry, verdict, confidence)
    if answer is None:
        payload.pop("pendente", None)
    if after_reveal:
        payload["apos_revelacao"] = True
    return payload


def _latest(attempts: list[Attempt], qid: str, predicate) -> Attempt | None:
    for attempt in reversed(attempts):
        if attempt.id == qid and predicate(attempt):
            return attempt
    return None


def classify(paths: SubjectPaths, qid: str, error_type: str, now: datetime) -> dict[str, Any]:
    materia = load_materia(paths)
    allowed = list(ERROR_TYPES) + [str(t) for t in materia.get("tipos_erro_extra", [])]
    if error_type not in allowed:
        raise TutorError("tipo_erro_invalido", f"Tipo de erro deve ser um de: {', '.join(allowed)}.")
    target = _latest(history(paths), qid, lambda a: a.correct is False)
    if target is None:
        raise TutorError("nada_a_classificar", f"Não há erro registrado na questão {qid}.")
    append_jsonl(
        paths.tentativas,
        {"v": SCHEMA_VERSION, "tipo": "classificacao", "id": qid, "ref_seq": target.seq,
         "tipo_erro": error_type, "em": now.isoformat()},
    )
    return {"status": "ok", "questao": qid, "tipo_erro": error_type,
            "llm_directive": "Erro classificado. Siga para a próxima questão ou feche a sessão com checkpoint."}


def grade(paths: SubjectPaths, qid: str, mark: str, error_type: str | None, now: datetime) -> dict[str, Any]:
    if mark not in GRADES:
        raise TutorError("nota_invalida", "A nota deve ser certo, parcial ou errado.")
    target = _latest(history(paths), qid, lambda a: a.correct is None and a.grade is None)
    if target is None:
        raise TutorError("nada_a_avaliar", f"Não há resposta aberta aguardando avaliação na questão {qid}.")
    if mark != "certo" and error_type is not None and error_type not in ERROR_TYPES:
        materia = load_materia(paths)
        if error_type not in materia.get("tipos_erro_extra", []):
            raise TutorError("tipo_erro_invalido", f"Tipo de erro deve ser um de: {', '.join(ERROR_TYPES)}.")
    append_jsonl(
        paths.tentativas,
        {"v": SCHEMA_VERSION, "tipo": "avaliacao", "id": qid, "ref_seq": target.seq, "nota": mark,
         "tipo_erro": error_type if mark != "certo" else None, "em": now.isoformat()},
    )
    return {"status": "ok", "questao": qid, "nota": mark, "llm_directive": "Avaliação registrada."}


# ---------------------------------------------------------------- simulado


def start_exam(
    paths: SubjectPaths, ids: list[str], limit_minutes: int, forecast: dict[str, Any] | None, now: datetime,
) -> dict[str, Any]:
    if _active_exam(paths) is not None:
        raise TutorError(
            "simulado_em_andamento", "Já existe um simulado em andamento.",
            "Use `simulado estado` para retomar ou `simulado encerrar` para corrigir.",
        )
    exam = {
        "schema_version": SCHEMA_VERSION,
        "iniciado_em": now.isoformat(),
        "limite_min": limit_minutes,
        "questoes": ids,
        "respostas": {},
        "previsao": forecast,
    }
    write_json(paths.simulado, exam)
    return exam


def exam_status(paths: SubjectPaths, now: datetime) -> dict[str, Any]:
    exam = _active_exam(paths)
    if exam is None:
        raise TutorError("sem_simulado", "Não há simulado em andamento.", "Inicie com `simulado iniciar`.")
    elapsed = int((now - datetime.fromisoformat(exam["iniciado_em"])).total_seconds() // 60)
    answered = exam.get("respostas", {})
    remaining = [qid for qid in exam["questoes"] if qid not in answered]
    return {
        "status": "ok",
        "decorrido_min": elapsed,
        "limite_min": exam["limite_min"],
        "tempo_esgotado": elapsed >= exam["limite_min"],
        "respondidas": len(answered),
        "total": len(exam["questoes"]),
        "proxima": remaining[0] if remaining else None,
        "faltam": remaining,
        "llm_directive": (
            "Continue o simulado pela próxima questão, sem feedback. Se o tempo acabou ou todas foram respondidas, "
            "rode `simulado encerrar`."
        ),
    }


def answer_exam(
    paths: SubjectPaths, qid: str, answer: str | None, confidence: int, seconds: int | None, now: datetime,
    replace: bool = False,
) -> dict[str, Any]:
    exam = _active_exam(paths)
    if exam is None:
        raise TutorError("sem_simulado", "Não há simulado em andamento.")
    if qid not in exam["questoes"]:
        raise TutorError("fora_do_simulado", f"A questão {qid} não faz parte do simulado.")
    if not 1 <= confidence <= 5:
        raise TutorError("confianca_invalida", "A confiança deve ser de 1 a 5.")
    if qid in exam["respostas"] and not replace:
        raise TutorError("ja_respondida", f"A questão {qid} já foi respondida (use --substituir para trocar).")
    question = load_bank(paths)[qid]
    if answer is not None and question.get("tipo", "multipla-escolha") == "multipla-escolha":
        answer = normalize_letter(answer, sorted(question.get("alternativas") or {}))
    exam["respostas"][qid] = {"resposta": answer, "confianca": confidence, "segundos": seconds, "em": now.isoformat()}
    write_json(paths.simulado, exam)
    status = exam_status(paths, now)
    status["llm_directive"] = "Resposta guardada sem correção. " + status["llm_directive"]
    return status


def finish_exam(paths: SubjectPaths, now: datetime) -> dict[str, Any]:
    exam = _active_exam(paths)
    if exam is None:
        raise TutorError("sem_simulado", "Não há simulado em andamento.")
    questions = load_bank(paths)
    key = load_key(paths)
    previous = history(paths)
    rows = []
    total = 0.0
    for qid in exam["questoes"]:
        question, entry = questions.get(qid), key.get(qid)
        if question is None or entry is None:
            continue
        given = exam["respostas"].get(qid)
        answer = given.get("resposta") if given else None
        verdict = check_answer(question, entry, answer)
        confidence = int(given["confianca"]) if given else 1
        when = given["em"] if given else now.isoformat()
        after_reveal = any(a.id == qid and datetime.fromisoformat(when) - a.at <= REVEAL_WINDOW for a in previous)
        append_jsonl(
            paths.tentativas,
            {
                "v": SCHEMA_VERSION, "tipo": "tentativa", "seq": _next_seq(paths), "id": qid, "em": when, "modo": "simulado",
                "resposta": verdict.get("resposta_aluno"), "nao_sei": given is None or answer is None,
                "confianca": confidence, "dicas": 0, "segundos": given.get("segundos") if given else None,
                "correta": verdict["correta"], "apos_revelacao": after_reveal,
            },
        )
        if verdict["correta"]:
            total += 1
        rows.append(
            {
                "questao": qid,
                "em_branco": given is None,
                "resposta_aluno": verdict.get("resposta_aluno"),
                "resposta_correta": verdict.get("resposta_correta"),
                "correta": verdict["correta"],
                "confianca": confidence if given else None,
                "tema": question.get("tema"),
                "conceito_decisivo": entry.get("conceito_decisivo"),
                "por_que_tentadora": verdict.get("por_que_tentadora"),
            }
        )
    started = datetime.fromisoformat(exam["iniciado_em"])
    result = {
        "em": now.isoformat(),
        "iniciado_em": exam["iniciado_em"],
        "duracao_min": int((now - started).total_seconds() // 60),
        "limite_min": exam["limite_min"],
        "acertos": total,
        "total": len(rows),
        "previsao": exam.get("previsao"),
    }
    append_jsonl(paths.simulados, {"v": SCHEMA_VERSION, **result})
    paths.simulado.unlink()
    high_confidence_errors = [r["questao"] for r in rows if r["correta"] is False and (r["confianca"] or 0) >= 4]
    return {
        "status": "ok",
        **result,
        "questoes": rows,
        "erros_com_confianca_alta": high_confidence_errors,
        "llm_directive": (
            "Agora sim, corrija: mostre a nota, o tempo, os erros por tema e os erros com confiança alta. Para cada "
            "erro, pergunte o que o aluno pensou e classifique com `classificar`. Compare com a previsão (se houver) "
            "sem prometer nota na prova. Monte uma lista de reforço de 3 a 5 conceitos."
        ),
    }


# ---------------------------------------------------------------- subcomandos


def _answer_arg(args: argparse.Namespace) -> str | None:
    if args.nao_sei:
        return None
    if args.resposta is None:
        raise TutorError(
            "sem_resposta", "Informe --resposta ou --nao-sei.",
            "O aluno precisa se comprometer com uma resposta (ou dizer que não sabe) antes da correção.",
        )
    return args.resposta


def cmd_present(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    return present(paths, args.questao, args.modo, ctx.clock.now())


def cmd_check(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    return check(paths, args.questao, _answer_arg(args), args.confianca, args.dicas, args.segundos, ctx.clock.now())


def cmd_classify(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    return classify(paths, args.questao, args.tipo, ctx.clock.now())


def cmd_grade(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    paths = resolve_subject(ctx, args.materia)
    return grade(paths, args.questao, args.nota, args.tipo_erro, ctx.clock.now())


def add_answer_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--resposta", help="resposta do aluno: letra, número ou texto")
    parser.add_argument("--nao-sei", action="store_true", help="o aluno desistiu (revela a solução)")
    parser.add_argument("--confianca", type=int, required=True, help="confiança do aluno, de 1 a 5")
    parser.add_argument("--segundos", type=int, help="tempo gasto (padrão: desde o apresentar)")


def add_commands(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("apresentar", help="mostra a questão em texto e abre a tentativa (tema oculto)")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.add_argument("--modo", choices=PRACTICE_MODES + ("simulado",), default="treino")
    p.set_defaults(handler=cmd_present)

    p = sub.add_parser("corrigir", help="registra a resposta e a confiança do aluno e só então revela")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    add_answer_args(p)
    p.add_argument("--dicas", type=int, default=0, help=f"degraus da escada de dicas usados (0 a {MAX_HINTS})")
    p.set_defaults(handler=cmd_check)

    p = sub.add_parser("classificar", help="registra o tipo do último erro numa questão")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.add_argument("--tipo", required=True, help=f"{', '.join(ERROR_TYPES)} ou tipo extra da matéria")
    p.set_defaults(handler=cmd_classify)

    p = sub.add_parser("avaliar", help="nota de uma questão aberta depois da rubrica")
    p.add_argument("--materia")
    p.add_argument("--questao", required=True)
    p.add_argument("--nota", required=True, choices=tuple(GRADES))
    p.add_argument("--tipo-erro")
    p.set_defaults(handler=cmd_grade)
