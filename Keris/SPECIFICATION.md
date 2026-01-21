# Keris Programming Language Specification

## Language Overview

Keris is a general-purpose, dynamically-typed, interpreted programming language inspired by Python. It emphasizes readability, simplicity, and expressiveness.

### Design Principles
- **Readability**: Code should be clear and self-documenting
- **Simplicity**: Minimal syntax, maximum expressiveness
- **Python-inspired**: Familiar to Python developers
- **Dynamic**: Flexible type system with runtime type checking

---

## Syntax

### Comments

```keris
# Single-line comment (preferred)
// Single-line comment (also supported)

/*
  Multi-line comment
  Can span multiple lines
*/
```

### Identifiers

- Start with letter or underscore
- Followed by letters, digits, or underscores
- Case-sensitive
- Examples: `x`, `myVar`, `_private`, `count123`

### Keywords

```
if, else, elif, while, for, in, break, continue, return
def, let, const
true, false, nil
and, or, not
import, from
try, catch, throw
```

### Literals

#### Numbers
```keris
42          // Integer
3.14        // Float
0xFF        // Hexadecimal
0b1010      // Binary
1e5         // Scientific notation
```

#### Strings
```keris
"Hello, World!"     // Double quotes
'Hello, World!'     // Single quotes
"Line 1\nLine 2"    // Escape sequences: \n, \t, \\, \", \'
```

#### Booleans
```keris
true
false
```

#### Nil
```keris
nil  // Represents absence of value
```

---

## Data Types

### Primitive Types
- **Number**: Integers and floats (unified type)
- **String**: Immutable sequences of characters
- **Boolean**: `true` or `false`
- **Nil**: Represents no value

### Collection Types
- **List**: Ordered, mutable sequences `[1, 2, 3]`
- **Dict**: Key-value mappings `{"key": "value"}`
- **Set**: Unordered collections of unique elements (future)

---

## Variables

### Declaration

```keris
let x = 10              // Mutable variable
const PI = 3.14159      // Immutable constant
y = 20                  // Implicit declaration (global)
```

### Assignment

```keris
x = 42
x = x + 1
x += 1
x -= 1
x *= 2
x /= 2
```

---

## Expressions

### Arithmetic Operators
```keris
+   // Addition
-   // Subtraction
*   // Multiplication
/   // Division
%   // Modulo
**  // Exponentiation
```

### Comparison Operators
```keris
==  // Equality
!=  // Inequality
<   // Less than
>   // Greater than
<=  // Less than or equal
>=  // Greater than or equal
```

### Logical Operators
```keris
and  // Logical AND
or   // Logical OR
not  // Logical NOT
```

### String Operations
```keris
"Hello" + " " + "World"  // Concatenation
"Hello" * 3             // Repetition
```

---

## Statements

### If/Else

```keris
if condition {
    // code
} elif other_condition {
    // code
} else {
    // code
}
```

### While Loop

```keris
while condition {
    // code
    if should_break {
        break
    }
    if should_continue {
        continue
    }
}
```

### For Loop

```keris
for item in list {
    print(item)
}

for i in range(0, 10) {
    print(i)
}
```

### Return

```keris
return value
return  // Returns nil
```

---

## Functions

### Definition

```keris
def greet(name) {
    return "Hello, " + name
}

def add(a, b) {
    return a + b
}

def no_args() {
    print("No arguments")
}
```

### Calling

```keris
greet("World")
add(5, 3)
no_args()
```

### Default Parameters

```keris
def greet(name = "Guest") {
    return "Hello, " + name
}
```

### Variable Arguments (Future)

---

## Collections

### Lists

```keris
let numbers = [1, 2, 3, 4, 5]
let empty = []

// Access
numbers[0]        // First element
numbers[-1]       // Last element

// Assignment
numbers[0] = 10

// Methods
numbers.append(6)
numbers.pop()
numbers.len()
```

### Dictionaries

```keris
let person = {
    "name": "Alice",
    "age": 30
}

// Access
person["name"]
person.name  // Dot notation (if key is identifier)

// Assignment
person["city"] = "New York"
person.city = "New York"

// Methods
person.keys()
person.values()
person.len()
```

---

## Error Handling

```keris
try {
    // code that might throw
    throw "Error message"
} catch error {
    print("Caught: " + error)
}
```

---

## Modules

```keris
import math
import io from "io"

math.sqrt(16)
io.print("Hello")
```

