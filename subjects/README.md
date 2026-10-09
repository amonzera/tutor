# subjects/

Aqui ficam as suas matérias, uma pasta por matéria. **Nada desta pasta vai para o git**, exceto este arquivo e o `.gitkeep`: seus PDFs, anotações, respostas e histórico de estudo são privados.

## Como criar uma matéria

1. Crie uma pasta com um nome curto, sem acentos nem espaços, por exemplo `calculo-2`.
2. Dentro dela, crie `fontes/` e coloque o material: PDFs, anotações em Markdown ou texto, slides exportados em PDF, listas de exercícios.
3. Provas antigas, listas com gabarito e resoluções vão em `fontes/provas/`. O texto delas fica numa área protegida, para o tutor não ver a resposta antes de você tentar.
4. Abra o Claude Code na raiz do repositório e rode `/nova-materia calculo-2`.

```
subjects/
└── calculo-2/
    └── fontes/
        ├── apostila.pdf
        ├── anotacoes.md
        └── provas/
            └── prova-2025-1.pdf
```

## Privacidade e direitos autorais

- O conteúdo de `subjects/` nunca é enviado para lugar nenhum pelo tutor. Ele é lido localmente pelo Claude Code durante as suas sessões.
- O material que você coloca em `fontes/` continua pertencendo aos seus autores. Use apenas material que você tem direito de usar para estudo pessoal e não o publique.
- Se quiser versionar uma matéria (por exemplo, para não perder o histórico), crie um repositório **privado** só para ela dentro da pasta da matéria. Não remova `subjects/` do `.gitignore` deste repositório.
