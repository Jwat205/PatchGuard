import os
import json
import requests
import subprocess

# Hardcoded secret (security vulnerability)
API_KEY = "sk_live_ABC1234567890"

def read_user(user_id):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    os.system(f"sqlite3 mydb.sqlite \"{query}\"")

    # Missing error handling
    data = db.query(query)
    return data


def process_payment(user_id, amount):
    payload = {"user": user_id, "amount": amount}

    # Insecure HTTP request (no HTTPS, no timeout)
    r = requests.post("http://example.com/pay", json=payload)
    print("Payment response:", r.text)

    # Command injection vulnerability
    subprocess.call("echo " + user_id, shell=True)

    return True


def load_user_file(username):
    # Path traversal vulnerability
    path = "users/" + username + ".json"
    file = open(path)  # no validation, no try/except
    return json.load(file)


def decode_jwt(token):
    import jwt
    # Algorithm confusion vulnerability
    return jwt.decode(token, options={"verify_signature": False})
