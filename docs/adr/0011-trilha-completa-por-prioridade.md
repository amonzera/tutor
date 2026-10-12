# ADR 0011: trilha completa por prioridade e primeira sessão conforme o nível

- Status: aceita
- Data: 2026-10-11

## Contexto

Na primeira sessão real de um aluno iniciante, com prova em 6 dias, o tutor abriu com um diagnóstico de 8 questões de prova, sem ensinar nada: o nível estava gravado, mas o fluxo da primeira sessão o ignorava ([ADR 0010](0010-diagnostico-no-primeiro-estudo.md)). O plano do primeiro dia tinha 7 conceitos, e os textos do replanejamento sugeriam cortar conceitos quando o tempo apertasse.

## Decisão

- **Trilha completa.** Todos os conceitos do mapa entram na trilha; nenhum é cortado nem fica "para depois". A trilha só termina quando todos estiverem concluídos.
- **Ordem.** Pré-requisitos sempre antes. Entre os conceitos prontos, primeiro o que mais cai na prova (`peso`); entre empatados, o mais difícil (média da `dificuldade` das questões). Um pré-requisito leve herda o peso do conceito que ele libera, para não ir para o fim.
- **Concluído.** O conceito foi estudado (o tutor roda `trilha estudado` depois de explicá-lo) e praticado com pelo menos 2 respostas, sem contar "não sei", respostas logo depois de ver a solução nem abertas sem nota. Agendar revisão não serve como marca, porque `/quiz`, `/simulado` e `/ensinar` também agendam.
- **Calendário.** Os conceitos pendentes, na ordem da trilha, são distribuídos por contagem pelos dias livres (sem dias livres, por todos os dias). O que não terminar num dia volta no seguinte, porque o plano é recalculado a cada sessão. O motor compara o ritmo necessário com um ritmo recomendado para o tempo diário e o nível (heurística: um conceito novo a cada 30, 20 ou 15 minutos para iniciante, intermediário e avançado) e, se o necessário passar do recomendado, sugere mais tempo por dia ou mais dias de estudo, nunca cortes.
- **Primeira sessão.** O texto de boas-vindas é fixo, por nível, e sai do motor: o hook de início de sessão o mostra direto ao aluno (o `systemMessage` não passa pelo modelo, que nos testes o omitiu em parte das vezes), e o `contexto` o devolve para a skill repetir. Aluno iniciante não faz diagnóstico: cada conceito começa com explicação baseada nas fontes, exemplo resolvido e questões da mais fácil para a mais difícil. Os outros níveis fazem um diagnóstico de 4 questões, em que "não sei" vale.
- **Conceito sem questões suficientes.** Fica na trilha, marcado em `sem_questoes`, e o tutor gera e verifica questões para ele (escritor, verificador, `banco comparar`).

## Alternativas consideradas

- **Cortar ou deixar "se sobrar tempo" os conceitos de menor peso:** recusada pelo usuário; o aluno acaba sem estudar parte da matéria.
- **Concluído só quando "dominado"** (acerto estimado de 85%): mais rigoroso, mas a trilha poderia não terminar antes da prova.
- **Marcar "estudado" pelas revisões agendadas:** simples, mas outras skills também agendam sem explicar.

## Consequências

- `plano.md`, o painel e o diário mostram "Trilha: X de Y conceitos concluídos".
- Com pouco tempo até a prova, o calendário fica pesado, mas completo, e o aviso de ritmo diz isso com franqueza.
- O ritmo recomendado e o limiar de 2 respostas são heurísticas ajustáveis (`modelo_aluno.respostas_para_concluir` em `materia.json`).
