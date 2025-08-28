from functools import wraps
from app.main import bp
from flask import render_template, request, redirect, url_for, flash, session, current_app
from app.models import Lead, OTP, Property, Session, Answer, Event, PropertyAsset
from app import db
import datetime
import random
from app.email import send_email
from app.main.forms import RegistrationForm, OTPForm
from sqlalchemy import or_

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

@bp.route('/', methods=['GET', 'POST'])
def index():
    form = RegistrationForm()
    if form.validate_on_submit():
        session.clear()
        lead = Lead.query.filter_by(email=form.email.data).first()
        if not lead:
            lead = Lead(nome=form.nome.data, cognome=form.cognome.data,
                        email=form.email.data, consensi_json={'privacy': True})
            db.session.add(lead)
            db.session.commit()
        session['lead_id'] = lead.id
        try:
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            otp = OTP(email=lead.email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))
            db.session.add(otp)
            db.session.commit()
            send_email(to=lead.email, subject='Il tuo codice di verifica ADA',
                       template_prefix='email/otp', lead=lead, otp_code=otp_code)
            flash(f'Ti abbiamo inviato un codice di verifica all\'indirizzo {lead.email}.', 'success')
        except Exception as e:
            print(f"ERRORE: Impossibile inviare l'OTP via email. {e}")
            flash('Errore del server durante la generazione del codice. Riprova.', 'danger')
        return redirect(url_for('main.verify_otp', email=lead.email))
    return render_template('main/index.html', form=form)

@bp.route('/verify_otp/<email>', methods=['GET', 'POST'])
def verify_otp(email):
    if 'lead_id' not in session:
        flash('Sessione non valida, per favore ricomincia.', 'warning')
        return redirect(url_for('main.index'))
    form = OTPForm()
    if form.validate_on_submit():
        otp_code = form.otp.data
        otp_obj = OTP.query.filter_by(email=email, hash_codice=otp_code).order_by(OTP.scade_il.desc()).first()

        # Bypass for development
        is_bypass = current_app.debug and otp_code == '123456'

        if (otp_obj and otp_obj.scade_il > datetime.datetime.utcnow()) or is_bypass:
            lead = Lead.query.get(session['lead_id'])
            lead.stato = 'verificato'
            db.session.commit()
            session['otp_verified'] = True
            flash('Email verificata con successo!', 'success')
            return redirect(url_for('main.insert_rif'))
        else:
            flash('Codice OTP non valido o scaduto.', 'danger')
            return redirect(url_for('main.verify_otp', email=email))
    return render_template('main/verify_otp.html', email=email, form=form)

@bp.route('/resend-otp/<email>')
def resend_otp(email):
    lead = Lead.query.filter_by(email=email).first()
    if not lead: return {'success': False, 'message': 'Utente non trovato.'}, 404
    try:
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        otp = OTP(email=email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))
        db.session.add(otp)
        db.session.commit()
        send_email(to=lead.email, subject='Il tuo nuovo codice di verifica ADA',
                   template_prefix='email/otp', lead=lead, otp_code=otp_code)
        return {'success': True, 'message': 'Un nuovo codice è stato inviato.'}
    except Exception as e:
        print(f"ERRORE: Impossibile reinviare l'OTP. {e}")
        return {'success': False, 'message': 'Errore del server.'}, 500

@bp.route('/insert_rif', methods=['GET', 'POST'])
@otp_required
def insert_rif():
    if request.method == 'POST':
        rif_input = request.form.get('rif')
        if not rif_input:
            flash('Il campo RIF è obbligatorio.', 'danger')
            return redirect(url_for('main.insert_rif'))
        rif_normalized = rif_input.replace('RIF:', '').strip().upper()
        prop = Property.query.filter_by(rif=rif_normalized).first()
        if prop:
            lead_id = session['lead_id']
            db_session = Session.query.filter_by(lead_id=lead_id, rif=prop.rif).first()
            if not db_session:
                db_session = Session(lead_id=lead_id, rif=prop.rif)
                db.session.add(db_session)
                db.session.commit()
            session['session_id'] = db_session.id
            return redirect(url_for('main.property_details', rif=prop.rif))
        else:
            flash('RIF non trovato. Per favore, riprova.', 'danger')
            return redirect(url_for('main.insert_rif'))
    return render_template('main/insert_rif.html')

@bp.route('/property/<rif>')
@otp_required
def property_details(rif):
    prop = Property.query.filter_by(rif=rif).first_or_404()
    return render_template('main/property_details.html', property=prop)

from flask_wtf.csrf import generate_csrf

@bp.route('/questionnaire', methods=['GET', 'POST'])
@otp_required
def questionnaire():
    if 'session_id' not in session:
        flash('Per favore, inserisci prima un RIF valido.', 'warning')
        return redirect(url_for('main.insert_rif'))

    if request.method == 'POST':
        session_id = session['session_id']

        # Clear any previous answers for this session's pre-qualification phase
        Answer.query.filter_by(session_id=session_id, fase='pre').delete()

        # Iterate through the new form data and save it
        for key, value in request.form.items():
            if key != 'csrf_token' and value:  # Only save non-empty answers
                # A simple way to make the question text more readable
                domanda_testo = key.replace('_', ' ').replace('char ', '').replace(' hidden', '').capitalize()
                answer = Answer(
                    session_id=session_id,
                    domanda_id=key,
                    domanda_testo=domanda_testo,
                    risposta=value,
                    fase='pre'
                )
                db.session.add(answer)

        lead = Lead.query.get(session['lead_id'])
        lead.stato = 'questionario completato'
        db.session.commit()
        return redirect(url_for('main.view_plan'))

    # For GET request, generate a CSRF token manually for the template
    csrf_token = generate_csrf()
    return render_template('main/questionnaire.html', form={'hidden_tag': lambda: f'<input type="hidden" name="csrf_token" value="{csrf_token}">'})

