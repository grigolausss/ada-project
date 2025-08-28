import os
from functools import wraps
from app.main import bp
from flask import render_template, request, redirect, url_for, flash, session, current_app, send_from_directory
from app.models import Lead, OTP, Property, Session, Answer, Event, PropertyAsset

# DECORATOR for session protection
def otp_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('otp_verified'):
            flash('Per accedere a questa pagina, devi prima verificare la tua email.', 'warning')
            return redirect(url_for('main.index'))
        if 'lead_id' not in session:
            flash('Sessione non valida. Per favore, ricomincia.', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
from app import db
import datetime
import random
from app.email import send_email
from app.main.forms import RegistrationForm, OTPForm
from sqlalchemy import or_
from flask_wtf.csrf import generate_csrf

# ... (Decorator and initial routes are unchanged) ...

@bp.route('/final_choice')
@otp_required
def final_choice():
    # ...
    pass

@bp.route('/show_address', methods=['POST'])
@otp_required
def show_address():
    # ...
    pass

@bp.route('/address_ok', methods=['POST'])
@otp_required
def address_ok():
    # ...
    pass

@bp.route('/rejection_questionnaire', methods=['GET', 'POST'])
@otp_required
def rejection_questionnaire():
    if request.method == 'POST':
        # This will handle the form submission from the rejection questionnaire
        session_id = session['session_id']
        # Save the rejection reason
        for key, value in request.form.items():
             if key != 'csrf_token' and value:
                answer = Answer(session_id=session_id, domanda_id=f"rejection_{key}", domanda_testo=key.replace('_', ' ').title(), risposta=value, fase='rejection')
                db.session.add(answer)

        # Mark lead for follow-up
        lead = Lead.query.get(session['lead_id'])
        lead.stato = 'da richiamare'
        db.session.commit()

        # Find alternatives
        current_session = Session.query.get(session_id)
        current_property = Property.query.filter_by(rif=current_session.rif).first()
        price_min = (current_property.prezzo_min or 0) * 0.85
        price_max = (current_property.prezzo_max or float('inf')) * 1.15
        mq_min = (current_property.mq or 0) * 0.90
        mq_max = (current_property.mq or float('inf')) * 1.10
        alternatives = Property.query.filter(
            Property.rif != current_property.rif,
            Property.zona == current_property.zona,
            Property.prezzo_min.between(price_min, price_max),
            Property.mq.between(mq_min, mq_max)
        ).limit(3).all()

        # Store alternatives in session to pass to the next page
        session['alternatives'] = [prop.id for prop in alternatives]
        return redirect(url_for('main.show_alternatives'))

    # For GET request, just show the form
    csrf_token = generate_csrf()
    return render_template('main/rejection_questionnaire.html', csrf_token=csrf_token)

@bp.route('/show_alternatives')
@otp_required
def show_alternatives():
    if 'alternatives' not in session:
        return redirect(url_for('main.index'))

    prop_ids = session.get('alternatives', [])
    alternatives = Property.query.filter(Property.id.in_(prop_ids)).all()

    if not alternatives:
        return render_template('main/no_alternatives.html')

    return render_template('main/alternatives.html', alternatives=alternatives)


@bp.route('/collect_phone_and_redirect', methods=['GET', 'POST'])
@otp_required
def collect_phone_and_redirect():
    if request.method == 'POST':
        telefono = request.form.get('telefono')
        if telefono:
            lead = Lead.query.get(session['lead_id'])
            lead.telefono = telefono
            db.session.commit()
    message = "Grazie per il tuo tempo. Un nostro consulente potrebbe contattarti. Verrai ora reindirizzato al nostro sito principale."
    return render_template('main/thank_you.html', message=message, redirect_url="https://www.artediabitare.it/")


@bp.route('/reset_session_for_test')
def reset_session_for_test():
    session.clear()
    return "Session cleared"

@bp.route('/', methods=['GET', 'POST'])
def index():
    # If user is already part-way through the process, redirect them appropriately
    if 'session_id' in session and 'otp_verified' in session and session['otp_verified']:
        return redirect(url_for('main.insert_rif'))
    if 'session_id' in session and 'email' in session:
        return redirect(url_for('main.verify_otp', email=session['email']))

    form = RegistrationForm()
    if form.validate_on_submit():
        lead = Lead.query.filter_by(email=form.email.data).first()
        if not lead:
            lead = Lead(
                nome=form.nome.data,
                email=form.email.data,
                privacy_consent=form.privacy_consent.data
            )
            db.session.add(lead)
            db.session.commit()

        # Create a new session for this interaction
        user_session = Session(lead_id=lead.id, ip_address=request.remote_addr)
        db.session.add(user_session)
        db.session.commit()

        # OTP Generation and Sending
        otp_code = str(random.randint(100000, 999999))
        otp_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
        otp = OTP(code=otp_code, expiry=otp_expiry, lead_id=lead.id)
        db.session.add(otp)
        db.session.commit()

        send_email(
            subject='Il tuo codice di verifica',
            recipients=[lead.email],
            text_body=f'Il tuo codice di verifica è: {otp_code}',
            html_body=render_template('email/otp.html', otp_code=otp_code)
        )

        session['lead_id'] = lead.id
        session['session_id'] = user_session.id
        session['email'] = lead.email
        flash('Ti abbiamo inviato un codice di verifica via email.', 'info')
        return redirect(url_for('main.verify_otp', email=lead.email))

    return render_template('main/index.html', form=form)


@bp.route('/verify_otp/<email>', methods=['GET', 'POST'])
def verify_otp(email):
    form = OTPForm()
    if form.validate_on_submit():
        lead = Lead.query.filter_by(email=email).first()
        if not lead:
            flash('Utente non trovato.', 'danger')
            return redirect(url_for('main.index'))

        otp = OTP.query.filter_by(lead_id=lead.id, code=form.otp.data).order_by(OTP.created_at.desc()).first()

        if otp and not otp.is_expired() and not otp.is_verified:
            session['otp_verified'] = True
            otp.is_verified = True # Mark OTP as used
            db.session.commit()
            flash('Email verificata con successo!', 'success')
            return redirect(url_for('main.insert_rif'))
        else:
            flash('Codice OTP non valido, scaduto o già utilizzato.', 'danger')

    return render_template('main/verify_otp.html', form=form, email=email)


@bp.route('/resend_otp/<email>')
def resend_otp(email):
    lead = Lead.query.filter_by(email=email).first()
    if not lead:
        flash('Utente non trovato.', 'danger')
        return redirect(url_for('main.index'))

    # Generate and send a new OTP
    otp_code = str(random.randint(100000, 999999))
    otp_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    new_otp = OTP(code=otp_code, expiry=otp_expiry, lead_id=lead.id)
    db.session.add(new_otp)
    db.session.commit()

    send_email(
        subject='Il tuo nuovo codice di verifica',
        recipients=[lead.email],
        text_body=f'Il tuo nuovo codice di verifica è: {otp_code}',
        html_body=render_template('email/otp.html', otp_code=otp_code)
    )

    flash('Un nuovo codice è stato inviato alla tua email.', 'info')
    return redirect(url_for('main.verify_otp', email=email))

from app.main.forms import RIFForm

@bp.route('/insert_rif', methods=['GET', 'POST'])
@otp_required
def insert_rif():
    form = RIFForm()
    if form.validate_on_submit():
        prop = Property.query.filter_by(rif=form.rif.data).first()
        if prop:
            # Associate RIF with the current session
            user_session = Session.query.get(session['session_id'])
            user_session.rif = prop.rif
            db.session.commit()

            flash('Immobile trovato!', 'success')
            return redirect(url_for('main.property_details', rif=prop.rif))
        else:
            flash('Codice RIF non valido o immobile non trovato.', 'danger')
    return render_template('main/insert_rif.html', form=form)

from flask import abort

@bp.route('/property/<rif>')
@otp_required
def property_details(rif):
    prop = Property.query.filter_by(rif=rif).first_or_404()
    # Check if the user has submitted this RIF in the current session
    user_session = Session.query.get(session.get('session_id'))
    if not user_session or user_session.rif != rif:
        flash('Accesso non autorizzato a questa pagina.', 'warning')
        return redirect(url_for('main.insert_rif'))

    return render_template('main/property_details.html', prop=prop)

@bp.route('/questionnaire', methods=['GET', 'POST'])
@otp_required
def questionnaire():
    # Hard-coded questions for now to restore functionality
    questions = [
        {'id': 'budget', 'text': 'Qual è il tuo budget massimo?', 'type': 'radio', 'options': ['Meno di 150.000€', '150.000€ - 250.000€', '250.000€ - 350.000€', 'Oltre 350.000€']},
        {'id': 'purchase_timeline', 'text': 'Quando prevedi di acquistare?', 'type': 'radio', 'options': ['Entro 3 mesi', 'Entro 6 mesi', 'Entro un anno', 'Non ho fretta']},
        {'id': 'financing', 'text': 'Hai già una pre-approvazione del mutuo?', 'type': 'radio', 'options': ['Sì', 'No, ma ho già parlato con la banca', 'No, devo ancora iniziare', 'Comprerò in contanti']},
        {'id': 'first_home', 'text': 'Si tratta della tua prima casa?', 'type': 'radio', 'options': ['Sì', 'No']},
        {'id': 'visiting', 'text': 'Sei disponibile per visite in loco nei prossimi 7 giorni?', 'type': 'radio', 'options': ['Sì', 'No']}
    ]

    if request.method == 'POST':
        session_id = session.get('session_id')
        if not session_id:
            flash('Sessione non valida.', 'danger')
            return redirect(url_for('main.index'))

        for question in questions:
            question_id = question['id']
            answer_text = request.form.get(question_id)
            if answer_text:
                answer = Answer(
                    session_id=session_id,
                    domanda_id=question_id,
                    domanda_testo=question['text'],
                    risposta=answer_text,
                    fase='pre-qualifica'
                )
                db.session.add(answer)

        db.session.commit()
        flash('Questionario completato, grazie!', 'success')
        return redirect(url_for('main.view_plan'))

    return render_template('main/questionnaire.html', questions=questions)

@bp.route('/view_plan')
@otp_required
def view_plan():
    user_session = Session.query.get(session.get('session_id'))
    if not user_session or not user_session.rif:
        flash('Per favore, seleziona prima un immobile.', 'warning')
        return redirect(url_for('main.insert_rif'))

    prop = Property.query.filter_by(rif=user_session.rif).first_or_404()
    floor_plan = PropertyAsset.query.filter_by(property_id=prop.id, asset_type='plan').first()

    if not floor_plan:
        flash('Planimetria non disponibile per questo immobile.', 'warning')
        # Decide on a redirect destination, maybe property details
        return redirect(url_for('main.property_details', rif=prop.rif))

    return render_template('main/view_plan.html', floor_plan_url=url_for('main.serve_file', filename=floor_plan.file_path))

@bp.route('/serve_file/<filename>')
@otp_required
def serve_file(filename):
    # Security check: ensure the requested file belongs to the property in the user's session
    user_session = Session.query.get(session.get('session_id'))
    if not user_session or not user_session.rif:
        abort(403) # Forbidden

    prop = Property.query.filter_by(rif=user_session.rif).first()
    if not prop:
        abort(404)

    asset = PropertyAsset.query.filter_by(property_id=prop.id, file_path=filename).first()
    if not asset:
        abort(403) # Forbidden, trying to access a file not related to their session property

    # Assuming UPLOAD_FOLDER is configured in the app config
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    plans_directory = os.path.join(upload_folder, 'plans')
    return send_from_directory(plans_directory, filename, as_attachment=False)

@bp.route('/post_view_questionnaire', methods=['GET', 'POST'])
@otp_required
def post_view_questionnaire():
    questions = [
        {'id': 'plan_liked', 'text': 'La planimetria che hai visto ha soddisfatto le tue aspettative?', 'type': 'radio', 'options': ['Sì, molto', 'In parte', 'No, per niente']},
        {'id': 'next_step', 'text': 'Quale vorresti che fosse il prossimo passo?', 'type': 'radio', 'options': ['Vorrei prenotare una visita', 'Vorrei maggiori informazioni', 'Non sono interessato']}
    ]

    if request.method == 'POST':
        session_id = session.get('session_id')
        if not session_id:
            flash('Sessione non valida.', 'danger')
            return redirect(url_for('main.index'))

        for question in questions:
            question_id = question['id']
            answer_text = request.form.get(question_id)
            if answer_text:
                answer = Answer(
                    session_id=session_id,
                    domanda_id=question_id,
                    domanda_testo=question['text'],
                    risposta=answer_text,
                    fase='post-visualizzazione'
                )
                db.session.add(answer)

        db.session.commit()

        # Logic to decide where to go next based on answers could be added here
        # For now, redirecting to a generic next step
        return redirect(url_for('main.final_choice'))

    return render_template('main/post_view_questionnaire.html', questions=questions)
