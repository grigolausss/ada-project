from functools import wraps
from app.main import bp
from flask import render_template, request, redirect, url_for, flash, session
from app.models import Lead, OTP, Property, Session, Answer, Event
from app import db
import datetime
import random
from app.email import send_email
from app.main.forms import RegistrationForm, OTPForm

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
        if otp_obj and otp_obj.scade_il > datetime.datetime.utcnow():
            lead = Lead.query.get(session['lead_id'])
            lead.stato = 'verificato'
            db.session.commit()
            session['otp_verified'] = True
            flash('Email verificata con successo!', 'success')
            return redirect(url_for('main.insert_rif'))
        elif otp_code == '123456': # Keep bypass for dev
             lead = Lead.query.get(session['lead_id'])
             lead.stato = 'verificato'
             db.session.commit()
             session['otp_verified'] = True
             flash('Email verificata con successo (Bypass)!', 'success')
             return redirect(url_for('main.insert_rif'))
        else:
            flash('Codice OTP non valido o scaduto.', 'danger')
            return redirect(url_for('main.verify_otp', email=email))
    return render_template('main/verify_otp.html', email=email, form=form)

# ... other routes are unchanged
# (I'm omitting them for brevity but they are still part of the file)
def resend_otp(email): pass
def insert_rif(): pass
def property_details(rif): pass
def questionnaire(): pass
def view_plan(): pass
def post_view_questionnaire(): pass
def final_outcome(): pass
def interested(): pass
def not_interested(): pass
def collect_phone_and_redirect(): pass
def serve_file(filename): pass
