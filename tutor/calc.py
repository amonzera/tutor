"""Calculadora segura para conferir contas: `bash bin/tutor.sh calc "comb(5, 2) / 2**5"`.

Avalia só aritmética (AST com lista fechada de nós e funções). Com inteiros e as
quatro operações o resultado é exato (fração); funções como `sqrt` passam a usar
ponto flutuante. Serve para o tutor e os agentes conferirem números sem ganhar
permissão para executar código arbitrário. Decimais usam ponto; a vírgula separa
argumentos de funções.
"""

from __future__ import annotations

import argparse
import ast
import math
import operator
from fractions import Fraction
from typing import Any, Callable

from tutor.core import Context, TutorError

MAX_EXPRESSION = 300
MAX_EXPONENT = 1000
MAX_FACTORIAL = 1000
MAX_COMB_N = 10_000
MAX_INT_DIGITS = 400

Number = int | float | Fraction

CONSTANTS: dict[str, Number] = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _factorial(n: Number) -> int:
    k = _as_int(n, "factorial")
    if not 0 <= k <= MAX_FACTORIAL:
        raise TutorError("calc_limite", f"factorial aceita de 0 a {MAX_FACTORIAL}.")
    return math.factorial(k)


def _comb(n: Number, k: Number) -> int:
    a, b = _as_int(n, "comb"), _as_int(k, "comb")
    if not 0 <= a <= MAX_COMB_N:
        raise TutorError("calc_limite", f"comb/perm aceitam n de 0 a {MAX_COMB_N}.")
    return math.comb(a, b)


def _perm(n: Number, k: Number | None = None) -> int:
    a = _as_int(n, "perm")
    if not 0 <= a <= MAX_COMB_N:
        raise TutorError("calc_limite", f"comb/perm aceitam n de 0 a {MAX_COMB_N}.")
    return math.perm(a, None if k is None else _as_int(k, "perm"))


def _as_int(value: Number, name: str) -> int:
    if isinstance(value, Fraction) and value.denominator == 1:
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise TutorError("calc_argumento", f"{name} precisa de número inteiro.")


def _float_fn(fn: Callable[..., float]) -> Callable[..., float]:
    def wrapper(*args: Number) -> float:
        return fn(*(float(a) for a in args))

    return wrapper


def _snap(value: float) -> float:
    """Arredonda para 12 casas: cosd(60) dá 0,5, e não 0,5000000000000001."""
    value = round(value, 12)
    return 0.0 if value == 0 else value


def _tand(degrees: float) -> float:
    if math.isclose(math.remainder(degrees - 90.0, 180.0), 0.0, abs_tol=1e-9):
        raise TutorError("calc_dominio", "tand não existe em 90° + k·180°.")
    return _snap(math.tan(math.radians(degrees)))


def _inverse_degrees(fn: Callable[[float], float]) -> Callable[[float], float]:
    def wrapper(value: float) -> float:
        try:
            return _snap(math.degrees(fn(value)))
        except ValueError as exc:
            raise TutorError("calc_dominio", "Valor fora do domínio da função.") from exc

    return wrapper


DEGREE_FUNCTIONS: dict[str, Callable[..., float]] = {
    "sind": _float_fn(lambda x: _snap(math.sin(math.radians(x)))),
    "cosd": _float_fn(lambda x: _snap(math.cos(math.radians(x)))),
    "tand": _float_fn(_tand),
    "asind": _float_fn(_inverse_degrees(math.asin)),
    "acosd": _float_fn(_inverse_degrees(math.acos)),
    "atand": _float_fn(_inverse_degrees(math.atan)),
    "atan2d": _float_fn(lambda y, x: _snap(math.degrees(math.atan2(y, x)))),
}
RADIAN_FUNCTIONS = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2"}
RADIAN_WARNING = (
    "sin, cos e tan recebem o ângulo em radianos (e asin, acos, atan devolvem radianos). Para graus, use sind, cosd, "
    "tand, asind, acosd, atand ou atan2d."
)

FUNCTIONS: dict[str, Callable[..., Any]] = {
    **DEGREE_FUNCTIONS,
    "sqrt": _float_fn(math.sqrt),
    "exp": _float_fn(math.exp),
    "log": _float_fn(math.log),
    "log10": _float_fn(math.log10),
    "log2": _float_fn(math.log2),
    "sin": _float_fn(math.sin),
    "cos": _float_fn(math.cos),
    "tan": _float_fn(math.tan),
    "asin": _float_fn(math.asin),
    "acos": _float_fn(math.acos),
    "atan": _float_fn(math.atan),
    "atan2": _float_fn(math.atan2),
    "sinh": _float_fn(math.sinh),
    "cosh": _float_fn(math.cosh),
    "tanh": _float_fn(math.tanh),
    "degrees": _float_fn(math.degrees),
    "radians": _float_fn(math.radians),
    "hypot": _float_fn(math.hypot),
    "floor": lambda x: math.floor(x),
    "ceil": lambda x: math.ceil(x),
    "abs": abs,
    "round": lambda x, n=0: round(float(x), _as_int(n, "round")),
    "min": min,
    "max": max,
    "factorial": _factorial,
    "comb": _comb,
    "perm": _perm,
    "gcd": lambda a, b: math.gcd(_as_int(a, "gcd"), _as_int(b, "gcd")),
}

