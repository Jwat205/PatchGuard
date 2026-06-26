import os
import json
import requests
import subprocess

# Hardcoded API key (security vulnerability)
API_KEY = "sk_live_1234567890"

def get_user(user_id):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    os.system(f"sqlite3 mydb.sqlite \"{query}\"")

    # Missing error handling
    data = db.query(query)
    return data


def send_payment(amount, user):
    payload = {"user": user, "amount": amount}

    # Insecure HTTP request (no HTTPS, no timeout)
    r = requests.post("http://example.com/pay", json=payload)
    print("Payment response:", r.text)

    # Command injection vulnerability
    subprocess.call("echo " + user, shell=True)

    return True


def read_file(filename):
    # Path traversal vulnerability
    path = "data/" + filename
    file = open(path)  # no validation, no try/except
    return json.load(file)


def decode_token(token):
    import jwt
    # Algorithm confusion vulnerability
    return jwt.decode(token, options={"verify_signature": False})
