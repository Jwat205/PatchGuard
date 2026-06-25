from flask import request

def create_user():
    username = request.json["username"]
    email = request.json["email"]
    age = request.json["age"]
    db.insert(username=username, email=email, age=age)
    return {"status": "created"}

def update_profile():
    bio = request.args.get("bio")
    db.update(bio=bio)
