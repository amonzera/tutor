# Changelog

Todas as mudanças relevantes deste projeto. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado

- Primeira sessão conforme o nível: quem é iniciante começa com explicação e exemplo resolvido, sem diagnóstico; os outros níveis fazem um diagnóstico de 4 questões. O texto de boas-vindas vem pronto do motor e aparece ao aluno no início da sessão.
- Trilha completa em ordem de prioridade (frequência na prova, depois dificuldade, sempre depois dos pré-requisitos), sem cortes: um conceito conclui quando é estudado e praticado com 2 respostas, e a trilha só termina com todos.
- Fórmulas em LaTeX nas explicações e nas questões; a importação recusa LaTeX mal escapado no JSON.
- Num conceito novo, as questões vêm da mais fácil para a mais difícil.

### Adicionado

- Figuras: o tutor desenha os conceitos espaciais (vetores, forças, gráficos) e mostra a figura das questões de prova por link, recortada do PDF pelo subcomando `recortar`. O recorte é recusado quando há cor de marca de resposta, e aí a figura é redesenhada a partir da descrição. `/nova-materia <pasta> figuras` faz os recortes numa matéria já pronta.
- Subcomando `trilha estudado`.
- Funções em graus na calculadora (`sind`, `cosd`, `tand`, `asind`, `acosd`, `atand`, `atan2d`) e aviso quando a conta usa radianos.
- Progresso da trilha no plano, no painel e no diário.

### Corrigido

- O diário registrava "Próximo passo: Próximo passo" e duplicava o bloco do dia a cada checkpoint.
- A guarda deixava passar buscas recursivas com caminho absoluto (inclusive no formato do Windows) que alcançam `subjects/`.

## [0.1.0] - 2026-10-09

Primeira versão.

### Adicionado

- Motor em Python 3.10+ só com biblioteca padrão: matérias em `subjects/`, ingestão de PDF, Markdown e texto com proveniência, mapa de conhecimento, banco de questões com gabarito separado e codificado, verificação às cegas, correção que exige resposta e confiança, revisão espaçada SM-2 limitada pela prova, domínio por conceito com incerteza, calibração, preparo estimado, plano reverso, painel e caderno de erros.
- Wrapper `bin/tutor.sh` para Linux, macOS, WSL e Git Bash no Windows (usa o Python do WSL quando a pasta está no WSL).
- Skills: `/materias`, `/nova-materia`, `/estudar`, `/revisar`, `/quiz`, `/simulado`, `/ensinar`, `/diagnostico`, `/progresso`, `/plano`, `/erros`.
- Agentes: `ingestor-de-fontes`, `escritor-de-questoes`, `verificador`, `corretor`, `planejador`.
- Hooks: resumo das matérias no início da sessão e guarda `PreToolUse` (verificador cego, área protegida, buscas recursivas).
- Matéria de exemplo fictícia `probabilidade-basica` com 26 questões verificadas.
- Testes `unittest`, verificação local (`tools/verificar.py`), CI e cenários de avaliação com o Claude Code (`evals/`).
- Documentação em português: guia de uso, arquitetura e ADRs, ciência da aprendizagem, referências, segurança e limites, desenvolvimento, migração.
