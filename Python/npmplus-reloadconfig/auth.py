# --- Configuration ---
# Define each NPM instance once; switch by setting ACTIVE below.
DARKNET = {
    "host": "https://10.0.2.123:81",
    "username": "nginx@roste.org",
    "password": "Garrysmod1996!?",
}
TUNGA = {
    "host": "https://192.168.100.50:81",
    "username": "nginx@roste.org",
    "password": "Garrysmod1996!?",
}

ACTIVE = TUNGA
NPM_HOST = ACTIVE["host"]
USERNAME = ACTIVE["username"]
PASSWORD = ACTIVE["password"]
NO_ACCESS_LIST_ID = 0  # ID to temporarily set for reloading