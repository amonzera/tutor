# Arquitetura

Este documento explica como o tutor é montado e por quê. As decisões estão registradas em [ADRs](adr/); as bases de aprendizagem de cada recurso estão em [CIENCIA-DA-APRENDIZAGEM.md](CIENCIA-DA-APRENDIZAGEM.md).

## Visão geral

```text
aluno ──> Claude Code (sessão na raiz do repositório)
             │  lê CLAUDE.md (protocolo do tutor)
             │  skills: /materias, /nova-materia, /estudar, /revisar, /quiz, /simulado,
             │          /ensinar, /diagnostico, /progresso, /plano, /erros
             │  agentes: ingestor-de-fontes, escritor-de-questoes, verificador, corretor, planejador
             │  hooks: SessionStart (estado das matérias), PreToolUse (guarda)
             ▼
        bash bin/tutor.sh <subcomando>   (escolhe o Python certo; no Windows, usa o do WSL)
             ▼
        tutor/  motor em Python 3.10+, só biblioteca padrão, saída sempre em JSON
             ▼
        subjects/<slug>/   dados do aluno (fora do git): fontes, mapa, banco, estado
```

O Claude Code conversa e decide a pedagogia; o motor guarda o estado, calcula (revisões, domínio, plano) e impõe as regras que não podem depender de boa vontade (a correção exige a resposta do aluno; o gabarito fica codificado). Toda memória está em arquivos: uma sessão nova retoma pelo `contexto`, sem depender do histórico do chat.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `CLAUDE.md` | Protocolo do tutor, proteção do gabarito, uso do motor. Carregado em toda sessão. |
| `.claude/settings.json` | Permissões (`allow`/`deny`), hooks e `claudeMdExcludes`. Versionado, sem dados pessoais. |
| `.claude/skills/` | Uma pasta por skill (`SKILL.md` e arquivos de apoio). |
| `.claude/agents/` | Subagentes, cada um com ferramentas, modelo e esforço próprios. |
| `bin/` | `tutor.sh` (ponto único de execução) e `guarda.sh` (hook PreToolUse), em sh POSIX. |
| `tutor/` | O motor. |
| `templates/materia/` | Modelo do `CLAUDE.md` de cada matéria. |
| `examples/probabilidade-basica/` | Matéria fictícia completa: demonstração e fixture de testes. |
| `tests/` | Testes `unittest` (relógio fixo, aleatoriedade com semente, aluno sintético). |
| `evals/` | Cenários que testam o tutor com o Claude Code de verdade. |
| `tools/` | `verificar.py` (tudo o que a CI roda) e `gerar_exemplo.py`. |
| `subjects/` | Matérias do aluno. Ignorada pelo git, exceto `README.md` e `.gitkeep`. |

## Dados de uma matéria

| Arquivo | Quem escreve | Observação |
|---|---|---|
| `fontes/` | aluno | Material. `fontes/provas/` guarda provas e listas com gabarito (área protegida). |
| `materia.json` | motor (`iniciar`, `configurar`) | Prova, tempo diário, revisão, etapas da preparação. |
| `CLAUDE.md` | motor | Gerado de `templates/materia/` a partir do `materia.json`. |
| `mapa-conhecimento.json` | agente ingestor ou planejador | Conceitos, pré-requisitos, pesos, fontes, equívocos. Validado pelo motor. |
| `plano.md` | motor (`plano`, `checkpoint`) | Calendário reverso, sempre gerado a partir dos dados. |
| `banco/questoes.json` | motor (`banco importar`, `comparar`) | Questões **sem** resposta, com status de verificação. |
| `banco/gabarito.json` | motor | Resposta, conceito decisivo, solução, por que cada distrator é tentador. **Codificado.** |
| `banco/verificacao.json` | motor | Respostas às cegas do verificador. **Codificado.** |
| `banco/verificacao.md` | motor | Status por questão, sem letras. |
| `banco/rascunhos/` | agentes | Questão e gabarito juntos, apagados na importação. |
| `estado/tentativas.jsonl` | motor | Uma linha por evento (tentativa, classificação, avaliação), só acréscimo. |
| `estado/revisoes.json` | motor | Agenda de revisão espaçada por conceito. |
| `estado/sessao.json` | motor | Questões apresentadas e ainda não corrigidas. |
| `estado/simulado-atual.json`, `estado/simulados.jsonl` | motor | Simulado em andamento e histórico (previsto × real). |
| `estado/proximo-passo.md` | tutor (Claude) | Texto livre do checkpoint: o que fazer na próxima sessão. |
| `estado/diario.md` | motor (`checkpoint`) | Uma entrada por sessão, com os números que o motor calcula. |
| `estado/dominio.md`, `estado/caderno-de-erros.md` | motor | Painel e caderno de erros gerados. |
| `ingestao/` | motor (`ingerir`) | Texto por página e `indice.json`. Provas vão para `ingestao/protegido/`, codificadas. |
| `notas/` | aluno ou tutor | Anotações livres. |

