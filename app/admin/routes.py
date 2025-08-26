from app.admin import bp
from flask import render_template, request, flash, redirect, url_for
from app.models import User, Lead, Session, Answer, Event, Property
from flask_login import login_user, logout_user, login_required, current_user
from app import db
import json

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

    return render_template('admin/dashboard.html',
                           da_chiamare_subito_leads=da_chiamare_subito_leads,
                           da_richiamare_leads=da_richiamare_leads)

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

@bp.route('/property/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if request.method == 'POST':
        rif = request.form.get('rif')
        # Check for uniqueness
        if Property.query.filter_by(rif=rif).first():
            flash('Un immobile con questo RIF esiste già.', 'danger')
            return render_template('admin/property_form.html')

        new_prop = Property(
            rif=rif,
            titolo=request.form.get('titolo'),
            tipologia=request.form.get('tipologia'),
            zona=request.form.get('zona'),
            mq=int(request.form.get('mq')) if request.form.get('mq') else None,
            prezzo_min=float(request.form.get('prezzo_min')) if request.form.get('prezzo_min') else None,
            prezzo_max=float(request.form.get('prezzo_max')) if request.form.get('prezzo_max') else None,
            stato=request.form.get('stato'),
            attivo=True if request.form.get('attivo') else False
        )
        try:
            new_prop.caratteristiche_json = json.loads(request.form.get('caratteristiche_json', '{}'))
        except json.JSONDecodeError:
            flash('Formato JSON non valido per le caratteristiche.', 'danger')
            return render_template('admin/property_form.html', property=new_prop)

        db.session.add(new_prop)
        db.session.commit()
        flash('Immobile aggiunto con successo!', 'success')
        return redirect(url_for('admin.properties'))

    return render_template('admin/property_form.html')

@bp.route('/property/edit/<int:property_id>', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if request.method == 'POST':
        # Check for RIF uniqueness if it was changed
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

        db.session.commit()
        flash('Immobile modificato con successo!', 'success')
        return redirect(url_for('admin.properties'))

    return render_template('admin/property_form.html', property=prop)

@bp.route('/property/delete/<int:property_id>', methods=['POST'])
@login_required
def delete_property(property_id):
    prop = Property.query.get_or_404(property_id)
    # Here you might want to check for related assets or leads before deleting
    db.session.delete(prop)
    db.session.commit()
    flash('Immobile eliminato con successo.', 'success')
    return redirect(url_for('admin.properties'))
