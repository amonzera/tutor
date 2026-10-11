# tutor

Tutor de estudo guiado com IA, construído sobre o [Claude Code](https://code.claude.com/docs). Você coloca o material de uma matéria numa pasta, abre o Claude Code na pasta do tutor e estuda com um tutor que:

- pede a **sua tentativa e a sua confiança antes de ajudar**, dá dicas em escada e explica por que a alternativa que você escolheu é tentadora;
- **protege o gabarito**: a resposta só aparece depois do seu compromisso;
- agenda **revisões espaçadas** até a véspera da prova e monta um **plano reverso** a partir da data;
- mostra o **domínio por conceito com faixa de incerteza**, a sua calibração e um preparo estimado (sem prometer nota);
- cria e **verifica às cegas** as questões a partir das suas fontes;
- **retoma de onde parou** na sessão seguinte, porque toda a memória fica em arquivos.

## Antes de começar (uma vez)

Você precisa de uma conta com acesso ao Claude Code.

- **Windows (app do Claude):** abra o PowerShell **como administrador**, rode `wsl --install` e reinicie; ao abrir o Ubuntu pela primeira vez, crie usuário e senha. Depois, no terminal do Ubuntu: `sudo apt update && sudo apt install -y git python3 poppler-utils`.
- **Mac ou Linux:** instale git, Python 3.10 ou mais novo e o poppler (`brew install poppler` ou `sudo apt install poppler-utils`).

## Como usar (6 passos)

1. Clone o tutor (no Windows, no terminal do Ubuntu): `git clone https://github.com/amonzera/tutor.git ~/tutor`
2. Crie `subjects/<nome-da-materia>/fontes/` (nome sem acento nem espaço) e coloque o material: PDFs com texto, anotações `.md` ou `.txt`. Provas antigas e listas com gabarito vão em `fontes/provas/`. No Windows, abra a pasta pelo Explorador de Arquivos: `\\wsl.localhost\Ubuntu\home\<seu-usuário>\tutor\subjects`.
3. Abra o Claude Code na pasta do tutor e aceite a confiança na pasta. No app do Windows: aba **Code**, seletor de ambiente, **WSL**, **Ubuntu**, pasta `~/tutor`.
4. `/materias` lista as matérias e o que vence hoje; a pasta nova aparece como `nova`.
5. `/nova-materia <nome-da-materia>` prepara a matéria: perguntas sobre a prova, mapa de conceitos, plano e banco de questões verificado. Demora e consome uso do seu plano; se parar, rode de novo que ele continua.
6. Abra uma sessão nova e rode `/estudar` todo dia. A primeira sessão começa com um diagnóstico.

Quer só experimentar? No passo 3, peça no chat "instale a matéria de exemplo" e rode `/estudar probabilidade-basica`.

Plano B para computador da empresa, Mac e Linux em detalhe e problemas comuns: [guia de uso](docs/GUIA-DE-USO.md).

## Uma semana até a prova

Exemplo gerado pelo tutor (prova na segunda-feira, 6 dias de estudo por semana):

| Dia | O que fazer |
|---|---|
| Segunda a quinta | `/estudar`: revisões de memória e os conceitos do dia (a primeira sessão começa com o diagnóstico) |
| Sexta (D-3) | `/simulado` em tempo de prova e `/revisar` |
| Sábado (D-2) | `/estudar`: revisão geral e pontos fracos; se quiser, `/erros` e `/quiz` |
| Domingo (véspera) | só `/revisar`, curto; nada novo |

A qualquer momento: `/progresso` mostra como você está e `/plano` refaz o calendário se a data mudar ou você perder um dia. O dia a dia em detalhe está em [uma semana até a prova](docs/GUIA-DE-USO.md#6-uma-semana-até-a-prova).

## Que matérias funcionam

- **Bem:** matérias estudadas por texto e cobradas com questões de múltipla escolha, numéricas ou abertas (exatas, biológicas, humanas, direito, concursos).
- **Com limites:** fórmulas em PDF podem sair embaralhadas, figuras viram descrição em texto, em programação a correção não executa código, idiomas são revisados por conceito e não por palavra.
- **Não atende:** PDF escaneado (sem OCR), `.docx` e `.pptx` (exporte para PDF), áudio e vídeo, habilidades práticas.

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
