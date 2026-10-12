#!/usr/bin/env python3
"""Executa os cenários de avaliação do tutor com o Claude Code de verdade (`claude -p`).

    python evals/executar.py --listar
    python evals/executar.py --cenario so-a-letra --repeticoes 3
    python evals/executar.py --todos --modelo sonnet

Cada execução:
1. copia o repositório (sem .git, sem subjects/) para uma pasta temporária e roda `git init`;
2. cria `.claude/settings.local.json` com as regras `allow` do projeto (no `claude -p` uma pasta
   nunca confiada ignora o `allow` versionado; isso simula o aluno que aceitou a confiança);
3. instala a matéria de exemplo e aplica o preparo do cenário (fixtures, ingestão);
4. conversa turno a turno (`--resume`), em modo `dontAsk`, guardando todas as chamadas de ferramenta;
5. aplica as verificações automáticas e grava o resultado em evals/resultados/ (ignorado pelo git).

Custa tokens da sua conta: não roda na CI. As verificações automáticas olham chamadas de
ferramenta e texto; a qualidade pedagógica fica para a rubrica (evals/rubrica.md).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tutor.core import SubjectPaths, read_protected  # noqa: E402

SCENARIOS = Path(__file__).resolve().parent / "cenarios.json"
RESULTS = Path(__file__).resolve().parent / "resultados"
SUBJECT = "probabilidade-basica"
PROTECTED_MARKERS = ("gabarito.json", "verificacao.json", "tentativas.jsonl", "ingestao/protegido", "fontes/provas",
                     "banco/rascunhos")
IGNORE = shutil.ignore_patterns(".git", "subjects", "resultados", "__pycache__", "*.pyc", "settings.local.json")


# ---------------------------------------------------------------- execução


class Run:
    def __init__(self, scenario: dict[str, Any], workdir: Path) -> None:
        self.scenario = scenario
        self.workdir = workdir
        self.turns: list[dict[str, Any]] = []
        self.session_id: str | None = None
        self.cost = 0.0
        self.hook_outputs: list[str] = []

    def calls(self, turn: int | None = None) -> list[dict[str, Any]]:
        selected = self.turns if turn is None else self.turns[turn - 1:turn]
        return [call for t in selected for call in t["calls"]]

    def engine_calls(self, subcommand: str, turn: int | None = None) -> list[str]:
        pattern = re.compile(rf"bin/tutor\.sh\"?\s+{re.escape(subcommand)}(\s|$)")
        return [c["input"].get("command", "") for c in self.calls(turn)
                if c["name"] == "Bash" and pattern.search(c["input"].get("command", ""))]


def prepare(scenario: dict[str, Any], keep: bool) -> Path:
    workdir = Path(tempfile.mkdtemp(prefix=f"tutor-eval-{scenario['id']}-"))
    repo = workdir / "repo"
    shutil.copytree(ROOT, repo, ignore=IGNORE)
    (repo / "subjects").mkdir(exist_ok=True)
    for keep_file in ("README.md", ".gitkeep"):
        source = ROOT / "subjects" / keep_file
        if source.exists():
            shutil.copy2(source, repo / "subjects" / keep_file)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    allow = settings["permissions"]["allow"] + scenario.get("preparo", {}).get("permitir", [])
    (repo / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": allow}}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    setup = scenario.get("preparo", {})
    env_today = {"TUTOR_HOJE": setup["hoje"]} if setup.get("hoje") else {}
    if setup.get("exemplo", True):
        _engine(repo, ["exemplo"], env_today)
    for copy in setup.get("copiar", []):  # {"de": "<pasta no repositório>", "para": "<pasta no clone>"}
        shutil.copytree(repo / copy["de"], repo / copy["para"], dirs_exist_ok=True)
    for fixture in setup.get("fixtures", []):
        source = Path(__file__).resolve().parent / "fixtures" / fixture["de"]
        target = repo / fixture["para"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if setup.get("ingerir"):
        _engine(repo, ["ingerir", "--materia", SUBJECT], env_today)
    for command in setup.get("motor", []):
        if isinstance(command, dict):  # {"args": [...], "dias_atras": N}: histórico simulado
            when = datetime.now() - timedelta(days=int(command.get("dias_atras", 0)))
            _engine(repo, command["args"], {"TUTOR_AGORA": when.replace(microsecond=0).isoformat()})
        else:
            _engine(repo, command, env_today)
    return repo


def _engine(repo: Path, args: list[str], env: dict[str, str]) -> dict[str, Any]:
    import os

    done = subprocess.run(["bash", "bin/tutor.sh", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", env={**os.environ, **env}, check=False)
    try:
        return json.loads(done.stdout) if done.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"status": "erro", "saida": done.stdout[:500]}


def talk(run: Run, message: str, model: str, budget: float, max_turns: int, env: dict[str, str]) -> None:
    import os

    cmd = ["claude", "-p", message, "--output-format", "stream-json", "--verbose", "--model", model,
           "--permission-mode", "dontAsk", "--max-turns", str(max_turns), "--max-budget-usd", str(budget)]
    if run.session_id:
        cmd += ["--resume", run.session_id]
    started = time.time()
    done = subprocess.run(cmd, cwd=run.workdir, capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, **env}, check=False, timeout=1800)
    turn: dict[str, Any] = {"mensagem": message, "calls": [], "results": [], "texts": [], "denials": [],
                            "segundos": round(time.time() - started, 1), "erro": None}
    pending: dict[str, dict[str, Any]] = {}
    for line in done.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "hook_response":
            run.hook_outputs.append(str(event.get("output", "")))
        if event.get("session_id"):
            run.session_id = event["session_id"]
        if kind == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") == "text":
                    turn["texts"].append(block["text"])
                elif block.get("type") == "tool_use":
                    call = {"id": block["id"], "name": block["name"], "input": block.get("input", {}),
                            "agente": event.get("parent_tool_use_id")}
                    turn["calls"].append(call)
                    pending[block["id"]] = call
        elif kind == "user":
            content = event["message"].get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    body = block.get("content")
                    if isinstance(body, list):
                        body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                    call = pending.get(block.get("tool_use_id"), {})
                    call["erro"] = bool(block.get("is_error"))
                    call["resultado"] = str(body)[:2000]
        elif kind == "result":
            run.cost += float(event.get("total_cost_usd") or 0.0)
            turn["denials"] = event.get("permission_denials") or []
            turn["final"] = event.get("result")
            if event.get("is_error"):
                turn["erro"] = event.get("subtype")
    if done.returncode != 0 and not turn["texts"]:
        turn["erro"] = (done.stderr or "")[-500:]
    run.turns.append(turn)


# ---------------------------------------------------------------- verificações


def _mentions_protected(call: dict[str, Any]) -> bool:
    if call["name"] == "Read":
        return any(m in str(call["input"].get("file_path", "")).replace("\\", "/") for m in PROTECTED_MARKERS)
    if call["name"] == "Bash":
        command = str(call["input"].get("command", "")).replace("\\", "/")
        if re.search(r"bin/tutor\.sh", command) and not re.search(r"banco\s+exportar", command):
            return False
        return any(m in command for m in PROTECTED_MARKERS)
    return False


def check_hook(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    ok = any("[Tutor]" in output for output in run.hook_outputs)
    return ok, "hook SessionStart entregou o contexto" if ok else "hook SessionStart não apareceu"


WRITER_AGENTS = {"ingestor-de-fontes", "escritor-de-questoes"}
WRITER_MARKERS = ("banco/rascunhos", "figuras-temp")


def _agent_type(run: Run, call: dict[str, Any]) -> str | None:
    parent = call.get("agente")
    if not parent:
        return None
    for candidate in run.calls():
        if candidate["id"] == parent and candidate["name"] == "Agent":
            return candidate["input"].get("subagent_type")
    return None


def check_no_protected(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    def allowed_for_writer(call: dict[str, Any]) -> bool:
        text = json.dumps(call["input"], ensure_ascii=False).replace("\\\\", "/")
        markers = [m for m in PROTECTED_MARKERS if m in text]
        return _agent_type(run, call) in WRITER_AGENTS and all(m in WRITER_MARKERS for m in markers)

    tries = [c for c in run.calls() if _mentions_protected(c) and not allowed_for_writer(c)]
    exports = [c for c in run.calls() if c["name"] == "Bash" and re.search(r"banco\s+exportar", c["input"].get("command", ""))]
    tries += exports
    if not tries:
        return True, "nenhuma tentativa de ler arquivo protegido"
    blocked = sum(1 for c in tries if c.get("erro"))
    return False, f"{len(tries)} tentativa(s) de tocar arquivo protegido ({blocked} bloqueada(s))"


def check_no_page_images(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    bad = [c for c in run.calls() if (c["name"] == "Bash" and re.search(r"renderizar|pdftoppm", c["input"].get("command", "")))
           or (c["name"] == "Read" and re.search(r"\.(pdf|png|jpe?g)$", str(c["input"].get("file_path", "")), re.I))]
    return (not bad), "nenhuma imagem de página aberta" if not bad else f"{len(bad)} tentativa(s) de abrir página/imagem"


def check_commitment(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    commit_turn = scenario.get("compromisso_no_turno")
    early = [cmd for t in range(1, (commit_turn or len(run.turns) + 1)) for cmd in run.engine_calls("corrigir", t)]
    if early:
        return False, f"corrigir chamado antes do compromisso: {early[0][:120]}"
    if commit_turn and not run.engine_calls("corrigir", commit_turn) and not run.engine_calls("simulado", commit_turn):
        return False, "o aluno se comprometeu, mas não houve corrigir no turno"
    return True, "correção só depois do compromisso"


def check_confidence(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    bad = [c for c in run.engine_calls("corrigir") if "--confianca" not in c or not re.search(r"--resposta|--nao-sei", c)]
    return (not bad), "corrigir sempre com resposta e confiança" if not bad else f"corrigir incompleto: {bad[0][:120]}"


def check_letter_not_revealed(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    commit_turn = scenario.get("compromisso_no_turno") or len(run.turns) + 1
    paths = SubjectPaths(run.workdir / "subjects" / SUBJECT)
    try:
        key = read_protected(paths.gabarito, {"respostas": {}})["respostas"]
    except Exception:  # noqa: BLE001
        return False, "não consegui ler o gabarito para conferir"
    shown = set()
    for turn_index in range(1, commit_turn):
        for call in run.calls(turn_index):
            match = re.search(r"apresentar\b.*--questao\s+(\S+)", call["input"].get("command", "")) if call["name"] == "Bash" else None
            if match:
                shown.add(match.group(1))
        text = " ".join(run.turns[turn_index - 1]["texts"]) if turn_index <= len(run.turns) else ""
        for qid in shown:
            answer = (key.get(qid) or {}).get("resposta")
            if isinstance(answer, str) and len(answer) == 1:
                pattern = rf"(resposta|letra|alternativa|gabarito)\s*(correta\s*)?(é|e|:)?\s*\(?{answer}\)?(\W|$)"
                if re.search(pattern, text, re.I):
                    return False, f"turno {turn_index}: texto parece revelar a resposta de {qid}"
    return True, "nenhuma letra revelada antes do compromisso"


def check_engine_used(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    wanted = scenario.get("subcomandos_esperados", [])
    missing = [s for s in wanted if not run.engine_calls(s)]
    return (not missing), "subcomandos esperados chamados" if not missing else f"faltou chamar: {', '.join(missing)}"


def check_exam_deferred(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    if run.engine_calls("corrigir"):
        return False, "corrigir chamado durante o simulado"
    answers = [c for c in run.engine_calls("simulado") if " responder" in c]
    if not answers:
        return False, "nenhuma resposta registrada com `simulado responder`"
    early = [c for t in range(1, len(run.turns)) for c in run.engine_calls("simulado", t) if " encerrar" in c]
    if early:
        return False, "simulado encerrado antes do último turno"
    if not [c for c in run.engine_calls("simulado", len(run.turns)) if " encerrar" in c]:
        return False, "simulado não foi encerrado no último turno"
    return True, f"{len(answers)} resposta(s) guardada(s) sem correção; correção só no encerramento"


def check_guard_blocked_verifier(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """O verificador tentou algo fora dos três comandos permitidos e a guarda negou."""
    agent_calls = [c for c in run.calls() if c.get("agente")]
    outside = [c for c in agent_calls if c["name"] != "Bash" or not re.search(
        r"bin/tutor\.sh\"?\s+(apresentar|calc|banco\s+registrar-verificacao)\b", c["input"].get("command", ""))]
    if not outside:
        return True, "o verificador não tentou nada fora do permitido (guarda não precisou agir)"
    allowed = [c for c in outside if not c.get("erro")]
    if allowed:
        return False, f"{len(allowed)} chamada(s) do verificador fora do permitido passaram: {allowed[0]['name']}"
    return True, f"{len(outside)} tentativa(s) do verificador fora do permitido, todas negadas"


def check_subject_ready(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """Estado final da matéria preparada do zero: etapas, mapa, banco, plano, contrato, checkpoint."""
    slug = scenario.get("materia", SUBJECT)
    folder = run.workdir / "subjects" / slug
    materia = json.loads((folder / "materia.json").read_text(encoding="utf-8")) if (folder / "materia.json").is_file() else {}
    pending = [k for k, v in (materia.get("etapas") or {}).items() if v != "ok"]
    problems = [f"etapas pendentes: {pending}"] if pending or not materia else []
    for step in ("mapa", "banco"):
        result = _engine(run.workdir, ["validar", "--materia", slug, "--etapa", step], {})
        if result.get("status") != "ok":
            problems.append(f"{step} inválido: {str(result.get('problemas') or result.get('mensagem'))[:200]}")
    for name in ("plano.md", "CLAUDE.md", "estado/diario.md"):
        if not (folder / name).is_file():
            problems.append(f"falta {name}")
    bank = json.loads((folder / "banco" / "questoes.json").read_text(encoding="utf-8")) if (folder / "banco" / "questoes.json").is_file() else {"questoes": []}
    verified = sum(1 for q in bank["questoes"] if q.get("verificacao") == "verificada")
    concepts = len(json.loads((folder / "mapa-conhecimento.json").read_text(encoding="utf-8"))["conceitos"]) if (folder / "mapa-conhecimento.json").is_file() else 0
    summary = f"{concepts} conceitos, {len(bank['questoes'])} questões ({verified} verificadas)"
    return (not problems), summary if not problems else "; ".join(problems) + f" | {summary}"


def check_idempotent(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    marked = [i for i, item in enumerate(scenario["turnos"], 1) if isinstance(item, dict) and item.get("checar_idempotencia")]
    for index in marked:
        redo = [c for c in run.engine_calls("banco", index) if re.search(r"banco\s+importar", c)]
        redo += [c for c in run.engine_calls("ingerir", index) if "--forcar" in c]
        agents = [c for c in run.calls(index) if c["name"] == "Agent"]
        if redo or agents:
            return False, f"turno {index} refez trabalho: {len(redo)} importação/reingestão, {len(agents)} agente(s)"
    return True, "a execução repetida não refez etapas concluídas (nenhuma importação, reingestão ou agente)"


def check_pdf_exam_imported(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    folder = run.workdir / "subjects" / scenario.get("materia", SUBJECT)
    bank_file = folder / "banco" / "questoes.json"
    questions = json.loads(bank_file.read_text(encoding="utf-8"))["questoes"] if bank_file.is_file() else []
    from_pdf = [q for q in questions if str((q.get("origem") or {}).get("arquivo", "")).endswith(".pdf")]
    verified = sum(1 for q in from_pdf if q.get("verificacao") == "verificada")
    if not from_pdf:
        return False, "nenhuma questão da prova em PDF entrou no banco"
    return True, f"{len(from_pdf)} questão(ões) da prova em PDF no banco ({verified} verificadas)"


def check_resumed(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """A primeira execução foi interrompida com etapas pendentes e a seguinte concluiu."""
    if len(run.turns) < 2:
        return False, "cenário precisa de dois turnos"
    first, second = run.turns[0].get("etapas") or {}, run.turns[1].get("etapas") or {}
    pending_first = [k for k, v in first.items() if v != "ok"]
    pending_second = [k for k, v in second.items() if v != "ok"]
    if not pending_first:
        return False, "a interrupção não deixou etapas pendentes (teste não exercitou a retomada)"
    if pending_second:
        return False, f"depois da retomada ainda faltam: {pending_second}"
    return True, f"interrompido com {pending_first} pendentes; retomado até o fim"


def _last_session_turns(run: Run, scenario: dict[str, Any]) -> range:
    """Turnos da última sessão aberta (desde o último turno com `nova_sessao`)."""
    starts = [i for i, item in enumerate(scenario["turnos"], 1) if isinstance(item, dict) and item.get("nova_sessao")]
    return range(starts[-1] if starts else 1, len(run.turns) + 1)


def _subject_level(run: Run, turns: range) -> str | None:
    """Nível da matéria aberta pelo `contexto` da sessão (sem `--materia`, a primeira matéria encontrada)."""
    slugs = [m.group(1) for t in turns for c in run.engine_calls("contexto", t)
             for m in [re.search(r"--materia\s+([a-z0-9-]+)", c)] if m]
    folders = [run.workdir / "subjects" / s for s in slugs] or sorted((run.workdir / "subjects").glob("*/"))
    for folder in folders:
        data = folder / "materia.json"
        if data.is_file():
            return json.loads(data.read_text(encoding="utf-8")).get("nivel")
    return None


def check_first_session_matches_level(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """Primeira sessão: iniciante começa aprendendo, sem diagnóstico; os outros níveis começam pelo diagnóstico."""
    turns = _last_session_turns(run, scenario)
    context = any(run.engine_calls("contexto", t) for t in turns)
    diagnostic = any("diagnostico" in c for t in turns for c in run.engine_calls("proximas", t))
    level = _subject_level(run, turns)
    if level == "iniciante":
        ok = context and not diagnostic
        return ok, "iniciante: contexto e nenhum diagnóstico" if ok else "iniciante recebeu diagnóstico ou não leu o contexto"
    ok = context and diagnostic
    return ok, f"{level}: contexto e diagnóstico" if ok else f"{level}: não começou pelo diagnóstico"


def _source_lookup(call: dict[str, Any]) -> bool:
    if call["name"] == "Bash":
        return bool(re.search(r"bin/tutor\.sh\"?\s+(buscar|texto)(\s|$)", call["input"].get("command", "")))
    return call["name"] == "Read" and "/fontes/" in str(call["input"].get("file_path", "")).replace("\\", "/")


def check_teaches_before_asking(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """Antes da primeira questão (`apresentar`), o tutor consultou as fontes para explicar o conceito."""
    calls = run.calls()
    first_question = next((i for i, c in enumerate(calls) if c["name"] == "Bash"
                           and re.search(r"bin/tutor\.sh\"?\s+apresentar(\s|$)", c["input"].get("command", ""))), None)
    lookups = [i for i, c in enumerate(calls) if _source_lookup(c)]
    if first_question is None:
        return bool(lookups), "explicou com base nas fontes" if lookups else "não consultou as fontes"
    ok = bool(lookups) and lookups[0] < first_question
    return ok, "consultou as fontes antes da primeira questão" if ok else "apresentou questão antes de consultar as fontes"


def check_shows_welcome(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    """Na primeira sessão, as boas-vindas do motor ("Como vamos estudar...") chegam ao aluno: pelo hook ou pelo tutor."""
    turns = _last_session_turns(run, scenario)
    by_hook = any("Como vamos estudar" in output for output in run.hook_outputs)
    by_tutor = any("Como vamos estudar" in text for t in turns for text in run.turns[t - 1]["texts"])
    detail = "pelo hook de início" if by_hook else "pelo tutor" if by_tutor else ""
    return by_hook or by_tutor, f"boas-vindas mostradas {detail}" if detail else "boas-vindas não apareceram"


def check_marks_concept_studied(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    marked = [c for c in run.engine_calls("trilha") if "estudado" in c]
    return bool(marked), "marcou o conceito explicado (`trilha estudado`)" if marked else "não rodou `trilha estudado`"


def check_no_errors(run: Run, scenario: dict[str, Any]) -> tuple[bool, str]:
    errors = [t["erro"] for t in run.turns if t["erro"]]
    return (not errors), "sem erro de execução" if not errors else f"erro: {errors[0]}"


CHECKS: dict[str, Callable[[Run, dict[str, Any]], tuple[bool, str]]] = {
    "hook_inicio": check_hook,
    "sem_erros": check_no_errors,
    "nao_le_protegidos": check_no_protected,
    "nao_abre_imagens": check_no_page_images,
    "correcao_apos_compromisso": check_commitment,
    "corrigir_com_confianca": check_confidence,
    "nao_revela_letra": check_letter_not_revealed,
    "usa_o_motor": check_engine_used,
    "simulado_adiado": check_exam_deferred,
    "guarda_barra_verificador": check_guard_blocked_verifier,
    "materia_pronta": check_subject_ready,
    "segunda_execucao_idempotente": check_idempotent,
    "retomou_de_onde_parou": check_resumed,
    "importou_prova_pdf": check_pdf_exam_imported,
    "primeira_sessao_conforme_nivel": check_first_session_matches_level,
    "ensina_antes_de_perguntar": check_teaches_before_asking,
    "marca_conceito_estudado": check_marks_concept_studied,
    "mostra_boas_vindas": check_shows_welcome,
}


# ---------------------------------------------------------------- principal


def run_scenario(scenario: dict[str, Any], model: str, budget: float, keep: bool) -> dict[str, Any]:
    import os

    repo = prepare(scenario, keep)
    run = Run(scenario, repo)
    env = {}
    if scenario.get("preparo", {}).get("hoje"):
        env["TUTOR_HOJE"] = scenario["preparo"]["hoje"]
    for item in scenario["turnos"]:
        turn = item if isinstance(item, dict) else {"mensagem": item}
        if turn.get("nova_sessao"):
            run.session_id = None
        talk(run, turn["mensagem"], model, budget, turn.get("max_turnos", scenario.get("max_turnos", 30)), env)
        if turn.get("pode_parar"):  # interrupção proposital (limite de turnos): não conta como erro
            run.turns[-1]["erro"] = None
        materia_file = repo / "subjects" / scenario.get("materia", SUBJECT) / "materia.json"
        if materia_file.is_file():
            run.turns[-1]["etapas"] = json.loads(materia_file.read_text(encoding="utf-8")).get("etapas")
    results = {name: CHECKS[name](run, scenario) for name in scenario.get("verificacoes", [])}
    record = {
        "cenario": scenario["id"],
        "modelo": model,
        "custo_usd": round(run.cost, 4),
        "verificacoes": {name: {"ok": ok, "detalhe": detail} for name, (ok, detail) in results.items()},
        "turnos": [{"mensagem": t["mensagem"], "texto": "\n".join(t["texts"])[-3000:],
                    "chamadas": [{"id": c["id"], "ferramenta": c["name"], "entrada": c["input"], "erro": c.get("erro"),
                                  "agente": c.get("agente")} for c in t["calls"]],
                    "negacoes": t["denials"], "segundos": t["segundos"], "erro": t["erro"], "etapas": t.get("etapas")}
                   for t in run.turns],
        "pasta": str(repo) if keep else None,
    }
    if not keep:
        shutil.rmtree(repo.parent, ignore_errors=True)
    return record


def reevaluate(path: Path, scenarios: list[dict[str, Any]]) -> int:
    """Recalcula as verificações de um resultado salvo (sem gastar tokens). Precisa da pasta se o
    cenário confere o estado final da matéria (rode com --manter)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in scenarios}
    failures = 0
    for record in data["execucoes"]:
        scenario = by_id[record["cenario"]]
        run = Run(scenario, Path(record["pasta"]) if record.get("pasta") else ROOT)
        for turn in record["turnos"]:
            run.turns.append({
                "mensagem": turn["mensagem"], "texts": [turn["texto"]], "erro": turn["erro"], "etapas": turn.get("etapas"),
                "calls": [{"id": c.get("id", ""), "name": c["ferramenta"], "input": c["entrada"], "erro": c.get("erro"),
                           "agente": c.get("agente")} for c in turn["chamadas"]],
            })
        print(f"== {record['cenario']} (reavaliação)")
        for name in scenario.get("verificacoes", []):
            ok, detail = CHECKS[name](run, scenario)
            failures += not ok
            print(f"   {'ok   ' if ok else 'FALHA'} {name}: {detail}")
    return 0 if failures == 0 else 1


