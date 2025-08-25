from app.main import bp
from flask import render_template, request, redirect, url_for, flash, session, send_from_directory
from app.models import Lead, OTP, Property, Session, Answer, Event, PropertyAsset
from app import db
import random
import datetime
import os
from flask import current_app

@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
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

        # Generate and send OTP
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        otp = OTP(email=email, hash_codice=otp_code, scade_il=datetime.datetime.utcnow() + datetime.timedelta(minutes=10))
        db.session.add(otp)
        db.session.commit()

        flash(f'Il tuo codice OTP è: {otp_code}', 'info')

        return redirect(url_for('main.verify_otp', email=email))

    return render_template('main/index.html')

@bp.route('/verify_otp/<email>', methods=['GET', 'POST'])
def verify_otp(email):
    if request.method == 'POST':
        otp_code = request.form.get('otp')
        otp = OTP.query.filter_by(email=email, hash_codice=otp_code).first()

        if otp and otp.scade_il > datetime.datetime.utcnow():
            lead = Lead.query.filter_by(email=email).first()
            lead.stato = 'verificato'
            db.session.commit()
            flash('Email verificata con successo!', 'success')
            return redirect(url_for('main.insert_rif'))
        else:
            flash('Codice OTP non valido o scaduto.', 'danger')
            return redirect(url_for('main.verify_otp', email=email))

    return render_template('main/verify_otp.html', email=email)

@bp.route('/insert_rif', methods=['GET', 'POST'])
def insert_rif():
    if 'lead_id' not in session:
        flash('Sessione non valida, per favore ricomincia.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        rif_input = request.form.get('rif')
        if not rif_input:
            flash('Il campo RIF è obbligatorio.', 'danger')
            return redirect(url_for('main.insert_rif'))

        rif_normalized = rif_input.replace('RIF:', '').strip().upper()

        property = Property.query.filter_by(rif=rif_normalized).first()

        if property:
            lead_id = session['lead_id']
            db_session = Session.query.filter_by(lead_id=lead_id, rif=property.rif).first()
            if not db_session:
                db_session = Session(lead_id=lead_id, rif=property.rif)
                db.session.add(db_session)
                db.session.commit()

            session['session_id'] = db_session.id
            session['rif'] = property.rif
            return redirect(url_for('main.property_details', rif=property.rif))
        else:
            flash('RIF non trovato. Per favore, riprova.', 'danger')
            return redirect(url_for('main.insert_rif'))

    return render_template('main/insert_rif.html')

@bp.route('/property/<rif>')
def property_details(rif):
    if 'session_id' not in session:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))

    property = Property.query.filter_by(rif=rif).first_or_404()
    return render_template('main/property_details.html', property=property)

