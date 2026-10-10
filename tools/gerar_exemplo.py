#!/usr/bin/env python3
"""Gera as fontes protegidas da matéria de exemplo (conteúdo original e fictício).

    python tools/gerar_exemplo.py

Escreve em examples/probabilidade-basica/fontes/provas/:
- prova-ficticia-2025.pdf: 6 questões de múltipla escolha; a alternativa oficial sai em
  vermelho, como em provas reais que trazem a marcação. O texto extraído não carrega a
  cor, mas a imagem da página carregaria: é por isso que o tutor nunca mostra imagens de
  páginas de prova.
- lista-1.md: 6 exercícios com as respostas no fim.

Por que um script: dentro do Claude Code, as regras do projeto bloqueiam ler e escrever
em fontes/provas/ (área protegida). Gerar por script mantém o exemplo reproduzível sem
abrir exceção nas regras.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.pdf_minimo import build_pdf  # noqa: E402

TARGET = ROOT / "examples" / "probabilidade-basica" / "fontes" / "provas"
RED = (0.85, 0.0, 0.0)

EXAM = [
    ("1. Um dado honesto de seis faces é lançado uma vez. Qual é a probabilidade de sair um",
     "número maior que 4?", ["1/6", "1/3", "1/2", "2/3", "5/6"], "B"),
    ("2. Num lote, a probabilidade de uma peça ter defeito é 0,08. Escolhida uma peça ao acaso,",
     "qual é a probabilidade de ela não ter defeito?", ["0,08", "0,80", "0,92", "0,98", "1,08"], "C"),
    ("3. Numa turma de 40 estudantes, 24 estudam pela manhã e, desses, 6 também trabalham. Sorteado",
     "um estudante, e sabendo que ele estuda pela manhã, qual é a probabilidade de que trabalhe?",
     ["6/40", "6/24", "24/40", "6/34", "18/24"], "B"),
    ("4. Uma moeda honesta é lançada duas vezes. Qual é a probabilidade de sair cara nos dois",
     "lançamentos?", ["1/8", "1/4", "1/3", "1/2", "3/4"], "B"),
    ("5. De um grupo de 6 pessoas, quantas comissões diferentes de 2 pessoas podem ser formadas?",
     "", ["12", "15", "30", "36", "64"], "B"),
    ("6. Um teste para uma doença rara (1% da população) detecta 90% dos doentes e dá falso",
     "positivo em 5% dos sãos. Uma pessoa teve resultado positivo. A chance de ela estar doente é mais "
     "próxima de:", ["1%", "15%", "50%", "90%", "95%"], "B"),
]

LIST = """# Lista de exercícios 1 (fictícia)

> Material fictício e original. Esta lista traz as respostas no fim, por isso fica em `fontes/provas/` (área protegida).

1. Um jogo paga R$ 10 com probabilidade 0,2 e nada caso contrário. Qual é o valor esperado do pagamento?
2. Uma moeda honesta é lançada 4 vezes. Qual é a probabilidade de saírem exatamente 2 caras?
3. Uma urna tem 3 bolas vermelhas e 2 azuis. Retiram-se duas bolas, sem reposição. Qual é a probabilidade de as duas serem vermelhas?
4. Uma fábrica tem duas máquinas. A máquina A produz 60% das peças, com 2% de defeituosas; a máquina B produz 40%, com 5% de defeituosas. Qual é a probabilidade de uma peça escolhida ao acaso ser defeituosa?
5. No lançamento de um dado, sejam A = {1, 2, 3} e B = {2, 4, 6}. Descreva A ∪ B, A ∩ B e o complementar de A.
6. Os eventos A e B têm P(A) = 0,5, P(B) = 0,4 e P(A ∩ B) = 0,2. Eles são independentes? Justifique.

## Respostas

1. R$ 2.
2. 6/16 = 0,375.
3. 3/10 = 0,3.
4. 0,032.
5. A ∪ B = {1, 2, 3, 4, 6}; A ∩ B = {2}; complementar de A = {4, 5, 6}.
6. Sim: P(A) · P(B) = 0,2 = P(A ∩ B).
"""


def _page(items):
    lines = []
    for first, second, options, answer in items:
        lines.append((first, None))
        if second:
            lines.append((second, None))
        for letter, text in zip("ABCDE", options):
            lines.append((f"   {letter}) {text}", RED if letter == answer else None))
        lines.append(("", None))
    return lines


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    header = [
        ("Prova 1 (fictícia) - Probabilidade Básica - 2025", None),
        ("Material fictício criado para demonstrar o tutor. As alternativas oficiais estão em vermelho.", None),
        ("", None),
    ]
    pdf = build_pdf([header + _page(EXAM[:3]), _page(EXAM[3:])], title="Prova ficticia de probabilidade")
    (TARGET / "prova-ficticia-2025.pdf").write_bytes(pdf)
    (TARGET / "lista-1.md").write_text(LIST, encoding="utf-8", newline="\n")
    print(f"gerados em {TARGET.relative_to(ROOT)}: prova-ficticia-2025.pdf ({len(pdf)} bytes), lista-1.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
