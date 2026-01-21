"""Tree-walking interpreter for the Keris programming language."""

from typing import Any, Dict, List, Optional
from .ast import *
from .runtime import RuntimeError
from .stdlib import create_stdlib


class Environment:
    """Represents a scope/environment for variable storage."""
    
    def __init__(self, enclosing: Optional['Environment'] = None):
        self.values: Dict[str, Any] = {}
        self.constants: set[str] = set()
        self.enclosing = enclosing
    
    def define(self, name: str, value: Any, is_const: bool = False):
        """Define a variable in this environment."""
        if is_const:
            self.constants.add(name)
        self.values[name] = value
    
    def get(self, name: str) -> Any:
        """Get a variable value."""
        if name in self.values:
            return self.values[name]
        if self.enclosing:
            return self.enclosing.get(name)
        raise RuntimeError(f"Undefined variable '{name}'")
    
    def assign(self, name: str, value: Any):
        """Assign to a variable."""
        if name in self.values:
            if name in self.constants:
                raise RuntimeError(f"Cannot reassign constant '{name}'")
            self.values[name] = value
            return value
        if self.enclosing:
            return self.enclosing.assign(name, value)
        raise RuntimeError(f"Undefined variable '{name}'")
    
    def get_at(self, distance: int, name: str) -> Any:
        """Get variable at a specific scope distance."""
        return self.ancestor(distance).values.get(name)
    
    def assign_at(self, distance: int, name: str, value: Any):
        """Assign variable at a specific scope distance."""
        self.ancestor(distance).values[name] = value
    
    def ancestor(self, distance: int) -> 'Environment':
        """Get ancestor environment at given distance."""
        env = self
        for _ in range(distance):
            env = env.enclosing
        return env


class ReturnException(Exception):
    """Exception used for return statements."""
    
    def __init__(self, value: Any):
        self.value = value


class BreakException(Exception):
    """Exception used for break statements."""
    pass


class ContinueException(Exception):
    """Exception used for continue statements."""
    pass


class KerisFunction:
    """Represents a Keris function."""
    
    def __init__(self, declaration: Function, closure: Environment):
        self.declaration = declaration
        self.closure = closure
    
    def call(self, interpreter: 'Interpreter', arguments: List[Any]) -> Any:
        """Call this function."""
        environment = Environment(self.closure)
        
        if len(arguments) != len(self.declaration.params):
            raise RuntimeError(
                f"Expected {len(self.declaration.params)} arguments but got {len(arguments)}"
            )
        
        for param, arg in zip(self.declaration.params, arguments):
            environment.define(param, arg)
        
        try:
            interpreter.execute_block(self.declaration.body, environment)
        except ReturnException as ret:
            return ret.value
        return None
    
    def __repr__(self):
        return f"<function {self.declaration.name}>"


