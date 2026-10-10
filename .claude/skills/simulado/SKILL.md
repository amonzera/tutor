---
name: simulado
description: Prova completa em tempo real, estratificada como a prova de verdade, sem feedback até o fim; depois correção, análise de erros e comparação com a previsão.
argument-hint: "[matéria] [número de questões]"
allowed-tools: Bash(bash bin/tutor.sh *)
disable-model-invocation: true
---

# Simulado

Argumentos: `$ARGUMENTS`.

1. `bash bin/tutor.sh contexto --materia <slug>`. Se houver `simulado_em_andamento`, retome: `simulado estado` mostra o tempo e as questões que faltam.
2. Combine as regras: tempo, sem consulta, sem dicas, só calculadora se a prova permitir (veja o `contrato`). Pergunte se pode começar.
3. `simulado iniciar --materia <slug> [--n N]`. Banco insuficiente: ofereça um simulado menor. Não mostre a previsão agora (para não ancorar o aluno).
4. Para cada questão: `apresentar --questao <id>` (vai no modo simulado sozinho), mostre só o enunciado e as alternativas, receba resposta e confiança e registre com `simulado responder`. **Não comente acerto, erro nem dê dicas.** A cada poucas questões, `simulado estado` para avisar o tempo restante.
5. Tempo esgotado ou fim: `simulado encerrar`. Agora corrija: nota, tempo, erros por tema, erros com confiança alta (prioridade). Para cada erro, pergunte o que ele pensou e `classificar`.
6. Compare com a `previsao` (se houver): diga se o resultado ficou dentro da faixa, sem transformar isso em promessa sobre a prova real.
7. Monte uma lista de reforço de 3 a 5 conceitos; `revisao agendar` (ou `revisao registrar --nota esqueci` para os já agendados), `estado/proximo-passo.md` e `checkpoint --materia <slug>`.