@bp.route('/plan')
@otp_required
def view_plan():
    if 'session_id' not in session: return redirect(url_for('main.insert_rif'))
    session_id = session['session_id']
    db_session_obj = Session.query.get_or_404(session_id)
    lead = db_session_obj.lead
    if lead.stato not in ['questionario completato', 'planimetria vista']: return redirect(url_for('main.questionnaire'))
    property_asset = PropertyAsset.query.join(Property).filter(Property.rif == db_session_obj.rif, PropertyAsset.tipo == 'planimetria').first()
    if not property_asset:
        flash('Planimetria non disponibile per questo immobile. Si procede con le domande finali.', 'info')
        return redirect(url_for('main.post_view_questionnaire'))
    if lead.stato != 'planimetria vista':
        event = Event(session_id=session_id, tipo='vista_planimetria', meta_json={'ip': request.remote_addr})
        db.session.add(event)
        lead.stato = 'planimetria vista'
        db.session.commit()
    now = datetime.datetime.utcnow()
    return render_template('main/view_plan.html', lead=lead, asset_path=property_asset.path_privato, now=now)

@bp.route('/post_view_questionnaire', methods=['GET', 'POST'])
@otp_required
def post_view_questionnaire():
    if 'session_id' not in session: return redirect(url_for('main.insert_rif'))
    if request.method == 'POST':
        session_id = session['session_id']
        # Clear previous post-answers for this session to avoid duplicates
        Answer.query.filter_by(session_id=session_id, fase='post').delete()
        for key, value in request.form.items():
             if key != 'csrf_token' and value:
                answer = Answer(session_id=session_id, domanda_id=key, domanda_testo=key.replace('_', ' ').title(), risposta=value, fase='post')
                db.session.add(answer)
        db.session.commit()
        return redirect(url_for('main.final_outcome'))

    # Manually generate CSRF token for the template
    csrf_token_value = generate_csrf()
    return render_template('main/post_view_questionnaire.html', csrf_token_value=csrf_token_value)

@bp.route('/final_outcome')
@otp_required
def final_outcome():
    if 'session_id' not in session: return redirect(url_for('main.insert_rif'))
    return render_template('main/final_outcome.html')

@bp.route('/interested', methods=['POST'])
@otp_required
def interested():
    if 'session_id' not in session: return redirect(url_for('main.insert_rif'))
    telefono = request.form.get('telefono')
    if not telefono:
        flash('Il numero di telefono è obbligatorio.', 'danger')
        return redirect(url_for('main.final_outcome'))
    lead = Lead.query.get(session['lead_id'])
    lead.telefono = telefono
    lead.stato = 'da chiamare subito'
    db.session.commit()
    message = "Grazie! Verrai presto chiamato per concordare un appuntamento."
    return render_template('main/thank_you.html', message=message)

@bp.route('/not_interested', methods=['POST'])
@otp_required
def not_interested():
    if 'session_id' not in session: return redirect(url_for('main.insert_rif'))
    session_id = session['session_id']
    reason = request.form.get('reason')
    reason_text = request.form.get('reason_text')
    answer = Answer(session_id=session_id, domanda_id='not_interested_reason', domanda_testo=reason, risposta=reason_text, fase='post')
    db.session.add(answer)
    lead = Lead.query.get(session['lead_id'])
    lead.stato = 'da richiamare'
    db.session.commit()
    current_session = Session.query.get(session_id)
    current_property = Property.query.filter_by(rif=current_session.rif).first()
    price_min = (current_property.prezzo_min or 0) * 0.85
    price_max = (current_property.prezzo_max or float('inf')) * 1.15
    mq_min = (current_property.mq or 0) * 0.90
    mq_max = (current_property.mq or float('inf')) * 1.10
    alternatives = Property.query.filter(Property.rif != current_property.rif, Property.zona == current_property.zona, Property.prezzo_min.between(price_min, price_max), Property.mq.between(mq_min, mq_max)).limit(3).all()
    if alternatives:
        return render_template('main/alternatives.html', alternatives=alternatives)
    else:
        return render_template('main/no_alternatives.html')

@bp.route('/collect_phone_and_redirect', methods=['GET', 'POST'])
@otp_required
def collect_phone_and_redirect():
    if request.method == 'POST':
        telefono = request.form.get('telefono')
        if telefono:
            lead = Lead.query.get(session['lead_id'])
            lead.telefono = telefono
            db.session.commit()
    message = "Grazie per il tuo tempo. Un nostro consulente potrebbe contattarti."
    return render_template('main/thank_you.html', message=message, redirect_url="https://www.artediabitare.it/")

@bp.route('/files/<path:filename>')
@otp_required
def serve_file(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(current_app.root_path, '..', 'uploads'), filename)
