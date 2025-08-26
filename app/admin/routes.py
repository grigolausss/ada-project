from app.admin import bp
from flask import render_template, request, flash, redirect, url_for, current_app, session
from app.models import User, Lead, Session, Answer, Event, Property, PropertyAsset
from flask_login import login_user, logout_user, login_required, current_user
from app import db
import json
import os
from werkzeug.utils import secure_filename
import pandas as pd

# --- Helper Function for File Upload ---
def save_plan_file(file, property_id):
    if not file or file.filename == '':
        return # No file uploaded
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
        flash(f"Errore durante il caricamento del file: {e}", "danger")
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

# --- Import Routes ---
@bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_properties():
    if request.method == 'POST':
        if 'import_file' not in request.files:
            flash('Nessun file selezionato.', 'danger')
            return redirect(request.url)
        file = request.files['import_file']
        if file.filename == '':
            flash('Nessun file selezionato.', 'danger')
            return redirect(request.url)
        if file:
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file, dtype=str).fillna('')
                else:
                    df = pd.read_excel(file, dtype=str).fillna('')
                session['import_data'] = df.to_json(orient='split')
                return redirect(url_for('admin.map_import'))
            except Exception as e:
                flash(f"Errore durante la lettura del file: {e}", 'danger')
                return redirect(request.url)
    return render_template('admin/import.html')

@bp.route('/import/map', methods=['GET', 'POST'])
@login_required
def map_import():
    if 'import_data' not in session:
        return redirect(url_for('admin.import_properties'))
    df = pd.read_json(session['import_data'], orient='split')
    headers = list(df.columns)
    db_fields = [c.name for c in Property.__table__.columns if c.name not in ['id', 'assets']]
    if request.method == 'POST':
        mapping = {}
        for header in headers:
            mapped_field = request.form.get(f'map_{header}')
            if mapped_field:
                mapping[header] = mapped_field
        session['import_mapping'] = mapping
        return redirect(url_for('admin.confirm_import'))
    return render_template('admin/import_map.html', headers=headers, db_fields=db_fields, preview_data=df.head())

@bp.route('/import/confirm', methods=['GET', 'POST'])
@login_required
def confirm_import():
    if 'import_data' not in session or 'import_mapping' not in session:
        return redirect(url_for('admin.import_properties'))
    df = pd.read_json(session['import_data'], orient='split')
    mapping = session['import_mapping']
    valid_rows = []
    error_rows = []
    existing_rifs = [p.rif for p in Property.query.with_entities(Property.rif).all()]
    for index, row in df.iterrows():
        error = None
        rif_header = next((h for h, f in mapping.items() if f == 'rif'), None)
        if not rif_header or not row.get(rif_header):
            error = "RIF mancante."
        elif row.get(rif_header) in existing_rifs:
            error = "RIF già esistente nel database."
        if error:
            error_rows.append({'row_data': row.to_dict(), 'error': error})
        else:
            valid_rows.append(row.to_dict())
            existing_rifs.append(row[rif_header])
    session['valid_import_rows'] = valid_rows
    if request.method == 'POST':
        if not session.get('valid_import_rows'):
            flash("Nessuna riga valida da importare.", "warning")
            return redirect(url_for('admin.properties'))
        for row_data in session['valid_import_rows']:
            new_prop = Property()
            for header, field in mapping.items():
                if field in Property.__table__.columns and header in row_data:
                    value = row_data[header]
                    column_type = str(Property.__table__.columns[field].type)
                    if 'INTEGER' in column_type and value: value = int(float(value))
                    elif 'FLOAT' in column_type and value: value = float(value)
                    elif 'JSON' in column_type and value:
                        try: value = json.loads(value)
                        except (json.JSONDecodeError, TypeError): value = {}
                    setattr(new_prop, field, value)
            db.session.add(new_prop)
        db.session.commit()
        session.pop('import_data', None)
        session.pop('import_mapping', None)
        session.pop('valid_import_rows', None)
        flash(f"{len(valid_rows)} immobili importati con successo!", "success")
        return redirect(url_for('admin.properties'))
    return render_template('admin/import_confirm.html', valid_rows=valid_rows, error_rows=error_rows)

# --- Property CRUD Routes ---
@bp.route('/property/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if request.method == 'POST':
        if Property.query.filter_by(rif=request.form.get('rif')).first():
            flash('Un immobile con questo RIF esiste già.', 'danger')
            return render_template('admin/property_form.html')
        new_prop = Property(rif=request.form.get('rif'))
        new_prop.titolo=request.form.get('titolo')
        new_prop.tipologia=request.form.get('tipologia')
        new_prop.zona=request.form.get('zona')
        new_prop.mq=int(request.form.get('mq')) if request.form.get('mq') else None
        new_prop.prezzo_min=float(request.form.get('prezzo_min')) if request.form.get('prezzo_min') else None
        new_prop.prezzo_max=float(request.form.get('prezzo_max')) if request.form.get('prezzo_max') else None
        new_prop.stato=request.form.get('stato')
        new_prop.attivo=True if request.form.get('attivo') else False
        try:
            new_prop.caratteristiche_json = json.loads(request.form.get('caratteristiche_json', '{}'))
        except json.JSONDecodeError:
            flash('Formato JSON non valido per le caratteristiche.', 'danger')
            return render_template('admin/property_form.html')
        db.session.add(new_prop)
        db.session.flush()
        if 'planimetria' in request.files:
            save_plan_file(request.files['planimetria'], new_prop.id)
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
        prop.rif = new_rif
        prop.titolo = request.form.get('titolo')
        prop.tipologia = request.form.get('tipologia')
        prop.zona = request.form.get('zona')
        prop.mq = int(request.form.get('mq')) if request.form.get('mq') else None
        prop.prezzo_min = float(request.form.get('prezzo_min')) if request.form.get('prezzo_min') else None
        prop.prezzo_max = float(request.form.get('prezzo_max')) if request.form.get('prezzo_max') else None
        prop.stato = request.form.get('stato')
        prop.attivo = True if request.form.get('attivo') else False
        try:
            prop.caratteristiche_json = json.loads(request.form.get('caratteristiche_json', '{}'))
        except json.JSONDecodeError:
            flash('Formato JSON non valido per le caratteristiche.', 'danger')
            return render_template('admin/property_form.html', property=prop)
        if 'planimetria' in request.files:
            save_plan_file(request.files['planimetria'], prop.id)
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
