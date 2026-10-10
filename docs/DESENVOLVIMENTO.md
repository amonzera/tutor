# Desenvolvimento

Como trabalhar no motor, nas skills e nos agentes. Para contribuir, veja também o [CONTRIBUTING.md](../CONTRIBUTING.md).

## Requisitos

- Python 3.10 ou mais novo (o motor só usa a biblioteca padrão).
- `pdftotext` e `pdftoppm` (poppler) para os testes de PDF; sem eles, esses testes são pulados.
- Claude Code, só para os evals com modelo de verdade.

## Verificar tudo

```bash
python tools/verificar.py            # testes, privacidade, .gitignore, links, exemplo, Markdown
python tools/verificar.py testes     # uma etapa só
```

A CI roda exatamente este script em Linux, macOS e Windows, com Python 3.10 a 3.14. Os testes rodam com `-X warn_default_encoding -W error::EncodingWarning`: todo `open()` precisa de `encoding="utf-8"`.

Para testar a versão mínima localmente com o [uv](https://docs.astral.sh/uv/):

```bash
uv run --no-project --python 3.10 -- python -m unittest discover -s tests -t .
```

## Estrutura dos testes

- `tests/helpers.py`: `TempWorkspaceCase` cria uma pasta `subjects/` temporária e congela o relógio; `run_cli` roda a CLI no próprio processo.
- `tests/fixtures.py`: matéria sintética com 4 conceitos e 8 questões, importada pelo fluxo real (rascunho, `banco importar`, verificação).
- `tests/pdf_minimo.py`: gera PDFs pequenos (com texto colorido) para testar a ingestão.
- O relógio é injetável: `TUTOR_AGORA=2026-03-02T10:00:00` ou `TUTOR_HOJE=2026-03-02` também funcionam na linha de comando.

## Uma matéria de teste

```bash
TUTOR_MATERIAS_DIR=/tmp/materias bash bin/tutor.sh exemplo     # instala o exemplo fora de subjects/
TUTOR_MATERIAS_DIR=/tmp/materias bash bin/tutor.sh contexto
```

`TUTOR_MATERIAS_DIR` aponta o motor para outra pasta de matérias. Use-o para não misturar testes com as suas matérias reais.

## A matéria de exemplo

- `examples/probabilidade-basica/` é original e fictícia. Mantenha assim: nada copiado de livros, provas ou listas reais.
- As fontes protegidas (`fontes/provas/`) são geradas por `python tools/gerar_exemplo.py`. Dentro do Claude Code, as regras do projeto bloqueiam ler e escrever nessa pasta, então o script é o caminho.
- Para mudar questões: escreva um rascunho em `examples/probabilidade-basica/banco/rascunhos/<lote>.json` (formato em `.claude/skills/nova-materia/etapas.md`) e importe com `TUTOR_MATERIAS_DIR=examples bash bin/tutor.sh banco importar --materia probabilidade-basica --arquivo banco/rascunhos/<lote>.json`. Depois verifique às cegas (`python evals/executar.py --cenario verificar-exemplo --manter`) e confira as abertas com `banco conferir-aberta` e `banco confirmar`.
- Apague o `examples/.local.json` que o motor cria ao rodar com `TUTOR_MATERIAS_DIR=examples`.

## Acrescentar um subcomando

1. Escreva `cmd_<nome>(args, ctx)` no módulo certo, devolvendo um dicionário com `status` e, se orientar o agente, `llm_directive` (texto constante, nunca com conteúdo das fontes).
2. Registre em `add_commands` do módulo, com nomes e ajuda em português.
3. Erros esperados: `raise TutorError(codigo, mensagem, diretiva)`.
4. Subcomando chamado por hook ou por injeção `!`: `set_defaults(always_zero=True)`.
5. O teste `EverySubcommandTest` confere o contrato JSON; acrescente testes do comportamento.

## Acrescentar uma skill

1. Crie `.claude/skills/<nome>/SKILL.md` com `name`, `description` (diga quando usar), `argument-hint` e `allowed-tools: Bash(bash bin/tutor.sh *)`.
2. Use `disable-model-invocation: true` se a skill for pesada ou tiver efeito colateral.
3. Use injeção `!` só com comandos fixos (sem `$ARGUMENTS` dentro do shell); um `!` que falha aborta a skill inteira.
4. Comece por `contexto --materia <slug>` e termine com `checkpoint`.
5. Crie um cenário em `evals/cenarios.json` e rode-o.

## Acrescentar um agente

1. Crie `.claude/agents/<nome>.md` com `name`, `description`, `tools` mínimos, `model` e `effort`.
2. Se ele precisar de acesso especial (como o ingestor à área protegida), a regra fica em `tutor/guard.py`, testada em `tests/test_guard.py`.
3. Relatórios de agentes nunca trazem respostas de questões.

## A guarda também vale para você

Com o projeto aberto no Claude Code, a guarda nega, por exemplo, `grep -r` a partir da raiz (alcança `subjects/` e `examples/`), comandos que citam arquivos protegidos (inclusive dentro de heredocs) e chamadas ao motor com variáveis na frente, exceto `TUTOR_HOJE`, `TUTOR_AGORA` e `TUTOR_MATERIAS_DIR`. Restrinja buscas a `tutor/`, `tests/`, `docs/`. Para editar código ou documentos que citam esses arquivos, use a ferramenta de edição de arquivos, não comandos de shell. Ao mudar a guarda, acrescente o caso em `tests/test_guard.py` (há uma lista de ataques conhecidos que precisam continuar negados).

## Evals

```bash
python evals/executar.py --listar
python evals/executar.py --cenario so-a-letra --repeticoes 3 --modelo sonnet
```

Custam tokens da sua conta e não rodam na CI. Veja [evals/README.md](../evals/README.md).

## Antes de abrir um PR

- `python tools/verificar.py` sem falhas.
- Commits em Conventional Commits (`feat:`, `fix:`, `docs:`...).
- Nenhum dado pessoal, caminho da sua máquina ou material de terceiros.
- Documentação atualizada (README, GUIA-DE-USO, CHANGELOG).
