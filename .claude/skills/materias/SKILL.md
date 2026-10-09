---
name: materias
description: Lista as matérias do aluno em subjects/, com estado, dias até a prova e revisões vencidas. Use quando o aluno perguntar quais matérias tem, o que estudar hoje ou o que está pendente.
allowed-tools: Bash(bash bin/tutor.sh *)
---

# Matérias

Situação atual, gerada pelo motor:

!`bash bin/tutor.sh materias`

## O que fazer

1. Mostre uma tabela curta: matéria, estado, dias até a prova, revisões vencidas.
2. Para cada estado, indique o próximo passo:
   - `nova`: a pasta tem material mas ainda não foi preparada. Sugira `/nova-materia <pasta>`.
   - `configurando`: a preparação parou no meio. `/nova-materia <pasta>` continua de onde parou.
   - `nome_invalido`: o nome da pasta tem acento, espaço ou maiúscula. Sugira renomear para o valor de `sugestao`.
   - `com_erro`: o `materia.json` está corrompido. Mostre o erro e não tente consertar sem o aluno pedir.
   - `ativa` ou `prova_passou`: `/estudar <pasta>`.
3. Se não houver matérias, explique os passos de `subjects/README.md` e ofereça a matéria de exemplo (`bash bin/tutor.sh exemplo`).
4. Não comece a estudar sem o aluno escolher.
