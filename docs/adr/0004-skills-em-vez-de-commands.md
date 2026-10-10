# ADR 0004: skills em vez de `.claude/commands`

- Status: aceita
- Data: 2026-10-09

## Contexto

A documentação atual do Claude Code diz que os comandos personalizados foram incorporados às skills: um arquivo em `.claude/commands/x.md` e uma skill em `.claude/skills/x/SKILL.md` criam o mesmo `/x`, e a recomendação para coisas novas é usar skills.

## Decisão

Cada comando do tutor é uma skill em `.claude/skills/<nome>/SKILL.md`, com nome ASCII (`/diagnostico`, sem acento, porque a documentação não garante caracteres acentuados em nomes).

## Consequências

- Arquivos de apoio por skill (a rubrica do `/ensinar`, os formatos do `/nova-materia`).
- `disable-model-invocation: true` nas skills pesadas ou com efeito colateral (`/nova-materia`, `/simulado`, `/plano`, `/diagnostico`); as demais podem ser acionadas pelo Claude quando o aluno pede em linguagem natural.
- `allowed-tools` vale só durante o turno que invoca a skill; sessões de várias rodadas dependem das regras `allow` do `settings.json` (que valem depois de o aluno aceitar a confiança na pasta).
