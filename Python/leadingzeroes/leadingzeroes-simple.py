import hashlib
import time

target = '000000'
prefix = "my_homelab_challenge_"
nonce = 0
start_time = time.time()

while True:
    check = f"{prefix}{nonce}".encode()
    hash_result = hashlib.sha256(check).hexdigest()
    if hash_result.endswith(target):
        print(f"Found! Hash: {hash_result}")
        print(f"Input: {prefix}{nonce}")
        print(f"Time: {time.time() - start_time:.2f} seconds")
        break
    nonce += 1