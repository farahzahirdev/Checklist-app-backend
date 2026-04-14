from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus


class PaymentState(BaseModel):
    payment_id: UUID | None = None
    stripe_payment_intent_id: str | None = None
    payment_status: PaymentStatus | None = None
    paid_at: datetime | None = None
    access_window_id: UUID | None = None
    access_expires_at: datetime | None = None


class PaymentSetupRequest(BaseModel):
    user_id: UUID
    amount_cents: int | None = Field(default=None, gt=0)
    currency: str | None = None


class PaymentSetupResponse(BaseModel):
    payment_id: UUID
    stripe_payment_intent_id: str
    client_secret: str
    amount_cents: int
    currency: str


class StripeWebhookAck(BaseModel):
    received: bool = True
    event_type: str
    state: PaymentState | None = None