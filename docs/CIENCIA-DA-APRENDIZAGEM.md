# Ciência da aprendizagem no tutor

Este documento liga cada recurso do tutor ao que a pesquisa sobre aprendizagem diz, com a força da evidência, o lugar no código e os limites. As obras citadas estão em [REFERENCIAS.md](REFERENCIAS.md), cada uma com o status da verificação. Quando a referência foi conferida só em parte, o texto marca "(parcial)".

Vale para o documento todo: a pesquisa citada estudou técnicas isoladas, em geral com universitários, materiais curtos e testes dentro de algumas semanas. **Ninguém testou este tutor**, e a combinação das técnicas não foi avaliada como um todo. Os evals do repositório medem se o tutor segue o protocolo, não se o aluno aprende mais.

## Como ler

Cada seção traz: o que a pesquisa diz, a força da evidência, o que o tutor faz, onde isso está no código e os limites. Os níveis de evidência são uma classificação nossa, apoiada nas duas sínteses verificadas (Dunlosky et al., 2013; Pashler et al., 2007):

- **Forte**: sínteses e metanálises com resultados consistentes, incluindo estudos em sala de aula.
- **Moderada**: vários experimentos favoráveis, mas com moderadores importantes, poucos estudos em sala de aula ou dependência do material.
- **Limitada**: poucos estudos, resultados mistos ou transposição indireta para o caso do tutor.
- **Heurística**: escolha de projeto, sem estudo que a sustente diretamente.

## Prática de recuperação

**O que a pesquisa diz.** Tentar lembrar fixa mais do que reler. No experimento de Roediger e Karpicke (2006), quem se testou lembrou mais, depois de 2 dias e de 1 semana, do que quem reestudou o mesmo texto; depois de 5 minutos, reestudar foi melhor. Karpicke e Roediger (2008) acharam um efeito grande da recuperação repetida na recordação uma semana depois, nenhum efeito do reestudo repetido, e previsões dos alunos que não acompanhavam o resultado. Testes de prática superaram reestudar e as demais condições de comparação numa metanálise (Adesope et al., 2017, parcial), e testes de evocação deram benefício maior que testes de reconhecimento (Rowland, 2014, parcial). Gerar a resposta também supera lê-la (Slamecka & Graf, 1978, parcial; Bertsch et al., 2007).

**Força da evidência: forte.** Prática de testes tem utilidade alta na síntese de Dunlosky et al. (2013), e o guia do IES classifica como forte a evidência de quizzes que reexpõem o conteúdo-chave (Pashler et al., 2007).

**No tutor.**

- "Tenta primeiro": o aluno dá a resposta e a confiança antes de qualquer explicação.
- O estudo é feito com questões e com recordação livre ("explique de memória"), nunca com resumos para reler.
- Ao acertar uma questão de múltipla escolha, o aluno explica por que as outras alternativas falham, o que acrescenta evocação ao reconhecimento.

**No código.** Protocolo em `CLAUDE.md` (itens 1 e 3); `tutor/attempts.py` (`check` recusa corrigir sem resposta e confiança, e grava a tentativa antes de revelar); `.claude/skills/revisar/SKILL.md` e `.claude/skills/quiz/SKILL.md`.

**Limites.** Os estudos citados usam prosa, pares de palavras e testes de memória. O efeito de 4 desvios-padrão relatado por Karpicke e Roediger (2008) compara duas condições específicas daquele experimento e não é o tamanho típico do efeito.

## Prática espaçada

**O que a pesquisa diz.** Distribuir o estudo no tempo melhora a retenção, e o intervalo ideal entre sessões cresce com o tempo até o teste (Cepeda et al., 2006). Num estudo com mais de 1.350 pessoas, o intervalo ideal caiu de cerca de 20% a 40% do prazo, para um teste 1 semana depois, para cerca de 5% a 10% do prazo, para um teste 1 ano depois (Cepeda et al., 2008).

