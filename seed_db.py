import os
from app import create_app, db
from app.models import Property, PropertyAsset, Lead, Session, Answer, Event, OTP

# Create an application context
app = create_app()
app.app_context().push()

def clear_data():
    """Deletes all data from the tables."""
    print("Clearing all existing data...")
    # Delete in order to respect foreign key constraints
    Event.query.delete()
    Answer.query.delete()
    Session.query.delete()
    PropertyAsset.query.delete()
    Property.query.delete()
    Lead.query.delete()
    OTP.query.delete()
    db.session.commit()
    print("Data cleared.")

def seed_data():
    """Seeds the database with test data."""
    print("Seeding database with test data...")

    # --- Create Properties ---
    p1 = Property(
        rif='R806',
        titolo='Appartamento in centro',
        tipologia='Appartamento',
        zona='Centro',
        mq=120,
        prezzo_min=300000,
        prezzo_max=350000,
        stato='Ristrutturato',
        caratteristiche_json={'camere': 3, 'bagni': 2, 'piano': 'secondo'}
    )

    p2 = Property(
        rif='R530-D',
        titolo='Villa con giardino',
        tipologia='Villa',
        zona='Centro',
        mq=200,
        prezzo_min=450000,
        prezzo_max=500000,
        stato='Nuova costruzione',
        caratteristiche_json={'camere': 4, 'bagni': 3, 'giardino': 'sì'}
    )

    p3 = Property(
        rif='G210',
        titolo='Attico panoramico',
        tipologia='Attico',
        zona='Periferia',
        mq=100,
        prezzo_min=250000,
        prezzo_max=280000,
        stato='Ottimo stato',
        caratteristiche_json={'camere': 2, 'bagni': 2, 'terrazzo': 'sì'}
    )

    db.session.add_all([p1, p2, p3])
    db.session.commit()
    print(f"Added 3 properties: {p1.rif}, {p2.rif}, {p3.rif}")

    # --- Create Property Asset (Floor Plan) ---
    # Ensure the placeholder file and directory exist
    uploads_dir = os.path.join(app.root_path, '..', 'uploads', 'plans')
    os.makedirs(uploads_dir, exist_ok=True)
    plan_path = os.path.join(uploads_dir, 'plan_r806.png')
    if not os.path.exists(plan_path):
        with open(plan_path, 'w') as f:
            f.write("This is a placeholder for the floor plan image.")
        print(f"Created placeholder floor plan at {plan_path}")

    # Link asset to property
    prop_to_link = Property.query.filter_by(rif='R806').first()
    asset = PropertyAsset(
        property_id=prop_to_link.id,
        tipo='planimetria',
        path_privato='uploads/plans/plan_r806.png' # Path relative to project root
    )
    db.session.add(asset)
    db.session.commit()
    print(f"Linked floor plan to property {prop_to_link.rif}")

    print("\nDatabase seeding complete!")
    print("You can now run the application with 'python run.py'")


if __name__ == '__main__':
    clear_data()
    seed_data()