Todos os JSON têm `schema_version`. Arquivo de versão mais nova que o motor gera um erro pedindo `git pull`.

## O motor

Um ponto de entrada (`python -m tutor`, chamado por `bash bin/tutor.sh`), subcomandos em português e saída JSON com `status` e, quando orienta o agente, `llm_directive`. Os textos de diretiva são constantes do código: nunca incluem texto das fontes.

| Módulo | Papel |
|---|---|
| `core` | Erros, relógio injetável (`TUTOR_HOJE`, `TUTOR_AGORA`), caminhos seguros, escrita atômica, `schema_version`, codificação em repouso. |
| `cli` | argparse; erros de uso também saem em JSON. Subcomandos de contexto (`materias`, `contexto`, `inicio-sessao`, `ambiente`, `guarda`) sempre terminam com código 0, porque uma injeção `!` que falha aborta a skill. |
| `subjects` | Listagem, criação e configuração, `contexto`, `checkpoint`, `validar`, `exemplo`, hook de início. |
| `ingest` | Inventário, ingestão (PDF via `pdftotext`, Markdown, texto), `texto`, `buscar`, `renderizar`. |
| `knowledge_map` | Validação do mapa (ids, pré-requisitos, ciclos, fontes), ordem topológica e ordem da trilha. |
| `bank` | Banco, gabarito, apresentação em texto, conferência de respostas, importação, verificação cega. |
| `attempts` | Máquina de estados da tentativa e simulado com correção adiada. |
| `srs` | Revisão espaçada (interface `Scheduler`), triagem diária, orçamento entre matérias. |
| `learner` | Domínio por conceito, calibração, preparo estimado. |
| `selection` | Próximas questões, simulado estratificado, diagnóstico. |
| `planner` | Trilha completa por prioridade, calendário reverso, `plano.md` e `trilha estudado`. |
| `report` | Painel e caderno de erros. |
| `calc` | Calculadora segura (AST) para conferir contas. |
| `guard` | Política do hook PreToolUse. |

### Ciclo de uma questão

```text
proximas ──> apresentar (abre a tentativa, marca o horário; tema oculto)
                 │
          aluno: resposta + confiança      (dicas em escada, se ele não souber)
                 ▼
             corrigir --resposta R --confianca N --dicas D
                 │  grava a tentativa ANTES de revelar
                 ▼
          resposta, conceito decisivo, solução, por que o distrator escolhido é tentador
                 │
          errou? ──> classificar --tipo conceito|metodo|sinal|conta|chute
```

`corrigir` recusa questão não apresentada, repete a resposta (sem duplicar) se a mesma chamada vier de novo em 10 minutos e marca como `apos_revelacao` uma tentativa feita até 24 horas depois de a resposta ter sido mostrada (ela fica fora do domínio e da calibração). No simulado, `simulado responder` só guarda resposta e confiança; a correção sai toda no `simulado encerrar`.

## Proteção do gabarito (camadas)

1. **Estrutura:** banco e gabarito separados; `apresentar` só entrega texto; `corrigir` exige o compromisso e grava antes de revelar.
2. **Codificação em repouso:** gabarito, respostas do verificador e texto das provas ficam em zlib + base64. Um teste no Claude Code real mostrou que o `deny` de leitura bloqueia `cat`, `head`, `awk` e `grep` quando o arquivo é nomeado, mas não `cat banco/*.json` (curinga) nem `grep -r` com caminho explícito. A codificação torna o conteúdo ilegível nesses casos. Não é criptografia.
3. **Permissões:** `deny` de leitura nos arquivos protegidos (vale também para Edit e Write; só o motor escreve neles).
4. **Guarda (`bin/guarda.sh` + `tutor/guard.py`, hook `PreToolUse` para Bash, Read, Grep e Glob):** o verificador só roda três comandos exatos (lista fechada sobre o comando inteiro, sem operadores, variáveis, comentários nem quebras de linha); texto protegido e páginas renderizadas só para o ingestor; `registrar-verificacao` só para o verificador; `banco exportar` nunca por agente (também negado por regra `deny`); chamadas ao motor sem variáveis de ambiente na frente e nenhuma definição de variáveis que executam código (`BASH_ENV`, `PYTHONPATH`, `PATH`...); nada fora do motor toca arquivos protegidos; buscas recursivas (inclusive a ferramenta Grep) não alcançam `subjects/` nem `examples/`. A tokenização segue o shell (quebra de linha separa comandos; `#` no meio da palavra não é comentário) e as flags do motor não aceitam abreviação. O motor também se defende: o Python roda com `-E` (ignora `PYTHON*`), a conferência de questões abertas só funciona enquanto a etapa do banco está pendente e `--renomear-de` só aceita pastas de `subjects/`.
5. **Instruções e evals:** o protocolo no `CLAUDE.md` e nas skills, medido pelos cenários de `evals/`.