class Interpreter:
    """Tree-walking interpreter for Keris."""
    
    def __init__(self):
        self.globals = Environment()
        self.environment = self.globals
        self.stdlib = create_stdlib()
        
        # Add standard library to global environment
        for name, value in self.stdlib.items():
            self.globals.define(name, value)
    
    def interpret(self, statements: List[Stmt]):
        """Interpret a list of statements."""
        try:
            for statement in statements:
                self.execute(statement)
        except RuntimeError as e:
            raise e
    
    def execute(self, stmt: Stmt):
        """Execute a statement."""
        if isinstance(stmt, Expression):
            self.evaluate(stmt.expr)
        elif isinstance(stmt, Var):
            value = None
            if stmt.initializer:
                value = self.evaluate(stmt.initializer)
            self.environment.define(stmt.name, value, stmt.is_const)
        elif isinstance(stmt, Block):
            self.execute_block(stmt.statements, Environment(self.environment))
        elif isinstance(stmt, If):
            self.execute_if(stmt)
        elif isinstance(stmt, While):
            self.execute_while(stmt)
        elif isinstance(stmt, For):
            self.execute_for(stmt)
        elif isinstance(stmt, Break):
            raise BreakException()
        elif isinstance(stmt, Continue):
            raise ContinueException()
        elif isinstance(stmt, Return):
            value = None
            if stmt.value:
                value = self.evaluate(stmt.value)
            raise ReturnException(value)
        elif isinstance(stmt, Function):
            func = KerisFunction(stmt, self.environment)
            self.environment.define(stmt.name, func)
        elif isinstance(stmt, Try):
            self.execute_try(stmt)
        else:
            raise RuntimeError(f"Unknown statement type: {type(stmt)}")
    
    def execute_block(self, statements: List[Stmt], environment: Environment):
        """Execute a block of statements in a new environment."""
        previous = self.environment
        try:
            self.environment = environment
            for statement in statements:
                self.execute(statement)
        finally:
            self.environment = previous
    
    def execute_if(self, stmt: If):
        """Execute an if statement."""
        if self.is_truthy(self.evaluate(stmt.condition)):
            self.execute(stmt.then_branch)
        elif stmt.else_branch:
            self.execute(stmt.else_branch)
    
    def execute_while(self, stmt: While):
        """Execute a while loop."""
        while self.is_truthy(self.evaluate(stmt.condition)):
            try:
                self.execute(stmt.body)
            except BreakException:
                break
            except ContinueException:
                continue
    
    def execute_for(self, stmt: For):
        """Execute a for loop."""
        iterable = self.evaluate(stmt.iterable)
        
        if not isinstance(iterable, (list, str)):
            raise RuntimeError("For loop iterable must be a list or string")
        
        for item in iterable:
            self.environment.define(stmt.variable, item)
            try:
                self.execute(stmt.body)
            except BreakException:
                break
            except ContinueException:
                continue
    
    def execute_try(self, stmt: Try):
        """Execute a try-catch statement."""
        try:
            self.execute(stmt.try_block)
        except RuntimeError as e:
            self.environment.define(stmt.catch_var, str(e.message))
            self.execute(stmt.catch_block)
    
    def evaluate(self, expr: Expr) -> Any:
        """Evaluate an expression."""
        if isinstance(expr, Literal):
            return expr.value
        elif isinstance(expr, Identifier):
            return self.environment.get(expr.name)
        elif isinstance(expr, Binary):
            return self.evaluate_binary(expr)
        elif isinstance(expr, Unary):
            return self.evaluate_unary(expr)
        elif isinstance(expr, Call):
            return self.evaluate_call(expr)
        elif isinstance(expr, Get):
            return self.evaluate_get(expr)
        elif isinstance(expr, Set):
            return self.evaluate_set(expr)
        elif isinstance(expr, Index):
            return self.evaluate_index(expr)
        elif isinstance(expr, IndexSet):
            return self.evaluate_index_set(expr)
        elif isinstance(expr, ListLiteral):
            return [self.evaluate(elem) for elem in expr.elements]
        elif isinstance(expr, DictLiteral):
            result = {}
            for key_expr, value_expr in expr.pairs:
                key = self.evaluate(key_expr)
                # Convert key to string if it's not already
                if not isinstance(key, (str, int, float, bool)):
                    key = str(key)
                result[key] = self.evaluate(value_expr)
            return result
        elif isinstance(expr, Assign):
            value = self.evaluate(expr.value)
            self.environment.assign(expr.name, value)
            return value
        elif isinstance(expr, Throw):
            value = self.evaluate(expr.value)
            raise RuntimeError(str(value))
        else:
            raise RuntimeError(f"Unknown expression type: {type(expr)}")
    
    def evaluate_binary(self, expr: Binary) -> Any:
        """Evaluate a binary expression."""
        left = self.evaluate(expr.left)
        right = self.evaluate(expr.right)
        
        op = expr.operator
        
        # Arithmetic
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        elif op == "-":
            self.check_number_operands(op, left, right)
            return left - right
        elif op == "*":
            if isinstance(left, str) and isinstance(right, (int, float)):
                return left * int(right)
            elif isinstance(right, str) and isinstance(left, (int, float)):
                return right * int(left)
            self.check_number_operands(op, left, right)
            return left * right
        elif op == "/":
            self.check_number_operands(op, left, right)
            if right == 0:
                raise RuntimeError("Division by zero")
            return left / right
        elif op == "%":
            self.check_number_operands(op, left, right)
            return left % right
        elif op == "**":
            self.check_number_operands(op, left, right)
            return left ** right
        
        # Comparison
        elif op == "==":
            return self.is_equal(left, right)
        elif op == "!=":
            return not self.is_equal(left, right)
        elif op == "<":
            self.check_number_operands(op, left, right)
            return left < right
        elif op == "<=":
            self.check_number_operands(op, left, right)
            return left <= right
        elif op == ">":
            self.check_number_operands(op, left, right)
            return left > right
        elif op == ">=":
            self.check_number_operands(op, left, right)
            return left >= right
        
        # Logical
        elif op == "and":
            return left and right
        elif op == "or":
            return left or right
        
        raise RuntimeError(f"Unknown binary operator: {op}")
    
    def evaluate_unary(self, expr: Unary) -> Any:
        """Evaluate a unary expression."""
        right = self.evaluate(expr.right)
        op = expr.operator
        
        if op == "-":
            self.check_number_operand(op, right)
            return -right
        elif op == "!" or op == "not":
            return not self.is_truthy(right)
        
        raise RuntimeError(f"Unknown unary operator: {op}")
    
    def evaluate_call(self, expr: Call) -> Any:
        """Evaluate a function call."""
        callee = self.evaluate(expr.callee)
        arguments = [self.evaluate(arg) for arg in expr.arguments]
        
        if isinstance(callee, KerisFunction):
            return callee.call(self, arguments)
        elif callable(callee):
            # Native function
            try:
                return callee(*arguments)
            except TypeError as e:
                raise RuntimeError(f"Function call error: {e}")
        else:
            raise RuntimeError("Can only call functions")
    
    def evaluate_get(self, expr: Get) -> Any:
        """Evaluate property access."""
        obj = self.evaluate(expr.obj)
        
        if isinstance(obj, dict):
            return obj.get(expr.name)
        elif isinstance(obj, list):
            # List methods
            if expr.name == "append":
                return lambda item: obj.append(item)
            elif expr.name == "pop":
                return lambda: obj.pop() if obj else None
            elif expr.name == "len":
                return len(obj)
            elif expr.name == "contains":
                return lambda item: item in obj
        elif hasattr(obj, '__getattr__'):
            return getattr(obj, expr.name, None)
        
        raise RuntimeError(f"Property '{expr.name}' not found")
    
    def evaluate_set(self, expr: Set) -> Any:
        """Evaluate property assignment."""
        obj = self.evaluate(expr.obj)
        value = self.evaluate(expr.value)
        
        if isinstance(obj, dict):
            obj[expr.name] = value
            return value
        
        raise RuntimeError(f"Cannot set property '{expr.name}'")
    
    def evaluate_index(self, expr: Index) -> Any:
        """Evaluate index operation."""
        obj = self.evaluate(expr.obj)
        index = self.evaluate(expr.index)
        
        if isinstance(obj, list):
            if not isinstance(index, int):
                raise RuntimeError("List index must be an integer")
            if index < 0:
                index = len(obj) + index
            if index < 0 or index >= len(obj):
                raise RuntimeError("List index out of range")
            return obj[index]
        elif isinstance(obj, dict):
            return obj.get(index)
        elif isinstance(obj, str):
            if not isinstance(index, int):
                raise RuntimeError("String index must be an integer")
            if index < 0:
                index = len(obj) + index
            if index < 0 or index >= len(obj):
                raise RuntimeError("String index out of range")
            return obj[index]
        
        raise RuntimeError("Indexing not supported for this type")
    
    def evaluate_index_set(self, expr: IndexSet) -> Any:
        """Evaluate index assignment."""
        obj = self.evaluate(expr.obj)
        index = self.evaluate(expr.index)
        value = self.evaluate(expr.value)
        
        if isinstance(obj, list):
            if not isinstance(index, int):
                raise RuntimeError("List index must be an integer")
            if index < 0:
                index = len(obj) + index
            if index < 0 or index >= len(obj):
                raise RuntimeError("List index out of range")
            obj[index] = value
            return value
        elif isinstance(obj, dict):
            obj[index] = value
            return value
        
        raise RuntimeError("Index assignment not supported for this type")
    
    def is_truthy(self, value: Any) -> bool:
        """Check if a value is truthy."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return True
    
    def is_equal(self, a: Any, b: Any) -> bool:
        """Check if two values are equal."""
        if a is None and b is None:
            return True
        if a is None:
            return False
        return a == b
    
    def check_number_operand(self, operator: str, operand: Any):
        """Check if operand is a number."""
        if not isinstance(operand, (int, float)):
            raise RuntimeError(f"Operand must be a number for {operator}")
    
    def check_number_operands(self, operator: str, left: Any, right: Any):
        """Check if operands are numbers."""
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            raise RuntimeError(f"Operands must be numbers for {operator}")
