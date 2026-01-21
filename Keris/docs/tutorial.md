# Keris Tutorial

Welcome to the Keris programming language! This tutorial will guide you through the basics of Keris.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Variables and Types](#variables-and-types)
3. [Functions](#functions)
4. [Control Flow](#control-flow)
5. [Collections](#collections)
6. [Error Handling](#error-handling)
7. [Standard Library](#standard-library)

## Getting Started

### Your First Program

Create a file called `hello.ks`:

```keris
print("Hello, World!")
```

Run it:

```bash
python main.py hello.ks
```

Output:
```
Hello, World!
```

### Interactive REPL

You can also use the interactive REPL:

```bash
python main.py
```

```
keris> print("Hello from REPL!")
Hello from REPL!
keris> exit
```

## Variables and Types

### Variable Declaration

Keris has two ways to declare variables:

```keris
let x = 10        // Mutable variable
const PI = 3.14   // Immutable constant
y = 20            // Implicit global (not recommended)
```

### Types

Keris is dynamically typed. Types are inferred at runtime:

```keris
let number = 42           // Number
let decimal = 3.14        // Number (float)
let text = "Hello"        // String
let flag = true           // Boolean
let nothing = nil         // Nil (null)
```

### Type Checking

You can check types at runtime:

```keris
let x = 42
print(type.of(x))  // "number"

let y = "hello"
print(type.of(y))  // "string"
```

### Type Conversion

Keris automatically converts types when needed:

```keris
let num = 42
let text = "The answer is " + num  // Automatic conversion
print(text)  // "The answer is 42"
```

## Functions

### Defining Functions

```keris
def greet(name) {
    return "Hello, " + name
}

print(greet("Alice"))  // "Hello, Alice"
```

### Functions with Multiple Parameters

```keris
def add(a, b) {
    return a + b
}

print(add(5, 3))  // 8
```

### Functions Without Return

Functions without a return statement return `nil`:

```keris
def say_hello(name) {
    print("Hello, " + name)
}

let result = say_hello("Bob")  // Prints "Hello, Bob"
print(result)  // nil
```

### Recursion

Functions can call themselves:

```keris
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

print(factorial(5))  // 120
```

## Control Flow

### If Statements

```keris
let age = 20

if age >= 18 {
    print("Adult")
} else {
    print("Minor")
}
```

### Elif Chains

```keris
let score = 85

if score >= 90 {
    print("A")
} elif score >= 80 {
    print("B")
} elif score >= 70 {
    print("C")
} else {
    print("F")
}
```

### While Loops

```keris
let count = 0

while count < 5 {
    print(count)
    count = count + 1
}
```

### For Loops

Iterate over lists:

```keris
let fruits = ["apple", "banana", "cherry"]

for fruit in fruits {
    print(fruit)
}
```

Iterate over strings:

```keris
for char in "hello" {
    print(char)
}
```

Use range for numeric loops:

```keris
for i in range(0, 5) {
    print(i)
}
```

### Break and Continue

```keris
let i = 0
while true {
    i = i + 1
    if i > 10 {
        break  // Exit loop
    }
    if i % 2 == 0 {
        continue  // Skip to next iteration
    }
    print(i)
}
```

## Collections

### Lists

Create and manipulate lists:

```keris
let numbers = [1, 2, 3, 4, 5]
let empty = []

// Access elements
print(numbers[0])   // 1
print(numbers[-1])  // 5 (last element)

// Modify elements
numbers[0] = 10
print(numbers)  // [10, 2, 3, 4, 5]

// List methods
list.append(numbers, 6)
print(numbers)  // [10, 2, 3, 4, 5, 6]

let last = list.pop(numbers)
print(last)     // 6
print(numbers)  // [10, 2, 3, 4, 5]

print(list.len(numbers))  // 5
print(list.contains(numbers, 3))  // true
```

### Dictionaries

Create and use dictionaries:

```keris
let person = {
    "name": "Alice",
    "age": 30,
    "city": "New York"
}

// Access values
print(person["name"])  // "Alice"
print(person.name)     // "Alice" (dot notation)

// Add/modify values
person["email"] = "alice@example.com"
person.email = "alice@example.com"

// Dictionary methods
let keys = dict.keys(person)
print(keys)  // ["name", "age", "city", "email"]

let values = dict.values(person)
print(values)  // ["Alice", 30, "New York", "alice@example.com"]

print(dict.len(person))  // 4
print(dict.contains(person, "name"))  // true
```

## Error Handling

### Try-Catch

Handle errors gracefully:

```keris
try {
    let result = 10 / 0
} catch error {
    print("Error: " + error)
}
```

### Throwing Errors

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
    print("Caught: " + error)
}
```

## Standard Library

### I/O

```keris
print("Hello")                    // Print to stdout
print("Multiple", "values", 42)  // Print multiple values

let name = read_line()            // Read a line from stdin
let age = read_number()           // Read a number
```

### Math

```keris
math.abs(-5)        // 5
math.sqrt(16)       // 4.0
math.pow(2, 3)      // 8.0
math.max(1, 2, 3)   // 3
math.min(1, 2, 3)   // 1
math.floor(3.7)     // 3.0
math.ceil(3.2)      // 4.0
math.round(3.5)     // 4
math.sin(math.pi / 2)  // 1.0
math.cos(0)         // 1.0
math.pi             // 3.14159...
math.e              // 2.71828...
```

### String Operations

```keris
str.len("hello")                    // 5
str.upper("hello")                  // "HELLO"
str.lower("HELLO")                  // "hello"
str.split("a,b,c", ",")             // ["a", "b", "c"]
str.join(["a", "b", "c"], ",")      // "a,b,c"
```

## Complete Example

Here's a complete program that demonstrates many features:

```keris
// Calculate factorial
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

// Process a list of numbers
let numbers = [1, 2, 3, 4, 5]
let results = []

for num in numbers {
    let fact = factorial(num)
    list.append(results, fact)
    print(num + "! = " + fact)
}

print("Results:", results)

// Create a person dictionary
let person = {
    "name": "Alice",
    "age": 30,
    "favorites": results
}

print(person["name"] + " calculated factorials: " + person["favorites"])
```

## Next Steps

- Read the [Language Specification](SPECIFICATION.md) for complete details
- Check out the [examples](../examples/) directory
- Experiment with the REPL
- Build your own programs!

Happy coding with Keris! 🎉