**Força da evidência: forte em laboratório, moderada em sala de aula.** A síntese de Dunlosky et al. (2013) dá utilidade alta à prática espaçada; o guia do IES classifica a evidência como moderada (Pashler et al., 2007). Na síntese de Cepeda et al. (2006), 80% das comparações mediram a retenção em menos de 1 dia e só 4% em mais de 1 mês.

**No tutor.**

- Cada conceito do mapa tem a própria agenda de revisões pelo algoritmo SM-2 (Wozniak, 1990), que espaça mais o que o aluno acerta com facilidade e traz de volta o que ele esquece.
- O intervalo nunca passa de metade dos dias que faltam para a prova, com piso de 2 dias para conceito já estabelecido, e nenhuma revisão cai depois da véspera.
- O plano distribui os conceitos pelos dias até a prova, em vez de concentrá-los no fim.

**No código.** `tutor/srs.py` (`SM2Scheduler`, `schedule_date`, `triage`) e `tutor/planner.py` (`build_plan`).

**Limites e heurísticas.**

- O teto de 50% e o piso de 2 dias são **heurísticas nossas**, calibradas por simulação (de 4 a 9 revisões para provas de 1 semana a 2 meses). Só se inspiram na ideia de que o espaçamento ideal depende do prazo; as proporções de Cepeda et al. (2008) valem para o intervalo entre duas sessões de estudo de um conjunto de fatos, não para várias revisões de conceitos.
- O SM-2 é um algoritmo de uso prático, não um resultado experimental, e não foi comparado com alternativas neste projeto. O tutor o adapta: quatro notas (esqueci = 1, difícil = 3, bom = 4, fácil = 5) em vez de seis; o fator de facilidade é atualizado também quando o aluno esquece, enquanto a descrição original manda recomeçar as repetições "without changing the E-Factor"; o intervalo é arredondado para o inteiro mais próximo, não para cima; e não há a repetição, no mesmo dia, dos itens com nota abaixo de 4.
- O FSRS, um agendador mais recente com parâmetros ajustáveis aos dados (Open Spaced Repetition, s.d.), está fora do escopo desta versão; a interface `Scheduler` permite trocá-lo depois.

## Intercalação

**O que a pesquisa diz.** Misturar tipos de problema, em vez de praticar um tipo por vez, pode melhorar o aprendizado, dependendo do material. Uma metanálise achou efeito moderado no geral, maior com material visual, pequeno em matemática e contrário com listas de palavras; o efeito cresce quando as categorias se parecem e é ambíguo com textos expositivos (Brunmair & Richter, 2019). Em turmas reais de matemática, a prática intercalada teve resultado melhor (Rohrer et al., 2015, parcial; Rohrer et al., 2020, parcial). Num estudo com pinturas, os participantes acharam que o bloco tinha funcionado melhor, mesmo depois de irem melhor com a intercalação (Kornell & Bjork, 2008).

**Força da evidência: moderada.** Utilidade moderada em Dunlosky et al. (2013).

**No tutor.** A seleção de questões alterna temas, e o protocolo pede para não fazer blocos longos do mesmo assunto.

**No código.** `tutor/selection.py` (`interleave`, `next_questions`); `CLAUDE.md` (item 5).

**Limites.** O benefício depende do material. O tutor intercala temas da mesma matéria, e não há regra para conteúdos em que o bloco é melhor (como listas de vocabulário).

## Dificuldades desejáveis e ilusão de competência

**O que a pesquisa diz.** Condições que deixam o aprendizado aparentemente mais lento muitas vezes melhoram a retenção, mas se o aprendiz não tem base para enfrentá-las, viram dificuldades indesejáveis (Bjork & Bjork, 2011, parcial). Julgar o próprio aprendizado com a informação à vista dá uma sensação de competência que o teste desmente (Koriat & Bjork, 2005).

**Força da evidência: moderada** para o princípio geral; a dosagem certa da dificuldade não tem receita.

**No tutor.**

- O tutor não entrega a resposta antes da tentativa, mesmo quando o aluno pede.
- A escada de dicas e o exemplo resolvido para conceitos novos evitam que a dificuldade vire bloqueio.
- O painel mostra a diferença entre a confiança do aluno e o acerto real.