@bp.route('/questionnaire', methods=['GET', 'POST'])
def questionnaire():
    if 'session_id' not in session:
        flash('Sessione non valida, per favore ricomincia.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        session_id = session['session_id']

        questions = {
            'mutuo': 'Ha già un mutuo?',
            'mutuo_residuo': 'Se sì: con quanto residuo?',
            'liquidita': 'Ha disponibilità liquida per anticipo/spese?',
            'finanziamento': 'Necessità di finanziamento?',
            'tempistiche': 'Tempistiche di acquisto?',
            'situazione': 'Situazione attuale?',
            'esigenze': 'Esigenze non negoziabili?',
            'ricontatto': 'Consenso ad essere ricontattato per fissare appuntamento'
        }

        for q_id, q_text in questions.items():
            answer_text = request.form.get(q_id)
            if answer_text:
                answer = Answer.query.filter_by(session_id=session_id, domanda_id=q_id).first()
                if answer:
                    answer.risposta = answer_text
                else:
                    answer = Answer(
                        session_id=session_id,
                        domanda_id=q_id,
                        domanda_testo=q_text,
                        risposta=answer_text,
                        fase='pre'
                    )
                    db.session.add(answer)

        lead = Lead.query.join(Session).filter(Session.id == session_id).first()
        lead.stato = 'questionario completato'

        db.session.commit()

        flash('Questionario completato con successo! Ora puoi vedere la planimetria.', 'success')
        return redirect(url_for('main.view_plan'))

    return render_template('main/questionnaire.html')

@bp.route('/plan')
def view_plan():
    if 'session_id' not in session:
        flash('Sessione non valida.', 'danger')
        return redirect(url_for('main.index'))

    session_id = session['session_id']
    db_session_obj = Session.query.get_or_404(session_id)
    lead = db_session_obj.lead

    if lead.stato != 'questionario completato':
        flash('Devi prima completare il questionario.', 'warning')
        return redirect(url_for('main.questionnaire'))

    property_asset = PropertyAsset.query.join(Property).filter(Property.rif == db_session_obj.rif, PropertyAsset.tipo == 'planimetria').first()

    if not property_asset:
        flash('Planimetria non disponibile per questo immobile.', 'danger')
        return redirect(url_for('main.property_details', rif=db_session_obj.rif))

    # Log event
    event = Event(session_id=session_id, tipo='vista_planimetria', meta_json={'ip': request.remote_addr})
    db.session.add(event)
    lead.stato = 'planimetria vista'
    db.session.commit()

    now = datetime.datetime.utcnow()
    return render_template('main/view_plan.html', lead=lead, asset_path=property_asset.path_privato, now=now)

@bp.route('/post_view_questionnaire', methods=['GET', 'POST'])
def post_view_questionnaire():
    if 'session_id' not in session:
        flash('Sessione non valida, per favore ricomincia.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        session_id = session['session_id']

        questions = {
            'adeguata': 'La metratura è adeguata?',
            'taglio_spazi': 'Il taglio degli spazi è adatto alle sue esigenze?',
            'posto_auto': 'Posto auto/box necessari?',
            'range_prezzo': 'Il range di prezzo è sostenibile per lei?',
            'note_libere': 'Note libere'
        }

        for q_id, q_text in questions.items():
            answer_text = request.form.get(q_id)
            if answer_text:
                answer = Answer.query.filter_by(session_id=session_id, domanda_id=q_id, fase='post').first()
                if answer:
                    answer.risposta = answer_text
                else:
                    answer = Answer(
                        session_id=session_id,
                        domanda_id=q_id,
                        domanda_testo=q_text,
                        risposta=answer_text,
                        fase='post'
                    )
                    db.session.add(answer)

        db.session.commit()

        return redirect(url_for('main.final_outcome'))

    return render_template('main/post_view_questionnaire.html')

@bp.route('/final_outcome')
def final_outcome():
    if 'session_id' not in session:
        flash('Sessione non valida.', 'warning')
        return redirect(url_for('main.index'))
    return render_template('main/final_outcome.html')

@bp.route('/interested', methods=['POST'])
def interested():
    if 'session_id' not in session:
        flash('Sessione non valida.', 'warning')
        return redirect(url_for('main.index'))

    session_id = session['session_id']
    telefono = request.form.get('telefono')

    if not telefono:
        flash('Il numero di telefono è obbligatorio.', 'danger')
        return redirect(url_for('main.final_outcome'))

    lead = Lead.query.join(Session).filter(Session.id == session_id).first()
    lead.telefono = telefono
    lead.stato = 'da chiamare subito'
    db.session.commit()

    return render_template('main/thank_you.html', message="Grazie! Verrai presto chiamato per concordare un appuntamento.")

@bp.route('/not_interested', methods=['POST'])
def not_interested():
    if 'session_id' not in session:
        flash('Sessione non valida.', 'warning')
        return redirect(url_for('main.index'))

    session_id = session['session_id']
    reason = request.form.get('reason')
    reason_text = request.form.get('reason_text')

    answer = Answer(session_id=session_id, domanda_id='not_interested_reason', domanda_testo=reason, risposta=reason_text, fase='post')
    db.session.add(answer)

    lead = Lead.query.join(Session).filter(Session.id == session_id).first()
    lead.stato = 'non interessato'
    db.session.commit()

    current_session = Session.query.get(session_id)
    current_property = Property.query.filter_by(rif=current_session.rif).first()

    price_min = (current_property.prezzo_min or 0) * 0.8
    price_max = (current_property.prezzo_max or float('inf')) * 1.2

    alternatives = Property.query.filter(
        Property.rif != current_property.rif,
        Property.zona == current_property.zona,
        Property.prezzo_min.between(price_min, price_max)
    ).limit(3).all()

    if alternatives:
        return render_template('main/alternatives.html', alternatives=alternatives)
    else:
        return render_template('main/no_alternatives.html')

@bp.route('/files/<path:filename>')
def serve_file(filename):
    if 'session_id' not in session:
        return "Accesso negato", 403

    session_id = session['session_id']
    lead = Lead.query.join(Session).filter(Session.id == session_id).first()
    if lead.stato not in ['questionario completato', 'planimetria vista']:
         return "Accesso negato", 403

    return send_from_directory(os.path.join(current_app.root_path, '..'), filename, as_attachment=False)
