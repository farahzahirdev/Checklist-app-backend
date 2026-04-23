from fastapi import Query
from app.services.payments import create_checkout_session_for_user
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
from uuid import UUID

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.access_window import AccessWindow
from app.models.checklist import Checklist, ChecklistTranslation
from app.models.payment import Payment
from app.models.reference import Language
from app.models.user import UserRole
from app.schemas.payment import AdminPaymentStatusUpdateRequest, ChecklistInfo, PaymentSetupRequest, PaymentSetupResponse, PaymentState, StripeWebhookAck
from app.services.payments import admin_set_payment_status, construct_webhook_event, create_payment_intent_for_user, handle_webhook_event

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/stripe/setup-intent",
    response_model=PaymentSetupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe Setup Intent",
    description=(
        "Creates a payment record and Stripe PaymentIntent for the authenticated user. "
        "Requires bearer auth and returns client_secret for Stripe SDK confirmation. "
        "Checklist is selected separately after payment succeeds."
    ),
)
def setup_payment_intent(
    request: Request,
    payload: PaymentSetupRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentSetupResponse:
    lang_code = get_language_code(request, db)
    payment, client_secret = create_payment_intent_for_user(
        db,
        user_id=current_user.id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        lang_code=lang_code,
    )
    return PaymentSetupResponse(
        payment_id=payment.id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        client_secret=client_secret,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
    )


@router.get(
    "/users/{user_id}/status",
    response_model=PaymentState,
    summary="Get user payment status",
    description=(
        "Returns the most recent payment and access window state for a user. "
        "Authenticated users may only fetch their own status unless they are admin."
    ),
)
def get_user_payment_status(
    user_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentState:
    lang_code = get_language_code(request, db)
    if user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("forbidden", lang_code))

    payment = db.scalar(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("payment_not_found", lang_code))

    access_window = db.scalar(select(AccessWindow).where(AccessWindow.payment_id == payment.id))
    
    # Fetch checklist info if available
    checklist_info = None
    checklist_id = payment.checklist_id or (access_window.checklist_id if access_window else None)
    if checklist_id:
        checklist = db.get(Checklist, checklist_id)
        if checklist:
            # Get default language for translation
            default_language = db.scalar(select(Language).where(Language.is_default == True))
            if default_language:
                translation = db.scalar(
                    select(ChecklistTranslation)
                    .where(ChecklistTranslation.checklist_id == checklist_id)
                    .where(ChecklistTranslation.language_id == default_language.id)
                )
                if translation:
                    checklist_info = ChecklistInfo(
                        id=checklist.id,
                        title=translation.title,
                        version=checklist.version,
                    )
    
    return PaymentState(
        payment_id=payment.id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        payment_status=payment.status,
        paid_at=payment.paid_at,
        access_window_id=access_window.id if access_window else None,
        access_expires_at=access_window.expires_at if access_window else None,
        checklist=checklist_info,
    )


@router.post(
    "/stripe/checkout-session",
    summary="Create Stripe Checkout Session",
    description="Creates a Stripe Checkout Session for the configured product/price and returns the session URL. Uses a single product for all checklists. Checklist selection is after payment.",
)
def create_checkout_session(
    request: Request,
    success_url: str = Query(..., description="URL to redirect after successful payment"),
    cancel_url: str = Query(..., description="URL to redirect if payment is cancelled"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lang_code = get_language_code(request, db)
    url = create_checkout_session_for_user(
        user_id=current_user.id,
        success_url=success_url,
        cancel_url=cancel_url,
        lang_code=lang_code,
    )
    return {"checkout_url": url}

@router.post(
    "/stripe/webhook",
    response_model=StripeWebhookAck,
    summary="Handle Stripe Webhook",
    description=(
        "Processes Stripe webhook events, verifies signature, and updates payment/access states. "
        "This endpoint is intended for Stripe servers only and should not be called from frontend clients. "
        "On payment_intent.succeeded, API marks payment succeeded and creates access window linked to the same checklist."
    ),
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> StripeWebhookAck:
    lang_code = get_language_code(request, db)
    payload = await request.body()
    event = construct_webhook_event(payload, stripe_signature, lang_code)
    state = handle_webhook_event(db, event)
    return StripeWebhookAck(event_type=str(event.get("type", "unknown")), state=state)


@router.post(
    "/admin/users/{user_id}/status",
    response_model=PaymentState,
    summary="Admin Update User Payment Status",
    description=(
        "Admin-only development endpoint to set payment status for a user. "
        "Creates a synthetic payment record if one does not exist yet."
    ),
)
def admin_update_payment_status(
    user_id: UUID,
    request: Request,
    payload: AdminPaymentStatusUpdateRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> PaymentState:
    lang_code = get_language_code(request, db)
    return admin_set_payment_status(
        db,
        user_id=user_id,
        payment_status=payload.payment_status,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        lang_code=lang_code,
    )