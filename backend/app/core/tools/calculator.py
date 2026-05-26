import math
import re


_SAFE_NAMES = {
    k: v for k, v in vars(math).items() if not k.startswith("_")
}
_SAFE_NAMES.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow})

_FORBIDDEN = re.compile(r'\b(import|exec|eval|open|__|\bos\b|\bsys\b)\b')


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    if _FORBIDDEN.search(expression):
        return "Error: unsafe expression"
    try:
        result = eval(expression, {"__builtins__": {}}, _SAFE_NAMES)  # noqa: S307
        return str(round(float(result), 10) if isinstance(result, (int, float)) else result)
    except ZeroDivisionError:
        return "Error: division by zero"
    except Exception as e:
        return f"Error: {e}"
