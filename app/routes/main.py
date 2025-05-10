from flask import Blueprint, render_template, request, jsonify
from app.models.user import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/api/users', methods=['GET'])
def get_users():
    users = User.get_all()
    # Convert ObjectId to string for JSON serialization
    for user in users:
        user['_id'] = str(user['_id'])
    return jsonify(users)

@main_bp.route('/api/users', methods=['POST'])
def create_user():
    user_data = request.json
    print(user_data)
    user_id = User.create(user_data)
    return jsonify({'id': user_id, 'message': 'User created successfully'}), 201

@main_bp.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = User.get_by_id(user_id)
    if user:
        user['_id'] = str(user['_id'])
        return jsonify(user)
    return jsonify({'message': 'User not found'}), 404

@main_bp.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    user_data = request.json
    user = User.update(user_id, user_data)
    if user:
        user['_id'] = str(user['_id'])
        return jsonify(user)
    return jsonify({'message': 'User not found'}), 404

@main_bp.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    User.delete(user_id)
    return jsonify({'message': 'User deleted successfully'})