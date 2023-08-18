import sys, os, argparse
from cryptography.fernet import Fernet
# ──────────────────────────────────────────────────────────────────────────── #
def writeToFile(fileName = "", content = ""):
    content = content.decode()
    if fileName != None:
        if os.path.isfile(fileName) and args.overwrite != True:

            c = input("File already exists, are you sure you want to overwrite? [Y/n]")
            if c.upper() != "Y" and c != "":
                exit()

            with open(fileName, 'w+') as f:
                f.write(content)
                
        return f"[Written to file '{fileName}']"
    else:
        return content
# ──────────────────────────────────────────────────────────────────────────── #
parser = argparse.ArgumentParser(
                    prog=f'{os.path.basename(__file__)}',
                    description='Encrypt a secret value and store the key separately.',
                    epilog='Enjoy'
)

parser.add_argument('secret', help="The secret you want to encrypt", type=str)
parser.add_argument('-k', '--keyfile', help="Filename to store the key in", type=str)
parser.add_argument('-o', '--output', help="Filename to store the output (encrypted) in", type=str)
parser.add_argument('-O', '--overwrite', help="Automatically overwrite output and key file without asking", type=bool, choices=[True, False])

args = parser.parse_args()

# print(f"""
# USAGE: {os.path.basename(__file__)} [SECRET] [KEYFILE] [OUTPUTFILE]

# If KEYFILE or OUTPUTFILE are omitted, it will print the key/output to stdout.
# """)
    

secret = args.secret
secretBytes = bytes(secret, encoding='utf-8')
keyfile = args.keyfile
output = args.output

# Put this somewhere safe!
key = Fernet.generate_key()
f = Fernet(key)
token = f.encrypt(secretBytes)

print(f"KEY: {writeToFile(keyfile, key)}")
print(f"ENCRYPTED: {writeToFile(output, token)}")


    