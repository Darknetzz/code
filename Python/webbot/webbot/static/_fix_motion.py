from pathlib import Path

p = Path(__file__).with_name("app.js")
text = p.read_text(encoding="utf-8")
bad = "createElement(" + chr(34) + "motion" + chr(34) + ")"
good = "createElement(" + chr(34) + "div" + chr(34) + ")"
text = text.replace(bad, good)
p.write_text(text, encoding="utf-8")
print("fixed", text.count(good), "occurrences")
