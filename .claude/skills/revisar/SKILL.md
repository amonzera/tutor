---
name: revisar
description: Só as revisões espaçadas vencidas hoje, em recordação livre (o aluno explica de memória). Use quando o aluno quiser revisar ou tiver pouco tempo.
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Revisão espaçada

Matéria: `$ARGUMENTS` (vazio: a última usada ou a única).

1. `bash bin/tutor.sh contexto --materia <slug>` e depois `revisao listar --materia <slug>`. Sem revisões vencidas: diga a data da próxima e ofereça `/quiz` ou `/estudar`.
2. Para cada conceito em `hoje`, um por vez:
   - Peça a explicação de memória, sem consultar: "Explique <conceito> com suas palavras" (varie: "como você ensinaria isso a um colega?", "qual é a ideia central?", "dê um exemplo").
   - Avalie e registre com `revisao registrar --conceito <id> --nota <nota>`: `facil` (claro e completo, rápido), `bom` (correto com pequena hesitação), `dificil` (precisou de uma pista), `esqueci` (não lembrou ou errou a ideia central).
   - Esqueceu: não dê a resposta de cara. Faça uma pergunta que leve à ideia, depois explique em poucas linhas e peça que ele reformule.
3. Se houver `excedentes`, diga que ficaram para amanhã (limite diário).
4. Escreva `estado/proximo-passo.md` (o que ficou fraco) e rode `checkpoint --materia <slug>`.
