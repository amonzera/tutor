---
name: estudar
description: Sessão diária de estudo guiada. Retoma o checkpoint, faz as revisões vencidas, segue os próximos conceitos da trilha (explicação, exemplo e questões no modo tenta-primeiro) e termina com ensinar de volta e checkpoint. Use quando o aluno quiser estudar.
argument-hint: "[matéria]"
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Sessão de estudo

Matéria pedida: `$ARGUMENTS` (vazio: a última usada ou a única existente).

Siga o protocolo do `CLAUDE.md` da raiz durante toda a sessão. Uma questão por vez; nada de resposta antes do compromisso do aluno. Fórmulas em LaTeX.

## 1. Retomar

1. Rode `bash bin/tutor.sh contexto --materia <slug>` (sem `--materia` se não veio argumento). Com `materia_ambigua`, pergunte qual matéria (AskUserQuestion, opções da lista `materias`).
2. Leia o `contrato` (regras desta matéria), o `proximo_passo`, o `diario_recente` e a `trilha`. Siga o `llm_directive`: ele tem precedência sobre o `proximo_passo`.
3. Etapas de preparação pendentes: sugira `/nova-materia <slug>` e pare. Simulado em andamento: ofereça retomar (`/simulado`) ou encerrar.
4. Se vier `boas_vindas`, mostre esse texto exatamente como veio, antes de qualquer outra coisa.

## 2. Tempo, energia e o que o aluno já viu

Num só AskUserQuestion: quanto tempo há hoje, a energia de 1 a 5 e, para os conceitos de hoje (`plano_hoje.conceitos`, ou `trilha.proximos`), o que ele já viu ("nunca vi", "já vi, mas não sei fazer", "sei fazer"). Sem AskUserQuestion, pergunte em texto; sem resposta, vale o nível declarado. Energia baixa: sessão leve (revisões e um conceito); a trilha avança menos, mas nada é pulado.

## 3. Pendências e revisões

- Erros sem classificação (`pendencias.classificar`): pergunte o que o aluno pensou e classifique com `classificar`. Abertas sem nota (`pendencias.avaliar`): avalie com `avaliar`.
- Revisões vencidas (`revisoes.hoje`), uma por vez, em recordação livre: "explique <conceito> com suas palavras, sem consultar". Avalie e registre com `revisao registrar --conceito <id> --nota esqueci|dificil|bom|facil`. Esqueceu: faça uma pergunta que leve à ideia, explique em poucas linhas e peça que ele reformule.

## 4. Primeira sessão

Siga o `llm_directive` do motor:

- **Nível iniciante:** sem diagnóstico. Vá direto ao passo 5, começando pelo primeiro conceito da trilha.
- **Outros níveis:** diagnóstico curto com `proximas --modo diagnostico` (4 questões), correções curtas, sem aula longa; "não sei" é resposta válida e errar aqui é esperado. Depois, passo 5.

## 5. Conceitos do dia (trilha)

Os conceitos de hoje são os próximos da trilha, na ordem: `plano_hoje.conceitos` (sem plano para hoje, `trilha.proximos`). Não pule nenhum: o que não terminar hoje continua na próxima sessão. Para cada conceito:

1. **Explique antes de perguntar**, se o aluno é iniciante ou o conceito é novo para ele: explicação curta com base nas fontes (`buscar`, `texto`; cite arquivo e página) e um exemplo resolvido parecido com as questões. Se ele já sabe fazer, um resumo de duas ou três linhas e problema primeiro. Conceito espacial vem com desenho (seção Figuras do `CLAUDE.md`).
2. Rode `trilha estudado --materia <slug> --conceito <id>`.
3. Questões com `proximas --conceito <id>`, que vêm da mais fácil para a mais difícil. Em cada uma: `apresentar` → resposta e confiança → escada de dicas, se ele não souber → `corrigir` (com `--dicas`) → feedback → `classificar`, se errou. São necessárias pelo menos 2 respostas (fora "não sei") para o conceito ficar concluído. Confira números com `calc` antes de afirmá-los.

Conceitos em `trilha.sem_questoes` não têm questões suficientes: depois da explicação, acione o agente `escritor-de-questoes` para eles e, em seguida, o `verificador`, `banco comparar` e `validar --etapa banco` (como no passo 6 do `/nova-materia`).

## 6. Ensinar de volta

No fim, peça que ele explique o conceito principal do dia como se ensinasse um colega. Avalie: está correto? completo? tem exemplo? trata o caso-limite? Dê feedback sobre o raciocínio.

## 7. Fechar

1. `revisao agendar --conceito <id>` para cada conceito estudado.
2. Escreva `subjects/<slug>/estado/proximo-passo.md` com 3 a 6 linhas: onde a trilha parou (o próximo conceito), o que fazer na próxima sessão e as dúvidas em aberto.
3. `checkpoint --materia <slug>` e diga ao aluno quando deveria ser a próxima sessão, qual o foco e quanto da trilha já foi concluído.
