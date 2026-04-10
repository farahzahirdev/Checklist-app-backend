from datetime import datetime

from pydantic import BaseModel


class PaymentState(BaseModel):
    stripe_payment_intent_id: str | None = None
    paid_at: datetime | None = None
    access_expires_at: datetime | None = None