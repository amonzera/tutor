---
name: estudar
description: Sessão diária de estudo guiada. Retoma o checkpoint, faz as revisões vencidas, escolhe o foco do dia e conduz questões no modo tenta-primeiro, terminando com ensinar de volta e checkpoint. Use quando o aluno quiser estudar.
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Sessão de estudo

Matéria pedida: `$ARGUMENTS` (vazio: a última usada ou a única existente).

Siga o protocolo do `CLAUDE.md` da raiz durante toda a sessão. Uma questão por vez; nada de resposta antes do compromisso do aluno.

## 1. Retomar

1. Rode `bash bin/tutor.sh contexto --materia <slug>` (sem `--materia` se não veio argumento). Com `materia_ambigua`, pergunte qual matéria (AskUserQuestion, opções da lista `materias`).
2. Leia o `contrato` (regras desta matéria), o `proximo_passo` e o `diario_recente`. Siga o `llm_directive`.
3. Etapas de preparação pendentes: sugira `/nova-materia <slug>` e pare. Simulado em andamento: ofereça retomar (`/simulado`) ou encerrar.

## 2. Tempo e energia

Pergunte (AskUserQuestion) quanto tempo há hoje e a energia de 1 a 5. Energia baixa: sessão leve (revisões e duas questões).

## 3. Pendências e revisões

- Erros sem classificação (`pendencias.classificar`): pergunte o que o aluno pensou e classifique com `classificar`.
- Revisões vencidas (`revisoes.hoje`), uma por vez, em recordação livre: "explique <conceito> com suas palavras, sem consultar". Avalie e registre com `revisao registrar --conceito <id> --nota esqueci|dificil|bom|facil`. Esqueceu: faça uma pergunta que leve à ideia, explique em poucas linhas e peça que ele reformule.

## 4. Primeira sessão

Se `primeira_sessao` for verdadeiro, explique em três linhas como o tutor funciona (tenta primeiro, confiança, dicas em escada) e faça o diagnóstico com `proximas --modo diagnostico`: correções curtas, sem aula longa; errar aqui é esperado.

## 5. Foco do dia

Use `plano_hoje.conceitos` (ou, sem plano para hoje, o conceito mais fraco do `painel`). Para cada conceito:

- Iniciante nele (sem dados ou fraco): exemplo resolvido curto, com base nas fontes (`buscar`, `texto`; cite arquivo e página), depois questões com dicas que vão sumindo.
- Já domina o básico: problema primeiro.

Questões com `proximas --conceito <id>` (ou `proximas`, intercaladas). Em cada uma: `apresentar` → resposta e confiança → escada de dicas, se ele não souber → `corrigir` (com `--dicas`) → feedback → `classificar`, se errou. Conte com `calc` antes de afirmar números.

## 6. Ensinar de volta

No fim, peça que ele explique o conceito principal do dia como se ensinasse um colega. Avalie: está correto? completo? tem exemplo? trata o caso-limite? Dê feedback sobre o raciocínio.

## 7. Fechar

1. `revisao agendar --conceito <id>` para cada conceito estudado.
2. Escreva `subjects/<slug>/estado/proximo-passo.md` com 3 a 6 linhas: o que fazer na próxima sessão e as dúvidas em aberto.
3. `checkpoint --materia <slug>` e diga ao aluno quando deveria ser a próxima sessão e qual o foco.
