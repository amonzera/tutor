# ADR 0003: gabarito protegido em camadas, com codificação em repouso

- Status: aceita
- Data: 2026-10-09

## Contexto

Um tutor que entrega a resposta antes da tentativa atrapalha o aprendizado. No projeto anterior, o gabarito ficava num JSON legível e a proteção era só instrução e uma regra `deny`. Um teste com o Claude Code real mostrou que a regra `deny` de leitura bloqueia `cat`, `head`, `awk` e `grep` quando o arquivo é nomeado, mas deixa passar `cat banco/*.json` (curinga) e `grep -r` com caminho explícito.

## Decisão

1. Banco (`questoes.json`, sem respostas) e gabarito (`gabarito.json`) separados.
2. A resposta só sai de `corrigir`, que exige a resposta e a confiança do aluno e grava a tentativa antes de revelar.
3. Gabarito, respostas do verificador e texto das provas gravados em zlib + base64 pelo motor (ilegíveis por acidente).
4. `deny` de leitura nesses arquivos (vale também para Edit e Write).
5. Guarda `PreToolUse` para buscas recursivas, curingas e agentes (veja a ADR 0007).

## Alternativas consideradas

- **Só `deny` e instrução:** o teste mostrou os vazamentos.
- **Criptografia com chave:** a chave teria de ficar na mesma máquina, acessível ao mesmo agente; complexidade sem ganho real contra quem quer ler.
- **Sandbox do Claude Code:** opcional, não existe no Windows nativo e também bloquearia o próprio motor.

## Consequências

- O aluno vê o gabarito em texto rodando `banco exportar` no próprio terminal.
- Para criar ou corrigir questões, use rascunhos e `banco importar`; não se edita o gabarito à mão.
- Não é um cofre: veja [SEGURANCA-E-LIMITES.md](../SEGURANCA-E-LIMITES.md).
