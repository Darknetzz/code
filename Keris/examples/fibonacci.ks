// Fibonacci sequence generator
def fibonacci(n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

print("First 10 Fibonacci numbers:")
for i in range(0, 10) {
    print("fib(" + i + ") = " + fibonacci(i))
}
