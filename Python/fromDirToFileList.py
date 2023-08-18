import os

# ────── This is just a very temporary script to generate lists of files ───── #

absolutePath = r"Z:\Code\!GitHub\Shell"
allFiles     = []

for file in os.scandir(absolutePath):
    if os.path.isfile(file):
        allFiles.append(f"\"{file.name}\"")

print(", ".join(allFiles))