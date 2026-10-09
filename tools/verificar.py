#!/usr/bin/env python3
"""Verificação local completa. A CI só chama este script, então o que passa aqui passa lá.

    python tools/verificar.py            # tudo
    python tools/verificar.py testes     # só uma etapa: testes, privacidade, gitignore, links, markdown

Só biblioteca padrão. O markdownlint roda se `markdownlint-cli2` estiver no PATH
(na CI ele roda por uma action própria).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PLACEHOLDER_USERS = r"(?:usuario|aluno|user|voce|nome|runner)"
PRIVACY_PATTERNS = {
    "caminho pessoal (Linux)": re.compile(rf"/home/(?!{PLACEHOLDER_USERS}\b)[a-z_][a-z0-9_.-]*/"),
    "caminho pessoal (macOS)": re.compile(rf"/Users/(?!{PLACEHOLDER_USERS}\b)[A-Za-z0-9_.-]+/"),
    "caminho pessoal (Windows)": re.compile(rf"[A-Za-z]:\\Users\\(?!{PLACEHOLDER_USERS}\b)[A-Za-z0-9_.-]+", re.I),
    "distro do WSL": re.compile(
        r"wsl(?:\.localhost|\$)[/\\]+"
        r"(?!(?:<distro>|\.\.\.|Ubuntu(?:-\d{2}\.\d{2})?|Debian)(?:[/\\\s\"'`),.]|$))[A-Za-z0-9._-]+"
    ),
    "e-mail": re.compile(
        r"[A-Za-z0-9._%+-]+@(?!(?:example\.(?:com|org)|users\.noreply\.github\.com)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    ),
    "chave AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
    "token GitHub": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})"),
    "chave de API": re.compile(r"(?:sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{32,}|xox[abprs]-[A-Za-z0-9-]{10,})"),
    "chave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B50, 0x2B55), (0xFE0F, 0xFE0F))

MUST_BE_IGNORED = [
    "subjects/calculo-2/fontes/apostila.pdf",
    "subjects/calculo-2/materia.json",
    "subjects/calculo-2/estado/tentativas.jsonl",
    "subjects/.local.json",
    ".claude/settings.local.json",
    "CLAUDE.local.md",
    "tutor/__pycache__/core.cpython-312.pyc",
    "evals/resultados/execucao.json",
]
MUST_BE_TRACKABLE = [
    "subjects/README.md",
    "subjects/.gitkeep",
    ".claude/settings.json",
    ".claude/skills/estudar/SKILL.md",
    "examples/probabilidade-basica/fontes/apostila.md",
    "examples/probabilidade-basica/banco/gabarito.json",
]


def _files() -> list[Path]:
    """Arquivos versionados ou versionáveis (respeita o .gitignore)."""
    done = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    names = [n for n in done.stdout.decode("utf-8").split("\0") if n]
    return [ROOT / n for n in sorted(set(names)) if (ROOT / n).is_file()]


def _text(path: Path) -> str | None:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def check_tests() -> list[str]:
    cmd = [
        sys.executable, "-X", "warn_default_encoding", "-W", "error::EncodingWarning",
        "-m", "unittest", "discover", "-s", "tests", "-t", ".",
    ]
    done = subprocess.run(cmd, cwd=ROOT)
    return [] if done.returncode == 0 else ["testes falharam"]


def check_privacy() -> list[str]:
    problems = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        text = _text(path)
        if text is None:
            text = path.read_bytes().decode("latin-1")  # PDFs: metadados e texto cru
        for label, pattern in PRIVACY_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line}: {label}: {match.group(0)!r}")
        if path.suffix in {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".cff", ""} and _text(path) is not None:
            for number, line_text in enumerate(text.splitlines(), start=1):
                for char in line_text:
                    code = ord(char)
                    if any(lo <= code <= hi for lo, hi in EMOJI_RANGES):
                        name = unicodedata.name(char, hex(code))
                        problems.append(f"{rel}:{number}: emoji ou símbolo decorativo: {name}")
                        break
    return problems


def check_gitignore() -> list[str]:
    problems = []
    for rel in MUST_BE_IGNORED:
        if subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode != 0:
            problems.append(f"deveria ser ignorado pelo git: {rel}")
    for rel in MUST_BE_TRACKABLE:
        if subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0:
            problems.append(f"não deveria ser ignorado pelo git: {rel}")
    return problems


LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _anchor(heading: str) -> str:
    text = re.sub(r"[`*_~]", "", heading).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s", "-", text)


def _anchors(path: Path) -> set[str]:
    anchors, counts = set(), {}
    in_code = False
    for line in (_text(path) or "").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        match = None if in_code else HEADING.match(line)
        if match:
            base = _anchor(match.group(2))
            n = counts.get(base, 0)
            anchors.add(base if n == 0 else f"{base}-{n}")
            counts[base] = n + 1
    return anchors


def check_links() -> list[str]:
    problems = []
    for path in _files():
        if path.suffix != ".md":
            continue
        rel = path.relative_to(ROOT).as_posix()
        in_code = False
        for number, line in enumerate((_text(path) or "").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for target in LINK.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                    continue  # http, https, mailto: checados pela CI (lychee)
                file_part, _, anchor = target.partition("#")
                dest = path if not file_part else (path.parent / file_part)
                if not dest.exists():
                    problems.append(f"{rel}:{number}: link quebrado: {target}")
                elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
                    problems.append(f"{rel}:{number}: âncora inexistente: {target}")
    return problems


def check_markdown() -> list[str]:
    tool = shutil.which("markdownlint-cli2")
    if tool is None:
        print("  (markdownlint-cli2 não está no PATH; etapa pulada localmente, roda na CI)")
        return []
    done = subprocess.run([tool, "**/*.md", "#subjects", "#node_modules"], cwd=ROOT)
    return [] if done.returncode == 0 else ["markdownlint encontrou problemas"]


STEPS = {
    "testes": check_tests,
    "privacidade": check_privacy,
    "gitignore": check_gitignore,
    "links": check_links,
    "markdown": check_markdown,
}


def main(argv: list[str]) -> int:
    wanted = argv or list(STEPS)
    unknown = [w for w in wanted if w not in STEPS]
    if unknown:
        print(f"Etapas desconhecidas: {', '.join(unknown)}. Use: {', '.join(STEPS)}")
        return 2
    failed = False
    for name in wanted:
        print(f"== {name}")
        problems = STEPS[name]()
        for problem in problems:
            print(f"  {problem}")
        print(f"  {'FALHOU' if problems else 'ok'}")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
