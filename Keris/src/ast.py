"""Abstract Syntax Tree (AST) node definitions."""

from abc import ABC, abstractmethod
from typing import Any, Optional, List


class ASTNode(ABC):
    """Base class for all AST nodes."""
    
    @abstractmethod
    def __repr__(self) -> str:
        pass


# Expression nodes

class Expr(ASTNode):
    """Base class for expressions."""
    pass


class Literal(Expr):
    """Literal value (number, string, boolean, nil)."""
    
    def __init__(self, value: Any):
        self.value = value
    
    def __repr__(self):
        return f"Literal({self.value!r})"


class Identifier(Expr):
    """Variable identifier."""
    
    def __init__(self, name: str):
        self.name = name
    
    def __repr__(self):
        return f"Identifier({self.name!r})"


class Binary(Expr):
    """Binary operation (+, -, *, /, etc.)."""
    
    def __init__(self, left: Expr, operator: str, right: Expr):
        self.left = left
        self.operator = operator
        self.right = right
    
    def __repr__(self):
        return f"Binary({self.left}, {self.operator!r}, {self.right})"


class Unary(Expr):
    """Unary operation (-, !, not)."""
    
    def __init__(self, operator: str, right: Expr):
        self.operator = operator
        self.right = right
    
    def __repr__(self):
        return f"Unary({self.operator!r}, {self.right})"


class Call(Expr):
    """Function call."""
    
    def __init__(self, callee: Expr, arguments: List[Expr]):
        self.callee = callee
        self.arguments = arguments
    
    def __repr__(self):
        return f"Call({self.callee}, {self.arguments})"


class Get(Expr):
    """Get property/member (obj.property or obj[key])."""
    
    def __init__(self, obj: Expr, name: str):
        self.obj = obj
        self.name = name
    
    def __repr__(self):
        return f"Get({self.obj}, {self.name!r})"


class Set(Expr):
    """Set property/member (obj.property = value or obj[key] = value)."""
    
    def __init__(self, obj: Expr, name: str, value: Expr):
        self.obj = obj
        self.name = name
        self.value = value
    
    def __repr__(self):
        return f"Set({self.obj}, {self.name!r}, {self.value})"


class Index(Expr):
    """Index operation (list[index] or dict[key])."""
    
    def __init__(self, obj: Expr, index: Expr):
        self.obj = obj
        self.index = index
    
    def __repr__(self):
        return f"Index({self.obj}, {self.index})"


class IndexSet(Expr):
    """Index assignment (list[index] = value)."""
    
    def __init__(self, obj: Expr, index: Expr, value: Expr):
        self.obj = obj
        self.index = index
        self.value = value
    
    def __repr__(self):
        return f"IndexSet({self.obj}, {self.index}, {self.value})"


class ListLiteral(Expr):
    """List literal [1, 2, 3]."""
    
    def __init__(self, elements: List[Expr]):
        self.elements = elements
    
    def __repr__(self):
        return f"ListLiteral({self.elements})"


class DictLiteral(Expr):
    """Dictionary literal {"key": value}."""
    
    def __init__(self, pairs: List[tuple[Expr, Expr]]):
        self.pairs = pairs
    
    def __repr__(self):
        return f"DictLiteral({self.pairs})"


class Assign(Expr):
    """Variable assignment."""
    
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value
    
    def __repr__(self):
        return f"Assign({self.name!r}, {self.value})"


# Statement nodes

class Stmt(ASTNode):
    """Base class for statements."""
    pass


class Expression(Stmt):
    """Expression statement."""
    
    def __init__(self, expr: Expr):
        self.expr = expr
    
    def __repr__(self):
        return f"Expression({self.expr})"


class Var(Stmt):
    """Variable declaration (let/const)."""
    
    def __init__(self, name: str, initializer: Expr, is_const: bool = False):
        self.name = name
        self.initializer = initializer
        self.is_const = is_const
    
    def __repr__(self):
        const_str = "const" if self.is_const else "let"
        return f"Var({const_str} {self.name!r}, {self.initializer})"


class Block(Stmt):
    """Block of statements."""
    
    def __init__(self, statements: List[Stmt]):
        self.statements = statements
    
    def __repr__(self):
        return f"Block({len(self.statements)} statements)"


class If(Stmt):
    """If statement."""
    
    def __init__(self, condition: Expr, then_branch: Stmt, else_branch: Optional[Stmt] = None):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
    
    def __repr__(self):
        return f"If({self.condition}, {self.then_branch}, {self.else_branch})"


class While(Stmt):
    """While loop."""
    
    def __init__(self, condition: Expr, body: Stmt):
        self.condition = condition
        self.body = body
    
    def __repr__(self):
        return f"While({self.condition}, {self.body})"


class For(Stmt):
    """For loop."""
    
    def __init__(self, variable: str, iterable: Expr, body: Stmt):
        self.variable = variable
        self.iterable = iterable
        self.body = body
    
    def __repr__(self):
        return f"For({self.variable!r}, {self.iterable}, {self.body})"


class Break(Stmt):
    """Break statement."""
    
    def __repr__(self):
        return "Break()"


class Continue(Stmt):
    """Continue statement."""
    
    def __repr__(self):
        return "Continue()"


class Return(Stmt):
    """Return statement."""
    
    def __init__(self, value: Optional[Expr] = None):
        self.value = value
    
    def __repr__(self):
        return f"Return({self.value})"


class Function(Stmt):
    """Function definition."""
    
    def __init__(self, name: str, params: List[str], body: List[Stmt]):
        self.name = name
        self.params = params
        self.body = body
    
    def __repr__(self):
        return f"Function({self.name!r}, {self.params}, {len(self.body)} statements)"


class Try(Stmt):
    """Try-catch statement."""
    
    def __init__(self, try_block: Stmt, catch_var: str, catch_block: Stmt):
        self.try_block = try_block
        self.catch_var = catch_var
        self.catch_block = catch_block
    
    def __repr__(self):
        return f"Try({self.try_block}, catch {self.catch_var!r}, {self.catch_block})"


class Throw(Stmt):
    """Throw statement."""
    
    def __init__(self, value: Expr):
        self.value = value
    
    def __repr__(self):
        return f"Throw({self.value})"
