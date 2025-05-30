import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/flask_mongo_app'
    RESOURCE_FOLDER = os.environ.get('RESOURCE_FOLDER')
    ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'}
