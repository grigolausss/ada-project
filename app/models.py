from app import db
from datetime import datetime

class Property(db.Model):
    __tablename__ = 'properties'
    id = db.Column(db.Integer, primary_key=True)
    rif = db.Column(db.String(50), unique=True, nullable=False)
    titolo = db.Column(db.String(200), nullable=False)
    tipologia = db.Column(db.String(100))
    zona = db.Column(db.String(100))
    indirizzo_parziale = db.Column(db.String(200))
    mq = db.Column(db.Integer)
    prezzo_min = db.Column(db.Float)
    prezzo_max = db.Column(db.Float)
    stato = db.Column(db.String(50))
    caratteristiche_json = db.Column(db.JSON)
    attivo = db.Column(db.Boolean, default=True)
    assets = db.relationship('PropertyAsset', backref='property', lazy=True)

class PropertyAsset(db.Model):
    __tablename__ = 'property_assets'
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # es. planimetria
    path_privato = db.Column(db.String(255), nullable=False)
    checksum = db.Column(db.String(255))
    creato_il = db.Column(db.DateTime, default=datetime.utcnow)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    consensi_json = db.Column(db.JSON)
    stato = db.Column(db.String(50), default='nuovo')
    creato_il = db.Column(db.DateTime, default=datetime.utcnow)
    sessions = db.relationship('Session', backref='lead', lazy=True)

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    rif = db.Column(db.String(50))
    iniziata_il = db.Column(db.DateTime, default=datetime.utcnow)
    completata_il = db.Column(db.DateTime)
    answers = db.relationship('Answer', backref='session', lazy=True)
    events = db.relationship('Event', backref='session', lazy=True)

class OTP(db.Model):
    __tablename__ = 'otps'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    hash_codice = db.Column(db.String(255), nullable=False)
    scade_il = db.Column(db.DateTime, nullable=False)
    tentativi = db.Column(db.Integer, default=0)

class Answer(db.Model):
    __tablename__ = 'answers'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    domanda_id = db.Column(db.String(100))
    domanda_testo = db.Column(db.String(500))
    risposta = db.Column(db.Text)
    peso = db.Column(db.Integer)
    fase = db.Column(db.String(50))  # pre o post planimetria

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    tipo = db.Column(db.String(100), nullable=False)
    meta_json = db.Column(db.JSON)
    ts = db.Column(db.DateTime, default=datetime.utcnow)
