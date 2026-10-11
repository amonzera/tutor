# Guia de uso

O resumo está no [README](../README.md).

## 1. Instalação

**Windows (app do Claude):**

1. No PowerShell como administrador, rode `wsl --install` e reinicie. Ao abrir o Ubuntu, crie um usuário e uma senha.
2. No Ubuntu:

   ```bash
   sudo apt update && sudo apt install -y git python3 poppler-utils
   git clone https://github.com/amonzera/tutor.git ~/tutor
   ```

3. No app do Claude, aba **Code**: escolha o ambiente **WSL**, a distribuição **Ubuntu** e a pasta `~/tutor`. Aceite a confiança na pasta.

**Mac ou Linux:** instale git, Python 3.10 ou mais novo e o poppler, clone o repositório e abra a pasta no Claude Code.

## 2. Primeira vez

1. Abra a pasta do tutor no Claude Code e aceite a confiança na pasta.
2. Peça no chat "instale a matéria de exemplo".
3. Rode `/estudar probabilidade-basica`.

## 3. Criar uma matéria

1. Crie `subjects/<nome>/fontes/` com um nome curto, sem acento nem espaço (`calculo-2`). No Windows, a pasta fica em `\\wsl.localhost\Ubuntu\home\<seu-usuário>\tutor\subjects`.
2. Coloque o material em `fontes/`: PDFs com texto, anotações `.md` ou `.txt`.
3. Provas antigas e listas com gabarito vão em `fontes/provas/`: o tutor usa as questões, mas não vê a resposta antes de você.
4. Rode `/nova-materia <nome>`. Ele pergunta sobre a prova e monta o plano e as questões.
5. Abra uma sessão nova e rode `/estudar <nome>`.

## 4. Estudar todo dia: `/estudar`

1. Retoma de onde parou.
2. Pergunta o tempo disponível e a sua energia.
3. Faz as revisões do dia: você explica de memória.
4. Passa aos conceitos do dia, com questões.
5. Em cada questão, você responde e diz a confiança (1 a 5) antes de qualquer ajuda. Se travar, recebe dicas em degraus.
6. No fim, você explica o conceito com as suas palavras.
7. O tutor agenda as revisões e anota o próximo passo.

| Confiança | Quer dizer |
|---|---|
| 1 | Chutei. |
| 2 | Tenho um palpite. |
| 3 | Acho que é isso. |
| 4 | Tenho bastante certeza. |
| 5 | Tenho certeza absoluta. |

## 5. Uma semana até a prova

| Dia | O que fazer | Comando |
|---|---|---|
| Segunda a quinta | revisões e conceitos do dia | `/estudar` |
| Sexta | simulado em tempo de prova | `/simulado` |
| Sábado | revisão geral e pontos fracos | `/estudar` |
| Domingo (véspera) | revisões curtas, nada novo | `/revisar` |

As revisões se espalham sozinhas ao longo da semana e param na véspera.

## 6. Todas as funções

| Skill | Para quê |
|---|---|
| `/materias` | Lista as matérias, dias até a prova e revisões do dia. |
| `/nova-materia <pasta>` | Prepara uma matéria nova. |
| `/estudar [matéria]` | Sessão diária completa. |
| `/revisar` | Só as revisões do dia, de memória. |
| `/quiz [matéria] [tema]` | Cinco questões rápidas. |
| `/simulado [matéria] [n]` | Prova cronometrada, correção só no fim. |
| `/ensinar [matéria] [conceito]` | Você ensina um "novato" que comete erros típicos. |
| `/diagnostico` | Pré-teste do que você já sabe. |
| `/progresso` | Como você está em cada conceito. |
| `/plano` | Refaz o calendário quando algo muda. |
| `/erros` | As armadilhas em que você mais cai. |

## 7. Que matérias funcionam

| Situação | Exemplos |
|---|---|
| Funciona bem | Matérias estudadas por texto e cobradas com questões: exatas, biológicas, humanas, direito, concursos. |
| Funciona com limites | Fórmulas e figuras de PDF, programação, idiomas. |
| Não funciona | PDF escaneado, `.docx` e `.pptx` (exporte para PDF), áudio, vídeo, habilidades práticas. |

## 8. Problemas comuns

| Problema | O que fazer |
|---|---|
| Cada comando pede permissão | Aceite a confiança na pasta (feche e abra o Claude Code na pasta do tutor). |
| `sem_pdftotext` | Instale o poppler ou converta o PDF para `.txt`. |
| PDF sem texto (escaneado) | Gere o texto em outro programa. |
| "Nome de matéria inválido" | Renomeie a pasta para o nome sugerido. |
| `materia_ambigua` | Diga a matéria: `/estudar <nome>`. |
