---
name: erros
description: Caderno de erros da matéria: padrões recorrentes por conceito, tipo de erro e armadilha escolhida, sem revelar respostas. Use para entender o que mais derruba o aluno.
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Caderno de erros

Matéria: `$ARGUMENTS`.

1. `bash bin/tutor.sh erros --materia <slug> --escrever` (atualiza `estado/caderno-de-erros.md`).
2. Mostre primeiro os padrões `recorrente`. Para cada um, peça que o aluno explique por que aquela armadilha engana e como reconhecê-la na próxima vez (é ele quem formula a regra).
3. Ofereça praticar o conceito com `/quiz <slug> <tema>` ou `proximas --conceito <id>`. Não revele respostas de questões: elas voltam.