**No código.** `CLAUDE.md` (itens 1, 2 e 6); `tutor/learner.py` (`calibration`); `tutor/report.py`.

## Pré-teste e diagnóstico

**O que a pesquisa diz.** Responder perguntas antes de estudar um texto melhorou o aprendizado posterior, comparado a estudar pelo mesmo tempo (Richland et al., 2009), e tentativas de lembrar que falham também ajudam (Kornell et al., 2009).

**Força da evidência: limitada.** Os estudos são de laboratório, e o guia do IES classifica como baixa a evidência das perguntas prévias em sala de aula (Pashler et al., 2007).

**No tutor.** O diagnóstico abre o primeiro `/estudar`: uma rodada curta que cobre os conceitos de base e os de maior peso, apresentada como mapa de partida, não como nota.

**No código.** `tutor/selection.py` (`_diagnostic`); `.claude/skills/diagnostico/SKILL.md`; [ADR 0010](adr/0010-diagnostico-no-primeiro-estudo.md).

**Limites.** Numa matéria totalmente nova, o pré-teste pode frustrar; por isso ele é curto e o tutor explica o objetivo.

## Feedback

**O que a pesquisa diz.** Na média, o feedback melhora o desempenho, mas mais de um terço das intervenções estudadas piorou o desempenho, e a eficácia cai quando a atenção sai da tarefa e vai para a pessoa (Kluger & DeNisi, 1996). O efeito do feedback pode ser positivo ou negativo (Hattie & Timperley, 2007, parcial), e fortalecer o feedback frequente traz ganhos substanciais (Black & Wiliam, 1998, parcial).

**Força da evidência: forte** para "feedback ajuda, mas depende de como é dado"; o melhor momento do feedback não foi verificado aqui.

**No tutor.**

- Feedback sobre a tarefa e o processo, nunca sobre a pessoa ("você isolou a variável certa", não "você é inteligente").
- A correção traz o conceito decisivo, a solução e por que o distrator escolhido é tentador.
- Na sessão de estudo o feedback vem logo depois da tentativa; no simulado ele é adiado para o fim, para reproduzir a prova, não por evidência.

**No código.** `CLAUDE.md` (itens 3 e 7); `tutor/attempts.py` (`_result_payload`, com `por_que_tentadora`); `tutor/bank.py` (`check_answer`, com `erros_comuns` nas numéricas).

## Exemplos resolvidos e retirada gradual de apoio

**O que a pesquisa diz.** Para iniciantes, estudar exemplos resolvidos levou a resolver problemas parecidos mais rápido e com menos erros (Sweller & Cooper, 1985, parcial). Uma explicação proposta: resolver problemas por análise meios-fins consome uma capacidade de processamento que fica indisponível para formar esquemas (Sweller, 1988). Com aprendizes experientes, o mesmo apoio perde efeito e pode atrapalhar: o efeito de reversão da expertise (Kalyuga et al., 2003, parcial). Retirar gradualmente os passos resolvidos ajudou a transição para a resolução (Renkl et al., 2002). Em sentido contrário, resolver um problema antes da instrução teve efeito moderado favorável, com tendência contrária para alunos do 2º ao 5º ano e para habilidades gerais (Sinha & Kapur, 2021).

**Força da evidência: moderada.** O guia do IES classifica como moderada a recomendação de intercalar exemplos resolvidos com exercícios (Pashler et al., 2007).

**No tutor.**

- Conceito novo para o aluno: um exemplo resolvido curto, depois questões com dicas que vão sumindo.
- Conceito que ele já domina no básico: problema primeiro.
- A escada de dicas tem quatro degraus (conceito, estratégia, primeiro passo, solução comentada). Acertar com três ou mais degraus conta como erro no modelo do aluno, porque ver o primeiro passo não é resolver sozinho.

**No código.** `CLAUDE.md` (itens 2 e 6); `tutor/attempts.py` (`--dicas`); `tutor/learner.py` (dica decisiva).

**Limites.** Retirar dicas não é o mesmo que retirar passos de um exemplo: a ligação é uma analogia nossa. A decisão entre "iniciante" e "avançado" fica com o tutor e não é medida.

