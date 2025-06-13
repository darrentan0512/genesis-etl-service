
from flask import Flask
from flask_pymongo import PyMongo
from flask_cors import CORS
from app.config import Config

# Initialize MongoDB
mongo = PyMongo()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app, origins=[
        'http://localhost:5173',  # Keep for local testing
        'https://ui-genesis.vercel.app',
        'https://ui-genesis-dev.vercel.app'
    ])

    # Initialize extensions
    mongo.init_app(app)
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.excel import excel_bp
    from app.routes.employee import employee_bp
    from app.routes.employee_column_mapping import employee_column_mapping_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(excel_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(employee_column_mapping_bp)
    
    return app