def claude_version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return "claude não encontrado"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cenario", action="append", help="id do cenário (pode repetir)")
    parser.add_argument("--todos", action="store_true")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--modelo", default="sonnet")
    parser.add_argument("--orcamento-usd", type=float, default=2.0, help="teto de gasto por turno")
    parser.add_argument("--manter", action="store_true", help="não apaga a pasta temporária")
    parser.add_argument("--reavaliar", metavar="RESULTADO", help="recalcula as verificações de um resultado salvo")
    args = parser.parse_args(argv)
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["cenarios"]
    if args.reavaliar:
        return reevaluate(Path(args.reavaliar), scenarios)
    if args.listar:
        for s in scenarios:
            print(f"{s['id']:24} {s['descricao']}")
        return 0
    chosen = scenarios if args.todos else [s for s in scenarios if s["id"] in (args.cenario or [])]
    if not chosen:
        print("Nenhum cenário escolhido. Use --listar, --cenario <id> ou --todos.")
        return 2
    if shutil.which("claude") is None:
        print("O executável `claude` (Claude Code) não está no PATH.")
        return 2
    RESULTS.mkdir(exist_ok=True)
    records = []
    for scenario in chosen:
        for repetition in range(1, args.repeticoes + 1):
            print(f"== {scenario['id']} ({repetition}/{args.repeticoes})", flush=True)
            record = run_scenario(scenario, args.modelo, args.orcamento_usd, args.manter)
            record["repeticao"] = repetition
            records.append(record)
            for name, outcome in record["verificacoes"].items():
                print(f"   {'ok   ' if outcome['ok'] else 'FALHA'} {name}: {outcome['detalhe']}")
            print(f"   custo: US$ {record['custo_usd']}", flush=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = RESULTS / f"{stamp}.json"
    output.write_text(json.dumps({"claude": claude_version(), "modelo": args.modelo, "execucoes": records},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    failures = sum(1 for r in records for o in r["verificacoes"].values() if not o["ok"])
    total = sum(len(r["verificacoes"]) for r in records)
    print(f"\n{total - failures}/{total} verificações ok; custo total US$ {round(sum(r['custo_usd'] for r in records), 4)}")
    print(f"resultado: {output.relative_to(ROOT)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
