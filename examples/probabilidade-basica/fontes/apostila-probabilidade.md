# Apostila de Probabilidade Básica

> Material fictício e original, escrito para demonstrar o tutor. Pode ser usado e adaptado livremente (licença MIT do repositório).

## Experimento aleatório e espaço amostral

Um experimento é aleatório quando, repetido nas mesmas condições, pode dar resultados diferentes e não sabemos de antemão qual sairá. Lançar um dado, sortear uma carta e escolher um estudante ao acaso são exemplos.

O espaço amostral, indicado por Ω, é o conjunto de todos os resultados possíveis. No lançamento de um dado, Ω = {1, 2, 3, 4, 5, 6}. Quando o experimento tem etapas, o número de resultados é o produto do número de resultados de cada etapa: lançar uma moeda e um dado gera 2 × 6 = 12 resultados.

Atenção: listar os resultados não garante que eles tenham a mesma chance. Ao anotar a soma de dois dados, os resultados vão de 2 a 12, mas a soma 7 aparece em seis combinações e a soma 2 em apenas uma.

## Eventos e operações

Um evento é um subconjunto do espaço amostral, ou seja, um grupo de resultados. No dado, "sair par" é o evento A = {2, 4, 6}.

- União A ∪ B: acontece A, B ou ambos.
- Interseção A ∩ B: acontecem A e B ao mesmo tempo.
- Complementar de A (indicado por Aᶜ): tudo o que está em Ω e não está em A.

Dois eventos são mutuamente exclusivos quando não podem ocorrer juntos, isto é, A ∩ B = ∅. Exemplo: "sair 1" e "sair par".

## Probabilidade clássica

Quando todos os resultados de Ω são igualmente prováveis, a probabilidade de um evento é

P(A) = (número de casos favoráveis) / (número de casos possíveis).

Exemplo: no dado honesto, P(sair maior que 4) = 2/6 = 1/3, porque os favoráveis são 5 e 6. Toda probabilidade fica entre 0 e 1. Cuidado com o denominador: ele é o total de resultados possíveis, não o número de casos desfavoráveis.

## Contagem: princípio multiplicativo e combinações

Princípio multiplicativo: se uma escolha tem m opções e outra, independente dela, tem n opções, as duas juntas têm m × n possibilidades. Senhas de 3 dígitos com repetição permitida: 10 × 10 × 10 = 1000.

Quando a ordem importa e não há repetição, contamos arranjos: escolher presidente e vice entre 6 pessoas dá 6 × 5 = 30 possibilidades. Quando a ordem não importa, contamos combinações:

C(n, k) = n! / (k! (n − k)!).

Comissões de 2 pessoas entre 6: C(6, 2) = 15. A pergunta-chave é sempre: trocar a ordem gera um resultado diferente?

## Regra da soma e evento complementar

Para eventos mutuamente exclusivos, P(A ∪ B) = P(A) + P(B). Em geral, é preciso descontar a interseção, que foi contada duas vezes:

P(A ∪ B) = P(A) + P(B) − P(A ∩ B).

Exemplo: no baralho de 52 cartas, P(ás ou copas) = 4/52 + 13/52 − 1/52 = 16/52, porque o ás de copas está nos dois eventos.

Como A e Aᶜ cobrem tudo e não se sobrepõem, P(Aᶜ) = 1 − P(A). Se a probabilidade de defeito numa peça é 0,08, a de não ter defeito é 0,92.

## Probabilidade condicional

A probabilidade de A sabendo que B ocorreu é

P(A | B) = P(A ∩ B) / P(B), com P(B) > 0.

A ideia é que a informação "B ocorreu" encolhe o universo para B. Numa turma de 40 estudantes, 24 estudam de manhã e 6 deles trabalham. Sabendo que o sorteado estuda de manhã, P(trabalha | manhã) = 6/24 = 1/4, e não 6/40.

Armadilha clássica: P(A | B) e P(B | A) em geral são diferentes. A chance de haver trânsito quando chove não é a mesma que a chance de estar chovendo quando há trânsito.

## Regra do produto

Reorganizando a definição de probabilidade condicional:

P(A ∩ B) = P(A) · P(B | A).

Exemplo: uma urna tem 3 bolas vermelhas e 2 azuis; retiram-se duas sem reposição. P(duas vermelhas) = 3/5 · 2/4 = 3/10. Sem reposição, a segunda retirada depende da primeira, por isso a segunda fração muda.

## Independência

A e B são independentes quando saber que um ocorreu não muda a probabilidade do outro: P(A | B) = P(A). Equivalentemente,

P(A ∩ B) = P(A) · P(B).

Dois lançamentos de uma moeda honesta são independentes: P(cara e cara) = 1/2 · 1/2 = 1/4.

Não confunda independentes com mutuamente exclusivos. Eventos mutuamente exclusivos com probabilidades positivas nunca são independentes: se um ocorre, o outro fica impossível.

## Probabilidade total

Quando o espaço amostral se divide em casos que não se sobrepõem (B₁, B₂, ...), a probabilidade de A é a soma ponderada:

P(A) = P(A | B₁) P(B₁) + P(A | B₂) P(B₂) + ...

Exemplo: duas máquinas fazem peças. A máquina 1 faz 60% delas, com 2% de defeito; a máquina 2 faz 40%, com 5% de defeito. P(defeito) = 0,02 · 0,6 + 0,05 · 0,4 = 0,032. Um diagrama de árvore ajuda a não esquecer nenhum ramo.

## Teorema de Bayes

Bayes inverte a condicional usando a probabilidade total no denominador:

P(B₁ | A) = P(A | B₁) P(B₁) / P(A).

No exemplo das máquinas, se uma peça tem defeito, a chance de ter vindo da máquina 2 é 0,05 · 0,4 / 0,032 = 0,625.

Exames diagnósticos são o caso mais conhecido: com uma doença rara, mesmo um teste bom produz muitos falsos positivos, e a chance de estar doente dado um resultado positivo pode ser bem menor do que a sensibilidade do teste. Pensar em frequências (de 1000 pessoas, quantas são doentes e dão positivo?) costuma deixar isso claro.

## Variável aleatória discreta e esperança

Uma variável aleatória associa um número a cada resultado do experimento. Se X assume os valores x₁, x₂, ... com probabilidades p₁, p₂, ..., sua esperança (valor esperado) é a média ponderada:

E[X] = x₁ p₁ + x₂ p₂ + ...

Um jogo que paga R$ 10 com probabilidade 0,2 e nada no resto tem E[pagamento] = 10 · 0,2 = R$ 2. A esperança não precisa ser um valor que X realmente assume; ela descreve a média no longo prazo.

## Distribuição binomial

Repetimos n vezes, de forma independente, um ensaio com probabilidade p de sucesso. O número X de sucessos tem distribuição binomial:

P(X = k) = C(n, k) · pᵏ · (1 − p)ⁿ⁻ᵏ.

O fator C(n, k) conta em quais das n tentativas os sucessos aparecem. Exemplo: em 4 lançamentos de moeda honesta, P(exatamente 2 caras) = C(4, 2) · (1/2)⁴ = 6/16. A esperança da binomial é n · p.
