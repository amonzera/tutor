# tutor

Tutor de estudo guiado com IA, para qualquer matéria, construído sobre o [Claude Code](https://code.claude.com/docs). Você coloca o seu material numa pasta, abre o Claude Code na raiz do repositório e estuda com um tutor que:

- pede a **sua tentativa e a sua confiança antes de ajudar**, dá dicas em escada e explica por que a alternativa que você escolheu é tentadora;
- **protege o gabarito**: a resposta só aparece depois do seu compromisso;
- agenda **revisões espaçadas** até a véspera da prova e monta um **plano reverso** a partir da data;
- mostra o **domínio por conceito com faixa de incerteza**, a sua calibração e um preparo estimado (sem prometer nota);
- cria e **verifica às cegas** as questões a partir das suas fontes;
- **retoma de onde parou** na sessão seguinte, porque toda a memória fica em arquivos.

## Demonstração rápida

Com a matéria de exemplo (fictícia), em menos de um minuto:

```bash
git clone https://github.com/amonzera/tutor.git
cd tutor
bash bin/tutor.sh exemplo        # instala "Probabilidade Básica" em subjects/
claude                           # abra o Claude Code aqui e aceite a confiança na pasta
```

No Claude Code: `/estudar probabilidade-basica`.

## Como usar com a sua matéria (6 passos)

1. `git clone https://github.com/amonzera/tutor.git`
2. Crie `subjects/<nome-da-materia>/fontes/` (nome sem acento nem espaço) e coloque o material: PDFs, anotações `.md` ou `.txt`. Provas antigas e listas com gabarito vão em `fontes/provas/`.
3. Abra o Claude Code **na raiz** do clone e aceite a confiança na pasta.
4. `/materias` lista as matérias e o que vence hoje; uma pasta ainda não preparada aparece como `nova`.
5. `/nova-materia <nome-da-materia>` na primeira vez: perguntas sobre a prova, mapa de conhecimento, plano e banco de questões verificado.
6. `/estudar` todo dia. Sem argumento, usa a última matéria (ou a única).

Detalhes, Windows e problemas comuns: [docs/GUIA-DE-USO.md](docs/GUIA-DE-USO.md).

## Requisitos

- [Claude Code](https://code.claude.com/docs) (terminal, desktop ou IDE).
- Python 3.10 ou mais novo. Nenhum pacote a instalar.
- Opcional: `pdftotext` (poppler) para ler PDFs. Sem ele, converta o material para `.md` ou `.txt`.
- Windows: Git for Windows (o Claude Code usa o Git Bash); de preferência, o repositório dentro do WSL.

## Skills

| Skill | Para quê |
|---|---|
| `/materias` | Matérias, dias até a prova, revisões vencidas. |
| `/nova-materia <pasta>` | Prepara uma matéria nova (retoma se for interrompido). |
| `/estudar [matéria]` | Sessão diária completa. |
| `/revisar` | Só as revisões do dia, de memória. |
| `/quiz [matéria] [tema]` | Cinco questões intercaladas. |
| `/simulado [matéria] [n]` | Prova cronometrada, correção só no fim. |
| `/ensinar [matéria] [conceito]` | Você ensina um "novato" que comete erros típicos. |
| `/diagnostico` | Pré-teste. |
| `/progresso` | Painel com incerteza, erros e calibração. |
| `/plano` | Replaneja quando a data ou o tempo mudam. |
| `/erros` | Caderno de erros. |

## Privacidade, direitos autorais e limites

- `subjects/` (seu material, suas respostas, seu histórico) fica **fora do git**. O tutor não tem telemetria e não envia nada a serviços externos além do que o Claude Code envia ao modelo durante a conversa.
- O material que você coloca em `fontes/` continua pertencendo aos autores: use só para estudo pessoal e não o publique.
- A proteção do gabarito é em camadas, não um cofre. O tutor erra, não substitui aulas e não deve ser usado em avaliações valendo nota. Leia [docs/SEGURANCA-E-LIMITES.md](docs/SEGURANCA-E-LIMITES.md).

## Base científica

Cada recurso está ligado a uma evidência da ciência da aprendizagem (prática de recuperação, espaçamento, intercalação, feedback, calibração, aprender ensinando), com o nível de evidência, os limites e o que a literatura **não** sustenta (estilos de aprendizagem, números mágicos da "curva do esquecimento"): [docs/CIENCIA-DA-APRENDIZAGEM.md](docs/CIENCIA-DA-APRENDIZAGEM.md) e [docs/REFERENCIAS.md](docs/REFERENCIAS.md).

## Documentação

- [Guia de uso](docs/GUIA-DE-USO.md)
- [Arquitetura](docs/ARQUITETURA.md) e [decisões (ADRs)](docs/adr/)
- [Segurança e limites](docs/SEGURANCA-E-LIMITES.md)
- [Desenvolvimento](docs/DESENVOLVIMENTO.md) e [como contribuir](CONTRIBUTING.md)
- [Migração do formato `.learning/`](docs/MIGRACAO.md)
- [Avaliação do próprio tutor](evals/README.md)

## Licença e créditos

[MIT](LICENSE), por Amon Pires. Créditos e inspirações (learn-faster-kit, de Hugo Lau; o mnemônico FASTER, de Jim Kwik) em [NOTICE](NOTICE).
