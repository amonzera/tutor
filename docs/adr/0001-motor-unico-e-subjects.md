# ADR 0001: motor único com as matérias em `subjects/`

- Status: aceita
- Data: 2026-10-09

## Contexto

O projeto anterior era um tutor de uma matéria só: para estudar outra, a orientação era copiar a pasta inteira. As cópias divergem (uma correção feita numa não chega às outras), e não há visão entre matérias.

## Decisão

Um único clone do repositório contém o motor, as skills e os agentes. Cada matéria é uma pasta em `subjects/<slug>/`, ignorada pelo git. O aluno atualiza o tutor com `git pull` sem tocar nos próprios dados.

## Alternativas consideradas

- **Um clone por matéria:** isola tudo, mas as cópias divergem e não há calendário entre matérias. Continua possível (cada clone com uma matéria só) e está documentado no README.
- **Plugin do Claude Code:** melhor para distribuir atualizações, mas acrescenta empacotamento e marketplace, e os dados do aluno precisariam de outro lugar. Fica no roadmap.

## Consequências

- Privacidade por padrão: nada em `subjects/` vai para o git deste repositório.
- Revisões e orçamento diário podem considerar todas as matérias (`revisao listar --todas`).
- Quem quiser versionar uma matéria cria um repositório privado dentro da pasta dela.
