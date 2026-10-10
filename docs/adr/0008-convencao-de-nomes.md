# ADR 0008: convenção de nomes

- Status: aceita
- Data: 2026-10-09

## Decisão

- Tudo o que o aluno vê está em português do Brasil: pastas, arquivos de dados, skills, subcomandos e flags do motor (que aparecem em todo pedido de permissão), mensagens e documentação. Identificadores de código (funções, variáveis, módulos) ficam em inglês.
- Chaves JSON dos dados em português, ASCII e snake_case; as chaves fixas são `schema_version`, `status` e `llm_directive`.
- Nomes de arquivo, slugs de matéria, skills e agentes só em ASCII. O nome com acento fica em `materia.json`. No projeto anterior, um slug com acento e parênteses obrigou um atalho (`auto`) em todos os scripts.
- `subjects/` foi mantido em inglês porque a decisão de arquitetura o nomeou assim.

## Consequências

Os erros do argparse saem em JSON e em português, com o texto original da biblioteca dentro da mensagem.
