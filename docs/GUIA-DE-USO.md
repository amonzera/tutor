# Guia de uso

Tudo o que você precisa para estudar com o tutor. O resumo está no [README](../README.md).

## 1. Instalação

Você precisa de uma conta com acesso ao [Claude Code](https://code.claude.com/docs). O tutor usa Python 3.10 ou mais novo (sem pacotes a instalar) e, para ler PDFs, o `pdftotext` do poppler.

### Windows: app do Claude com WSL (recomendado)

1. **Instale o WSL**, o Linux dentro do Windows. Abra o PowerShell **como administrador**, rode `wsl --install` e reinicie o computador. Na primeira vez que abrir o Ubuntu, crie um usuário e uma senha.
2. **Prepare o Ubuntu.** No terminal do Ubuntu:

   ```bash
   sudo apt update && sudo apt install -y git python3 poppler-utils
   git clone https://github.com/amonzera/tutor.git ~/tutor
   ```

3. **Abra o tutor no app.** No app do Claude, aba **Code**: abra o seletor de ambiente, escolha **WSL** e a distribuição **Ubuntu**, e selecione a pasta `~/tutor` (aparece como `/home/<seu-usuário>/tutor`). Aceite a confiança na pasta.

Nesse modo, o Claude Code roda dentro do Ubuntu, com os comandos e caminhos do Linux. As sessões WSL do app não têm terminal integrado: quando precisar de um comando no terminal (como `banco exportar`), use o terminal do Ubuntu.

**Computador da empresa:** o administrador pode ter desativado as sessões WSL. Nesse caso, abra a pasta `\\wsl.localhost\Ubuntu\home\<seu-usuário>\tutor` numa sessão local, com o [Git for Windows](https://git-scm.com/download/win) instalado. O `bin/tutor.sh` percebe o caminho e usa o Python e o `pdftotext` do Ubuntu; cada comando fica um pouco mais lento.

**Windows sem WSL** (não testado): clone o repositório no Windows e instale o Git for Windows e o Python do python.org (o atalho `python3` da Microsoft Store não serve e é pulado). Sem o poppler, converta os PDFs para `.md` ou `.txt`. Sem Git Bash (só PowerShell), o tutor não funciona.

### Mac ou Linux

Instale git, Python 3.10 ou mais novo e o poppler (Linux: `sudo apt install poppler-utils`; macOS: `brew install poppler`). Depois:

```bash
git clone https://github.com/amonzera/tutor.git
cd tutor
bash bin/tutor.sh ambiente      # confere Python e pdftotext
```

Abra a pasta no Claude Code (terminal, app desktop ou extensão de IDE).

## 2. Primeira vez

1. Abra o Claude Code na pasta do tutor (no Windows, pelo ambiente WSL, como acima).
2. Aceite a confiança na pasta. É isso que ativa os hooks (o resumo das matérias no início da sessão e a guarda do gabarito) e as permissões do projeto. Sem isso, cada comando pede permissão.
3. Experimente com a matéria de exemplo: peça no chat "instale a matéria de exemplo" (ou rode `bash bin/tutor.sh exemplo` no terminal) e depois `/estudar probabilidade-basica`.

Modelo: o tutor funciona com qualquer modelo do Claude Code; para conduzir as sessões, um modelo grande com esforço alto dá respostas melhores (`/model` e `/effort`). Os agentes já vêm com modelo e esforço próprios (veja a seção 11).

## 3. Que matérias funcionam

| Situação | Exemplos |
|---|---|
| Funciona bem | Matérias estudadas por texto e cobradas com questões de múltipla escolha, numéricas ou abertas: exatas, biológicas, humanas, direito, concursos. |
| Funciona com limites | Fórmulas em PDF podem sair embaralhadas na extração; figuras viram descrição em texto; em programação, a correção não executa código; em idiomas, a revisão é por conceito, não por palavra. |
| Não atende | PDF escaneado (o tutor não faz OCR), `.docx` e `.pptx` (exporte para PDF), áudio e vídeo, habilidades práticas. |

## 4. Criar uma matéria

1. Crie `subjects/<nome>/fontes/` com um nome curto, sem acento nem espaço (`calculo-2`). No Windows, abra `\\wsl.localhost\Ubuntu\home\<seu-usuário>\tutor\subjects` no Explorador de Arquivos, crie as pastas e copie o material.
2. Coloque o material em `fontes/`: PDFs com texto, anotações `.md` ou `.txt`, slides exportados em PDF.
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

## 5. Estudar todo dia: `/estudar`

Sem argumento, usa a última matéria (ou a única). A sessão:

1. retoma pelo checkpoint (`estado/proximo-passo.md`) e pelo diário;
2. pergunta o tempo disponível e a sua energia (1 a 5); com energia baixa, a sessão fica mais leve;
3. resolve pendências (erros sem classificação) e faz as revisões vencidas, de memória;
4. segue o foco do dia no plano (ou o seu conceito mais fraco); conceito novo começa com um exemplo resolvido;
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

## 6. Uma semana até a prova

Exemplo gerado pelo próprio tutor com a matéria de exemplo: prova numa segunda-feira, 40 minutos por dia e o padrão de 6 dias de estudo por semana (domingo livre).

| Dia | O que o plano manda | Comando |
|---|---|---|
| Seg (D-7) | diagnóstico + contagem, espaço amostral, probabilidade clássica, eventos | `/estudar` |
| Ter (D-6) | revisões + regra da soma, valor esperado, probabilidade condicional | `/estudar` |
| Qua (D-5) | revisões + independência, regra do produto, binomial | `/estudar` |
| Qui (D-4) | revisões + probabilidade total, Bayes | `/estudar` |
| Sex (D-3) | simulado em tempo de prova + revisões do dia | `/simulado` e `/revisar` |
| Sáb (D-2) | revisão geral e pontos fracos | `/estudar`; se quiser, `/erros` e `/quiz` |
| Dom (D-1) | nada novo; só revisões curtas de memória (as últimas caem aqui) | `/revisar` |
| Seg | prova | |

As revisões se espalham sozinhas: um conceito estudado na segunda volta na terça, na quarta, na sexta e no domingo; um da quinta volta na sexta, no sábado e no domingo. Nada é agendado depois da véspera.

- Com a prova mais distante, as semanas anteriores seguem o padrão de segunda a quinta (conceitos novos e revisões), e a reta final é igual.
- Com 7 dias de estudo por semana (`bash bin/tutor.sh configurar --materia <slug> --dias-semana 7`), a reta final tem simulado completo na D-3, reforço pelos erros do simulado na D-2 e simulado leve na D-1.
- A qualquer momento: `/progresso` para ver como está; `/plano` se perder um dia ou a data mudar.

## 7. Outras skills

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

## 8. Arquivos da matéria

Tudo fica em `subjects/<slug>/` e você pode ler (exceto os protegidos). Os principais:

- `plano.md`: calendário até a prova.
- `estado/dominio.md`: painel.
- `estado/caderno-de-erros.md`: padrões de erro.
- `estado/diario.md` e `estado/proximo-passo.md`: o histórico das sessões e o que fazer na próxima.
- `materia.json`: configuração. Mude com `bash bin/tutor.sh configurar --materia <slug> --data-prova AAAA-MM-DD` (ou pelo `/plano`), não à mão.

Quer ver o gabarito em texto? Rode no **seu** terminal: `bash bin/tutor.sh banco exportar --materia <slug> --para gabarito.json`.

## 9. Várias matérias, uma matéria ou um clone por matéria

- **Várias matérias** (padrão): cada uma em `subjects/`; `/materias` mostra todas, e `revisao listar --todas` divide as revisões do dia entre elas, dando mais espaço à prova mais próxima.
- **Uma matéria só:** funciona igual; `/estudar` sem argumento usa a única matéria.
- **Um clone por matéria:** clone o repositório várias vezes, uma matéria em cada. Isola tudo, mas você atualiza cada clone separadamente (`git pull` em cada um).

## 10. Atualizar o tutor

```bash
git pull
```

Suas matérias em `subjects/` não são tocadas. Se um arquivo de dados ficar com versão mais nova que o motor, o tutor avisa.

## 11. Modelos e custo

Cada agente define modelo e esforço no próprio arquivo (`.claude/agents/`). Padrões: `verificador` em Opus com esforço máximo (o erro aqui é caro); `escritor-de-questoes`, `ingestor-de-fontes` e `corretor` em Sonnet com esforço alto; `planejador` em Sonnet com esforço médio. Escritor e verificador usam modelos diferentes para errarem de forma menos parecida.

Para trocar por matéria, acrescente ao `materia.json`, por exemplo: `"modelos": {"verificador": {"modelo": "sonnet", "esforco": "high"}}`. As skills repassam esses valores ao chamar o agente.

Custos e limites dependem do seu plano. A documentação oficial explica a escolha de modelo e o efeito do esforço no consumo: [custos](https://code.claude.com/docs/en/costs) e [configuração de modelo](https://code.claude.com/docs/en/model-config).

## 12. Problemas comuns

| Problema | O que fazer |
|---|---|
| `python_nao_encontrado` | Instale o Python 3.10+; no Windows, use o ambiente WSL do app. |
| `sem_pdftotext` | Instale o poppler (`sudo apt install poppler-utils` no Ubuntu) ou converta o PDF para `.txt`. |
| PDF sem texto (escaneado) | O tutor não faz OCR; use outro programa para gerar o texto. |
| Cada comando pede permissão | Aceite a confiança na pasta (feche e abra o Claude Code na pasta do tutor). |
| O app não oferece o ambiente WSL | Confira se o WSL 2 e o Ubuntu estão instalados; em computador da empresa, use o plano B da seção 1. |
| "Nome de matéria inválido" | Renomeie a pasta para o nome sugerido (sem acento, sem espaço). |
| `materia_ambigua` | Diga a matéria: `/estudar <slug>`. |
| A guarda negou um comando | É esperado para buscas recursivas em `subjects/` e leitura de arquivos protegidos. Use `bash bin/tutor.sh buscar`. |
| Banco pequeno para simulado | `/simulado <slug> 5` ou gere mais questões (peça ao tutor; ele usa o escritor e o verificador). |
