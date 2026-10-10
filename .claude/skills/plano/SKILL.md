---
name: plano
description: Replaneja o calendário de estudo quando algo muda (nova data de prova, dias perdidos, mais ou menos tempo por dia, prioridades).
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
disable-model-invocation: true
---

# Replanejar

Matéria: `$ARGUMENTS`.

1. `bash bin/tutor.sh contexto --materia <slug>` e `plano --materia <slug>` para ver o plano atual.
2. Pergunte o que mudou (AskUserQuestion): data da prova (confirmada ou provisória), tempo diário, dias por semana, conceitos a priorizar ou deixar de lado.
3. Grave com `configurar --materia <slug> [--data-prova AAAA-MM-DD] [--data-confirmada sim|nao] [--tempo-diario N] [--dias-semana N]`.
4. Mudança de prioridade entre conceitos: chame o agente `planejador` para ajustar `peso` e ordem no mapa (depois `validar --etapa mapa`).
5. `plano --materia <slug> --escrever` e resuma: dias até a prova, foco desta semana, simulados. Plano apertado: diga com franqueza e proponha cortes; não prometa cobrir tudo.
