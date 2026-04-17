from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import stripe

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_window import AccessWindow
from app.models.checklist import Checklist
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.schemas.payment import PaymentState

def _stripe_required() -> Any:
    settings = get_settings()
    if stripe is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_package_not_installed",
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_secret_key_missing",
        )
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _webhook_secret_required() -> str:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_webhook_secret_missing",
        )
    return settings.stripe_webhook_secret



def create_checkout_session_for_user(
    user_id: UUID,
    success_url: str,
    cancel_url: str,
    checklist_id: UUID | None = None,
    quantity: int = 1,
) -> str:
    settings = get_settings()
    stripe_client = _stripe_required()
    from app.models.user import User
    from sqlalchemy.orm import Session
    from app.db.session import get_db

    db: Session = next(get_db())
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    # Ensure Stripe customer exists in DB, create on Stripe if missing
    if not user.stripe_customer_id:
        customer = stripe_client.Customer.create(email=user.email)
        user.stripe_customer_id = customer["id"]
        db.add(user)
        db.commit()
        db.refresh(user)

    # Use price/product from config
    line_items = [
        {
            "price": settings.stripe_price_id,
            "quantity": quantity,
        }
    ]
    metadata = {"user_id": str(user_id)}
    session = stripe_client.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer=user.stripe_customer_id,
        metadata=metadata,
    )
    return session.url


def create_payment_intent_for_user(
    db: Session,
    *,
    user_id: UUID,
    checklist_id: UUID,
    amount_cents: int | None,
    currency: str | None,
) -> tuple[Payment, str]:
    settings = get_settings()
    stripe_client = _stripe_required()

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")

    request_amount = amount_cents or settings.stripe_default_amount_cents
    request_currency = (currency or settings.stripe_currency).upper()

    intent = stripe_client.PaymentIntent.create(
        amount=request_amount,
        currency=request_currency.lower(),
        automatic_payment_methods={"enabled": True},
        metadata={"user_id": str(user.id), "checklist_id": str(checklist.id)},
    )

    payment = Payment(
        user_id=user.id,
        checklist_id=checklist.id,
        stripe_payment_intent_id=intent["id"],
        amount_cents=request_amount,
        currency=request_currency,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment, intent["client_secret"]


def construct_webhook_event(payload: bytes, signature_header: str) -> Any:
    stripe_client = _stripe_required()
    webhook_secret = _webhook_secret_required()
    try:
        return stripe_client.Webhook.construct_event(payload, signature_header, webhook_secret)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_webhook_signature") from exc


def _parse_paid_at(intent: dict[str, Any]) -> datetime:
    created_ts = int(intent.get("created") or datetime.now(timezone.utc).timestamp())
    return datetime.fromtimestamp(created_ts, tz=timezone.utc)


def _ensure_access_window(db: Session, payment: Payment, paid_at: datetime) -> AccessWindow:
    settings = get_settings()
    existing = db.scalar(select(AccessWindow).where(AccessWindow.payment_id == payment.id))
    if existing is not None:
        return existing

    access_window = AccessWindow(
        user_id=payment.user_id,
        payment_id=payment.id,
        activated_at=paid_at,
        expires_at=paid_at + timedelta(days=settings.access_unlock_days),
    )
    db.add(access_window)
    db.flush()
    return access_window


def handle_webhook_event(db: Session, event: Any) -> PaymentState | None:
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    if not isinstance(data, dict):
        return None

    if event_type not in {"payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.processing"}:
        return None

    intent_id = data.get("id")
    if not intent_id:
        return None

    payment = db.scalar(select(Payment).where(Payment.stripe_payment_intent_id == intent_id))
    if payment is None:
        metadata = data.get("metadata") or {}
        user_id_raw = metadata.get("user_id")
        checklist_id_raw = metadata.get("checklist_id")
        if user_id_raw is None or checklist_id_raw is None:
            return None
        try:
            user_id = UUID(user_id_raw)
            checklist_id = UUID(checklist_id_raw)
        except ValueError:
            return None
        payment = Payment(
            user_id=user_id,
            checklist_id=checklist_id,
            stripe_payment_intent_id=intent_id,
            amount_cents=int(data.get("amount") or 0),
            currency=str(data.get("currency") or "USD").upper(),
            status=PaymentStatus.pending,
        )
        db.add(payment)
        db.flush()

    access_window: AccessWindow | None = None
    if event_type == "payment_intent.succeeded":
        payment.status = PaymentStatus.succeeded
        payment.paid_at = _parse_paid_at(data)
        access_window = _ensure_access_window(db, payment, payment.paid_at)
    elif event_type == "payment_intent.payment_failed":
        payment.status = PaymentStatus.failed
    else:
        payment.status = PaymentStatus.pending

    db.commit()
    db.refresh(payment)

    return PaymentState(
        payment_id=payment.id,
        checklist_id=payment.checklist_id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        payment_status=payment.status,
        paid_at=payment.paid_at,
        access_window_id=access_window.id if access_window else None,
        access_expires_at=access_window.expires_at if access_window else None,
    )


def admin_set_payment_status(
    db: Session,
    *,
    user_id: UUID,
    checklist_id: UUID,
    payment_status: PaymentStatus,
    amount_cents: int | None,
    currency: str | None,
) -> PaymentState:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")

    payment = db.scalar(
        select(Payment)
        .where(Payment.user_id == user_id, Payment.checklist_id == checklist_id)
        .order_by(Payment.created_at.desc())
    )

    settings = get_settings()
    if payment is None:
        payment = Payment(
            user_id=user_id,
            checklist_id=checklist_id,
            stripe_payment_intent_id=f"dev_manual_{uuid4().hex}",
            amount_cents=amount_cents or settings.stripe_default_amount_cents,
            currency=(currency or settings.stripe_currency).upper(),
            status=PaymentStatus.pending,
        )
        db.add(payment)
        db.flush()

    payment.status = payment_status
    access_window: AccessWindow | None = None

    if payment_status == PaymentStatus.succeeded:
        payment.paid_at = payment.paid_at or datetime.now(timezone.utc)
        access_window = _ensure_access_window(db, payment, payment.paid_at)
    elif payment_status == PaymentStatus.failed:
        payment.paid_at = None

    db.commit()
    db.refresh(payment)

    if access_window is None:
        access_window = db.scalar(select(AccessWindow).where(AccessWindow.payment_id == payment.id))

    return PaymentState(
        payment_id=payment.id,
        checklist_id=payment.checklist_id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        payment_status=payment.status,
        paid_at=payment.paid_at,
        access_window_id=access_window.id if access_window else None,
        access_expires_at=access_window.expires_at if access_window else None,
    )