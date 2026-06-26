import requests
import os
import json
import subprocess

API_KEY = "sk_live_1234567890"   # hardcoded secret

def process_payment(user_id, amount):
    # no validation, no error handling
    data = {"user": user_id, "amount": amount}

    # insecure HTTP request, no timeout, no error handling
    r = requests.post("http://example.com/pay", json=data)
    print("Payment response:", r.text)

    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    os.system(f"sqlite3 mydb.sqlite \"{query}\"")

    # command injection vulnerability
    os.system("echo " + user_id)

    # unused variable
    temp = json.dumps(data)

    return True


def get_user_info(username):
    # wildcard dependency version risk (pretend this is used somewhere)
    import flask==2.*

    # missing error handling
    file = open("users/" + username + ".json")
    return json.load(file)


def insecure_jwt_decode(token):
    import jwt
    # algorithm confusion vulnerability
    return jwt.decode(token, options={"verify_signature": False})
