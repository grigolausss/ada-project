import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_login import LoginManager
from flask_mail import Mail  # <-- NOVITÀ

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'admin.login'
mail = Mail()  # <-- NOVITÀ

def create_app():
    # istanza relativa per avere un instance_path stabile
    app = Flask(__name__, instance_relative_config=True)

    # Secret key
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me')

    # Assicura che la cartella instance esista (serve a SQLite e ad altri file runtime)
    os.makedirs(app.instance_path, exist_ok=True)

    # ---------- DATABASE ----------
    raw_db_url = os.getenv('DATABASE_URL', '').strip()
    if not raw_db_url:
        # default di emergenza
        db_path = os.path.join(app.instance_path, 'app.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    else:
        if raw_db_url.startswith("sqlite:///"):
            # Estrae il pezzo dopo sqlite:///
            rel = raw_db_url[len("sqlite:///"):]
            # Se è un path relativo, ancoralo a instance_path
            if not os.path.isabs(rel):
                abs_path = os.path.join(app.instance_path, os.path.normpath(rel))
                app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{abs_path}"
            else:
                app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
        else:
            # Postgres/MySQL ecc. lasciamo intatto
            app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Evita errori con thread del dev server
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {"connect_args": {"check_same_thread": False}})

    db.init_app(app)
    migrate.init_app(app, db)

    # ---------- MAIL (LA PARTE CHE TI MANCA) ----------
    # Legge dalla .env e popola app.config
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'localhost')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '25'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', '0') in ('1', 'true', 'True')
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', '0') in ('1', 'true', 'True')
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    # Flask-Mail accetta stringa "Nome <email@dominio>" oppure tupla (nome, email)
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
    app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', '0') in ('1', 'true', 'True')

    mail.init_app(app)  # <-- inizializza l'estensione

    # Login manager
    from app.models import User  # noqa

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.init_app(app)

    # Blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    # CLI
    from app import commands
    app.cli.add_command(commands.seed_db_command)

    return app