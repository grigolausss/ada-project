import click
from flask.cli import with_appcontext
from . import db
from .models import Property, PropertyAsset, User, Lead, Session, Answer, Event, OTP

@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Clears existing data and seeds the database with a default admin user and test properties."""

    # --- Clear Data ---
    click.echo("Clearing all existing data...")
    # The order of deletion matters due to foreign key constraints
    Event.query.delete()
    Answer.query.delete()
    Session.query.delete()
    PropertyAsset.query.delete()
    Property.query.delete()
    OTP.query.delete()
    Lead.query.delete()
    User.query.delete()
    db.session.commit()
    click.echo("Data cleared.")

    # --- Seed Data ---
    click.echo("Seeding database with test data...")
    # Create Admin User with the user's requested email
    if not User.query.filter_by(email='grigolocri004@gmail.com').first():
        admin_user = User(email='grigolocri004@gmail.com')
        admin_user.set_password('1234567890ok')
        db.session.add(admin_user)
        click.echo(f"Created admin user: {admin_user.email}")

    # Create Properties
    p1 = Property(rif='R806', titolo='Appartamento in centro', tipologia='Appartamento', zona='Centro', mq=120, prezzo_min=300000, prezzo_max=350000, stato='Ristrutturato')
    p2 = Property(rif='R530-D', titolo='Villa con giardino', tipologia='Villa', zona='Centro', mq=200, prezzo_min=450000, prezzo_max=500000, stato='Nuova costruzione')
    p3 = Property(rif='G210', titolo='Attico panoramico', tipologia='Attico', zona='Periferia', mq=100, prezzo_min=250000, prezzo_max=280000, stato='Ottimo stato')
    db.session.add_all([p1, p2, p3])
    db.session.commit() # Commit here to get IDs
    click.echo(f"Added 3 properties: {p1.rif}, {p2.rif}, {p3.rif}")

    # Create Property Asset
    prop_to_link = Property.query.filter_by(rif='R806').first()
    if prop_to_link and not PropertyAsset.query.filter_by(property_id=prop_to_link.id).first():
        asset = PropertyAsset(property_id=prop_to_link.id, tipo='planimetria', path_privato='uploads/plans/plan_r806.png')
        db.session.add(asset)
        click.echo(f"Linked floor plan to property {prop_to_link.rif}")

    db.session.commit()
    click.echo("Database seeding complete!")
