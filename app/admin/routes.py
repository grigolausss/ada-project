from app.admin import bp
from flask import render_template

@bp.route('/login')
def login():
    # This is a placeholder for the admin login page
    return "<h1>Admin Login Page (Placeholder)</h1>"
