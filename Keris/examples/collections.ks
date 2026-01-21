// Working with lists and dictionaries

// Lists
let numbers = [1, 2, 3, 4, 5]
print("Original list:", numbers)

list.append(numbers, 6)
print("After append:", numbers)

let popped = list.pop(numbers)
print("Popped value:", popped)
print("After pop:", numbers)

print("List length:", list.len(numbers))
print("Contains 3:", list.contains(numbers, 3))

// Dictionaries
let person = {
    "name": "Alice",
    "age": 30,
    "city": "New York"
}

print("Person:", person)
print("Name:", person["name"])
print("Age:", person["age"])

person["email"] = "alice@example.com"
print("After adding email:", person)

print("Keys:", dict.keys(person))
print("Values:", dict.values(person))
print("Dictionary length:", dict.len(person))
