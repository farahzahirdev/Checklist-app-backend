from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.payment import PaymentSetupRequest, PaymentSetupResponse, StripeWebhookAck
from app.services.payments import construct_webhook_event, create_payment_intent_for_user, handle_webhook_event

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/stripe/setup-intent",
    response_model=PaymentSetupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe Setup Intent",
    description=(
        "Creates a payment record and Stripe intent for the selected user and amount. "
        "Use client_secret from the response on the frontend Stripe SDK flow."
    ),
)
def setup_payment_intent(request: PaymentSetupRequest, db: Session = Depends(get_db)) -> PaymentSetupResponse:
    payment, client_secret = create_payment_intent_for_user(
        db,
        user_id=request.user_id,
        amount_cents=request.amount_cents,
        currency=request.currency,
    )
    return PaymentSetupResponse(
        payment_id=payment.id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        client_secret=client_secret,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
    )


@router.post(
    "/stripe/webhook",
    response_model=StripeWebhookAck,
    summary="Handle Stripe Webhook",
    description=(
        "Processes Stripe webhook events, verifies signature, and updates payment/access states. "
        "This endpoint is intended for Stripe servers only."
    ),
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> StripeWebhookAck:
    payload = await request.body()
    event = construct_webhook_event(payload, stripe_signature)
    state = handle_webhook_event(db, event)
    return StripeWebhookAck(event_type=str(event.get("type", "unknown")), state=state)