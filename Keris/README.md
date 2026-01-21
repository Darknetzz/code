# Keris Programming Language

![Keris Logo](img/keris.png)

A general-purpose, dynamically-typed, interpreted programming language inspired by Python.

## Features

- **Python-inspired syntax**: Clean, readable code with familiar constructs
- **Dynamic typing**: Flexible type system with runtime type checking
- **Rich standard library**: I/O, math, string manipulation, collections
- **Error handling**: Try-catch blocks for robust error management
- **Functions**: First-class functions with closures
- **Collections**: Lists and dictionaries with convenient syntax
- **REPL**: Interactive shell for quick testing

## Installation

Keris is implemented in Python 3.7+. No additional dependencies required.

```bash
# Clone or download the repository
cd Keris

# Run directly
python main.py

# Or make it executable (Unix)
chmod +x main.py
./main.py
```

## Quick Start

### Hello World

```keris
print("Hello, World!")
```

### Variables and Functions

```keris
def greet(name) {
    return "Hello, " + name
}

let message = greet("Keris")
print(message)
```

### Control Flow

```keris
let x = 10

if x > 5 {
    print("x is greater than 5")
} else {
    print("x is not greater than 5")
}

while x > 0 {
    print(x)
    x = x - 1
}
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

## Usage

### Running a Script

```bash
python main.py script.ks
```

### Interactive REPL

```bash
python main.py
```

Then type Keris code:

```
keris> let x = 42
keris> print(x)
42
keris> def add(a, b) { return a + b }
keris> print(add(5, 3))
8
keris> exit
```

## Language Documentation

- [Language Specification](SPECIFICATION.md) - Complete language reference
- [Tutorial](docs/tutorial.md) - Learn Keris step by step
- [Examples](examples/) - Example programs

## Standard Library

### I/O

```keris
print("Hello")           // Print to stdout
let input = read_line()  // Read from stdin
let num = read_number()  // Read a number
```

### Math

```keris
math.sqrt(16)        // 4.0
math.pow(2, 3)       // 8.0
math.max(1, 2, 3)    // 3
math.pi              // 3.14159...
```

### String

```keris
str.len("hello")                    // 5
str.upper("hello")                  // "HELLO"
str.split("a,b,c", ",")             // ["a", "b", "c"]
str.join(["a", "b", "c"], ",")      // "a,b,c"
```

### List

```keris
let lst = [1, 2, 3]
list.append(lst, 4)      // [1, 2, 3, 4]
list.pop(lst)            // 4
list.len(lst)            // 3
list.contains(lst, 2)    // true
```

### Dict

```keris
let d = {"a": 1, "b": 2}
dict.keys(d)             // ["a", "b"]
dict.values(d)           // [1, 2]
dict.len(d)              // 2
dict.contains(d, "a")    // true
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

## Examples

See the [examples](examples/) directory for more complete programs.

## Project Structure

```
Keris/
├── README.md              # This file
├── SPECIFICATION.md        # Language specification
├── DESIGN_OUTLINE.md      # Design document
├── main.py                # Entry point
├── src/                   # Source code
│   ├── token.py          # Token definitions
│   ├── lexer.py          # Lexical analyzer
│   ├── parser.py         # Parser
│   ├── ast.py            # AST nodes
│   ├── interpreter.py    # Interpreter
│   ├── runtime.py        # Runtime errors
│   ├── stdlib.py         # Standard library
│   └── keris.py          # Main interpreter
├── docs/                  # Documentation
│   └── tutorial.md        # Tutorial
├── examples/              # Example programs
└── tests/                 # Test suite
```

## Contributing

This is a learning project, but contributions and feedback are welcome!

## License

See LICENSE file for details.

## Version

Current version: 1.0.0

---

**Note**: Keris is an educational project. For production use, consider more mature languages like Python, JavaScript, or Rust.
