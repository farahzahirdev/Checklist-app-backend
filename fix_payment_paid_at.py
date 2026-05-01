#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.db.session import get_db
from app.models.payment import Payment
from sqlalchemy import select

def fix_payment_paid_at(payment_id="22bfbb24-bfaa-47d2-b8aa-5df00df50ea3"):
    """Fix the paid_at timestamp for the payment"""
    try:
        db = next(get_db())
        
        payment = db.execute(select(Payment).where(Payment.id == payment_id)).scalar_one()
        
        if payment.paid_at is None:
            payment.paid_at = datetime.now(timezone.utc)
            db.commit()
            print(f"✅ Fixed paid_at for payment {payment_id}: {payment.paid_at}")
        else:
            print(f"ℹ️  paid_at already set: {payment.paid_at}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing payment: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    payment_id = sys.argv[1] if len(sys.argv) > 1 else "22bfbb24-bfaa-47d2-b8aa-5df00df50ea3"
    fix_payment_paid_at(payment_id)
