import time, random, hashlib, string
from numba import jit, cuda

def main():
    start = time.time()

    lz = 1
    tz = 1
    i = 0


    randChars = ''.join(random.choices(string.ascii_letters + string.digits, k=200))
    randChars = str.encode(randChars)

    lasthash = ""
    h = hashlib.new('sha256')
    h.update(randChars)
    hash = h.hexdigest()
    print(f"Starting with string {hash}")
    while True:
        ittime = time.time() - start

        if hash[-tz:len(hash)] == '0'*tz:
            print(f"""
[{ittime}] Found {tz} leading zeroes: \n\
{lasthash} {hash}""")
            tz = tz+1

        if hash[0:lz] == '0'*lz:
            print(f"""
[{ittime}] Found {lz} trailing zeroes: \n\
{lasthash} {hash}""")
            lz = lz+1
            
        if i % 100000000 == 0 and i != 0:
            print(f"[{ittime}] Try #{i}")

        lasthash = hash
        h = hashlib.new('sha256')
        h.update(str.encode(hash))
        hash = h.hexdigest()
        i = i+1


if __name__ == '__main__':
    main()