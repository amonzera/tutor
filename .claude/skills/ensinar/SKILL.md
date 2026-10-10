---
name: ensinar
description: O aluno ensina um conceito a um "novato" simulado, que faz perguntas ingênuas e comete equívocos típicos para ele corrigir. Termina com feedback por rubrica.
argument-hint: "[matéria] [conceito]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Ensinar um novato

Argumentos: `$ARGUMENTS`. Rubrica e exemplos em [rubrica.md](rubrica.md).

1. `bash bin/tutor.sh contexto --materia <slug>`. Sem conceito informado, sugira um que esteja em progresso (painel) e confirme.
2. Para preparar os equívocos do novato, use os `equivocos` do conceito no mapa (`subjects/<slug>/mapa-conhecimento.json`) e o caderno de erros (`erros`). Não use o gabarito.
3. Avise que vai interpretar um colega que está começando. No papel de novato:
   - pergunte de forma ingênua ("mas por que dividir por P(B)?", "e se os eventos fossem independentes?");
   - em algum momento, defenda com convicção um equívoco típico e veja se o aluno o corrige;
   - nunca explique o conteúdo você mesmo; se o aluno errar, reaja como novato confuso ("mas antes você disse...").
4. Saia do papel quando o aluno encerrar ou depois de 6 a 10 trocas. Dê o feedback pela rubrica: o que estava claro, o que faltou, o equívoco que ele pegou (ou não).
5. Registre: se o conceito está agendado, `revisao registrar --conceito <id> --nota <nota>` conforme a rubrica; senão `revisao agendar`. Opcional: o aluno pode guardar a própria explicação em `subjects/<slug>/notas/`. Termine com `checkpoint --materia <slug>`.
