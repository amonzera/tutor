# ADR 0009: reimplementação limpa, com crédito ao learn-faster-kit

- Status: aceita
- Data: 2026-10-09

## Contexto

O projeto de estudo que originou este repositório foi montado sobre o [learn-faster-kit](https://github.com/hluaguo/learn-faster-kit), de Hugo Lau, sob licença MIT. A licença é compatível, mas a arquitetura nova (motor único, matérias em pastas, banco protegido, modelo do aluno) não aproveita o código dele.

## Decisão

Reimplementar do zero, sem copiar arquivo, trecho de código ou texto do learn-faster-kit, e creditar no [NOTICE](../../NOTICE) as ideias de partida: conduzir o estudo por comandos do Claude Code, agendar revisões espaçadas e devolver um campo `llm_directive` nos scripts. O mnemônico FASTER (Jim Kwik) é creditado como inspiração de organização, sem tratá-lo como modelo validado.

## Consequências

Não há obrigação de reproduzir o aviso de licença do learn-faster-kit, porque nada dele foi copiado. O crédito fica por honestidade.
