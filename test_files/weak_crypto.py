import hashlib
import random

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

def generate_token():
    return str(random.randint(100000, 999999))

def verify_password(password, stored):
    return hash_password(password) == stored
