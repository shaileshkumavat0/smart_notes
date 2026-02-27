import bcrypt
from .database import users_collection

def register_user(username, password):
    if users_collection.find_one({"username": username}):
        return False
    
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    
    users_collection.insert_one({
        "username": username,
        "password": hashed
    })
    
    return True

def login_user(username, password):
    user = users_collection.find_one({"username": username})
    
    if user and bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return user
    
    return None