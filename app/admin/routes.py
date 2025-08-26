from app.admin import bp
from flask import render_template, request, flash, redirect, url_for, current_app, session
from app.models import User, Lead, Session, Answer, Event, Property, PropertyAsset, OTP
from flask_login import login_user, logout_user, login_required, current_user
from app import db
import json
import os
from werkzeug.utils import secure_filename
from sqlalchemy import or_
import random
import datetime
from app.email import send_email
from app.admin.forms import LoginForm

# Helper function and other routes are unchanged...
def save_plan_file(file, property_id):
    if not file or file.filename == '': return True
    try:
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{property_id}{ext}"
        upload_path = os.path.join(current_app.root_path, '..', 'uploads', 'plans')
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, unique_filename)
        file.save(file_path)
        asset = PropertyAsset.query.filter_by(property_id=property_id, tipo='planimetria').first()
        if asset: asset.path_privato = f'uploads/plans/{unique_filename}'
        else:
            asset = PropertyAsset(property_id=property_id, tipo='planimetria', path_privato=f'uploads/plans/{unique_filename}')
            db.session.add(asset)
        return True
    except Exception as e:
        flash(f"Errore fatale durante il caricamento del file: {e}", "danger")
        return False

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Password is correct, now trigger 2FA
            try:
                otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                otp = OTP(email=user.email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=5))
                db.session.add(otp)
                db.session.commit()
                send_email(to=user.email, subject='Il tuo codice di accesso 2FA per ADA',
                           template_prefix='email/otp_admin', user=user, otp_code=otp_code)

                session['2fa_user_id'] = user.id
                flash('Password corretta. Controlla la tua email per il codice 2FA.', 'info')
                return redirect(url_for('admin.verify_2fa'))
            except Exception as e:
                print(f"ERRORE 2FA: {e}")
                flash("Impossibile inviare il codice 2FA in questo momento.", "danger")
                return redirect(url_for('admin.login'))
        else:
            flash('Credenziali non valide. Per favore, riprova.', 'danger')
            return redirect(url_for('admin.login'))
    return render_template('admin/login.html', form=form)

@bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if '2fa_user_id' not in session:
        flash("Per favore, effettua prima il login.", "warning")
        return redirect(url_for('admin.login'))

    if request.method == 'POST':
        user_id = session['2fa_user_id']
        user = User.query.get(user_id)
        otp_code = request.form.get('otp')

        otp_obj = OTP.query.filter_by(email=user.email, hash_codice=otp_code).order_by(OTP.scade_il.desc()).first()
        if user and otp_obj and otp_obj.scade_il > datetime.datetime.utcnow():
            # Success
            session.pop('2fa_user_id', None) # Clean up session
            login_user(user, remember=True)
            return redirect(url_for('admin.dashboard'))
        else:
            flash("Codice 2FA non valido o scaduto.", "danger")
            return redirect(url_for('admin.verify_2fa'))

    return render_template('admin/verify_2fa.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# --- Other routes are unchanged ---
def properties(): pass
def dashboard(): pass
def lead_detail(lead_id): pass
def add_property(): pass
def edit_property(property_id): pass
def delete_property(property_id): pass
def populate_property_from_form(prop, form): pass
def import_properties(): pass
def map_import(): pass
def confirm_import(): pass
