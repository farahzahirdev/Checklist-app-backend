from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    user_id: UUID
    stripe_payment_intent_id: str
    amount_cents: int
    currency: str = "USD"


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    stripe_payment_intent_id: str
    amount_cents: int
    currency: str
    status: PaymentStatus
    paid_at: datetime | None
    created_at: datetime
