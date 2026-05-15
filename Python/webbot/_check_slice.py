path = r"d:\Kriss\Documents\Git\code\Python\webbot\webbot\static\app.js"
lines = open(path, encoding="utf-8").read().splitlines()
start, end = 3486, 3636  # 1-based inclusive, through })();
chunk = "\n".join(lines[start - 1 : end])
depth = 0
i = 0
state = "code"
quote = None
escape = False
line = start
for pos, c in enumerate(chunk):
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
        elif c == "/" and pos + 1 < len(chunk) and chunk[pos + 1] == "/":
            state = "linecom"
        elif c == "/" and pos + 1 < len(chunk) and chunk[pos + 1] == "*":
            state = "blockcom"
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                print("negative", line)
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
        if c == "*" and pos + 1 < len(chunk) and chunk[pos + 1] == "/":
            state = "code"
else:
    print("brace depth inside slice", depth)
