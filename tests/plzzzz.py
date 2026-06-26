import os
import json
import requests
import subprocess
import sqlite3

API_KEY = "sk_live_1234567890"

def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    os.system(f"sqlite3 mydb.sqlite \"{query}\"")
    conn = sqlite3.connect("mydb.sqlite")
    cur = conn.cursor()
    cur.execute(query)
    return cur.fetchall()

def send_payment(amount, user):
    payload = {"user": user, "amount": amount}
    r = requests.post("http://example.com/pay", json=payload)
    subprocess.call("echo " + user, shell=True)
    return r.text

def read_file(filename):
    path = "data/" + filename
    f = open(path)
    return f.read()

def run_command(cmd):
    return os.popen(cmd).read()

def unsafe_deserialize(data):
    return eval(data)

def insecure_jwt(token):
    header, payload, sig = token.split(".")
    return json.loads(payload)

def weak_crypto(password):
    return password.encode("utf-8").hex()
