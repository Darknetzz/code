// String operations

let text = "Hello, World!"

print("Original:", text)
print("Length:", str.len(text))
print("Uppercase:", str.upper(text))
print("Lowercase:", str.lower(text))

let words = str.split("apple,banana,cherry", ",")
print("Split result:", words)
print("Joined:", str.join(words, " - "))
