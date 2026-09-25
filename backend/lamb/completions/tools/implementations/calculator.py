"""
Safe arithmetic calculator using AST-based evaluation.
Only allows whitelisted operators — no eval() of raw input.
"""

import ast
import operator
from typing import Any

ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

ALLOWED_CONST_TYPES = (int, float)


def _safe_eval(node: ast.AST) -> Any:
    """Recursively evaluate an AST node using only whitelisted operators."""
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, ALLOWED_CONST_TYPES):
            raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError(f"Unsupported syntax: {type(node).__name__}")


def run_calculator(args: dict) -> dict:
    """
    Evaluate a mathematical expression safely.

    Expected args:
        expression (str): The math expression to evaluate.

    Returns:
        dict with success bool and either result (float) or error (str).
    """
    expr = (args.get("expression") or "").strip()
    if not expr:
        return {"success": False, "error": "No expression provided"}

    try:
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree.body)
        return {"success": True, "result": result}
    except ZeroDivisionError:
        return {"success": False, "error": "Division by zero"}
    except (SyntaxError, ValueError, OverflowError, MemoryError) as e:
        return {"success": False, "error": str(e)}