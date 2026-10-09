#!/bin/sh
# Hook PreToolUse do tutor. Caminho rápido em sh: só chama o motor (Python) quando o
# evento menciona algo que a guarda precisa examinar. Nunca bloqueia por falha própria.
# Política completa em tutor/guard.py.

input=$(cat)
case "$input" in
  *verificador* | *gabarito* | *verificacao.json* | *tentativas.jsonl* | *protegido* | *provas* | \
  *rascunhos* | *figuras-temp* | *renderizar* | *exportar* | *grep* | *'rg '* | *'ag '* | *ack* | \
  *xargs* | *-exec*) ;;
  *) exit 0 ;;
esac

dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 0
printf '%s' "$input" | sh "$dir/tutor.sh" guarda
exit 0
