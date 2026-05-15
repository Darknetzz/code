path = r"d:\Kriss\Documents\Git\code\Python\webbot\webbot\static\app.js"
code = open(path, encoding="utf-8").read()
i = 0
depth = 0
line = 1
state = "code"
quote = None
escape = False
while i < len(code):
    c = code[i]
    if c == "\n":
        line += 1
    if state == "code":
        if c in "\"'":
            quote = c
            state = "str"
            escape = False
        elif c == "`":
            state = "tmpl"
            escape = False
        elif c == "/" and i + 1 < len(code) and code[i + 1] == "/":
            state = "linecom"
        elif c == "/" and i + 1 < len(code) and code[i + 1] == "*":
            state = "blockcom"
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                print("negative at", line)
                break
    elif state == "str":
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c == quote:
            state = "code"
    elif state == "tmpl":
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c == "`":
            state = "code"
    elif state == "linecom":
        if c == "\n":
            state = "code"
    elif state == "blockcom":
        if c == "*" and i + 1 < len(code) and code[i + 1] == "/":
            state = "code"
            i += 1
    i += 1
else:
    print("final depth", depth)
