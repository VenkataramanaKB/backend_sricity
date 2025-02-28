from flask import Flask
from flask_jwt_extended import JWTManager
from .config import Config
from .models import init_db
from flask_cors import CORS
from .routes import routes

def create_app():
    app = Flask(__name__)
    
    # Load configurations from Config class
    app.config.from_object(Config)
    
    # Initialize Extensions
    init_db(app)  # Initialize the database
    jwt = JWTManager(app)
    CORS(app)
    
    # Register Blueprints
    app.register_blueprint(routes, url_prefix="/api")
    
    return app