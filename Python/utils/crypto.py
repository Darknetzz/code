import os
from cryptography.fernet import Fernet

class darkCrypt:
    def __init__(self):
        self.initialized = True
        
    def __readFile(self, fileName):
        try:
            with open(fileName) as f:
                return f.read()
        except Exception:
            exit(f"Unable to read file {fileName}")

    def secret_decrypt(self, secret, key):
        if os.path.isfile(secret):
            secret = self.__readFile(secret)
        if os.path.isfile(key):
            key = self.__readFile(key)

        fernet = Fernet(key)
        return fernet.decrypt(secret).decode()

    def secret_encrypt(self, secret, key):
        if os.path.isfile(secret):
            secret = self.__readFile(secret)
        if os.path.isfile(key):
            key = self.__readFile(key)

        fernet = Fernet(key)
        return fernet.encrypt(secret).decode()