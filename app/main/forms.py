from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email

class RegistrationForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    cognome = StringField('Cognome', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    privacy_consent = BooleanField('Acconsento al trattamento dei dati personali', validators=[DataRequired()])
    submit = SubmitField('Ricevi codice')

class OTPForm(FlaskForm):
    otp = StringField('Codice OTP', validators=[DataRequired()])
    submit = SubmitField('Verifica')
