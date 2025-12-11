#!/usr/bin/env python3
"""
Generate a Laravel-style APP_KEY (base64-encoded random 32 bytes)
The same as running `echo -n 'base64:'; openssl rand -base64 32;`
"""
import secrets
import base64

# Generate 32 random bytes and encode as base64
random_bytes = secrets.token_bytes(32)
base64_key = base64.b64encode(random_bytes).decode('utf-8')

print(f"base64:{base64_key}")

