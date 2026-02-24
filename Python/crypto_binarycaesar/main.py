import random
from cipher import ALPHABET, encrypt

key = 'a'
while (key == 'a'):
	key = random.choice(ALPHABET)

def main():
    # Danish text, flag is in text
    with open('flag.txt', 'rb') as f:
        text = f.read().decode("utf-8").strip()

    ciphertext = encrypt(text, key)

    with open('encryption.txt', 'wb') as f:
        f.write(ciphertext.encode("utf-8"))

    # Once you have decrypted the ciphertext, remember to add flag formatting
    # For example:
    # ddc example flag
    # to
    # ddc{example_flag}


if __name__ == '__main__':
    main()
