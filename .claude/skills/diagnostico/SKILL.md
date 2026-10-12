---
name: diagnostico
description: Pré-teste para mapear o que o aluno já sabe, com uma questão por conceito (começando pelos fundamentos). Ajusta o plano depois. Use no início de uma matéria ou quando o plano parecer errado.
argument-hint: "[matéria] [número de questões]"
allowed-tools: Bash(bash bin/tutor.sh *)
disable-model-invocation: true
---

# Diagnóstico

Argumentos: `$ARGUMENTS`.

1. `bash bin/tutor.sh contexto --materia <slug>`. Aluno de nível iniciante: diga numa frase que errar é esperado e que, se preferir aprender antes, o `/estudar` começa pela explicação; depois siga com o pré-teste, que ele pediu (sem esperar confirmação).
2. Explique: é um pré-teste curto; errar é esperado e ajuda a montar o plano; "não sei" também vale; tentar antes de estudar também ajuda a aprender depois.
3. `proximas --materia <slug> --modo diagnostico [--n N]` (padrão: 4 questões).
4. Para cada questão: `apresentar --modo diagnostico` → resposta e confiança → `corrigir` → explicação curta (uma ou duas frases, sem aula) → `classificar`, se errou.
5. No fim: `painel --materia <slug>` resumido (o que já sabe, o que é novo) e `plano --materia <slug> --escrever` para reordenar o calendário pelos resultados. `estado/proximo-passo.md` e `checkpoint --materia <slug>`.
