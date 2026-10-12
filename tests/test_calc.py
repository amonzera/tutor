"""Calculadora segura: aritmética exata quando possível e recusa de tudo que não é conta."""

from __future__ import annotations

import unittest
from fractions import Fraction

from tests.helpers import TempWorkspaceCase
from tutor.calc import evaluate, format_decimal
from tutor.core import TutorError


class EvaluateTest(unittest.TestCase):
    def test_exact_fractions(self) -> None:
        self.assertEqual(evaluate("comb(5, 2) / 2**5"), Fraction(5, 16))
        self.assertEqual(evaluate("1/6 + 1/3"), Fraction(1, 2))
        self.assertEqual(evaluate("(1/2)**3"), Fraction(1, 8))
        self.assertEqual(evaluate("factorial(5) / perm(5, 2)"), Fraction(6))

    def test_floats_and_functions(self) -> None:
        self.assertAlmostEqual(evaluate("sqrt(2*9.8*5)"), 9.899494936611665)
        self.assertAlmostEqual(evaluate("sin(pi/2)"), 1.0)
        self.assertAlmostEqual(evaluate("log(e)"), 1.0)
        self.assertEqual(evaluate("2^10"), 1024)
        self.assertEqual(evaluate("max(3, 7, 5)"), 7)

    def test_degree_functions(self) -> None:
        self.assertEqual(evaluate("cosd(60)"), 0.5)
        self.assertEqual(evaluate("sind(30)"), 0.5)
        self.assertEqual(evaluate("tand(45)"), 1.0)
        self.assertEqual(evaluate("40*cosd(60)"), 20.0)
        self.assertEqual(evaluate("asind(0.5)"), 30.0)
        self.assertEqual(evaluate("acosd(0.5)"), 60.0)
        self.assertEqual(evaluate("atand(1)"), 45.0)
        self.assertEqual(evaluate("atan2d(1, -1)"), 135.0)
        for expression in ("tand(90)", "tand(-270)", "asind(2)"):
            with self.subTest(expression=expression), self.assertRaises(TutorError):
                evaluate(expression)

    def test_rejects_non_arithmetic(self) -> None:
        for expression in ["__import__('os')", "open('x')", "x + 1", "(1).real", "[1, 2]", "lambda: 1",
                           "print(1)", "sqrt(x=4)", "'a' * 3", "1 if 1 else 2", "a.b"]:
            with self.subTest(expression=expression), self.assertRaises(TutorError):
                evaluate(expression)

    def test_limits(self) -> None:
        for expression in ["9**9**9", "factorial(5000)", "comb(100000, 3)", "1/0", "x" * 400, "", "(-8)**(1/3.0)",
                           "10.0**400", "exp(1000)"]:
            with self.subTest(expression=expression[:20]), self.assertRaises(TutorError):
                evaluate(expression)

    def test_decimal_format_is_brazilian(self) -> None:
        self.assertEqual(format_decimal(0.3125), "0,3125")
        self.assertEqual(format_decimal(2.0), "2")
        self.assertEqual(format_decimal(-0.0000001), "0")


class CalcCommandTest(TempWorkspaceCase):
    def test_command_output(self) -> None:
        code, out = self.run_cli("calc", "comb(4,2)/6")
        self.assertEqual(code, 0)
        self.assertEqual(out["exato"], "1")
        self.assertEqual(out["decimal"], "1")
        code, out = self.run_cli("calc", "import os")
        self.assertEqual(code, 1)
        self.assertEqual(out["erro"], "calc_invalida")

    def test_radian_warning(self) -> None:
        code, out = self.run_cli("calc", "40*cos(60)")
        self.assertIn("radianos", out["aviso"])
        code, out = self.run_cli("calc", "40*cosd(60)")
        self.assertNotIn("aviso", out)
        self.assertEqual(out["decimal"], "20")


if __name__ == "__main__":
    unittest.main()
