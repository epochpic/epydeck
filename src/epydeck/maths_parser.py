import math
import re

from scipy.constants import (
    Boltzmann,
    c,
    electron_mass,
    elementary_charge,
    epsilon_0,
    eV,
    mu_0,
    pi,
)

CONSTANTS = {
    "pi": pi,
    "kb": Boltzmann,
    "me": electron_mass,
    "qe": elementary_charge,
    "c": c,
    "epsilon0": epsilon_0,
    "mu0": mu_0,
    "ev": eV,
    "kev": 1e3 * eV,
    "mev": 1e6 * eV,
    "micron": 1e-6,
    "milli": 1e-3,
    "micro": 1e-6,
    "nano": 1e-9,
    "pico": 1e-12,
    "femto": 1e-15,
    "atto": 1e-18,
    "cc": 1e-6,
}


def _critical(omega):
    """Critical density: n_crit = omega^2 * me * epsilon0 / qe^2"""
    return (omega**2 * electron_mass * epsilon_0) / elementary_charge**2


def _gauss(x, x0, w):
    return math.exp(-(((x - x0) / w) ** 2))


def _supergauss(x, x0, w, n):
    return math.exp(-((((x - x0) / w) ** 2) ** n))


def _semigauss(t, A, A0, w):
    t0 = w * math.sqrt(-math.log(A0 / A))
    if t < t0:
        return A * math.exp(-(((t - t0) / w) ** 2))
    return A


_FUNCTIONS = {
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "nint": round,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "exp": math.exp,
    "loge": math.log,
    "log10": math.log10,
    "log_base": lambda a, b: math.log(a, b),
    "gauss": _gauss,
    "supergauss": _supergauss,
    "semigauss": _semigauss,
    "critical": _critical,
}

_BASE_NAMESPACE = {"__builtins__": {}, **CONSTANTS, **_FUNCTIONS}

# Matches EPOCH's if() function
_EPOCH_IF_PATTERN = re.compile(r"\bif\s*\(")


def _preprocess(expr: str) -> str:
    """Transform EPOCH expression syntax to Python eval-compatible syntax."""
    # lambda is a Python keyword but EPOCH uses it as a variable name
    expr = re.sub(r"\blambda\b", "_lambda", expr)
    # EPOCH uses ^ for exponentiation
    expr = expr.replace("^", "**")
    return expr


def _try_evaluate(expr: str, namespace: dict) -> bool | int | float | None:
    """
    Try to evaluate an EPOCH expression to a number.

    Returns None if the expression contains if(), references undefined
    variables, or cannot be reduced to a plain number.
    """
    if not isinstance(expr, str):
        return None
    if _EPOCH_IF_PATTERN.search(expr):
        return None

    processed = _preprocess(expr)
    eval_namespace = {**_BASE_NAMESPACE, **namespace}

    try:
        result = eval(processed, eval_namespace)
        if isinstance(result, (bool, int, float)):
            return result
    except Exception:
        pass
    return None


def _evaluate_block(block: dict, namespace: dict) -> dict:
    """
    Evaluate expressions in a block, accumulating resolved values so later
    lines in the same block can reference earlier ones.
    """
    result = {}
    local_namespace = dict(namespace)

    for key, value in block.items():
        # lambda is reserved in Python but remap to _lambda in the namespace
        namespace_key = "_lambda" if key == "lambda" else key

        # Blocks that contain the "name= ..." field are stored as nested
        # blocks in their parent block. e.g. species contains electrons,
        # ions, photons, etc.
        if isinstance(value, dict):
            result[key] = _evaluate_block(value, local_namespace)
        elif isinstance(value, str):
            evaluated = _try_evaluate(value, local_namespace)
            if evaluated is not None:
                result[key] = evaluated
                local_namespace[namespace_key] = evaluated
            else:
                result[key] = value

        elif isinstance(value, list):
            items = []
            for v in value:
                if isinstance(v, str):
                    ev = _try_evaluate(v, local_namespace)
                    items.append(ev if ev is not None else v)
                else:
                    items.append(v)
            result[key] = items

        elif isinstance(value, (bool, int, float)):
            result[key] = value
            local_namespace[namespace_key] = value
        else:
            result[key] = value

    return result


def evaluate(deck: dict) -> dict:
    """
    Evaluate mathematical expressions in an EPOCH ``input.deck``.

    This function evaluates the deck by first merging all ``constant`` blocks
    into a single global namespace. This global list of constants is processed
    and resolved before the parser looks at any other part of the simulation
    setup. While this makes user-defined constants available throughout the
    deck, it strictly enforces a "top-down" dependency where constants cannot
    "look back" at variables defined in other blocks like control or species.

    In practice, this means an expression like ``laser_focus = -x_min`` will
    fail to evaluate if ``x_min`` is defined in the control block which is
    placed before its definition in a ``constant`` block. Even though EPOCH
    will handle this by evaluating blocks sequentially, ``epydeck`` merges
    all the constant blocks into a single `dict` first. To ensure your deck
    parses correctly, define your simulation bounds and laser parameters as
    constants before assigning them to specific EPOCH control variables.

    Resolves string expressions to floats where all referenced variables are
    known. Uses EPOCH physical constants (via scipy) and any constants defined
    in the deck's ``constant`` block. Expressions containing ``if()`` or
    variables that have not been defined are left as strings.

    Within each block, lines are processed in order so a line can reference
    values defined earlier in the same block.

    Parameters
    ----------
    deck : dict
        Parsed EPOCH deck as returned by ``epydeck.load`` or ``epydeck.loads``.

    Returns
    -------
    dict
        Copy of the deck with evaluatable expressions resolved to floats.
    """
    # Build the global namespace from the constant block first so those
    # user-defined constants are available everywhere else in the deck.
    namespace: dict = {}

    if "constant" in deck:
        for key, value in deck["constant"].items():
            # lambda is reserved in Python but remap to _lambda in the namespace
            namespace_key = "_lambda" if key == "lambda" else key

            if isinstance(value, str):
                result = _try_evaluate(value, namespace)
                if result is not None:
                    namespace[namespace_key] = result

            elif isinstance(value, (bool, int, float)):
                namespace[namespace_key] = value

    evaluated: dict = {}
    for block_name, block in deck.items():
        evaluated[block_name] = _evaluate_block(block, namespace)

    return evaluated