## Autoexplicação

**O que a pesquisa diz.** Os alunos com melhor desempenho explicavam mais para si mesmos o que estudavam (Chi et al., 1989, estudo correlacional), e estimular essa explicação melhorou a compreensão (Chi et al., 1994, amostra pequena). Uma metanálise achou efeito médio de 0,55 para estímulos à autoexplicação (Bisra et al., 2018).

**Força da evidência: moderada.** Utilidade moderada em Dunlosky et al. (2013); o guia do IES classifica como forte a evidência para perguntas explicativas profundas (Pashler et al., 2007).

**No tutor.** Acertou: explique por que as outras alternativas falham. Acertou com confiança baixa: diga o porquê. Errou: conte o que pensou antes de ver a solução.

**No código.** `CLAUDE.md` (itens 3 e 4).

**Limites.** Os estímulos estudados eram, em geral, escritos por professores; nenhuma fonte verificada avalia estímulos gerados por um modelo de linguagem.

## Aprender ensinando

**O que a pesquisa diz.** Ensinar o conteúdo produziu compreensão mais profunda e duradoura do que só se preparar para ensinar (Fiorella & Mayer, 2013). Numa metanálise, preparar-se para ensinar e, mais ainda, ensinar depois de se preparar tiveram efeitos positivos, maiores com ensino interativo (Kobayashi, 2019). Alunos se esforçam mais quando ensinam um agente de software (Chase et al., 2009). O efeito pode aparecer sem plateia real, mas vários estudos recentes não o replicaram (Lachner et al., 2022).

**Força da evidência: moderada a limitada** para o formato do tutor.

**No tutor.** Toda sessão termina com o aluno explicando o conceito com as próprias palavras. Em `/ensinar`, ele ensina um "novato" simulado que comete equívocos típicos, e o tutor avalia com uma rubrica (correto, completo, com exemplo, com o caso-limite).

**No código.** `.claude/skills/ensinar/SKILL.md` e `.claude/skills/ensinar/rubrica.md`; `CLAUDE.md` (item 8).

**Limites.** O novato é um modelo de linguagem, não uma pessoa, e a replicação sem plateia real é inconsistente.

## Aprendizagem para o domínio

**O que a pesquisa diz.** Programas de aprendizagem para o domínio (avançar só depois de dominar o anterior) tiveram efeitos positivos nas provas, mais fortes nos alunos mais fracos, mas aumentam o tempo de estudo e, quando cada um vai no seu ritmo, reduziram as taxas de conclusão no ensino superior (Kulik et al., 1990, parcial).

**Força da evidência: moderada.**

**No tutor.**

- O domínio é estimado por conceito, e o plano prioriza conceitos fracos e de maior peso, na ordem dos pré-requisitos.
- Um conceito só conta como "dominado" com acerto estimado de pelo menos 0,85, faixa inferior de pelo menos 0,7 e evidência suficiente (**heurística**).
- Pré-requisito fraco reduz a prioridade do conceito que depende dele.

**No código.** `tutor/learner.py` (`estimate_concepts`); `tutor/planner.py` (`build_plan`); `tutor/selection.py` (`score_questions`); `tutor/knowledge_map.py` (pré-requisitos).

**Limites.** Com prova marcada, o tempo é finito: o plano não espera o domínio completo de um conceito para seguir adiante.

## Metacognição e calibração

**O que a pesquisa diz.** Alunos julgam mal o próprio aprendizado: as previsões não acompanharam o desempenho (Karpicke & Roediger, 2008), estudar com a resposta à vista dá ilusão de competência (Koriat & Bjork, 2005), e participantes julgaram a prática em bloco mais eficaz mesmo depois de irem melhor com a intercalada (Kornell & Bjork, 2008).

**Força da evidência: moderada** para o problema; a eficácia de mostrar a calibração ao aluno não foi verificada aqui.

**No tutor.**

