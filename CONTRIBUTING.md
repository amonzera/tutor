# Como contribuir

Obrigado pelo interesse. Contribuições são bem-vindas: correções, novas skills, melhorias no motor, documentação e cenários de avaliação.

## Antes de começar

- Leia o [código de conduta](CODE_OF_CONDUCT.md).
- Para mudanças grandes (novo módulo, mudança de formato de dados, novo agente), abra uma issue antes, descrevendo o problema e a proposta.
- Veja [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md): estrutura, testes, como criar uma matéria de teste, como acrescentar subcomandos, skills e agentes.

## Regras do projeto

- **Só biblioteca padrão** no motor. Nada de `pip install`.
- **Nada de material de terceiros**: provas, listas, apostilas, gabaritos ou trechos de livros. Exemplos e fixtures são originais e fictícios.
- **Nada pessoal**: caminhos da sua máquina, e-mails, dados de estudo. `python tools/verificar.py privacidade` ajuda.
- **Português do Brasil** em tudo o que o aluno vê; identificadores de código em inglês.
- **Afirmações científicas** só com referência verificada em [docs/REFERENCIAS.md](docs/REFERENCIAS.md).
- **Sem emojis** na documentação.

## Fluxo

1. Faça um fork e crie uma branch (`feat/nome-curto`, `fix/nome-curto`).
2. Escreva testes junto com o código.
3. Rode `python tools/verificar.py` até não haver falhas.
4. Se mexeu em skills ou no protocolo, rode os cenários relevantes de `evals/` e conte o resultado no PR.
5. Commits em [Conventional Commits](https://www.conventionalcommits.org/pt-br/) (`feat:`, `fix:`, `docs:`, `test:`...).
6. Abra o PR preenchendo o modelo.
