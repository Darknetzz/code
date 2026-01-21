"""Standard library functions for Keris."""

import math as py_math
from typing import Any, List, Dict


def create_stdlib() -> Dict[str, Any]:
    """Create and return the standard library."""
    stdlib = {}
    
    # I/O functions
    def print_func(*args):
        """Print values to stdout."""
        print(*args)
        return None
    
    def read_line_func():
        """Read a line from stdin."""
        try:
            return input()
        except EOFError:
            return ""
    
    def read_number_func():
        """Read a number from stdin."""
        try:
            line = input()
            if '.' in line:
                return float(line)
            return int(line)
        except (EOFError, ValueError):
            return 0
    
    stdlib["print"] = print_func
    stdlib["read_line"] = read_line_func
    stdlib["read_number"] = read_number_func
    
    # Math module
    math_module = {
        "abs": lambda x: abs(x),
        "sqrt": lambda x: py_math.sqrt(x),
        "pow": lambda x, y: x ** y,
        "max": lambda *args: max(args) if args else None,
        "min": lambda *args: min(args) if args else None,
        "floor": lambda x: py_math.floor(x),
        "ceil": lambda x: py_math.ceil(x),
        "round": lambda x: round(x),
        "sin": lambda x: py_math.sin(x),
        "cos": lambda x: py_math.cos(x),
        "tan": lambda x: py_math.tan(x),
        "pi": py_math.pi,
        "e": py_math.e,
    }
    stdlib["math"] = math_module
    
    # String module
    def str_len(s: str) -> int:
        return len(s)
    
    def str_upper(s: str) -> str:
        return s.upper()
    
    def str_lower(s: str) -> str:
        return s.lower()
    
    def str_split(s: str, delimiter: str = None) -> List:
        if delimiter is None:
            delimiter = " "
        return s.split(delimiter)
    
    def str_join(lst: List, delimiter: str = "") -> str:
        return delimiter.join(str(x) for x in lst)
    
    str_module = {
        "len": str_len,
        "upper": str_upper,
        "lower": str_lower,
        "split": str_split,
        "join": str_join,
    }
    stdlib["str"] = str_module
    
    # List module
    def list_append(lst: List, item: Any) -> None:
        lst.append(item)
        return None
    
    def list_pop(lst: List) -> Any:
        if len(lst) == 0:
            return None
        return lst.pop()
    
    def list_len(lst: List) -> int:
        return len(lst)
    
    def list_contains(lst: List, item: Any) -> bool:
        return item in lst
    
    list_module = {
        "append": list_append,
        "pop": list_pop,
        "len": list_len,
        "contains": list_contains,
    }
    stdlib["list"] = list_module
    
    # Dict module
    def dict_keys(d: Dict) -> List:
        return list(d.keys())
    
    def dict_values(d: Dict) -> List:
        return list(d.values())
    
    def dict_len(d: Dict) -> int:
        return len(d)
    
    def dict_contains(d: Dict, key: Any) -> bool:
        return key in d
    
    dict_module = {
        "keys": dict_keys,
        "values": dict_values,
        "len": dict_len,
        "contains": dict_contains,
    }
    stdlib["dict"] = dict_module
    
    # Type module
    def type_of(value: Any) -> str:
        """Get the type name of a value."""
        if value is None:
            return "nil"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "list"
        elif isinstance(value, dict):
            return "dict"
        else:
            return "unknown"
    
    type_module = {
        "of": type_of,
    }
    stdlib["type"] = type_module
    
    # Range function (for for loops)
    def range_func(start: int, end: int = None, step: int = 1) -> List:
        """Create a range of numbers."""
        if end is None:
            return list(py_math.range(0, start))
        return list(py_math.range(start, end, step))
    
    stdlib["range"] = range_func
    
    return stdlib
