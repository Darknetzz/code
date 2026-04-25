import argparse
import os
from typing import Optional

from cryptography.fernet import Fernet


# ──────────────────────────────────────────────────────────────────────────── #
def should_overwrite(file_name: str, overwrite: bool) -> bool:
    if overwrite or not os.path.isfile(file_name):
        return True
    answer = input("File already exists, are you sure you want to overwrite? [Y/n]")
    return answer == "" or answer.upper() == "Y"


def write_to_file(file_name: Optional[str], content: bytes, *, overwrite: bool = False) -> str:
    decoded = content.decode()
    if file_name is None:
        return decoded
    if not should_overwrite(file_name, overwrite):
        return f"[Skipped existing file '{file_name}']"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(decoded)
    return f"[Written to file '{file_name}']"

# ──────────────────────────────────────────────────────────────────────────── #
parser = argparse.ArgumentParser(
                    prog=f'{os.path.basename(__file__)}',
                    description='Encrypt a secret value and store the key separately.',
                    epilog='Enjoy'
)

parser.add_argument('secret', help="The secret you want to encrypt", type=str)
parser.add_argument('-k', '--keyfile', help="Filename to store the key in", type=str)
parser.add_argument('-o', '--output', help="Filename to store the output (encrypted) in", type=str)
parser.add_argument('-O', '--overwrite', help="Automatically overwrite output and key file without asking", action="store_true")

args = parser.parse_args()

# print(f"""
# USAGE: {os.path.basename(__file__)} [SECRET] [KEYFILE] [OUTPUTFILE]

# If KEYFILE or OUTPUTFILE are omitted, it will print the key/output to stdout.
# """)
    

secret = args.secret
secret_bytes = bytes(secret, encoding='utf-8')
keyfile = args.keyfile
output = args.output

# Put this somewhere safe!
key = Fernet.generate_key()
f = Fernet(key)
token = f.encrypt(secret_bytes)

print(f"KEY: {write_to_file(keyfile, key, overwrite=args.overwrite)}")
print(f"ENCRYPTED: {write_to_file(output, token, overwrite=args.overwrite)}")