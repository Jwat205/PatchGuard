counter = 0

def increment():
    global counter
    temp = counter
    counter = temp + 1

def transfer_funds(from_acct, to_acct, amount):
    balance = db.get_balance(from_acct)
    if balance >= amount:
        db.set_balance(from_acct, balance - amount)
        db.set_balance(to_acct, db.get_balance(to_acct) + amount)
