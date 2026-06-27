import os
import requests
import subprocess
import jwt
import hashlib
import random
import yaml
import pickle
import json

# Hardcoded secrets (Security Issue)
API_KEY = "sk_live_1234567890"
DB_PASSWORD = "password123"
JWT_SECRET = "not_secure_at_all"

# Outdated dependency usage (Dependency Issue)
# requests is fine, but using it insecurely is not
def download_data(url):
    # No SSL verification (Security Issue)
    return requests.get(url, verify=False).text

# Command injection vulnerability (Security Issue)
def run_system_command(cmd):
    return subprocess.check_output(cmd, shell=True)

# Insecure deserialization (Security Issue)
def load_user_config(path):
    with open(path, "rb") as f:
        return pickle.load(f)  # RCE vulnerability

# YAML unsafe load (Security Issue)
def load_yaml_config(path):
    with open(path) as f:
        return yaml.load(f)  # should use safe_load

# Weak hashing (Security Issue)
def hash_password(pw):
    return hashlib.md5(pw.encode()).hexdigest()

# SQL injection (Security Issue)
def get_user(db, username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)

# Terrible error handling (Quality Issue)
def divide(a, b):
    return a / b  # ZeroDivisionError not handled

# Unused variables, dead code (Quality Issue)
x = 10
y = 20
z = x + y

# Bad class design (Quality Issue)
class BadClass:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)

    def get(self, index):
        return self.data[index]  # no bounds checking

# Insecure JWT usage (Security Issue)
def create_token(data):
    return jwt.encode(data, JWT_SECRET, algorithm="HS256")

# Randomness misuse (Security Issue)
def generate_token():
    return str(random.random())

# No input validation (Quality Issue)
def process_user_input(user_input):
    return json.loads(user_input)

# Blocking network call inside async context (Quality Issue)
def fetch_remote():
    return requests.get("http://example.com").text

# Extremely inefficient algorithm (Quality Issue)
def slow_function(n):
    total = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                total += i + j + k
    return total

# Exposed internal debug endpoint (Security Issue)
def debug():
    return os.popen("whoami").read()