---

## Standard Library

### I/O

```keris
print("Hello, World!")
print(42, "items")

let input = read_line()
let number = read_number()
```

### Math

```keris
math.abs(-5)
math.sqrt(16)
math.pow(2, 3)
math.max(1, 2, 3)
math.min(1, 2, 3)
math.floor(3.7)
math.ceil(3.2)
math.round(3.5)
```

### String

```keris
str.len("hello")
str.upper("hello")
str.lower("HELLO")
str.split("a,b,c", ",")
str.join(["a", "b", "c"], ",")
```

### List

```keris
list.append([1, 2], 3)
list.pop([1, 2, 3])
list.len([1, 2, 3])
list.contains([1, 2, 3], 2)
```

### Dict

```keris
dict.keys({"a": 1, "b": 2})
dict.values({"a": 1, "b": 2})
dict.len({"a": 1, "b": 2})
dict.contains({"a": 1}, "a")
```

### Type

```keris
type.of(42)        // "number"
type.of("hello")   // "string"
type.of(true)      // "boolean"
type.of(nil)       // "nil"
type.of([1, 2])    // "list"
type.of({"a": 1})  // "dict"
```

---

## Operator Precedence

1. `()` (parentheses)
2. `**` (exponentiation)
3. `*`, `/`, `%` (multiplicative)
4. `+`, `-` (additive)
5. `<`, `>`, `<=`, `>=` (comparison)
6. `==`, `!=` (equality)
7. `and` (logical AND)
8. `or` (logical OR)
9. `=` (assignment)

---

## Examples

### Hello World

```keris
print("Hello, World!")
```

### Variables and Functions

```keris
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

let result = factorial(5)
print(result)
```

### Lists and Loops

```keris
let numbers = [1, 2, 3, 4, 5]
let sum = 0

for num in numbers {
    sum = sum + num
}

print("Sum:", sum)
```

### Dictionaries

```keris
let person = {
    "name": "Alice",
    "age": 30,
    "city": "New York"
}

print(person["name"] + " is " + person["age"] + " years old")
```

### Error Handling

```keris
def divide(a, b) {
    if b == 0 {
        throw "Division by zero"
    }
    return a / b
}

try {
    let result = divide(10, 0)
} catch error {
    print("Error:", error)
}
```

---

## Grammar (BNF-like)

```
program     := statement*

statement   := expr_stmt
            |  if_stmt
            |  while_stmt
            |  for_stmt
            |  return_stmt
            |  break_stmt
            |  continue_stmt
            |  let_stmt
            |  const_stmt
            |  def_stmt
            |  block
            |  try_stmt

expr_stmt   := expression ";"
            |  expression

if_stmt     := "if" expression block ("elif" expression block)* ("else" block)?

while_stmt  := "while" expression block

for_stmt    := "for" IDENTIFIER "in" expression block

return_stmt := "return" expression?
            |  "return"

break_stmt  := "break"
continue_stmt := "continue"

let_stmt    := "let" IDENTIFIER "=" expression
const_stmt  := "const" IDENTIFIER "=" expression

def_stmt    := "def" IDENTIFIER "(" parameters? ")" block

block       := "{" statement* "}"

try_stmt    := "try" block "catch" IDENTIFIER block

expression  := assignment

assignment  := (IDENTIFIER | member) "=" assignment
            |  logic_or

logic_or    := logic_and ("or" logic_and)*
logic_and   := equality ("and" equality)*
equality    := comparison (("==" | "!=") comparison)*
comparison  := term (("<" | ">" | "<=" | ">=") term)*
term        := factor (("+" | "-") factor)*
factor      := unary (("*" | "/" | "%") unary)*
unary       := ("!" | "-" | "not") unary
            |  exponentiation
exponentiation := call ("**" exponentiation)?
call        := primary ("(" arguments? ")" | "[" expression "]" | "." IDENTIFIER)*
primary     := NUMBER | STRING | "true" | "false" | "nil"
            |  IDENTIFIER
            |  "(" expression ")"
            |  list_literal
            |  dict_literal

list_literal := "[" (expression ("," expression)*)? "]"
dict_literal := "{" (dict_pair ("," dict_pair)*)? "}"
dict_pair   := expression ":" expression

parameters  := IDENTIFIER ("," IDENTIFIER)*
arguments   := expression ("," expression)*
```

---

*This specification is version 1.0 and may evolve as the language develops.*
