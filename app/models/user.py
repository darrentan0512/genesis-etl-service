from app import mongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

class User:
    @staticmethod
    def get_all():
        return list(mongo.db.users.find())
    
    @staticmethod
    def get_by_id(user_id):
        return mongo.db.users.find_one({'_id': ObjectId(user_id)})
    
    @staticmethod
    def create(user_data):
        # Hash the password before storing it
        if 'password' in user_data:
            user_data['password'] = generate_password_hash(user_data['password'])
        result = mongo.db.users.insert_one(user_data)
        return str(result.inserted_id)
    
    @staticmethod
    def update(user_id, user_data):
        if 'password' in user_data:
            user_data['password'] = generate_password_hash(user_data['password'])
        mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': user_data})
        return User.get_by_id(user_id)
    
    @staticmethod
    def delete(user_id):
        mongo.db.users.delete_one({'_id': ObjectId(user_id)})

    @staticmethod
    def find_by_email(email):
        return mongo.db.users.find_one({'email': email})
    
    @staticmethod
    def authenticate(email, password):
        user = User.find_by_email(email)
        if user and check_password_hash(user['password'], password):
            return user
        return None