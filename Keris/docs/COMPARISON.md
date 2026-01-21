# Keris vs Python: Language Comparison

This document compares Keris with Python, highlighting key differences, similarities, and design choices.

## Overview

Both Keris and Python are general-purpose, dynamically-typed, interpreted languages with Python-inspired syntax. However, there are significant differences in features, syntax, and capabilities.

---

## Syntax Differences

### Block Delimiters

**Python:**
```python
if x > 5:
    print("Greater")
else:
    print("Lesser")
```

**Keris:**
```keris
if x > 5 {
    print("Greater")
} else {
    print("Lesser")
}
```

- **Python**: Uses indentation (whitespace) for blocks
- **Keris**: Uses curly braces `{}` for blocks (C-style)
- **Impact**: Keris is more explicit about scope, Python is more concise

### Comments

**Python:**
```python
# Single-line comment only
```

**Keris:**
```keris
# Single-line comment (preferred)
// Single-line comment (also supported)
/* Multi-line comment */
```

- **Python**: Only `#` for comments
- **Keris**: Supports `#`, `//`, and `/* */` comments

### Variable Declaration

**Python:**
```python
x = 10
PI = 3.14  # Convention for constants
```

**Keris:**
```keris
let x = 10        # Explicit mutable variable
const PI = 3.14   # Explicit constant
y = 20            # Implicit global (not recommended)
```

- **Python**: No explicit variable declaration keywords
- **Keris**: `let` for variables, `const` for constants (more explicit)

### String Literals

**Python:**
```python
"Double quotes"
'Single quotes'
"""Triple quotes for multi-line"""
f"Formatted {variable}"
```

**Keris:**
```keris
"Double quotes"
'Single quotes'
# No triple quotes or f-strings
```

- **Python**: Supports triple quotes and f-strings
- **Keris**: Only single and double quotes (simpler, less features)

### Number Types

**Python:**
```python
x = 42      # int
y = 3.14    # float
z = 1 + 2j  # complex
```

**Keris:**
```keris
x = 42      # number (unified int/float)
y = 3.14    # number (unified int/float)
# No complex numbers
```

- **Python**: Separate `int` and `float` types, plus `complex`
- **Keris**: Unified `number` type (simpler type system)

---

## Type System

### Dynamic Typing

Both languages are dynamically typed, but:

**Python:**
- Strong typing with type hints (optional)
- Type checking available via `mypy`
- Rich type system (generics, unions, etc.)

**Keris:**
- Pure dynamic typing
- No type hints or static analysis
- Simpler type system

### Type Checking

**Python:**
```python
type(42)        # <class 'int'>
isinstance(42, int)  # True
```

**Keris:**
```keris
type.of(42)     # "number"
# No isinstance equivalent
```

- **Python**: Returns type objects, has `isinstance()`
- **Keris**: Returns string names, simpler API

---

## Collections

### Lists

**Python:**
```python
lst = [1, 2, 3]
lst.append(4)
lst.pop()
len(lst)
3 in lst
```

**Keris:**
```keris
let lst = [1, 2, 3]
list.append(lst, 4)
list.pop(lst)
list.len(lst)
list.contains(lst, 3)
```

- **Python**: Methods on objects (object-oriented)
- **Keris**: Functions in `list` module (functional style)

### Dictionaries

**Python:**
```python
d = {"a": 1, "b": 2}
d["a"]
d.get("a", 0)
d.keys()
d.values()
```

**Keris:**
```keris
let d = {"a": 1, "b": 2}
d["a"]
d["a"]  # Returns nil if not found (no .get())
dict.keys(d)
dict.values(d)
```

- **Python**: Rich dictionary API with `.get()`, `.items()`, etc.
- **Keris**: Simpler API, fewer methods

### Sets and Tuples

**Python:**
```python
s = {1, 2, 3}      # Set
t = (1, 2, 3)      # Tuple
```

**Keris:**
```keris
# No sets or tuples (yet)
```

- **Python**: Has sets and tuples
- **Keris**: Only lists and dictionaries

---

## Functions

### Function Definition

**Python:**
```python
def greet(name, age=0):
    return f"Hello, {name}"
```

**Keris:**
```keris
def greet(name, age = 0) {
    return "Hello, " + name
}
```

- **Python**: Uses `:` and indentation
- **Keris**: Uses `{}` blocks
- Both support default parameters

### Advanced Features

**Python:**
- `*args` and `**kwargs`
- Decorators
- Generators (`yield`)
- Lambda functions
- Type hints
- Docstrings

**Keris:**
- No `*args` or `**kwargs` (yet)
- No decorators
- No generators
- No lambda functions
- No type hints
- No docstrings

---

## Control Flow

### If/Else

Both are similar, but:

**Python:**
```python
if x > 5:
    pass
elif x > 3:
    pass
else:
    pass
```

**Keris:**
```keris
if x > 5 {
    # code
} elif x > 3 {
    # code
} else {
    # code
}
```

- Same logic, different syntax

### Loops

