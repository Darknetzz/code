// Error handling example

def divide(a, b) {
    if b == 0 {
        throw "Division by zero is not allowed"
    }
    return a / b
}

// Successful division
try {
    let result = divide(10, 2)
    print("10 / 2 =", result)
} catch error {
    print("Error:", error)
}

// Division by zero
try {
    let result = divide(10, 0)
    print("Result:", result)
} catch error {
    print("Caught error:", error)
}

print("Program continues after error handling")
