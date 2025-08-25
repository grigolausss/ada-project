from functools import wraps
from app.main import bp
from flask import render_template, request, redirect, url_for, flash, session, send_from_directory, current_app
from app.models import Lead, OTP, Property, Session, Answer, Event, PropertyAsset
from app import db
import datetime
import os

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
    if request.method == 'POST':
        session.clear()
        nome = request.form.get('nome')
        cognome = request.form.get('cognome')
        email = request.form.get('email')
        privacy_consent = request.form.get('privacy_consent')

        if not all([nome, cognome, email, privacy_consent]):
            flash('Tutti i campi sono obbligatori.', 'danger')
            return redirect(url_for('main.index'))

        lead = Lead.query.filter_by(email=email).first()
        if not lead:
            lead = Lead(nome=nome, cognome=cognome, email=email, consensi_json={'privacy': True})
            db.session.add(lead)
            db.session.commit()

        session['lead_id'] = lead.id

        # Generate a real OTP for testing purposes, even with the bypass available
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        otp = OTP(email=email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))
        db.session.add(otp)
        db.session.commit()

        print(f"-----> OTP generato per {email}: {otp_code} <-----")

        flash(f'Per testare, usa il codice di bypass 123456. (Il codice reale generato è visibile nel terminale)', 'info')
        return redirect(url_for('main.verify_otp', email=email))

    return render_template('main/index.html')

@bp.route('/verify_otp/<email>', methods=['GET', 'POST'])
def verify_otp(email):
    if 'lead_id' not in session:
        flash('Sessione non valida, per favore ricomincia.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        otp_code = request.form.get('otp')
        if otp_code == '123456':
            lead = Lead.query.get(session['lead_id'])
            lead.stato = 'verificato'
            db.session.commit()
            session['otp_verified'] = True
            flash('Email verificata con successo (Bypass)!', 'success')
            return redirect(url_for('main.insert_rif'))
        else:
            flash('Codice OTP non valido.', 'danger')
            return redirect(url_for('main.verify_otp', email=email))

    return render_template('main/verify_otp.html', email=email)

@bp.route('/resend-otp/<email>')
def resend_otp(email):
    # Generate a new OTP
    otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

    # In a real app, you'd likely invalidate the old OTP. For now, we just make a new one.
    otp = OTP(email=email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))
    db.session.add(otp)
    db.session.commit()

    print(f"-----> NUOVO OTP generato per {email}: {otp_code} <-----")

    return {'success': True, 'message': 'Un nuovo codice è stato generato.'}

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

@bp.route('/questionnaire', methods=['GET', 'POST'])
@otp_required
def questionnaire():
    if 'session_id' not in session:
        flash('Per favore, inserisci prima un RIF valido.', 'warning')
        return redirect(url_for('main.insert_rif'))

    if request.method == 'POST':
        session_id = session['session_id']
        questions = {
            'mutuo': 'Ha già un mutuo?', 'mutuo_residuo': 'Se sì: con quanto residuo?',
            'liquidita': 'Ha disponibilità liquida per anticipo/spese?',
            'finanziamento': 'Necessità di finanziamento?', 'tempistiche': 'Tempistiche di acquisto?',
            'situazione': 'Situazione attuale?', 'esigenze': 'Esigenze non negoziabili?',
            'ricontatto': 'Consenso ad essere ricontattato per fissare appuntamento'
        }
        for q_id, q_text in questions.items():
            answer_text = request.form.get(q_id)
            if answer_text:
                answer = Answer(session_id=session_id, domanda_id=q_id, domanda_testo=q_text, risposta=answer_text, fase='pre')
                db.session.add(answer)

        lead = Lead.query.get(session['lead_id'])
        lead.stato = 'questionario completato'
        db.session.commit()
        flash('Questionario completato! Ora puoi vedere la planimetria.', 'success')
        return redirect(url_for('main.view_plan'))

    return render_template('main/questionnaire.html')

@bp.route('/plan')
@otp_required
def view_plan():
    if 'session_id' not in session:
        return redirect(url_for('main.insert_rif'))

    session_id = session['session_id']
    db_session_obj = Session.query.get_or_404(session_id)
    lead = db_session_obj.lead

    if lead.stato not in ['questionario completato', 'planimetria vista']:
        return redirect(url_for('main.questionnaire'))

    property_asset = PropertyAsset.query.join(Property).filter(Property.rif == db_session_obj.rif, PropertyAsset.tipo == 'planimetria').first()
    if not property_asset:
        flash('Planimetria non disponibile.', 'danger')
        return redirect(url_for('main.property_details', rif=db_session_obj.rif))

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
        questions = {
            'adeguata': 'La metratura è adeguata?', 'taglio_spazi': 'Il taglio degli spazi è adatto?',
            'posto_auto': 'Posto auto/box necessari?', 'range_prezzo': 'Il range di prezzo è sostenibile?',
            'note_libere': 'Note libere'
        }
        for q_id, q_text in questions.items():
            answer_text = request.form.get(q_id)
            if answer_text:
                answer = Answer(session_id=session_id, domanda_id=q_id, domanda_testo=q_text, risposta=answer_text, fase='post')
                db.session.add(answer)
        db.session.commit()
        return redirect(url_for('main.final_outcome'))
    return render_template('main/post_view_questionnaire.html')

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
    lead.stato = 'da richiamare' # Changed from 'non interessato'
    db.session.commit()

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

    message = "Grazie per il tuo tempo. Un nostro consulente potrebbe contattarti per aiutarti nella ricerca."
    return render_template('main/thank_you.html', message=message, redirect_url="https://www.artediabitare.it/")

@bp.route('/files/<path:filename>')
@otp_required
def serve_file(filename):
    return send_from_directory(os.path.join(current_app.root_path, '..', 'uploads'), filename)