**Python:**
```python
for i in range(10):
    print(i)

for item in items:
    print(item)

while condition:
    break
    continue
```

**Keris:**
```keris
for i in range(0, 10) {
    print(i)
}

for item in items {
    print(item)
}

while condition {
    break
    continue
}
```

- Similar functionality, different syntax

### Pattern Matching

**Python:**
```python
match x:
    case 1:
        pass
    case _:
        pass
```

**Keris:**
```keris
# No pattern matching
```

---

## Error Handling

**Python:**
```python
try:
    risky_code()
except ValueError as e:
    handle_error(e)
except Exception:
    handle_other()
finally:
    cleanup()
```

**Keris:**
```keris
try {
    risky_code()
} catch error {
    handle_error(error)
}
# No multiple catch blocks or finally
```

- **Python**: Multiple exception types, `finally` blocks
- **Keris**: Single catch block, simpler model

---

## Object-Oriented Programming

**Python:**
```python
class Person:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}"
```

**Keris:**
```keris
# No classes or OOP (yet)
# Uses dictionaries and functions instead
```

- **Python**: Full OOP support (classes, inheritance, polymorphism)
- **Keris**: No OOP (functional/procedural style)

---

## Standard Library

### I/O

**Python:**
```python
print("Hello")
input()  # Read line
```

**Keris:**
```keris
print("Hello")
read_line()  # Read line
read_number()  # Read number
```

- Similar functionality

### Math

**Python:**
```python
import math
math.sqrt(16)
math.pi
```

**Keris:**
```keris
math.sqrt(16)
math.pi
```

- Similar, but Keris has fewer functions

### String Operations

**Python:**
```python
"hello".upper()
"hello".split(",")
",".join(["a", "b"])
```

**Keris:**
```keris
str.upper("hello")
str.split("hello", ",")
str.join(["a", "b"], ",")
```

- **Python**: Methods on strings
- **Keris**: Functions in `str` module

---

## Advanced Features

### Python Has, Keris Doesn't

- **List comprehensions**: `[x*2 for x in range(10)]`
- **Dictionary comprehensions**: `{k: v*2 for k, v in d.items()}`
- **Generator expressions**: `(x*2 for x in range(10))`
- **Context managers**: `with open("file") as f:`
- **Decorators**: `@decorator`
- **Properties**: `@property`
- **Metaclasses**
- **Import system**: `import`, `from`, `as`
- **Packages and modules**
- **Namespaces**
- **Closures with `nonlocal`**
- **Unpacking**: `a, b = (1, 2)`
- **Slicing**: `lst[1:5:2]`
- **Operator overloading**
- **Magic methods**: `__init__`, `__str__`, etc.

### Keris Has, Python Doesn't

- **Explicit variable declarations**: `let`, `const`
- **Curly brace blocks**: More explicit scope
- **Multiple comment styles**: `#`, `//`, `/* */`
- **Unified number type**: Simpler type system

---

## Performance

**Python:**
- Mature, highly optimized interpreter (CPython)
- JIT compilation available (PyPy)
- C extensions for performance
- Large ecosystem

**Keris:**
- Educational/toy interpreter
- Tree-walking interpreter (slower)
- No optimization
- Minimal ecosystem

---

## Use Cases

### Python
- Production applications
- Web development (Django, Flask)
- Data science (NumPy, Pandas)
- Machine learning (TensorFlow, PyTorch)
- Scripting and automation
- Large-scale projects

### Keris
- Learning language design
- Educational purposes
- Small scripts
- Prototyping ideas
- Understanding interpreters

---

## Summary Table

| Feature | Python | Keris |
|---------|--------|-------|
| **Block Syntax** | Indentation | Curly braces |
| **Variable Declaration** | Implicit | `let`/`const` |
| **Comments** | `#` only | `#`, `//`, `/* */` |
| **OOP** | Full support | None |
| **Type System** | Rich, with hints | Simple, dynamic only |
| **Collections** | List, dict, set, tuple | List, dict only |
| **Functions** | Advanced features | Basic features |
| **Error Handling** | Multiple exceptions, finally | Single catch |
| **Standard Library** | Extensive | Minimal |
| **Performance** | Optimized | Educational |
| **Ecosystem** | Huge | Minimal |
| **Maturity** | Production-ready | Educational |

---

## When to Use Python

- Production applications
- Need extensive libraries
- Team collaboration
- Performance matters
- Complex projects
- Industry standard

## When to Use Keris

- Learning language design
- Understanding interpreters
- Educational projects
- Simple scripts
- Experimentation
- Teaching programming concepts

---

## Conclusion

Keris is inspired by Python but is a much simpler language designed for educational purposes. It shares Python's philosophy of readability and simplicity but lacks many advanced features. Python is a mature, production-ready language with a vast ecosystem, while Keris is a learning tool that demonstrates language implementation concepts.

**Key Takeaway**: Keris is to Python what a bicycle is to a motorcycle - simpler, educational, and great for learning, but not suitable for production use.
