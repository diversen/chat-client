import ast
import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any


PY_NS: dict[str, Any] = {}


def python(code: str) -> str:
    """
    Execute Python code and return captured stdout/stderr and final expression result.
    """
    out, err = io.StringIO(), io.StringIO()
    result_obj: Any = None

    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result_obj = eval(compile(code, "<tool>", "eval"), PY_NS, PY_NS)
            except SyntaxError:
                tree = ast.parse(code, mode="exec")
                last_expr = None
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    last_expr = ast.Expression(tree.body.pop().value)

                exec(compile(tree, "<tool>", "exec"), PY_NS, PY_NS)

                if last_expr is not None:
                    try:
                        result_obj = eval(compile(last_expr, "<tool>", "eval"), PY_NS, PY_NS)
                    except NameError:
                        result_obj = None
    except Exception:
        err.write("\n[exception]\n" + traceback.format_exc())

    parts: list[str] = []
    stdout_text = out.getvalue().rstrip()
    stderr_text = err.getvalue().rstrip()
    if stdout_text:
        parts.append(stdout_text)
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text}")
    if result_obj is not None:
        parts.append(str(result_obj))

    return "\n".join(parts).strip() or "OK"
