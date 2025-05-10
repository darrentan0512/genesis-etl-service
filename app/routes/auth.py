import jwt
import datetime
from flask import Blueprint, render_template, request, jsonify
from werkzeug.security import check_password_hash
from app.models.user import User
from app.config import Config

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    user_data = request.json
    if not user_data or 'email' not in user_data or 'password' not in user_data:
        return jsonify({'error': 'Invalid or missing JSON payload'}), 400

    email = user_data['email']
    password = user_data['password']

    # Find user by email
    user = User.find_by_email(email)
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    # Check if the password matches
    if not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    # Generate JWT token
    token = jwt.encode(
        {
            'user_id': str(user['_id']),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        },
        Config.SECRET_KEY,
        algorithm='HS256'
    )

    return jsonify({'token': token}), 200