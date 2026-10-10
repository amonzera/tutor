# Changelog

Todas as mudanças relevantes deste projeto. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

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
