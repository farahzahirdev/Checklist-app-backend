#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.db.session import get_db
from app.models.payment import Payment
from app.models.access_window import AccessWindow
from app.models.checklist import Checklist, ChecklistTranslation
from app.models.reference import Language
from sqlalchemy import select

def check_payment_in_production(payment_id="22bfbb24-bfaa-47d2-b8aa-5df00df50ea3"):
    """Check if payment exists in production database"""
    try:
        db = next(get_db())
        
        # Check if payment exists
        payment = db.execute(select(Payment).where(Payment.id == payment_id)).scalar_one_or_none()
        
        if not payment:
            print(f"❌ Payment {payment_id} NOT FOUND in database")
            
            # Check recent payments for this user
            recent_payments = db.execute(select(Payment).order_by(Payment.created_at.desc()).limit(5)).scalars().all()
            print(f"\n📊 Recent payments in database:")
            for p in recent_payments:
                print(f"  ID: {p.id}")
                print(f"  Status: {p.status}")
                print(f"  Checklist: {p.checklist_id}")
                print(f"  Amount: {p.amount_cents}")
                print(f"  Created: {p.created_at}")
                print(f"  Stripe Intent: {p.stripe_payment_intent_id}")
                print("---")
            return False
        
        print(f"✅ Payment {payment_id} FOUND:")
        print(f"  Status: {payment.status}")
        print(f"  Checklist ID: {payment.checklist_id}")
        print(f"  Amount: {payment.amount_cents}")
        print(f"  Stripe Intent: {payment.stripe_payment_intent_id}")
        print(f"  Created: {payment.created_at}")
        print(f"  Paid At: {payment.paid_at}")
        
        # Check access window
        access_window = db.execute(select(AccessWindow).where(AccessWindow.payment_id == payment.id)).scalar_one_or_none()
        if access_window:
            print(f"✅ Access Window FOUND:")
            print(f"  ID: {access_window.id}")
            print(f"  Expires: {access_window.expires_at}")
        else:
            print(f"❌ No Access Window found for payment")
        
        # Check checklist details
        if payment.checklist_id:
            checklist = db.get(Checklist, payment.checklist_id)
            if checklist:
                print(f"✅ Checklist FOUND:")
                translations = checklist.translations or []
                if translations:
                    translation = translations[0]  # Get first translation
                    print(f"  Title: {translation.title}")
                    print(f"  Version: {checklist.version}")
                else:
                    print(f"  No translations found")
            else:
                print(f"❌ Checklist {payment.checklist_id} NOT FOUND")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking production database: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    payment_id = sys.argv[1] if len(sys.argv) > 1 else "22bfbb24-bfaa-47d2-b8aa-5df00df50ea3"
    check_payment_in_production(payment_id)
