import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-hard-to-guess-string')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///instance/app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models to ensure they are registered with SQLAlchemy
    from app import models

    # Blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
