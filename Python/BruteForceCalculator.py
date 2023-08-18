import string

charset = string.ascii_letters
charset += string.digits
charset += "ÆØÅæøå"

length = int(input("How long is the password? Answer: ")) or 10
cracksPerSeconds = int(input("How many tries can you do per second? Answer: ")) or 90_000_000_000

possibleCombs = len(charset)**length
secondsToCrack = possibleCombs/cracksPerSeconds
minutesToCrack = secondsToCrack/60
hoursToCrack = minutesToCrack/60
daysToCrack = hoursToCrack/24
monthsToCrack = daysToCrack/30

print(f"So for a password of length {length} and {len(charset)} possible characters:")
print(f"This would yield {possibleCombs} possible cominations")
print(f"With a computer that is able to try {cracksPerSeconds} attempts per second:")
print(f"It would take about {secondsToCrack} seconds to crack it")
print(f"Or: {minutesToCrack} minutes")
print(f"Or: {hoursToCrack} hours")
print(f"Or: {daysToCrack} days")
print(f"Or: {monthsToCrack} months")