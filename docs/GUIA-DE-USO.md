# Guia de uso

Tudo o que você precisa para estudar com o tutor. O resumo está no [README](../README.md).

## 1. Instalação

Requisitos:

- [Claude Code](https://code.claude.com/docs) (terminal, aplicativo desktop ou extensão de IDE).
- Python 3.10 ou mais novo. Não há pacotes a instalar.
- Opcional, para ler PDFs: `pdftotext` do poppler (Linux: `sudo apt install poppler-utils`; macOS: `brew install poppler`). Sem ele, converta o material para `.md` ou `.txt`.

```bash
git clone https://github.com/amonzera/tutor.git
cd tutor
bash bin/tutor.sh ambiente      # confere Python e pdftotext
```

### Windows

O Claude Code no Windows usa o Git Bash para os comandos (instale o [Git for Windows](https://git-scm.com/download/win)). O tutor funciona de duas formas:

- **Recomendado:** clone o repositório **dentro do WSL** (por exemplo, `~/tutor`) e abra essa pasta no Claude Code (no aplicativo desktop, o caminho aparece como `\\wsl.localhost\<distro>\home\<usuario>\tutor`). O `bin/tutor.sh` percebe isso e usa o Python e o `pdftotext` do próprio WSL, mesmo quando o comando sai do Git Bash do Windows.
- Clone no Windows com o Python do python.org instalado (o atalho `python3` da Microsoft Store não serve e é pulado).

Sem Git Bash (só PowerShell), o tutor não funciona.

## 2. Primeira vez

1. Abra o Claude Code na **raiz** do repositório.
2. Aceite a confiança na pasta. É isso que ativa os hooks (o resumo das matérias no início da sessão e a guarda do gabarito) e as permissões do projeto. Sem isso, cada comando pede permissão.
3. Experimente com a matéria de exemplo: `bash bin/tutor.sh exemplo` e depois `/estudar probabilidade-basica`.

Modelo: o tutor funciona com qualquer modelo do Claude Code; para conduzir as sessões, um modelo grande com esforço alto dá respostas melhores (`/model` e `/effort`). Os agentes já vêm com modelo e esforço próprios (veja a seção 9).

## 3. Criar uma matéria

1. Crie `subjects/<nome>/fontes/` com um nome curto, sem acento nem espaço (`calculo-2`).
2. Coloque o material em `fontes/`: PDFs, anotações `.md` ou `.txt`, slides exportados em PDF.
3. **Provas antigas, listas com gabarito e resoluções vão em `fontes/provas/`.** O texto delas fica numa área protegida: o tutor usa as questões, mas não vê a resposta antes de você.
4. Rode `/nova-materia <nome>`.

O `/nova-materia`:

1. confere o material (e recusa arquivos de configuração do Claude escondidos nas fontes);
2. pergunta só o que falta: objetivo, data e formato da prova, nível, tempo por dia, idioma, se as provas antigas vêm com a resposta marcada;
3. extrai o texto (PDF página a página);
4. monta o mapa de conhecimento (conceitos, pré-requisitos, pesos, onde cada um aparece);
5. gera o plano até a prova;
6. monta o banco de questões: extrai das provas e listas e/ou cria questões originais, e um verificador independente resolve cada uma sem ver o gabarito;
7. gera o `CLAUDE.md` da matéria e o primeiro checkpoint.

Pode levar algum tempo e consumir bastante uso do seu plano, porque envolve vários agentes. Se for interrompido, rode `/nova-materia <nome>` de novo: ele continua da etapa pendente. No fim, **abra uma sessão nova** e rode `/estudar <nome>`; a primeira sessão começa com um diagnóstico.

Já sabe as respostas? Passe na linha de comando: `/nova-materia calculo-2 prova em 2026-12-01, 10 questões de múltipla escolha, 120 minutos, 45 minutos por dia, nível intermediário`.

## 4. Estudar todo dia: `/estudar`

Sem argumento, usa a última matéria (ou a única). A sessão:

1. retoma pelo checkpoint (`estado/proximo-passo.md`) e pelo diário;
2. pergunta o tempo disponível e a sua energia;
3. resolve pendências (erros sem classificação) e faz as revisões vencidas, de memória;
4. segue o foco do dia no plano (ou o seu conceito mais fraco);
5. em cada questão: você responde **e** diz a confiança (1 a 5) antes de qualquer ajuda; se não souber, recebe dicas em escada (conceito, ferramenta, primeiro passo, solução); depois vem a correção, que explica por que a alternativa que você escolheu é tentadora;
6. no fim, você explica o conceito com as suas palavras;
7. o tutor agenda as revisões e registra o checkpoint.

### Escala de confiança

| Confiança | Quer dizer |
|---|---|
| 1 | Chutei. |
| 2 | Tenho um palpite. |
| 3 | Acho que é isso. |
| 4 | Tenho bastante certeza. |
| 5 | Tenho certeza absoluta. |

Erros com confiança 4 ou 5 viram prioridade: indicam uma ideia errada, não falta de estudo.

### Tipos de erro

`conceito` (ideia errada), `metodo` (escolheu a ferramenta errada), `sinal` (sinal ou sentido), `conta` (aritmética), `chute` (respondeu sem saber). Dá para criar tipos próprios: `bash bin/tutor.sh configurar --materia <slug> --tipo-erro-extra sintaxe`.

## 5. Outras skills

| Skill | Para quê |
|---|---|
| `/materias` | Lista as matérias, dias até a prova e revisões vencidas. |
| `/revisar` | Só as revisões espaçadas do dia, de memória. |
| `/quiz [matéria] [tema]` | Cinco questões intercaladas, rápidas. |
| `/simulado [matéria] [n]` | Prova completa cronometrada, sem feedback até o fim; compara o resultado com o preparo previsto. |
| `/ensinar [matéria] [conceito]` | Você ensina um "novato" que comete erros típicos; você precisa corrigi-lo. |
| `/diagnostico` | Pré-teste para mapear o que você já sabe. |
| `/progresso` | Painel: domínio por conceito (com faixa de incerteza), erros, calibração, preparo estimado. |
| `/plano` | Replaneja quando a data ou o tempo diário mudam. |
| `/erros` | Caderno de erros: as armadilhas em que você cai com frequência. |

## 6. Arquivos da matéria

Tudo fica em `subjects/<slug>/` e você pode ler (exceto os protegidos). Os principais:

- `plano.md`: calendário até a prova.
- `estado/dominio.md`: painel.
- `estado/caderno-de-erros.md`: padrões de erro.
- `estado/diario.md` e `estado/proximo-passo.md`: o histórico das sessões e o que fazer na próxima.
- `materia.json`: configuração. Mude com `bash bin/tutor.sh configurar --materia <slug> --data-prova AAAA-MM-DD` (ou pelo `/plano`), não à mão.

Quer ver o gabarito em texto? Rode no **seu** terminal: `bash bin/tutor.sh banco exportar --materia <slug> --para gabarito.json`.

## 7. Várias matérias, uma matéria ou um clone por matéria

- **Várias matérias** (padrão): cada uma em `subjects/`; `/materias` mostra todas, e `revisao listar --todas` divide as revisões do dia entre elas, dando mais espaço à prova mais próxima.
- **Uma matéria só:** funciona igual; `/estudar` sem argumento usa a única matéria.
- **Um clone por matéria:** clone o repositório várias vezes, uma matéria em cada. Isola tudo, mas você atualiza cada clone separadamente (`git pull` em cada um).

## 8. Atualizar o tutor

```bash
git pull
```

Suas matérias em `subjects/` não são tocadas. Se um arquivo de dados ficar com versão mais nova que o motor, o tutor avisa.

## 9. Modelos e custo

Cada agente define modelo e esforço no próprio arquivo (`.claude/agents/`). Padrões: `verificador` em Opus com esforço máximo (o erro aqui é caro); `escritor-de-questoes`, `ingestor-de-fontes` e `corretor` em Sonnet com esforço alto; `planejador` em Sonnet com esforço médio. Escritor e verificador usam modelos diferentes para errarem de forma menos parecida.

Para trocar por matéria, acrescente ao `materia.json`, por exemplo: `"modelos": {"verificador": {"modelo": "sonnet", "esforco": "high"}}`. As skills repassam esses valores ao chamar o agente.

Custos e limites dependem do seu plano. A documentação oficial explica a escolha de modelo e o efeito do esforço no consumo: [custos](https://code.claude.com/docs/en/costs) e [configuração de modelo](https://code.claude.com/docs/en/model-config).

## 10. Problemas comuns

| Problema | O que fazer |
|---|---|
| `python_nao_encontrado` | Instale o Python 3.10+; no Windows, abra a pasta pelo WSL. |
| `sem_pdftotext` | Instale o poppler ou converta o PDF para `.txt`. |
| PDF sem texto (escaneado) | O tutor não faz OCR; use outro programa para gerar o texto. |
| Cada comando pede permissão | Aceite a confiança na pasta (feche e abra o Claude Code na raiz). |
| "Nome de matéria inválido" | Renomeie a pasta para o nome sugerido (sem acento, sem espaço). |
| `materia_ambigua` | Diga a matéria: `/estudar <slug>`. |
| A guarda negou um comando | É esperado para buscas recursivas em `subjects/` e leitura de arquivos protegidos. Use `bash bin/tutor.sh buscar`. |
| Banco pequeno para simulado | `/simulado <slug> 5` ou gere mais questões (peça ao tutor; ele usa o escritor e o verificador). |
