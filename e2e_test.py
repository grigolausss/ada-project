import unittest
import time
import os
from playwright.sync_api import sync_playwright, expect
from flask_migrate import upgrade
from app import create_app, db
from app.models import OTP, Lead, Property
import random
import string

# --- Configuration ---
BASE_URL = "http://127.0.0.1:5000"
TEST_EMAIL = f"test_user_{''.join(random.choices(string.ascii_lowercase, k=8))}@example.com"
TEST_NAME = "Test"
TEST_RIF = "R001" # Assuming a property with this RIF exists

class EndToEndTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start the Flask app in a separate process? No, for simplicity, we'll run it manually.
        # This test assumes the Flask server is running.
        cls.app = create_app('development')
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

        # Create all database tables
        with cls.app.app_context():
            db.create_all() # Or use upgrade() if you have migrations
            # upgrade() is better if you have existing migrations
            # upgrade()

        # Ensure a test property exists
        with cls.app.app_context():
            if not Property.query.filter_by(rif=TEST_RIF).first():
                prop = Property(
                    rif=TEST_RIF,
                    titolo='Villa Prova',
                    zona='Testlandia',
                    prezzo_min=200000,
                    prezzo_max=250000,
                    mq=120
                )
                db.session.add(prop)
                db.session.commit()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def test_full_client_journey(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Start with a clean slate
            context.clear_cookies()
            page.goto(f"{BASE_URL}/reset_session_for_test")
            expect(page.locator("body")).to_have_text("Session cleared")


            # 1. Registration
            print("Navigating to registration page...")
            page.goto(f"{BASE_URL}/")
            print(f"Current URL: {page.url}")
            print(f"Current Title: {page.title()}")
            time.sleep(5) # Pause to allow manual inspection or log checking
            expect(page).to_have_title("Registrazione Lead")
            page.fill("input[name='nome']", TEST_NAME)
            page.fill("input[name='cognome']", "User") # Added cognome
            page.fill("input[name='email']", TEST_EMAIL)
            page.check("input[name='privacy_consent']")
            page.click("input[type='submit']")
            print("Registration form submitted.")

            # 2. OTP Verification
            print("On OTP verification page...")
            expect(page).to_have_url(f"{BASE_URL}/verify_otp/{TEST_EMAIL}")

            # Retrieve OTP from database
            time.sleep(2) # Give the app a moment to commit the OTP
            with self.app.app_context():
                lead = Lead.query.filter_by(email=TEST_EMAIL).first()
                self.assertIsNotNone(lead, "Lead should have been created.")
                otp_obj = OTP.query.filter_by(lead_id=lead.id).order_by(OTP.created_at.desc()).first()
                self.assertIsNotNone(otp_obj, "OTP object should exist.")
                otp_code = otp_obj.code
                print(f"Retrieved OTP from DB: {otp_code}")

            page.fill("input[name='otp']", otp_code)
            page.click("input[type='submit']")
            print("OTP submitted.")

            # 3. Insert RIF
            print("On Insert RIF page...")
            expect(page).to_have_url(f"{BASE_URL}/insert_rif")
            page.fill("input[name='rif']", TEST_RIF)
            page.click("input[type='submit']")
            print("RIF submitted.")

            # 4. Property Details & Start Questionnaire
            print("On Property Details page...")
            expect(page).to_have_url(f"{BASE_URL}/property/{TEST_RIF}")
            expect(page.locator("h3")).to_have_text("Villa Prova") # Corrected selector
            page.click("a:has-text('Inizia il questionario')")
            print("Clicked to start questionnaire.")

            # 5. Pre-qualification Questionnaire
            print("On Questionnaire page...")
            expect(page).to_have_url(f"{BASE_URL}/questionnaire")
            page.check("input[name='budget'][value='150.000€ - 250.000€']")
            page.check("input[name='purchase_timeline'][value='Entro 6 mesi']")
            page.check("input[name='financing'][value='Sì']")
            page.check("input[name='first_home'][value='Sì']")
            page.check("input[name='visiting'][value='Sì']")
            page.click("button[type='submit']")
            print("Questionnaire submitted.")

            # 6. View Plan
            print("On View Plan page...")
            expect(page).to_have_url(f"{BASE_URL}/view_plan")
            # We can't easily test the canvas, but we can check the page loaded
            expect(page.locator("h3")).to_have_text("Planimetria")
            page.click("a:has-text('Prosegui')") # Corrected link text
            print("Clicked to continue after viewing plan.")

            # 7. Post-view Questionnaire
            print("On Post-view Questionnaire page...")
            expect(page).to_have_url(f"{BASE_URL}/post_view_questionnaire")
            page.check("input[name='plan_liked'][value='Sì, molto']")
            page.check("input[name='next_step'][value='Vorrei prenotare una visita']")
            page.click("button[type='submit']")
            print("Post-view questionnaire submitted.")

            # 8. Final Choice
            print("On Final Choice page...")
            expect(page).to_have_url(f"{BASE_URL}/final_choice")
            expect(page.locator("h2")).to_have_text("Sei a un passo dalla tua nuova casa")
            print("E2E Test Passed!")

            browser.close()

if __name__ == "__main__":
    # This allows running the test directly
    # Note: Ensure the Flask server is running in a separate terminal
    # `export FLASK_APP=run.py; flask run`
    unittest.main()
