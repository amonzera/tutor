# ADR 0010: diagnóstico no primeiro `/estudar`, não no fim do `/nova-materia`

- Status: aceita
- Data: 2026-10-09

## Contexto

O pipeline original previa aplicar o diagnóstico no fim da preparação da matéria. A preparação passa por rascunhos de questões com resposta e por relatórios de agentes; fazer o pré-teste na mesma sessão arrisca vazamento de respostas pelo contexto e compactação no meio de um processo longo.

## Decisão

O `/nova-materia` termina pedindo uma sessão nova (ou `/clear`). O primeiro `/estudar` detecta que não há tentativas e começa pelo diagnóstico (`proximas --modo diagnostico`).

## Consequências

- O diagnóstico acontece num contexto limpo, com o mesmo protocolo de todas as sessões.
- `/diagnostico` continua disponível para refazer o pré-teste a qualquer momento.
