# ADR 0005: revisão espaçada SM-2 limitada pela data da prova

- Status: aceita
- Data: 2026-10-09

## Contexto

O projeto anterior usava uma escada fixa de intervalos (1, 2, 4, 7 dias) para todos os conceitos. Isso ignora a dificuldade de cada item e não se ajusta ao tempo até a prova.

## Decisão

- Itens de revisão são **conceitos** do mapa, não questões (revisar a mesma questão ensina a letra, não a ideia).
- Agendador padrão `sm2-prova`: SM-2 (fator de facilidade por item, lapso volta ao início), com notas esqueci, difícil, bom e fácil. As diferenças em relação à descrição original estão em [CIENCIA-DA-APRENDIZAGEM.md](../CIENCIA-DA-APRENDIZAGEM.md#prática-espaçada).
- O intervalo não passa de 50% dos dias até a prova, com piso de 2 dias para item já estabelecido, e nenhuma revisão cai depois da véspera. Os números foram escolhidos por simulação ([ARQUITETURA.md](../ARQUITETURA.md)) e são declarados como heurística.
- Limite diário por matéria e orçamento entre matérias aplicados na leitura (triagem), sem reagendar.
- Interface `Scheduler` substituível; `escada-fixa` existe para migração do formato antigo.

## Alternativas consideradas

- **Escada fixa:** simples, mas não diferencia itens.
- **FSRS:** modelo de memória mais recente, com estabilidade, dificuldade e recuperabilidade por item e 21 parâmetros ajustáveis aos dados na versão 6. Há valores padrão, mas ajustá-los ao aluno pede um histórico de revisões que uma matéria nova ainda não tem. Fica no roadmap.
- **Teto de 25% dos dias restantes:** a simulação mostrou revisões diárias na última semana, até de conceitos fáceis.

## Consequências

- Prova próxima comprime as revisões; prova distante deixa o SM-2 espaçar.
- Depois da prova, as revisões continuam sem teto (modo manutenção).