BINARY: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


def _check_size(value: Number) -> Number:
    if isinstance(value, complex):
        raise TutorError("calc_dominio", "O resultado não é um número real.")
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise TutorError("calc_dominio", "O resultado não é um número finito.")
    if isinstance(value, Fraction):
        if max(len(str(abs(value.numerator))), len(str(value.denominator))) > MAX_INT_DIGITS:
            return float(value)
        return value.numerator if value.denominator == 1 else value
    if isinstance(value, int) and len(str(abs(value))) > MAX_INT_DIGITS:
        raise TutorError("calc_limite", "Resultado grande demais.")
    return value


def _power(base: Number, exponent: Number) -> Number:
    if isinstance(exponent, (int, Fraction)) and Fraction(exponent).denominator == 1:
        k = int(exponent)
        if abs(k) > MAX_EXPONENT:
            raise TutorError("calc_limite", f"Expoente maior que {MAX_EXPONENT}.")
        if isinstance(base, (int, Fraction)):
            if base == 0 and k < 0:
                raise TutorError("calc_dominio", "Divisão por zero.")
            return Fraction(base) ** k
    try:
        return float(base) ** float(exponent)
    except OverflowError as exc:
        raise TutorError("calc_limite", "Resultado grande demais.") from exc


def _eval(node: ast.AST) -> Number:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(node.value) if isinstance(node.value, int) else node.value
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            return _check_size(_power(left, right))
        op = BINARY.get(type(node.op))
        if op is None:
            raise TutorError("calc_invalida", "Operador não permitido.")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise TutorError("calc_dominio", "Divisão por zero.")
        if isinstance(node.op, ast.Div) and isinstance(left, (int, Fraction)) and isinstance(right, (int, Fraction)):
            return _check_size(Fraction(left) / Fraction(right))
        try:
            return _check_size(op(left, right))
        except OverflowError as exc:
            raise TutorError("calc_limite", "Resultado grande demais.") from exc
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
        if node.keywords:
            raise TutorError("calc_invalida", "Use só argumentos posicionais.")
        args = [_eval(arg) for arg in node.args]
        try:
            return _check_size(FUNCTIONS[node.func.id](*args))
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise TutorError("calc_dominio", f"{node.func.id}: {exc}.") from exc
        except TypeError as exc:
            raise TutorError("calc_argumento", f"{node.func.id}: número de argumentos inválido.") from exc
    raise TutorError(
        "calc_invalida",
        "Expressão não permitida. Use números, + - * / // % **, parênteses, pi, e e funções de math.",
        funcoes=sorted(FUNCTIONS),
    )


def evaluate(expression: str) -> Number:
    text = expression.strip()
    if not text:
        raise TutorError("calc_invalida", "Expressão vazia.")
    if len(text) > MAX_EXPRESSION:
        raise TutorError("calc_limite", f"Expressão com mais de {MAX_EXPRESSION} caracteres.")
    try:
        tree = ast.parse(text.replace("^", "**"), mode="eval")
    except SyntaxError as exc:
        raise TutorError("calc_invalida", f"Erro de sintaxe na expressão: {exc.msg}.") from exc
    return _eval(tree)


def format_decimal(value: float, digits: int = 6) -> str:
    """Formata no padrão brasileiro: vírgula decimal, sem zeros sobrando."""
    if math.isinf(value) or math.isnan(value):
        return str(value)
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return (text if text not in ("-0", "") else "0").replace(".", ",")


def describe(value: Number, digits: int = 6) -> dict[str, Any]:
    out: dict[str, Any] = {"decimal": format_decimal(float(value), digits), "valor": float(value)}
    if isinstance(value, Fraction):
        out["exato"] = str(value)
    elif isinstance(value, int):
        out["exato"] = str(value)
    return out


def uses_radians(expression: str) -> bool:
    try:
        tree = ast.parse(expression.strip().replace("^", "**"), mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in RADIAN_FUNCTIONS
               for node in ast.walk(tree))


def cmd_calc(args: argparse.Namespace, ctx: Context) -> dict[str, Any]:
    value = evaluate(args.expressao)
    out = {
        "status": "ok",
        "expressao": args.expressao,
        **describe(value, args.casas),
        "llm_directive": (
            "Use o resultado para conferir a sua conta antes de afirmar qualquer número ao aluno. "
            "Se divergir do que você ia dizer, refaça o raciocínio."
        ),
    }
    if uses_radians(args.expressao):
        out["aviso"] = RADIAN_WARNING
    return out


def add_commands(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("calc", help='avalia uma expressão aritmética com segurança (ex.: "comb(5,2)/2**5")')
    parser.add_argument("expressao", help="expressão; decimais com ponto, argumentos separados por vírgula")
    parser.add_argument("--casas", type=int, default=6, help="casas decimais na forma decimal (padrão 6)")
    parser.set_defaults(handler=cmd_calc)
