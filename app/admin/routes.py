from app.admin import bp
from flask import render_template, request, flash, redirect, url_for, current_app
from app.models import User, Lead, Session, Answer, Event, Property, PropertyAsset, AuditLog
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from sqlalchemy import or_
from app.admin.forms import LoginForm, UserForm, RequestResetForm, ResetPasswordForm
from app.email import send_email
import json
import os
from werkzeug.utils import secure_filename

# --- Helper Function for Logging ---
def log_action(action, details=''):
    try:
        log = AuditLog(user_id=current_user.id, action=action, details=details)
        db.session.add(log)
    except Exception as e:
        print(f"Failed to log action: {e}")

# --- Helper Function for File Upload ---
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

# --- Auth Routes ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('admin.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            log_action('login_success')
            db.session.commit()
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Credenziali non valide.', 'danger')
    return render_template('admin/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    log_action('logout')
    db.session.commit()
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated: return redirect(url_for('admin.dashboard'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.get_reset_token()
            reset_url = url_for('admin.reset_password', token=token, _external=True)
            send_email(to=user.email, subject='Reset della tua Password - Pannello ADA', template_prefix='email/reset_password', user=user, url=reset_url)
        flash('Se l\'email è presente nel nostro sistema, abbiamo inviato le istruzioni per il reset.', 'info')
        return redirect(url_for('admin.login'))
    return render_template('admin/forgot_password.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated: return redirect(url_for('admin.dashboard'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('Il link per il reset non è valido o è scaduto.', 'warning')
        return redirect(url_for('admin.forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('La tua password è stata resettata. Ora puoi effettuare il login.', 'success')
        return redirect(url_for('admin.login'))
    return render_template('admin/reset_password.html', form=form)

# --- Dashboard & View Routes ---
@bp.route('/dashboard')
@login_required
def dashboard():
    q = request.args.get('q', '')
    sort_by = request.args.get('sort_by', 'date')
    sort_order = request.args.get('sort_order', 'desc')
    da_chiamare_query = Lead.query.filter_by(stato='da chiamare subito')
    da_richiamare_query = Lead.query.filter_by(stato='da richiamare')
    if q:
        search_term = f"%{q}%"
        search_filter = or_(Lead.nome.ilike(search_term), Lead.cognome.ilike(search_term), Lead.email.ilike(search_term))
        da_chiamare_query = da_chiamare_query.filter(search_filter)
        da_richiamare_query = da_richiamare_query.filter(search_filter)
    sort_map = {'date': Lead.creato_il, 'name': Lead.cognome}
    sort_column = sort_map.get(sort_by, Lead.creato_il)
    if sort_order == 'asc': sort_column = sort_column.asc()
    else: sort_column = sort_column.desc()
    da_chiamare_query = da_chiamare_query.order_by(sort_column)
    da_richiamare_query = da_richiamare_query.order_by(sort_column)
    da_chiamare_subito_leads = da_chiamare_query.all()
    da_richiamare_leads = da_richiamare_query.all()
    return render_template('admin/dashboard.html', da_chiamare_subito_leads=da_chiamare_subito_leads, da_richiamare_leads=da_richiamare_leads, q=q, sort_by=sort_by, sort_order=sort_order)

@bp.route('/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    session = Session.query.filter_by(lead_id=lead.id).first()
    answers, events = [], []
    if session:
        answers = Answer.query.filter_by(session_id=session.id).order_by(Answer.id).all()
        events = Event.query.filter_by(session_id=session.id).order_by(Event.ts).all()
    return render_template('admin/lead_detail.html', lead=lead, session=session, answers=answers, events=events)

@bp.route('/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=30)
    return render_template('admin/logs.html', logs=logs)

# --- Property CRUD ---
@bp.route('/properties')
@login_required
def properties():
    q = request.args.get('q', '')
    filter_zona = request.args.get('filter_zona', '')
    sort_by = request.args.get('sort_by', 'rif')
    sort_order = request.args.get('sort_order', 'asc')
    query = Property.query
    if q:
        search_term = f"%{q}%"
        query = query.filter(or_(Property.rif.ilike(search_term), Property.titolo.ilike(search_term), Property.zona.ilike(search_term)))
    if filter_zona: query = query.filter(Property.zona == filter_zona)
    sort_map = {'rif': Property.rif, 'zona': Property.zona, 'mq': Property.mq, 'prezzo': Property.prezzo_min}
    sort_column = sort_map.get(sort_by, Property.rif)
    if sort_order == 'desc': sort_column = sort_column.desc()
    else: sort_column = sort_column.asc()
    query = query.order_by(sort_column)
    props = query.all()
    available_zones = [z[0] for z in db.session.query(Property.zona).distinct().order_by(Property.zona).all() if z[0]]
    return render_template('admin/properties.html', properties=props, available_zones=available_zones, q=q, filter_zona=filter_zona, sort_by=sort_by, sort_order=sort_order)

def populate_property_from_form(prop, form):
    prop.rif, prop.titolo, prop.tipologia, prop.zona, prop.stato = form.get('rif'), form.get('titolo'), form.get('tipologia'), form.get('zona'), form.get('stato')
    prop.mq = int(form.get('mq')) if form.get('mq') else None
    prop.prezzo_min = float(form.get('prezzo_min')) if form.get('prezzo_min') else None
    prop.prezzo_max = float(form.get('prezzo_max')) if form.get('prezzo_max') else None
    prop.attivo = True if form.get('attivo') else False
    caratteristiche = {k.replace('char_', ''): v for k, v in form.items() if k.startswith('char_')}
    prop.caratteristiche_json = {k: v for k, v in caratteristiche.items() if v}
    return prop

@bp.route('/property/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if request.method == 'POST':
        if Property.query.filter_by(rif=request.form.get('rif')).first():
            flash('Un immobile con questo RIF esiste già.', 'danger')
            tmp_prop = populate_property_from_form(Property(), request.form)
            if tmp_prop.caratteristiche_json is None:
                tmp_prop.caratteristiche_json = {}
            return render_template('admin/property_form.html', property=tmp_prop)
        new_prop = populate_property_from_form(Property(), request.form)
        db.session.add(new_prop)
        db.session.flush()
        upload_success = save_plan_file(request.files.get('planimetria'), new_prop.id)
        if not upload_success:
            db.session.rollback()
            return redirect(request.url)
        log_action('property_add', f"Aggiunto immobile RIF: {new_prop.rif}")
        db.session.commit()
        flash('Immobile aggiunto con successo!', 'success')
        return redirect(url_for('admin.properties'))
    prop = Property()
    prop.caratteristiche_json = {}
    return render_template('admin/property_form.html', property=prop)

@bp.route('/property/edit/<int:property_id>', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if prop.caratteristiche_json is None:
        prop.caratteristiche_json = {}
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
        log_action('property_edit', f"Modificato immobile RIF: {prop.rif}")
        db.session.commit()
        flash('Immobile modificato con successo!', 'success')
        return redirect(url_for('admin.properties'))
    return render_template('admin/property_form.html', property=prop)

@bp.route('/property/delete/<int:property_id>', methods=['POST'])
@login_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    log_action('property_delete', f"Eliminato immobile RIF: {prop.rif}")
    PropertyAsset.query.filter_by(property_id=prop.id).delete()
    db.session.delete(prop)
    db.session.commit()
    flash('Immobile eliminato con successo.', 'success')
    return redirect(url_for('admin.properties'))

# --- User Management CRUD ---
@bp.route('/users')
@login_required
def users():
    all_users = User.query.order_by(User.email).all()
    return render_template('admin/users.html', users=all_users)

@bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        log_action('user_add', f"Aggiunto utente {user.email}")
        db.session.commit()
        flash('Nuovo utente aggiunto con successo.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', form=form)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm()
    if form.validate_on_submit():
        if user.email != form.email.data and User.query.filter_by(email=form.email.data).first():
             flash('Email già in uso.', 'danger')
        else:
            user.email = form.email.data
            if form.password.data: user.set_password(form.password.data)
            log_action('user_edit', f"Modificato utente {user.email}")
            db.session.commit()
            flash('Utente modificato con successo.', 'success')
            return redirect(url_for('admin.users'))
    elif request.method == 'GET':
        form.email.data = user.email
    return render_template('admin/user_form.html', form=form, user=user)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Non puoi eliminare te stesso.', 'danger')
        return redirect(url_for('admin.users'))
    user = User.query.get_or_404(user_id)
    log_action('user_delete', f"Eliminato utente {user.email}")
    db.session.delete(user)
    db.session.commit()
    flash('Utente eliminato con successo.', 'success')
    return redirect(url_for('admin.users'))
