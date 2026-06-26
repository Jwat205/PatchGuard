import os
import jwt
import sqlite3
####
API_KEY = "12345-SECRET-HARDCODED"  # hardcoded secret

def get_user_data(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)

    result = cursor.fetchall()
    conn.close()
    return result

def process_payment(amount, user):
    # unused variable
    temp = 0

    # missing error handling
    total = amount * 1.07

    # insecure eval
    risky = eval("amount + 1")

    # unreachable code
    return total
    print("This will never run")

def decode_jwt(token):
    # insecure: no signature verification, no expiry check
    return jwt.decode(token, options={"verify_signature": False})

def slow_loop():
    data = []
    for i in range(10000000):  # performance issue
        data.append(i)
    return data

def bad_exception():
    try:
        x = 1 / 0
    except Exception:
        pass  # swallowing all errors silently

def duplicate_logic(a, b):
    if a > b:
        return a - b
    if a > b:  # duplicate condition
        return a - b
    return 0
