# Eurojackpot
import random

primaryGen = []
secondaryGen = []
mergedGen = []
mergedLinesPrimary = []
mergedLinesSecondary = []
primaryCorrect = 0
secondaryCorrect = 0
attempts = 0
pRequired = 5
sRequired = 2

class c:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def assertwin(p, s):
    if p >= pRequired and s >= sRequired:
        return True
    else:
        return False


# Generate numbers pulled
def gen():
    thisPrimaryGen = []
    while len(thisPrimaryGen) < 5:
        generator = random.randint(1,50)
        if generator not in thisPrimaryGen:
            thisPrimaryGen.append(generator)

    thisSecondaryGen = []
    while len(thisSecondaryGen) < 2:
        generator = random.randint(1,10)
        if generator not in thisSecondaryGen:
            thisSecondaryGen.append(generator)
    
    return thisPrimaryGen, thisSecondaryGen


lines = input("How many lines [default 5]: ") or 5
lines = int(lines)

for i in range(0,lines):
    print(f"""
    {c.OKCYAN}
    Enter the numbers you want comma separated. Or leave blank for auto generated lines.
    7 (5+2) numbers per line. First 5 between 1 and 50, and then last 2 between 1 and 10.
    Example primary:    10, 23, 24, 43, 49
    Example secondary:  3, 10
    {c.ENDC}
    """)
    thisLinePrimary = str(input(f"Line {i+1} primary: "))
    thisLineSecondary = str(input(f"Line {i+1} secondary: "))

    # Autogen if empty
    if len(thisLinePrimary) == 0:
        thisLinePrimary = ','.join(str(item) for item in gen()[0])
        print(f"Generated primary: {thisLinePrimary}")
    if len(thisLineSecondary) == 0:
        thisLineSecondary = ','.join(str(item) for item in gen()[1])
        print(f"Generated secondary: {thisLineSecondary}")

    # Split list
    appendPrimary = thisLinePrimary.split(",")
    appendSecondary = thisLineSecondary.split(",")

    # Verify validity of numbers
    if len(appendPrimary) == 5 and len(appendSecondary) == 2:
        for n in appendPrimary:
            n = int(n)
            if n <= 0 or n > 50:
                print("Invalid numbers in primary.")
                exit()
        for n in appendSecondary:
            n = int(n)
            if n <= 0 or n > 10:
                print("Invalid numbers in secondary.")
                exit()
    else:
        print("Invalid length")
        exit()

    # Convert all to integers
    appendPrimary = [int(i) for i in appendPrimary]
    appendSecondary = [int(i) for i in appendSecondary]

    mergedLinesPrimary.append(appendPrimary)
    mergedLinesSecondary.append(appendSecondary)


while primaryCorrect < 4 and secondaryCorrect < 2:
    primaryCorrect = 0
    secondaryCorrect = 0
    primaryGen, secondaryGen = gen()

    for line in range(0,lines):
        for p in primaryGen:
            if p in mergedLinesPrimary[line]:
                primaryCorrect += 1
        for s in secondaryGen:
            if s in mergedLinesSecondary[line]:
                secondaryCorrect += 1
        if assertwin(primaryCorrect, secondaryCorrect):
            print(f"{c.OKGREEN}[Attempt #{attempts}] You have numbers: {mergedLinesPrimary[line]} | {mergedLinesSecondary[line]}")
            print(f"[Attempt #{attempts}] The numbers pulled: {primaryGen} | {secondaryGen}")
            print(f"[Attempt #{attempts}] Correctness:        {primaryCorrect} | {secondaryCorrect}")
            print(f"[Attempt #{attempts}] In reality, this would take about {attempts/52} years to achieve.{c.ENDC}")
            exit()
        if attempts % 1000000 == 0 and attempts != 0:
            print(f"{c.FAIL}[Attempt #{attempts}] No success ({primaryCorrect} | {secondaryCorrect}){c.ENDC}")
        primaryCorrect = 0
        secondaryCorrect = 0
    attempts += 1

print(f"Used {attempts} attempts")