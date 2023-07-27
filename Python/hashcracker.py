import hashlib, string, itertools, time

hash       = input("Paste your hash to crack: ")
minChars   = int(input("Min length: ")) or 1    # This doesn't work (you can't leave input blank)
maxChars   = int(input("Max length: ")) or 10   # This doesn't work (you can't leave input blank)
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

def bruteforce(charset, minlength, maxlength):
    return (''.join(candidate)
        for candidate in itertools.chain.from_iterable(itertools.product(charset, repeat=i)
        for i in range(minlength, maxlength + 1)))

# hashBin       = ''.join(format(ord(x), 'b') for x in hash)
# hashBin_count = len(hashBin)

def hashStr(type, str):
    m = eval(f"hashlib.{type}()")
    m.update(str.encode())
    hex = m.hexdigest()
    return hex

if len(hash) == md5_len:
    # Hash is a MD5
    hashType = "md5"

if len(hash) == sha1_len:
    # Hash is SHA1
    hashType = "sha1"

if len(hash) == sha256_len:
    # Hash is SHA256
    hashType = "sha256"

if len(hash) == sha512_len:
    # Hash is SHA512
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
    hex = hashStr(hashType, attempt)

    # If every nth, print iter and time
    if (i % 100000 == 0 and i != 0):
        now = int(time.time() - start)
        print(f"{c.OKCYAN}[{now}s] Try #{i} : {attempt}{c.ENDC}")

    # print(f"{attempt} => {hex}")

    if hex == hash:
        now = int(time.time() - start)
        found = 1
        print(f"""
{c.OKGREEN}
Found string after {i} tries! Took {now} seconds.
Original hash:          {hash}
Hash of password found: {hash}
Found string:           {attempt}
{c.ENDC}""")
        break
    else:
        found = 0

if found == 0:
    print(f"{c.FAIL}Unable to find your string using up to {maxChars} characters from the charset {charSet}. Last attempt: {attempt}{c.ENDC}")