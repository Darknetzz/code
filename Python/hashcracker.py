import string, itertools, time

from utils.textStyle import C as c
from utils.crypto import hash_str

target_hash = input("Paste your hash to crack: ")
# `int(input(...) or "N")` lets empty input actually fall back to the default;
# `int(input(...)) or N` used to raise ValueError on "".
minChars   = int(input("Min length: ") or "1")
maxChars   = int(input("Max length: ") or "10")
lc         = string.ascii_lowercase
uc         = string.ascii_uppercase
dc         = string.digits
pc         = string.punctuation
hc         = string.hexdigits.lower()
charSet    = lc+uc+dc
# maxChars = int(input("Max length to try: "))
md5_len    = 32
sha1_len   = 40
sha256_len = 64
sha512_len = 128
hashType   = None

def bruteforce(charset, minlength, maxlength):
    return (''.join(candidate)
        for candidate in itertools.chain.from_iterable(itertools.product(charset, repeat=i)
        for i in range(minlength, maxlength + 1)))

if len(target_hash) == md5_len:
    hashType = "md5"

if len(target_hash) == sha1_len:
    hashType = "sha1"

if len(target_hash) == sha256_len:
    hashType = "sha256"

if len(target_hash) == sha512_len:
    hashType = "sha512"

if hashType == None:
    print("Unable to determine hash. Exiting.")
    exit()

print(f"{c.OKBLUE}Hash looks like {hashType}, attempting to crack{c.ENDC}")

start = time.time()
i = 0
for attempt in bruteforce(charSet, minChars, maxChars):
    # Iter add
    i += 1

    # Hash the current string attempt
    hex = hash_str(hashType, attempt)

    # If every nth, print iter and time
    if (i % 100000 == 0 and i != 0):
        now = int(time.time() - start)
        print(f"{c.OKCYAN}[{now}s] Try #{i} : {attempt}{c.ENDC}")

    # print(f"{attempt} => {hex}")

    if hex == target_hash:
        now = int(time.time() - start)
        found = 1
        print(f"""
{c.OKGREEN}
Found string after {i} tries! Took {now} seconds.
Original hash:          {target_hash}
Hash of password found: {target_hash}
Found string:           {attempt}
{c.ENDC}""")
        break
    else:
        found = 0

if found == 0:
    print(f"{c.FAIL}Unable to find your string using up to {maxChars} characters from the charset {charSet}. Last attempt: {attempt}{c.ENDC}")