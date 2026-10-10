# ADR 0002: motor em Python só com biblioteca padrão e um wrapper em sh

- Status: aceita
- Data: 2026-10-09

## Contexto

O tutor precisa funcionar logo depois do `git clone`, em Linux, macOS, WSL e Windows. No projeto anterior, o shell do aplicativo no Windows não tinha `python3` (só o atalho da Microsoft Store), e os scripts falhavam.

## Decisão

- Motor em Python 3.10+, **sem dependências**: nada de `pip install`.
- Um único ponto de execução, `bash bin/tutor.sh`, em sh POSIX (testado com dash e bash). Ele usa o Python do WSL quando a pasta é `//wsl.localhost/<distro>/...` aberta pelo Git Bash do Windows, e senão o primeiro entre `TUTOR_PYTHON`, `python3`, `python` e `py -3` que for 3.10 ou mais novo.
- Uma só regra de permissão cobre todo o motor: `Bash(bash bin/tutor.sh *)`.

## Alternativas consideradas

- **Bibliotecas externas** (por exemplo, para PDF ou validação de JSON): exigiriam instalação e ambiente virtual.
- **Chamar `python3` direto nas skills:** quebra no Windows sem WSL e espalha variações de comando nas permissões.

## Consequências

- PDF depende do `pdftotext` (poppler), opcional: sem ele, o aluno converte o material para `.md` ou `.txt`.
- Windows só com PowerShell (sem Git for Windows) não é suportado; a própria documentação do Claude Code recomenda o Git for Windows.
