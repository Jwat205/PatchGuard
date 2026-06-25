import jwt

def verify_token(token):
    return jwt.decode(token, options={"verify_signature": False})

def create_token(user_id):
    return jwt.encode({"user_id": user_id}, "", algorithm="none")