- Toda resposta vem com a confiança (1 a 5), dada **antes** da correção.
- Erro com confiança 4 ou 5 vira prioridade máxima (provável concepção errada); acerto com confiança 1 ou 2 leva a pedir o porquê.
- O painel mostra o escore de Brier (Brier, 1950, parcial): a média do quadrado da diferença entre a confiança convertida em probabilidade e o resultado (0 é perfeito). Mostra também o viés (excesso ou falta de confiança) e o acerto por nível de confiança.

**No código.** `tutor/learner.py` (`calibration`, `CONFIDENCE_PROBABILITY`); `tutor/selection.py` (`_base_score`); `tutor/report.py`.

**Limites.** A conversão da confiança em probabilidade (1 → 0,2 ... 5 → 0,95) é **heurística**. Com poucas respostas, o Brier oscila muito.

## Modelo do aluno e preparo estimado

**O que a pesquisa diz.** Sistemas de tutoria estimam o conhecimento por habilidade a partir das respostas: o rastreamento de conhecimento (Corbett & Anderson, 1995, parcial), sua versão com redes neurais (Piech et al., 2015) e adaptações do Elo (Pelánek, 2016, parcial). Modelos com muitos parâmetros precisam de muitos dados para estimá-los.

**Força da evidência: heurística.** O modelo do tutor é uma escolha de projeto ([ADR 0006](adr/0006-modelo-do-aluno-beta-bernoulli.md)).

**No tutor.**

- O domínio de cada conceito é a probabilidade de acertar uma questão nova dele, estimada por uma Beta-Bernoulli. Tentativas antigas valem menos (meia-vida de 21 dias), e o piso é a chance de acertar no chute.
- O preparo estimado sai de uma simulação com semente fixa e é mostrado como faixa (por exemplo, "entre 40% e 70%"), só quando há tentativas suficientes cobrindo a matéria.
- Cada simulado registra o previsto e o obtido, para o aluno ver se a estimativa acerta.

**No código.** `tutor/learner.py` (`estimate_concepts`, `readiness`); `tests/test_learner.py` (um aluno sintético confere que a faixa de 80% cobre o valor real na proporção esperada); `tutor/attempts.py` (`finish_exam`).

**Limites.**

- Todos os conceitos de uma questão recebem a mesma evidência, e não há transferência entre conceitos.
- Os parâmetros não foram ajustados a dados reais de alunos.
- O preparo mede o desempenho **no banco de questões**, não prevê a nota: a prova real pode cobrar outra coisa, de outro jeito.

## Motivação, metas e continuidade

**O que a pesquisa diz.** A teoria da autodeterminação considera necessidades de competência, autonomia e vínculo (Deci & Ryan, 2000, parcial). Planos concretos do tipo "quando x acontecer, farei y" ajudam a cumprir metas (Gollwitzer, 1999, parcial). O tempo para um comportamento novo virar hábito variou de 18 a 254 dias entre voluntários, e perder uma oportunidade não atrapalhou materialmente (Lally et al., 2010).

**Força da evidência: limitada** para o tutor: a ligação entre esses estudos e o desenho é indireta.

**No tutor.**

- O aluno escolhe a matéria, o tempo diário e a data da prova (autonomia); o painel mostra o progresso por conceito (competência).
- Cada `/estudar` começa perguntando o tempo disponível e a energia (1 a 5), e a sessão encolhe quando a energia está baixa.
- Cada sessão termina com o próximo passo concreto escrito em `estado/proximo-passo.md`, que abre a sessão seguinte.
- Dias perdidos não zeram nada: `/plano` refaz o calendário.

**No código.** `tutor/subjects.py` (`session_context`, `checkpoint`); `tutor/planner.py`; `.claude/skills/plano/SKILL.md`.

**Limites.** O tutor não mede motivação nem hábito.

## Tutores com IA: o que se sabe

