// Calculate factorial recursively
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

print("Factorial of 5:", factorial(5))
print("Factorial of 10:", factorial(10))
