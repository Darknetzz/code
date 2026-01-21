# Keris Quick Start Guide

Get up and running with Keris in minutes!

## Installation

No installation needed! Just make sure you have Python 3.7+ installed.

```bash
python --version  # Should be 3.7 or higher
```

## Your First Program

1. Create a file `hello.ks`:

```keris
print("Hello, Keris!")
```

2. Run it:

```bash
python main.py hello.ks
```

Output:
```
Hello, Keris!
```

## Interactive REPL

Start the interactive shell:

```bash
python main.py
```

Then type Keris code:

```
keris> let x = 42
keris> print(x)
42
keris> def greet(name) { return "Hello, " + name }
keris> print(greet("World"))
Hello, World
keris> exit
```

## Common Examples

### Variables

```keris
let name = "Alice"
let age = 30
const PI = 3.14159
```

### Functions

```keris
def add(a, b) {
    return a + b
}

print(add(5, 3))  # 8
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

### Lists

```keris
let numbers = [1, 2, 3, 4, 5]

for num in numbers {
    print(num)
}

list.append(numbers, 6)
print(list.len(numbers))  # 6
```

### Dictionaries

```keris
let person = {
    "name": "Alice",
    "age": 30
}

print(person["name"])  # "Alice"
person["city"] = "New York"
```

## Next Steps

- Read the [Tutorial](docs/tutorial.md) for a comprehensive guide
- Check out [Examples](examples/) for more programs
- Read the [Language Specification](SPECIFICATION.md) for complete details

Happy coding! 🎉