**O que a pesquisa diz.** Num ensaio com quase mil alunos do ensino médio, o GPT-4 liberado melhorou as notas na prática, mas piorou a prova feita sem IA; uma versão com salvaguardas (a solução e os erros comuns no prompt, com a instrução de não entregar a resposta) melhorou ainda mais a prática e só eliminou o prejuízo na prova, sem ganho (Bastani et al., 2025). Numa disciplina de física, um tutor de IA desenhado com base em pesquisa levou os alunos a aprender mais, em menos tempo, do que uma aula de aprendizagem ativa, num teste feito logo depois (Kestin et al., 2025). Antes dos modelos de linguagem, uma revisão achou que sistemas de tutoria inteligente (d = 0,76) chegavam perto da tutoria humana (d = 0,79), ambas comparadas com instrução sem tutoria (VanLehn, 2011). Fabricantes passaram a oferecer modos de estudo que guiam em vez de responder (Anthropic, 2025).

**Força da evidência: limitada.** Os estudos são recentes, curtos e feitos em um contexto cada.

**No tutor.** A lição de Bastani et al. (2025) orienta o desenho: a proteção não depende só de instrução no prompt. O gabarito fica fora do alcance do modelo, e a correção só sai depois da tentativa registrada ([ADR 0003](adr/0003-gabarito-protegido-em-camadas.md)). Mesmo assim, o tutor é apoio de estudo e não substitui aulas.

**No código.** `tutor/attempts.py`, `tutor/bank.py`, `tutor/guard.py`, `.claude/settings.json`.

## Desenho dos agentes

**O que a prática recomenda.** Começar pela solução mais simples e só aumentar a complexidade quando necessário; preferir fluxos definidos em código quando a tarefa é previsível; usar instâncias separadas do modelo para verificar; documentar e testar bem a interface entre o modelo e as ferramentas (Anthropic, 2024). Aplicações que leem conteúdo externo misturam dados e instruções, e um atacante pode plantar instruções nesse conteúdo (Greshake et al., 2023; OWASP Gen AI Security Project, 2025). Modelos usados como juízes têm vieses, inclusive o de preferir as próprias respostas (Zheng et al., 2023), e escolher a resposta mais consistente entre vários raciocínios independentes melhorou o desempenho de modelos em tarefas de raciocínio (Wang et al., 2023).

**No tutor.**

- O motor é código determinístico: guarda o estado, escolhe as questões, agenda as revisões e corrige o que dá para corrigir sem modelo. O modelo conduz a conversa.
- Toda saída do motor é JSON com um campo `llm_directive` de texto fixo, nunca com conteúdo das fontes.
- As questões passam por um verificador separado, que resolve sem ver o gabarito, com um modelo diferente do que as escreveu. Questões em que as duas resoluções divergem saem de uso, e só as verificadas entram no simulado ([ADR 0007](adr/0007-guarda-preToolUse-e-verificador-cego.md)).
- O conteúdo de `fontes/` é tratado como dado, nunca como instrução.
- Os evals medem o comportamento com o modelo real.

**Limites.** A verificação às cegas reduz erros, mas dois modelos podem errar igual. A detecção de instruções nas fontes é heurística.

## FASTER como mnemônico

O FASTER (Forget, Act, State, Teach, Enter, Review), atribuído a Jim Kwik no livro *Limitless* (Kwik, 2020, parcial), é um **mnemônico de método de estudo**, não um modelo validado por pesquisa: em buscas feitas em 9 de outubro de 2026 em bases acadêmicas abertas, não encontramos avaliação dele em literatura revisada por pares. O tutor o usa só como lembrete de organização. A leitura de cada letra abaixo é nossa.

| Letra | Leitura que adotamos | O que o tutor faz | Evidência |
|---|---|---|---|
| F (Forget) | deixar de lado o que se acha que sabe | o diagnóstico mede o que o aluno sabe, em vez de presumir | limitada (pré-teste) |
| A (Act) | aprender fazendo, não assistindo | tenta primeiro, geração, recuperação | forte (prática de recuperação) |
| S (State) | estado do aluno | `/estudar` pergunta o tempo disponível e a energia (1 a 5) e faz uma sessão mais leve quando a energia está baixa; o tutor não tenta alterar o estado | heurística |
| T (Teach) | aprender como quem vai ensinar | ensinar de volta, `/ensinar` | moderada a limitada |
| E (Enter) | pôr o estudo na agenda | plano reverso, próximo passo concreto | limitada (intenções de implementação) |
| R (Review) | revisar | revisões espaçadas por conceito | forte (prática espaçada) |

