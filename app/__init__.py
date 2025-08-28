import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'admin.login'
login_manager.login_message = 'Per favore, effettua il login per accedere a questa pagina.'
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name='default'):
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from config.py
    app.config.from_object(config[config_name])

    # Ensure the instance folder exists, as it will be used for the database.
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Set the database URI to an absolute path within the instance folder.
    # This is the robust solution as per user instruction, ensuring it works
    # across different execution contexts (web server vs. CLI).
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # User Loader for Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Register CLI commands
    from app import commands
    if hasattr(commands, 'seed_db_command'):
         app.cli.add_command(commands.seed_db_command)

    return app
