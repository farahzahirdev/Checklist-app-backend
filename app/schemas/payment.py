from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus


class PaymentState(BaseModel):
    payment_id: UUID | None = Field(default=None, description="Internal payment record ID.")
    stripe_payment_intent_id: str | None = Field(default=None, description="Stripe PaymentIntent ID.")
    payment_status: PaymentStatus | None = Field(default=None, description="Current payment status.")
    paid_at: datetime | None = Field(default=None, description="UTC timestamp when payment succeeded.")
    access_window_id: UUID | None = Field(default=None, description="Created access window ID after successful payment.")
    access_expires_at: datetime | None = Field(default=None, description="UTC expiry time of checklist access window.")


class PaymentSetupRequest(BaseModel):
    amount_cents: int | None = Field(default=None, gt=0, description="Optional amount in minor units; falls back to configured default.")
    currency: str | None = Field(default=None, description="Optional ISO-4217 currency code; falls back to configured default.")


class PaymentSetupResponse(BaseModel):
    payment_id: UUID = Field(description="Internal payment record ID.")
    stripe_payment_intent_id: str = Field(description="Stripe PaymentIntent ID used in frontend confirmation flow.")
    client_secret: str = Field(description="Stripe client_secret for frontend Stripe SDK confirmation.")
    amount_cents: int = Field(description="Amount in minor units.")
    currency: str = Field(description="Uppercase currency code.")


class AdminPaymentStatusUpdateRequest(BaseModel):
    payment_status: PaymentStatus = Field(description="Target payment status: pending, succeeded, or failed.")
    amount_cents: int | None = Field(default=None, gt=0, description="Optional amount for synthetic dev payment records.")
    currency: str | None = Field(default=None, description="Optional currency for synthetic dev payment records.")


class StripeWebhookAck(BaseModel):
    received: bool = Field(default=True, description="Webhook payload accepted by API.")
    event_type: str = Field(description="Stripe event type received.")
    state: PaymentState | None = Field(
        default=None,
        description="Updated payment/access state when the event was relevant and mapped to a payment.",
    )