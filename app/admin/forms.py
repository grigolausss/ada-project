from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo

from wtforms import ValidationError
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Ricordami')
    submit = SubmitField('Accedi')

class UserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password')
    password2 = PasswordField('Ripeti Password', validators=[EqualTo('password')])
    submit = SubmitField('Salva Utente')

    def validate_email(self, email):
        # This validation should only apply when creating a new user, not editing
        # We will handle this logic in the route instead.
        pass

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Richiedi Reset Password')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nuova Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Conferma Nuova Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Resetta Password')
