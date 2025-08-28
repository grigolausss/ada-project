import os
from app import create_app

# Load environment variables from .env or .flaskenv
from dotenv import load_dotenv
load_dotenv()

# Use FLASK_ENV to determine which config to load (e.g., 'development' or 'production')
config_name = os.environ.get('FLASK_ENV') or 'default'
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))
