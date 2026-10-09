"""Núcleo do motor: erros, relógio, caminhos e armazenamento.

Tudo o que toca o disco ou o relógio passa por aqui. O resto do motor recebe um
`Context` e pode ser testado com uma pasta temporária e um relógio fixo.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLUG_MAX_LENGTH = 40


class TutorError(Exception):
    """Erro esperado (entrada inválida, arquivo ausente). Vira JSON com status "erro"."""

    def __init__(self, code: str, message: str, directive: str | None = None, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.directive = directive
        self.extra = extra

    def payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": "erro", "erro": self.code, "mensagem": self.message}
        out.update(self.extra)
        if self.directive:
            out["llm_directive"] = self.directive
        return out


# ---------------------------------------------------------------- relógio


@dataclass(frozen=True)
class Clock:
    """Relógio injetável. Com `fixed`, data e hora ficam congeladas."""

    fixed: datetime | None = None

    def now(self) -> datetime:
        if self.fixed is not None:
            return self.fixed
        return datetime.now().replace(microsecond=0)

    def today(self) -> date:
        return self.now().date()


def clock_from_env(env: Mapping[str, str] | None = None) -> Clock:
    """TUTOR_AGORA (data e hora ISO) ou TUTOR_HOJE (AAAA-MM-DD) congelam o relógio."""
    env = os.environ if env is None else env
    raw_now = env.get("TUTOR_AGORA", "").strip()
    raw_today = env.get("TUTOR_HOJE", "").strip()
    try:
        if raw_now:
            return Clock(datetime.fromisoformat(raw_now).replace(microsecond=0))
        if raw_today:
            current = datetime.now().time().replace(microsecond=0)
            return Clock(datetime.combine(date.fromisoformat(raw_today), current))
    except ValueError as exc:
        raise TutorError(
            "data_invalida", f"TUTOR_HOJE ou TUTOR_AGORA inválido ({exc}). Use AAAA-MM-DD."
        ) from exc
    return Clock()


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise TutorError("data_invalida", f"Data inválida: {raw!r}. Use AAAA-MM-DD.") from exc


# ---------------------------------------------------------------- caminhos


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def slugify(text: str) -> str:
    """Sugere um nome de pasta válido: sem acentos, minúsculo, com hífens."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = slug[:SLUG_MAX_LENGTH].rstrip("-")
    return slug or "materia"


def is_valid_slug(slug: str) -> bool:
    return bool(SLUG_PATTERN.fullmatch(slug)) and len(slug) <= SLUG_MAX_LENGTH


def validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not is_valid_slug(slug):
        raise TutorError(
            "nome_de_materia_invalido",
            f"Nome de matéria inválido: {slug!r}. Use só letras minúsculas sem acento, "
            "números e hífens (ex.: calculo-2).",
            "Sugira ao aluno o nome do campo `sugestao` e, se ele concordar, renomeie a pasta.",
            sugestao=slugify(str(slug)),
        )
    return slug


def ensure_inside(base: Path, target: Path) -> Path:
    """Resolve `target` e garante que ele fica dentro de `base` (sem escapar por `..` ou symlink)."""
    base_resolved = base.resolve()
    resolved = target.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise TutorError("caminho_fora_da_materia", f"Caminho fora da pasta permitida: {target}")
    return resolved


@dataclass(frozen=True)
class Workspace:
    root: Path
    subjects: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Workspace":
        env = os.environ if env is None else env
        root = repo_root()
        custom = env.get("TUTOR_MATERIAS_DIR", "").strip()
        subjects = Path(custom).expanduser().resolve() if custom else root / "subjects"
        return cls(root=root, subjects=subjects)

    def subject_dir(self, slug: str) -> Path:
        return self.subjects / validate_slug(slug)

    @property
    def local_state_file(self) -> Path:
        """Estado local ignorado pelo git (por exemplo, a última matéria usada)."""
        return self.subjects / ".local.json"


@dataclass(frozen=True)
class Context:
    workspace: Workspace
    clock: Clock


# ---------------------------------------------------------------- armazenamento


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise TutorError(
            "json_invalido",
            f"{path.name} não é um JSON válido (linha {exc.lineno}): {exc.msg}.",
            "Mostre o erro ao aluno. Não reescreva o arquivo sem a confirmação dele.",
            arquivo=str(path),
        ) from exc


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def write_json(path: Path, data: Any) -> None:
    """Escrita atômica: grava num temporário na mesma pasta e troca de uma vez."""
    _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Path, text: str) -> None:
    _atomic_write(path, text if text.endswith("\n") else text + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Lê um JSONL. Tolera só a última linha truncada (queda no meio de uma escrita)."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except FileNotFoundError:
        return []
    records: list[dict[str, Any]] = []
    numbered = [(n, line.strip()) for n, line in enumerate(lines, start=1) if line.strip()]
    for index, (number, line) in enumerate(numbered):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            if index == len(numbered) - 1:
                break
            raise TutorError(
                "jsonl_invalido", f"{path.name}: linha {number} inválida ({exc.msg}).", arquivo=str(path)
            ) from exc
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def check_schema(data: Any, path: Path, expected: int = SCHEMA_VERSION) -> dict[str, Any]:
    """Confere `schema_version`. Arquivo de versão mais nova pede atualização do tutor."""
    if not isinstance(data, dict):
        raise TutorError("formato_invalido", f"{path.name} deveria conter um objeto JSON.", arquivo=str(path))
    version = data.get("schema_version")
    if not isinstance(version, int):
        raise TutorError("sem_schema_version", f"{path.name} não tem schema_version.", arquivo=str(path))
    if version > expected:
        raise TutorError(
            "versao_mais_nova",
            f"{path.name} foi criado por uma versão mais nova do tutor (schema {version}).",
            "Peça ao aluno para atualizar o repositório com `git pull`.",
            arquivo=str(path),
        )
    return data
