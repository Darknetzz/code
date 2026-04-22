import hashlib
import os
from cryptography.fernet import Fernet


# Algorithms explicitly allowed for ``hash_str``. Keeping this as an allowlist
# (instead of blindly looking up ``hashlib.<name>``) protects the helper from
# being turned into an arbitrary ``hashlib`` dispatch by a caller that forwards
# untrusted input.
HASH_ALGOS = ("md5", "sha1", "sha224", "sha256", "sha384", "sha512")


def hash_str(algo: str, data: str) -> str:
    """Return the hex digest of ``data`` using ``algo`` from :mod:`hashlib`.

    Replaces the previous ``eval(f"hashlib.{type}()")`` pattern that was
    duplicated in multiple scripts; ``getattr`` + allowlist is both safer
    and clearer.
    """
    if algo not in HASH_ALGOS:
        raise ValueError(
            f"Unsupported hash algorithm: {algo!r}. Expected one of {HASH_ALGOS}."
        )
    hasher = getattr(hashlib, algo)()
    hasher.update(data.encode())
    return hasher.hexdigest()


class darkCrypt:
    def __init__(self):
        self.initialized = True
        
    def __readFile(self, fileName):
        try:
            with open(fileName) as f:
                return f.read()
        except Exception:
            exit(f"Unable to read file {fileName}")

    # def secret_decrypt(self, secret, key):
    #     if os.path.isfile(secret):
    #         secret = self.__readFile(secret)
    #     if os.path.isfile(key):
    #         key = self.__readFile(key)

    #     fernet = Fernet(key)
    #     return fernet.decrypt(secret).decode()
    
    def secret_decrypt(self, secret_file, key_file):
        if os.path.isfile(secret_file):
            secret = self.__readFile(secret_file)
        if os.path.isfile(key_file):
            key = self.__readFile(key_file)
            
        fernet = Fernet(key)

        with open(secret_file, 'r') as file:
            secret = file.read()

        # Ensure secret is bytes
        if isinstance(secret, str):
            secret = secret.encode()

        return fernet.decrypt(secret).decode()

    def secret_encrypt(self, secret, key):
        if os.path.isfile(secret):
            secret = self.__readFile(secret)
        if os.path.isfile(key):
            key = self.__readFile(key)

        fernet = Fernet(key)
        return fernet.encrypt(secret).decode()