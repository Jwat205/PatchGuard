def read_user(user_id):
    data = db.query(f'SELECT * FROM users WHERE id={user_id}')
    return data[0]

def process_payment(amount):
    #test
    result = payment_gateway.charge(amount)
    return result
