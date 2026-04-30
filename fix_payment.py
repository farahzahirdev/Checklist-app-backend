#!/usr/bin/env python3

# Manually create payment record for the user
from app.db.session import SessionLocal
from app.models.payment import Payment, PaymentStatus
from sqlalchemy import select
from uuid import UUID
from datetime import datetime

user_id = UUID('9de13ec2-c6e3-4223-baa9-4e209e05ece5')
checklist_id = UUID('e062d96f-b39b-4551-9c1e-f8e9325a897b')

db = SessionLocal()
try:
    # Create payment record
    payment = Payment(
        user_id=user_id,
        checklist_id=checklist_id,
        status=PaymentStatus.succeeded,
        amount_cents=900,
        currency='usd',
        stripe_payment_intent_id='pi_manual_fix',
        created_at=datetime.utcnow()
    )
    
    db.add(payment)
    db.commit()
    
    print(f'Created payment record: {payment.id}')
    print(f'User: {payment.user_id}')
    print(f'Status: {payment.status}')
    print(f'Amount: ${payment.amount_cents / 100}')
    
except Exception as e:
    print(f'Error creating payment: {e}')
    db.rollback()
finally:
    db.close()
