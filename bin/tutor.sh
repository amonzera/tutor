#!/bin/sh
# Ponto único de execução do motor do tutor (Linux, macOS, WSL e Git Bash no Windows).
#
#   bash bin/tutor.sh <subcomando> [opções]
#
# Como o Python é escolhido:
#   1. Pasta dentro do WSL aberta pelo Windows (//wsl.localhost/<distro>/...):
#      usa o python3 da própria distribuição, via wsl.exe.
#   2. Senão, TUTOR_PYTHON, python3, python ou "py -3": o primeiro que for 3.10+.
#      (O atalho "python3" da Microsoft Store falha nessa checagem e é pulado.)
# A distribuição do WSL é deduzida do caminho em tempo de execução; nada disso
# fica gravado em arquivo.
#
# Escrito em sh POSIX (testado com dash e bash). Não use recursos de bash aqui.

set -u

# Converte //wsl.localhost/<distro>/<caminho> (ou //wsl$/...) em WSL_DISTRO e WSL_PATH.
wsl_target() {
  case "$1" in
    //wsl.localhost/* | //wsl\$/* | //WSL.LOCALHOST/* | //WSL\$/*) ;;
    *) return 1 ;;
  esac
  rest=${1#//}
  rest=${rest#*/}
  WSL_DISTRO=${rest%%/*}
  [ -n "$WSL_DISTRO" ] || return 1
  case "$rest" in
    */*) WSL_PATH="/${rest#*/}" ;;
    *) WSL_PATH="/" ;;
  esac
  return 0
}

python_ok() {
  "$@" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

fail_no_python() {
  msg="Python 3.10 ou mais novo não encontrado. Instale o Python (python.org) ou, no Windows, abra a pasta pelo WSL."
  if [ "${TUTOR_SAIDA_ERRO:-}" = "stderr" ]; then
    printf '%s\n' "$msg" >&2
  else
    printf '{"schema_version": 1, "status": "erro", "erro": "python_nao_encontrado", "mensagem": "%s", "llm_directive": "Mostre a mensagem ao aluno. O motor precisa do Python 3.10 ou mais novo; não tente contornar."}\n' "$msg"
  fi
  exit 127
}

# Diagnóstico usado pelos testes: bash bin/tutor.sh --alvo-wsl <caminho>
if [ "${1:-}" = "--alvo-wsl" ]; then
  if wsl_target "${2:-}"; then
    printf '%s\t%s\n' "$WSL_DISTRO" "$WSL_PATH"
    exit 0
  fi
  exit 1
fi

# Hooks não podem poluir a saída padrão com JSON de erro.
case "${1:-}" in
  inicio-sessao | guarda) TUTOR_SAIDA_ERRO=stderr ;;
esac

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
root=$(CDPATH='' cd -- "$script_dir/.." && pwd) || exit 1

if wsl_target "$root" && command -v wsl.exe >/dev/null 2>&1; then
  WSLENV="${WSLENV:+$WSLENV:}TUTOR_HOJE/u:TUTOR_AGORA/u:TUTOR_SAIDA_ERRO/u"
  export WSLENV
  MSYS_NO_PATHCONV=1 exec wsl.exe -d "$WSL_DISTRO" --cd "$WSL_PATH" -e \
    python3 -E -X utf8 -B -m tutor ${1+"$@"}
fi

cd "$root" || exit 1
# -E ignora PYTHONPATH e afins (nada de código injetado por variável de ambiente);
# -X utf8 e -B fazem o papel de PYTHONUTF8 e PYTHONDONTWRITEBYTECODE, que o -E ignoraria.

if [ -n "${TUTOR_PYTHON:-}" ] && python_ok "$TUTOR_PYTHON"; then
  exec "$TUTOR_PYTHON" -E -X utf8 -B -m tutor ${1+"$@"}
fi
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
    exec "$candidate" -E -X utf8 -B -m tutor ${1+"$@"}
  fi
done
if command -v py >/dev/null 2>&1 && python_ok py -3; then
  exec py -3 -E -X utf8 -B -m tutor ${1+"$@"}
fi
fail_no_python
