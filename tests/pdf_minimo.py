"""Gerador de PDF mínimo (só biblioteca padrão), para fixtures e para a prova fictícia do exemplo.

Cada página é uma lista de linhas; cada linha pode ter cor (r, g, b) para simular a
marcação da resposta oficial em vermelho, que aparece na imagem mas não no texto.
Fonte Helvetica com WinAnsiEncoding: acentos do português funcionam.
"""

from __future__ import annotations

from typing import Iterable, Sequence

Line = tuple[str, "tuple[float, float, float] | None"]


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content(lines: Sequence[Line]) -> bytes:
    parts = [b"BT", b"/F1 11 Tf", b"14 TL", b"50 800 Td"]
    for text, color in lines:
        r, g, b = color or (0, 0, 0)
        parts.append(f"{r:g} {g:g} {b:g} rg".encode("ascii"))
        parts.append(b"(" + _escape(text) + b") Tj T*")
    parts.append(b"ET")
    return b"\n".join(parts)


def build_pdf(pages: Iterable[Sequence[Line]], title: str = "Documento ficticio") -> bytes:
    pages = list(pages)
    objects: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(pages))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for index, lines in enumerate(pages):
        content = _content(lines)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {page_ids[index] + 1} 0 R >>".encode("ascii")
        )
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream")
    info_id = len(objects) + 1
    objects.append(b"<< /Title (" + _escape(title) + b") /Producer (tutor - gerador de exemplo) >>")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    out += b"".join(f"{off:010d} 00000 n \n".encode("ascii") for off in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)
