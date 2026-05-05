import ast
import math
import operator
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
from simpleeval import SimpleEval

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

_EVALUATOR = SimpleEval(names=CONSTANTS, functions=_FUNCTIONS)
# simpleeval locks the max power input value to 4000000 which causes some of
# the EPOCH statements to not evaluate. As recommended by their documentation
# we can circumvent this by removing the max power limit for the pow operator
# in simpleeval
_EVALUATOR.operators[ast.Pow] = operator.pow

# Functions that depend on simulation state or spatial position and therefore
# cannot be reduced to a scalar at parse time.
_UNEVALUATABLE_PATTERN = re.compile(
    r"\b(?:"
    r"if"  # conditional on spatial position
    r"|interpolate"  # piecewise spatial interpolation
    r"|number_density"  # species number density field
    r"|temp(?:_[xyz])?"  # {temp}{x,y,z} - species temperature field
    r"|[eb][xyz]"  # {e,b}{x,y,z} - electric and magnetic field components
    r")\s*\("
)


def _evaluate_line(expr: str, namespace: dict) -> bool | int | float | None:
    """
    Try to evaluate an EPOCH expression to a number.

    The following EPOCH functions depend on simulation state or spatial position
    and cannot be reduced to a scalar at parse time. Expressions containing
    them are returned unchanged as strings:

    - ``if()`` - conditional on spatial position
    - ``interpolate()`` - piecewise spatial interpolation
    - ``number_density()`` - species number density field
    - ``temp``, ``temp_{x,y,z}`` - species temperature field
    - ``{e,b}{x,y,z}`` - electric / magnetic field components

    Any other expression that references an undefined variable or raises an
    error during evaluation returns ``None``.

    Parameters
    ----------
    expr : str
        Raw EPOCH expression string, e.g. ``"2 * pi * c / lambda_L"``.
    namespace : dict
        Mapping of currently resolved variable names to their values.  The
        EPOCH physical constants and built-in functions are merged in
        automatically.

    Returns
    -------
    bool | int | float | str | None
        The evaluated result if the expression resolved to a scalar, the
        original string if it contains ``if()``, or ``None`` if evaluation
        failed due to an unresolved variable or other error.
    """
    if _UNEVALUATABLE_PATTERN.search(expr):
        return expr

    # Transform EPOCH expression syntax to Python eval-compatible syntax
    # lambda is a Python keyword but EPOCH uses it as a variable name
    processed = re.sub(r"\blambda\b", "_lambda", expr)
    # EPOCH uses ^ for exponentiation
    processed = processed.replace("^", "**")

    _EVALUATOR.names = {**CONSTANTS, **namespace}
    try:
        return _EVALUATOR.eval(processed)
    except Exception:
        return None


def _evaluate_block(block: dict, namespace: dict, deferred: list) -> dict:
    """
    Evaluate expressions in a block against a shared mutable namespace.

    Resolved values are written back into ``namespace`` immediately so later
    lines in the same block and later blocks can reference them. Items that
    fail due to an unresolved variable (but are not the above functions)
    are appended to ``deferred`` for a second-pass retry.

    Parameters
    ----------
    block : dict
        A single parsed block from the deck, e.g. the contents of a
        ``begin:control`` / ``end:control`` section.
    namespace : dict
        Shared mutable mapping of all variable names resolved so far.
        Updated in place as each expression is evaluated.
    deferred : list
        Accumulator for ``(result_dict, namespace_key, result_key, expr)``
        tuples whose evaluation failed due to a missing variable.  Updated
        in place.

    Returns
    -------
    dict
        The block with evaluatable string expressions replaced by their
        numeric values; unevaluatable strings are left unchanged.
    """
    result = {}

    for key, value in block.items():
        # lambda is a reserved keyword in Python, remap it in the namespace
        namespace_key = "_lambda" if key == "lambda" else key

        # Blocks that contain the "name= ..." field are stored as nested
        # blocks in their parent block. e.g. species contains electrons,
        # ions, photons, etc.
        if isinstance(value, dict):
            result[key] = _evaluate_block(value, namespace, deferred)

        elif isinstance(value, str):
            evaluated = _evaluate_line(value, namespace)
            if evaluated is not None:
                result[key] = evaluated
                namespace[namespace_key] = evaluated
            else:
                result[key] = value
                deferred.append((result, namespace_key, key, value))

        else:
            result[key] = value
            namespace[namespace_key] = value

    return result


def evaluate(deck: dict) -> dict:
    """
    Evaluate mathematical expressions in an EPOCH ``input.deck``. If an
    expression cannot be evaluated it is returned as a string.

    Blocks are processed in deck order with a single shared namespace so each
    block can reference values resolved by any earlier block. Items whose
    variables are not yet defined at the time they are encountered are
    collected and retried once the full namespace has been built. The retry
    loop repeats until no further progress is made, handling chains of
    inter-block dependencies.

    The following EPOCH functions depend on simulation state or spatial position
    and cannot be reduced to a scalar at parse time. Expressions containing
    them are returned unchanged as strings:

    - ``if()`` - conditional on spatial position
    - ``interpolate()`` - piecewise spatial interpolation
    - ``number_density()`` - species number density field
    - ``temp``, ``temp_{x,y,z}`` - species temperature field
    - ``{e,b}{x,y,z}`` - electric / magnetic field components

    .. warning::
        Expression strings are evaluated using ``simpleeval``, which restricts
        execution to arithmetic operations and the whitelisted EPOCH functions.
        Only call this function on deck files from sources you trust.

    Parameters
    ----------
    deck : dict
        Parsed EPOCH deck as returned by ``epydeck.load`` or ``epydeck.loads``

    Returns
    -------
    dict
        Copy of the deck with evaluatable expressions resolved to numbers
    """
    namespace: dict = {}
    deferred: list[tuple[dict, str, str, str]] = []

    evaluated: dict = {}
    for block_name, block in deck.items():
        evaluated[block_name] = _evaluate_block(block, namespace, deferred)

    # Retry items that failed because their dependencies were defined in a
    # later block.  Repeat until no further progress is made in case deferred
    # items depend on one another.
    while deferred:
        unresolved = []
        for result_dict, namespace_key, result_key, expr in deferred:
            value = _evaluate_line(expr, namespace)
            if value is not None:
                result_dict[result_key] = value
                namespace[namespace_key] = value
            else:
                unresolved.append((result_dict, namespace_key, result_key, expr))
        if len(unresolved) == len(deferred):
            break  # no progress this iteration so remaining items cannot be resolved
        deferred = unresolved

    return evaluated
