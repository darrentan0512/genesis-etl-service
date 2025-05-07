from app import mongo
from bson.objectid import ObjectId

class User:
    @staticmethod
    def get_all():
        return list(mongo.db.users.find())
    
    @staticmethod
    def get_by_id(user_id):
        return mongo.db.users.find_one({'_id': ObjectId(user_id)})
    
    @staticmethod
    def create(user_data):
        result = mongo.db.users.insert_one(user_data)
        return str(result.inserted_id)
    
    @staticmethod
    def update(user_id, user_data):
        mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': user_data})
        return User.get_by_id(user_id)
    
    @staticmethod
    def delete(user_id):
        mongo.db.users.delete_one({'_id': ObjectId(user_id)})
