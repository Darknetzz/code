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