from app.admin import bp
from flask import render_template, request, flash, redirect, url_for, current_app
from app.models import User, Lead, Session, Answer, Event, Property, PropertyAsset
from flask_login import login_user, logout_user, login_required, current_user
from app import db
import json
import os
from werkzeug.utils import secure_filename

# --- Helper Function for File Upload ---
def save_plan_file(file, property_id):
    if not file or file.filename == '':
        return True
    try:
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{property_id}{ext}"
        upload_path = os.path.join(current_app.root_path, '..', 'uploads', 'plans')
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, unique_filename)
        file.save(file_path)
        asset = PropertyAsset.query.filter_by(property_id=property_id, tipo='planimetria').first()
        if asset:
            asset.path_privato = f'uploads/plans/{unique_filename}'
        else:
            asset = PropertyAsset(property_id=property_id, tipo='planimetria', path_privato=f'uploads/plans/{unique_filename}')
            db.session.add(asset)
        return True
    except Exception as e:
        flash(f"Errore fatale durante il caricamento del file: {e}", "danger")
        return False

# --- Auth Routes ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user is None or not user.check_password(request.form.get('password')):
            flash('Credenziali non valide.', 'danger')
            return redirect(url_for('admin.login'))
        login_user(user, remember=request.form.get('remember'))
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# --- Dashboard Routes ---
@bp.route('/properties')
@login_required
def properties():
    props = Property.query.order_by(Property.rif).all()
    return render_template('admin/properties.html', properties=props)

@bp.route('/dashboard')
@login_required
def dashboard():
    da_chiamare_subito_leads = Lead.query.filter_by(stato='da chiamare subito').order_by(Lead.creato_il.desc()).all()
    da_richiamare_leads = Lead.query.filter_by(stato='da richiamare').order_by(Lead.creato_il.desc()).all()
    return render_template('admin/dashboard.html', da_chiamare_subito_leads=da_chiamare_subito_leads, da_richiamare_leads=da_richiamare_leads)

@bp.route('/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    session = Session.query.filter_by(lead_id=lead.id).first()
    answers = []
    events = []
    if session:
        answers = Answer.query.filter_by(session_id=session.id).order_by(Answer.id).all()
        events = Event.query.filter_by(session_id=session.id).order_by(Event.ts).all()
    return render_template('admin/lead_detail.html', lead=lead, session=session, answers=answers, events=events)

# --- Property CRUD Routes ---
def populate_property_from_form(prop, form):
    """Helper function to populate a Property object from form data."""
    prop.rif = form.get('rif')
    prop.titolo = form.get('titolo')
    prop.tipologia = form.get('tipologia')
    prop.zona = form.get('zona')
    prop.mq = int(form.get('mq')) if form.get('mq') else None
    prop.prezzo_min = float(form.get('prezzo_min')) if form.get('prezzo_min') else None
    prop.prezzo_max = float(form.get('prezzo_max')) if form.get('prezzo_max') else None
    prop.stato = form.get('stato')
    prop.attivo = True if form.get('attivo') else False

    # Assemble the JSON characteristics from all 'char_' fields
    caratteristiche = {}
    for key in form:
        if key.startswith('char_'):
            field_name = key.replace('char_', '')
            caratteristiche[field_name] = form.get(key)

    prop.caratteristiche_json = {k: v for k, v in caratteristiche.items() if v}
    return prop

@bp.route('/property/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if request.method == 'POST':
        if Property.query.filter_by(rif=request.form.get('rif')).first():
            flash('Un immobile con questo RIF esiste già.', 'danger')
            return render_template('admin/property_form.html')
        new_prop = populate_property_from_form(Property(), request.form)
        db.session.add(new_prop)
        db.session.flush()
        upload_success = save_plan_file(request.files.get('planimetria'), new_prop.id)
        if not upload_success:
            db.session.rollback()
            return redirect(request.url)
        db.session.commit()
        flash('Immobile aggiunto con successo!', 'success')
        return redirect(url_for('admin.properties'))
    return render_template('admin/property_form.html')

@bp.route('/property/edit/<int:property_id>', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if request.method == 'POST':
        new_rif = request.form.get('rif')
        if new_rif != prop.rif and Property.query.filter_by(rif=new_rif).first():
            flash('Un altro immobile con questo RIF esiste già.', 'danger')
            return render_template('admin/property_form.html', property=prop)
        prop = populate_property_from_form(prop, request.form)
        upload_success = save_plan_file(request.files.get('planimetria'), prop.id)
        if not upload_success:
            db.session.rollback()
            return render_template('admin/property_form.html', property=prop)
        db.session.commit()
        flash('Immobile modificato con successo!', 'success')
        return redirect(url_for('admin.properties'))
    return render_template('admin/property_form.html', property=prop)

@bp.route('/property/delete/<int:property_id>', methods=['POST'])
@login_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    PropertyAsset.query.filter_by(property_id=prop.id).delete()
    db.session.delete(prop)
    db.session.commit()
    flash('Immobile eliminato con successo.', 'success')
    return redirect(url_for('admin.properties'))
