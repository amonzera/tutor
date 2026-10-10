---
name: quiz
description: Rodada curta de 5 questões intercaladas, com resposta e confiança antes da correção. Aceita um tema. Use para praticar rápido ou atacar um ponto fraco.
argument-hint: "[matéria] [tema]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Quiz rápido

Argumentos: `$ARGUMENTS` (matéria e, opcionalmente, um tema).

1. `bash bin/tutor.sh contexto --materia <slug>` (leia o `contrato`).
2. `proximas --materia <slug> --modo quiz [--tema <tema>]`. Tema desconhecido: mostre os temas do painel e pergunte.
3. Para cada questão: `apresentar` → resposta e confiança → escada de dicas, se ele não souber → `corrigir` (com `--dicas`) → feedback curto (acertou: por que as outras falham; errou: o distrator escolhido e a solução) → `classificar`, se errou.
4. No fim: placar, padrão de erro (se houver) e um conceito para revisar. `revisao agendar` para conceitos novos, `estado/proximo-passo.md` e `checkpoint --materia <slug>`.