Limites em [SEGURANCA-E-LIMITES.md](SEGURANCA-E-LIMITES.md).

## Preparação de uma matéria (`/nova-materia`)

Etapas com status em `materia.json`, retomáveis: inventário → perguntas (só o que falta) → ingestão → mapa (agente ingestor + `validar`) → plano (agente planejador opcional + motor) → banco (extração ou escrita, importação, verificação às cegas, `comparar`, conferência das abertas) → contrato e checkpoint. O primeiro `/estudar` acontece numa sessão nova ([ADR 0010](adr/0010-diagnostico-no-primeiro-estudo.md)) e segue o nível do aluno: iniciante começa aprendendo, os outros níveis fazem um diagnóstico curto ([ADR 0011](adr/0011-trilha-completa-por-prioridade.md)).

## Trilha

Todos os conceitos do mapa formam uma trilha, sem cortes: pré-requisitos antes e, entre os prontos, o que mais cai na prova, depois o mais difícil. Um conceito está concluído quando foi estudado (`trilha estudado`, depois da explicação) e praticado com pelo menos 2 respostas. O plano é recalculado a cada sessão: o que não terminou volta nos dias seguintes, e a trilha só termina com todos os conceitos concluídos ([ADR 0011](adr/0011-trilha-completa-por-prioridade.md)).

## Heurísticas e parâmetros

Todos ajustáveis e declarados como escolhas de projeto, não resultados de pesquisa:

| Parâmetro | Valor | Onde | Por quê |
|---|---|---|---|
| Intervalos SM-2 | 1, 6, ×EF; EF mínimo 1,3 | `srs` | Algoritmo SM-2 como descrito por Wozniak (1990), com as adaptações listadas em [CIENCIA-DA-APRENDIZAGEM.md](CIENCIA-DA-APRENDIZAGEM.md#prática-espaçada). |
| Teto do intervalo | 50% dos dias até a prova, piso de 2 dias para item estabelecido | `srs` | Calibrado por simulação: 4 a 9 revisões para provas de 1 semana a 2 meses, sem revisão diária no fim. |
| Teto na véspera | nenhuma revisão depois da véspera | `srs` | Lição do projeto anterior: o objetivo é reter até a prova. |
| Limite diário | 15 por matéria; 30 no total | `srs` | Evitar sessões só de revisão. |
| Meia-vida da evidência | 21 dias | `learner` | Tentativas antigas valem menos. |
| "Dominado" | acerto estimado ≥ 0,85, faixa inferior ≥ 0,7, evidência ≥ 3 | `learner` | Convenção prática. Modelos de rastreamento de conhecimento usam outra escala (probabilidade de domínio latente). |
| Dica decisiva | 3 ou mais degraus contam como erro | `learner` | Acertar depois de ver o primeiro passo não é resolver sozinho. |
| Confiança → probabilidade | 1→0,2; 2→0,4; 3→0,6; 4→0,8; 5→0,95 | `learner` | Escala simples para a calibração (Brier). |
| Cobertura mínima do preparo | 50% do peso com 2+ tentativas | `learner` | Sem dados, a faixa seria enganosa. |
| Prioridades da seleção | erro 3 (+1,5 com confiança alta); acerto inseguro 2; nova 1 | `selection` | Ordem herdada do projeto anterior, mantida simples. |
| Simulados no plano | D-3 completo, D-2 reforço, D-1 leve | `planner` | Lição do projeto anterior. |
| Ordem da trilha | pré-requisitos; peso efetivo (herdado de quem o conceito libera); peso; com questões antes de sem questões; mais difícil antes | `knowledge_map` | Decisão do usuário: frequência na prova, depois dificuldade, sem cortar nada. |
| Concluído na trilha | estudado + 2 respostas (sem "não sei", depois de revelação ou aberta sem nota) | `planner`, `learner` | Explicação mais prática mínima antes de avançar. |
| Ritmo recomendado | 1 conceito novo a cada 30 (iniciante), 20 (intermediário) ou 15 min (avançado); sem tempo informado, 3 por dia | `planner` | Só para avisar quando o plano aperta; nunca corta conceitos. |
| Diagnóstico | 4 questões; nenhum para iniciante | `selection`, `planner` | O pré-teste é curto e não substitui a explicação para quem nunca viu a matéria. |
| Treino de conceito novo | questões da mais fácil para a mais difícil; respondidas nas últimas 24 h por último | `selection` | Exemplo resolvido, depois prática com apoio que diminui. |

## Pontos de extensão

- **Novo agendador:** implemente `Scheduler.next_state` em `tutor/srs.py`, registre em `SCHEDULERS` e escolha em `materia.json` (`revisao.algoritmo`).
- **Novo subcomando:** função `cmd_*` que devolve um dicionário com `status` e registro em `add_commands` do módulo. O teste `EverySubcommandTest` garante o contrato JSON.
- **Nova skill ou agente:** veja [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md).
- **Tipos de erro próprios:** `configurar --tipo-erro-extra <tipo>`.
