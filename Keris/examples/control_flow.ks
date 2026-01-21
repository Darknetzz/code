// Control flow examples

// If-elif-else
let score = 85

if score >= 90 {
    print("Grade: A")
} elif score >= 80 {
    print("Grade: B")
} elif score >= 70 {
    print("Grade: C")
} else {
    print("Grade: F")
}

// While loop
let count = 0
print("Counting to 5:")
while count < 5 {
    print(count)
    count = count + 1
}

// For loop with list
print("Fruits:")
let fruits = ["apple", "banana", "cherry"]
for fruit in fruits {
    print("  -", fruit)
}

// For loop with range
print("Numbers 0 to 4:")
for i in range(0, 5) {
    print(i)
}

// Break and continue
print("Odd numbers from 1 to 10:")
let num = 0
while num < 10 {
    num = num + 1
    if num % 2 == 0 {
        continue
    }
    if num > 10 {
        break
    }
    print(num)
}
