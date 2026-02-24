import string

ALPHABET = "abcdefghijklmnopqrstuvwxyzæøå{}_"


def xor_char(a: str, b: str, alphabet: str = ALPHABET) -> str:
    """XOR one character from text with one key character."""
    if a in string.whitespace:
        return a
    return alphabet[alphabet.index(a) ^ alphabet.index(b)]


def transform(text: str, key: str, alphabet: str = ALPHABET) -> str:
    """Encrypt/decrypt text using a single-character XOR key."""
    if len(key) != 1:
        raise ValueError("Key must be exactly one character")
    if key not in alphabet:
        raise ValueError("Key must exist in alphabet")
    return "".join(xor_char(ch, key, alphabet) for ch in text)


def encrypt(text: str, key: str, alphabet: str = ALPHABET) -> str:
    return transform(text, key, alphabet)


def decrypt(text: str, key: str, alphabet: str = ALPHABET) -> str:
    # XOR is symmetric, so decrypt is identical to encrypt.
    return transform(text, key, alphabet)


def brute_force_decrypt(ciphertext: str, alphabet: str = ALPHABET) -> dict[str, str]:
    """Return every possible plaintext candidate by trying all keys."""
    return {key: decrypt(ciphertext, key, alphabet) for key in alphabet}
