# ADR 0006: domínio por conceito com Beta-Bernoulli e decaimento

- Status: aceita
- Data: 2026-10-09

## Contexto

O projeto anterior media desempenho só por questão. A tarefa pedia um modelo por conceito, simples e testável (por exemplo, Elo ou BKT simplificado), com decaimento, e um preparo estimado com incerteza declarada.

## Decisão

Domínio de um conceito = probabilidade de acertar uma questão nova dele, estimada por Beta-Bernoulli: cada tentativa soma acerto (1), erro (0) ou parcial (0,5), com peso que cai pela metade a cada 21 dias. O piso é a chance de acerto no chute. Tentativas com 3 ou mais dicas contam como erro; tentativas logo depois de ver a resposta não contam. O preparo estimado vem da mesma Beta, por simulação com semente fixa, e só aparece com cobertura mínima.

## Alternativas consideradas

- **BKT (rastreamento bayesiano de conhecimento):** estima a probabilidade de domínio de cada habilidade com parâmetros próprios por habilidade, que, com poucas tentativas por aluno, ficariam nos valores chutados.
- **Elo:** simples e robusto, mas não entrega a incerteza de que o preparo precisa.
- **Rastreamento profundo (DKT):** exige muitos dados de muitos alunos.

## Consequências

- O painel mostra uma faixa ("entre 40% e 70%"), não um número enganosamente preciso.
- Um teste com aluno sintético confere que a faixa de 80% do preparo cobre a nota real na proporção esperada.
- Limites (todos os conceitos de uma questão recebem a mesma evidência; não há transferência entre conceitos) estão em [CIENCIA-DA-APRENDIZAGEM.md](../CIENCIA-DA-APRENDIZAGEM.md).