## O que a literatura NÃO sustenta

O tutor **não** usa estas ideias, comuns em materiais sobre "aprender mais rápido":

- **Estilos de aprendizagem.** Não há evidência adequada para adaptar o ensino ao "estilo" do aluno (visual, auditivo...). A revisão de Pashler et al. (2008) quase não achou a interação entre estilo e método que validaria a ideia, e vários dos poucos estudos com método adequado contradisseram a hipótese de "casar" o ensino com o estilo; os autores ressalvam que muitas versões nunca foram testadas. O tutor adapta o estudo ao **desempenho** em cada conceito, não a preferências de formato.
- **Números mágicos da curva do esquecimento** ("esquecemos 50% em uma hora e 70% em um dia"). Ebbinghaus mediu a economia de tempo ao reaprender listas de sílabas sem sentido, com ele mesmo como único sujeito, e advertiu que os resultados tinham "only individual significance" (Ebbinghaus, 1885/1913). A replicação de Murre e Dros (2015) também teve um único sujeito. Transformar essas curvas em porcentagens de esquecimento de qualquer conteúdo, para qualquer pessoa, é uma extrapolação que as fontes não autorizam. O tutor não usa números de esquecimento: a agenda se ajusta ao desempenho do aluno em cada conceito.
- **A regra das 10 mil horas.** Numa metanálise, a prática deliberada explicou 26% da variância do desempenho em jogos, 21% em música, 18% em esportes, 4% em educação e menos de 1% em profissões (Macnamara et al., 2014). Ela importa, mas não determina sozinha o desempenho, e nenhum número de horas garante domínio. O tutor mede o desempenho, não horas de estudo.
- **Mentalidade de crescimento como solução geral.** Duas metanálises acharam efeitos fracos, tanto da relação entre mentalidade e desempenho quanto das intervenções, com possível benefício para alunos de nível socioeconômico baixo ou em risco acadêmico (Sisk et al., 2018). As mais recentes divergem: uma atribui os efeitos aparentes das intervenções a falhas de desenho, de relato e a viés (Macnamara & Burgoyne, 2023); outra acha efeitos pequenos e muito variáveis, concentrados em subgrupos e em intervenções fiéis ao protocolo (Burnette et al., 2023). O tutor dá feedback sobre o processo, que tem outra base (Kluger & DeNisi, 1996), mas não faz intervenções de mentalidade nem promete que "acreditar" melhora a nota.
- **Reler e marcar o texto como estratégia principal.** Releitura e marca-texto tiveram utilidade baixa na síntese de Dunlosky et al. (2013): não melhoram o desempenho de forma consistente. O tutor não oferece resumo para reler como atividade de estudo.
- **Um número fixo de dias para criar um hábito.** O tempo até um comportamento novo ficar automático variou de 18 a 254 dias (Lally et al., 2010).
- **IA que resolve tudo ensina.** Com o GPT-4 liberado, alunos foram melhor na prática e pior na prova sem IA (Bastani et al., 2025). Por isso o tutor não entrega respostas antes da tentativa.
- **Tutoria individual rende 2 desvios-padrão.** O "problema dos 2 sigma" deu nome a um artigo clássico (Bloom, 1984, parcial), mas uma revisão posterior não confirmou a crença nesse efeito: achou d = 0,79 para a tutoria humana (VanLehn, 2011). Nenhum tutor, humano ou artificial, deve prometer saltos desse tamanho.
- **FASTER como método validado.** Veja a seção anterior.

## Heurísticas próprias

Todos os números de projeto (teto e piso do intervalo, limite diário de revisões, meia-vida da evidência, limiares de "dominado", conversão da confiança, cobertura mínima do preparo, prioridades da seleção, simulados no plano) são escolhas nossas, ajustáveis, e estão listados com a justificativa em [ARQUITETURA.md](ARQUITETURA.md#heurísticas-e-parâmetros). Nenhum deles vem de um estudo específico.
