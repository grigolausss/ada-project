from app.admin import bp
from flask import render_template, request, flash, redirect, url_for
from app.models import User
from flask_login import login_user, logout_user, login_required, current_user

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash('Credenziali non valide. Per favore, riprova.', 'danger')
            return redirect(url_for('admin.login'))

        login_user(user, remember=remember)
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

from app.models import Lead

@bp.route('/dashboard')
@login_required
def dashboard():
    da_chiamare_subito_leads = Lead.query.filter_by(stato='da chiamare subito').order_by(Lead.creato_il.desc()).all()
    da_richiamare_leads = Lead.query.filter_by(stato='da richiamare').order_by(Lead.creato_il.desc()).all()

    return render_template('admin/dashboard.html',
                           da_chiamare_subito_leads=da_chiamare_subito_leads,
                           da_richiamare_leads=da_richiamare_leads)
