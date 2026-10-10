---
name: progresso
description: Painel da matéria: domínio por conceito com incerteza, acerto por tema, tipos de erro, calibração, preparo estimado e próximas ações. Use quando o aluno perguntar como está indo.
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Progresso

Matéria: `$ARGUMENTS`.

1. `bash bin/tutor.sh painel --materia <slug> --escrever` (atualiza `estado/dominio.md`).
2. Mostre, em poucas linhas e uma tabela curta:
   - conceitos mais fracos, com a faixa de incerteza ("entre 40% e 70%");
   - tipo de erro dominante e o que ele sugere;
   - calibração: a confiança acompanha o acerto?
   - preparo estimado **com a faixa e o aviso**; se indisponível, o que praticar para ter dados.
3. Termine com as `proximas_acoes`. Comemore progresso real (mais acertos, menos erros com confiança alta), sem exagero e sem prometer nota.
