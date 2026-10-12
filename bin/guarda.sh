#!/bin/sh
# Hook PreToolUse do tutor. Caminho rápido em sh: só chama o motor (Python) quando o
# evento menciona algo que a guarda precisa examinar. Nunca bloqueia por falha própria.
# Política completa em tutor/guard.py.

input=$(cat)
lower=$(printf '%s' "$input" | tr '[:upper:]' '[:lower:]')
case "$lower" in
  *verificador* | *gabarito* | *verificacao* | *tentativas* | *protegido* | *provas* | *rascunhos* | \
  *figuras* | *renderizar* | *recortar* | *exportar* | *grep* | *'rg '* | *'"rg'* | *'ag '* | *ack* | *xargs* | \
  *-exec* | *-ok* | *recurse* | *bash_env* | *python* | *ld_* | *'path='* | *'env='* | *export*) ;;
  *) exit 0 ;;
esac

dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 0
printf '%s' "$input" | sh "$dir/tutor.sh" guarda
exit 0
