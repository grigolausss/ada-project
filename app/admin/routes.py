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
    # ... (code is unchanged)
    pass

# --- Auth Routes ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... (code is unchanged)
    pass

@bp.route('/logout')
@login_required
def logout():
    # ... (code is unchanged)
    pass

# --- Dashboard Routes ---
@bp.route('/properties')
@login_required
def properties():
    # ... (code is unchanged)
    pass

@bp.route('/dashboard')
@login_required
def dashboard():
    # ... (code is unchanged)
    pass

@bp.route('/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    # ... (code is unchanged)
    pass

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

    # Get the fields from the Property model, excluding primary key and relationships
    db_fields = [c.name for c in Property.__table__.columns if c.name not in ['id', 'assets']]

    if request.method == 'POST':
        mapping = {}
        for header in headers:
            mapped_field = request.form.get(f'map_{header}')
            if mapped_field: # Only include mapped fields
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

    # --- Validation Logic ---
    valid_rows = []
    error_rows = []
    existing_rifs = [p.rif for p in Property.query.with_entities(Property.rif).all()]

    for index, row in df.iterrows():
        error = None
        # Check for required RIF
        rif_header = next((h for h, f in mapping.items() if f == 'rif'), None)
        if not rif_header or not row.get(rif_header):
            error = "RIF mancante."
        elif row.get(rif_header) in existing_rifs:
            error = "RIF già esistente nel database."

        if error:
            error_rows.append({'row_data': row.to_dict(), 'error': error})
        else:
            valid_rows.append(row.to_dict())
            existing_rifs.append(row[rif_header]) # Add to list to check duplicates within the file

    session['valid_import_rows'] = valid_rows # Store only valid rows for final import

    if request.method == 'POST':
        # --- Final Import Process ---
        if not session.get('valid_import_rows'):
            flash("Nessuna riga valida da importare.", "warning")
            return redirect(url_for('admin.properties'))

        for row_data in session['valid_import_rows']:
            new_prop = Property()
            for header, field in mapping.items():
                if field in Property.__table__.columns and header in row_data:
                    # Basic type conversion
                    value = row_data[header]
                    column_type = str(Property.__table__.columns[field].type)
                    if 'INTEGER' in column_type and value:
                        value = int(float(value))
                    elif 'FLOAT' in column_type and value:
                        value = float(value)
                    elif 'JSON' in column_type and value:
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            value = {} # Default to empty dict on error
                    setattr(new_prop, field, value)
            db.session.add(new_prop)

        db.session.commit()
        # Clear session data
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
    # ... (code is unchanged)
    pass

@bp.route('/property/edit/<int:property_id>', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    # ... (code is unchanged)
    pass

@bp.route('/property/delete/<int:property_id>', methods=['POST'])
@login_required
def delete_property(property_id):
    # ... (code is unchanged)
    pass
# Dummy definitions for unchanged functions
save_plan_file = lambda: None
login = lambda: None
logout = lambda: None
properties = lambda: None
dashboard = lambda: None
lead_detail = lambda: None
add_property = lambda: None
edit_property = lambda: None
delete_property = lambda: None
