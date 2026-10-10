# ADR 0007: guarda PreToolUse e verificador cego por construção

- Status: aceita
- Data: 2026-10-09

## Contexto

O campo `tools` de um subagente aceita só nomes de ferramenta, não padrões como `Bash(...)`: um verificador com Bash poderia ler as fontes (onde muitas vezes está o gabarito) e deixaria de ser independente. No projeto anterior, a verificação do gabarito não foi totalmente cega porque os agentes viram a marca da resposta nas imagens das páginas.

## Decisão

Um hook `PreToolUse` (matcher `Bash|Read|Grep|Glob`) roda `bin/guarda.sh`. O caminho rápido em sh (sem diferenciar maiúsculas) só chama a política em Python (`tutor/guard.py`) quando o evento menciona algo relevante. A política usa o campo `agent_type` do evento:

- `verificador` só roda, literalmente, `bash bin/tutor.sh apresentar ... --modo verificacao`, `calc` e `banco registrar-verificacao`: uma expressão regular sobre o comando inteiro recusa operadores, variáveis, comentários e quebras de linha;
- `texto --protegido` e `renderizar` só para o `ingestor-de-fontes`; `registrar-verificacao` só para o `verificador`;
- `banco exportar` nunca por agente (e também por regra `deny` no `settings.json`);
- chamadas ao motor não levam variáveis de ambiente na frente, e variáveis que executam código não podem ser definidas;
- fora do motor, nada toca arquivos protegidos;
- buscas recursivas (inclusive a ferramenta Grep) não alcançam `subjects/` nem `examples/` (há `bash bin/tutor.sh buscar`).

Uma auditoria de segurança independente encontrou contornos na primeira versão (`#` e quebra de linha escondendo comandos, abreviação de flags, `BASH_ENV`, outro script chamado `tutor.sh`); todos viraram testes de regressão em `tests/test_guard.py`.

## Consequências

- O verificador tem `tools: Bash` e nada mais, e usa um modelo diferente do escritor.
- Desenvolvedores também são afetados (por exemplo, `grep -r` a partir da raiz é negado): restrinja a busca a `tutor/`, `tests/` e `docs/`.
- A guarda falha aberta (erro interno não bloqueia nada); a proteção principal continua estrutural.
- Hooks de projeto só rodam depois de o aluno aceitar a confiança na pasta (no `claude -p`, rodam sempre).
