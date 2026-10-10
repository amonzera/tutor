"""Guarda (hook PreToolUse): verificador cego, área protegida, exportação e buscas recursivas."""

from __future__ import annotations

import json
import subprocess
import unittest

from tests.helpers import ROOT, available_shells
from tutor.guard import decide


def bash(command: str, agent: str | None = None, cwd: str = "/repo") -> dict:
    event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    if agent:
        event["agent_type"] = agent
    return event


class DecideTest(unittest.TestCase):
    denied = {
        "busca recursiva em subjects": bash("grep -r TOKEN subjects/x/banco"),
        "busca recursiva a partir da raiz": bash("grep -rn segredo ."),
        "busca recursiva sem caminho": bash("grep -R segredo"),
        "rg em examples": bash("rg resposta examples/"),
        "git grep sem caminho": bash("git grep resposta"),
        "find com exec": bash("find subjects -name '*.json' -exec cat {} +"),
        "xargs lendo arquivos": bash("ls subjects/x/estado | xargs cat"),
        "busca dentro de subjects (cwd)": bash("grep -r x estado", cwd="/repo/subjects/prob"),
        "nomeando gabarito": bash("base64 -d subjects/x/banco/gabarito.json"),
        "provas por pdftotext": bash("pdftotext subjects/x/fontes/provas/p.pdf -"),
        "tentativas": bash("tail subjects/x/estado/tentativas.jsonl"),
        "rascunhos pelo tutor": bash("cat subjects/x/banco/rascunhos/lote.json"),
        "copiar da área protegida": bash("cp subjects/x/ingestao/protegido/a.json /tmp/a.json"),
        "texto protegido pelo tutor": bash("bash bin/tutor.sh texto --materia x --arquivo provas/p.pdf --protegido"),
        "renderizar pelo tutor": bash("bash bin/tutor.sh renderizar --materia x --arquivo provas/p.pdf --pagina 1"),
        "exportar pelo tutor": bash("bash bin/tutor.sh banco exportar --materia x --para /tmp/g.json"),
        "exportar com variável na frente": bash("X=1 bash bin/tutor.sh banco exportar --materia x --para g.json"),
        "leitura dentro de laço": bash("for f in a; do cat subjects/x/banco/gabarito.json; done"),
        "exportar chamando o script direto": bash("./bin/tutor.sh banco exportar --materia x --para g.json"),
        "exportar pelo ingestor": bash("bash bin/tutor.sh banco exportar --materia x --para g.json", "ingestor-de-fontes"),
        "verificador lendo fontes": bash("cat subjects/x/fontes/a.md", "verificador"),
        "verificador encadeando": bash("bash bin/tutor.sh calc 1+1 && cat segredo", "verificador"),
        "verificador com substituição": bash('bash bin/tutor.sh calc "$(cat x)"', "verificador"),
        "verificador com outro subcomando": bash("bash bin/tutor.sh texto --materia x --arquivo a.md", "verificador"),
        "verificador com Read": {"tool_name": "Read", "tool_input": {"file_path": "/repo/a.md"}, "agent_type": "verificador"},
        "Read de rascunho pelo tutor": {"tool_name": "Read", "tool_input": {"file_path": "/repo/subjects/x/banco/rascunhos/l.json"}},
    }
    allowed = {
        "comando comum": bash("ls -la"),
        "busca recursiva em pastas de código": bash("grep -rn foo tutor docs"),
        "motor": bash("bash bin/tutor.sh corrigir --materia x --questao q1 --resposta B --confianca 3"),
        "motor com variável na frente": bash("TUTOR_MATERIAS_DIR=examples bash bin/tutor.sh banco importar "
                                             "--materia x --arquivo banco/rascunhos/l.json"),
        "motor dentro de laço": bash("for l in a b; do bash bin/tutor.sh banco importar --materia x "
                                     "--arquivo banco/rascunhos/$l.json; done"),
        "motor com caminho do projeto": bash('bash "/repo/bin/tutor.sh" contexto --materia x'),
        "listar provas": bash("ls subjects/x/fontes/provas"),
        "mover para provas": bash("mv subjects/x/fontes/lista.md subjects/x/fontes/provas/"),
        "texto protegido pelo ingestor": bash("bash bin/tutor.sh texto --materia x --arquivo provas/p.pdf --protegido",
                                              "ingestor-de-fontes"),
        "escritor gravando rascunho": bash("ls subjects/x/banco/rascunhos", "escritor-de-questoes"),
        "Read de rascunho pelo escritor": {"tool_name": "Read", "agent_type": "escritor-de-questoes",
                                           "tool_input": {"file_path": "/repo/subjects/x/banco/rascunhos/l.json"}},
        "verificador apresentar": bash("bash bin/tutor.sh apresentar --materia x --questao q1", "verificador"),
        "verificador registrar": bash(
            'bash bin/tutor.sh banco registrar-verificacao --materia x --questao q1 --resposta C --confianca 4 '
            '--obs "conta (com parênteses) conferida"', "verificador"),
        "Edit comum": {"tool_name": "Edit", "tool_input": {"file_path": "/repo/subjects/x/estado/proximo-passo.md"}},
    }

    def test_denied(self) -> None:
        for name, event in self.denied.items():
            with self.subTest(name=name):
                self.assertIsNotNone(decide(event), name)

    def test_allowed(self) -> None:
        for name, event in self.allowed.items():
            with self.subTest(name=name):
                self.assertIsNone(decide(event), name)


class HookScriptTest(unittest.TestCase):
    """bin/guarda.sh de verdade, alimentado pela entrada padrão como o Claude Code faz."""

    def run_hook(self, shell: str, event: dict) -> str:
        done = subprocess.run(
            [shell, "bin/guarda.sh"], cwd=ROOT, input=json.dumps(event), capture_output=True, text=True,
            encoding="utf-8", check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_hook_output(self) -> None:
        shells = available_shells()
        if not shells:
            self.skipTest("nenhum shell POSIX")
        for shell in shells:
            with self.subTest(shell=shell):
                denied = json.loads(self.run_hook(shell, bash("grep -r x subjects/y")))
                decision = denied["hookSpecificOutput"]
                self.assertEqual(decision["hookEventName"], "PreToolUse")
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("buscar", decision["permissionDecisionReason"])
                self.assertEqual(self.run_hook(shell, bash("ls -la")), "", "caminho rápido: sem saída")
                self.assertEqual(self.run_hook(shell, bash("grep -rn foo tutor")), "")
                self.assertEqual(self.run_hook(shell, {}), "")


if __name__ == "__main__":
    unittest.main()
